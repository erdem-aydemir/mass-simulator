"""
MASS Protocol Simulator - Haberleşme Ünitesi Simülasyonu
Python 3.11+ | RabbitMQ MQTT | Docker Ready
"""

import json
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import uuid
import threading

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MASS-Simulator")

# ========================
# Configuration
# ========================
import os

class SimulatorConfig:
    DEVICE_FLAG = os.getenv("DEVICE_FLAG", "XYZ")
    DEVICE_SERIAL = os.getenv("DEVICE_SERIAL", "0123456789ABCDE")
    DEVICE_BRAND = os.getenv("DEVICE_BRAND", "SimulatorBrand")
    DEVICE_MODEL = os.getenv("DEVICE_MODEL", "SimV1.0")
    PROTOCOL_VERSION = "1.0.0"
    FIRMWARE = os.getenv("FIRMWARE", "1.01")
    
    # MQTT
    MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
    MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
    MQTT_USERNAME = os.getenv("MQTT_USERNAME", None)
    MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", None)
    
    # Topics
    TOPIC_DEVICE_TO_SERVER = os.getenv("TOPIC_DEVICE_TO_SERVER", "mass/device/to_server")
    TOPIC_SERVER_TO_DEVICE = os.getenv("TOPIC_SERVER_TO_DEVICE", "mass/server/to_device")
    
    # Heartbeat interval (seconds)
    HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "60"))
    
    # HTTP API Port
    API_PORT = int(os.getenv("API_PORT", "8000"))

# ========================
# Device State
# ========================
class DeviceState:
    def __init__(self):
        self.registered = False
        self.signal = 13
        self.cpu_temp = 17
        self.device_date = datetime.now()
        self.meters = []
        self.schedules = []
        self.notifications = []
        self.directives = []

device_state = DeviceState()

# ========================
# Protocol Message Builder
# ========================
class MASSProtocol:
    @staticmethod
    def create_header(function: str, reference_id: Optional[str] = None, streaming: bool = False) -> Dict:
        """Create MASS protocol header"""
        return {
            "device": {
                "flag": SimulatorConfig.DEVICE_FLAG,
                "serialNumber": SimulatorConfig.DEVICE_SERIAL
            },
            "function": function,
            "referenceId": reference_id or str(uuid.uuid4()),
            "streaming": streaming
        }
    
    @staticmethod
    def wrap_message(json_data: Dict) -> str:
        """Wrap JSON in MASS protocol format: #<length>$<json>"""
        json_str = json.dumps(json_data, separators=(',', ':'))
        length = len(json_str)
        return f"#{length}${json_str}"
    
    @staticmethod
    def parse_message(raw_message: str) -> Optional[Dict]:
        """Parse MASS protocol message"""
        try:
            if not raw_message.startswith('#'):
                return None
            
            # Find $ separator
            dollar_pos = raw_message.index('$')
            length_str = raw_message[1:dollar_pos]
            json_str = raw_message[dollar_pos + 1:]
            
            # Validate length
            declared_length = int(length_str)
            if len(json_str) != declared_length:
                logger.warning(f"Length mismatch: declared={declared_length}, actual={len(json_str)}")
            
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Message parse error: {e}")
            return None

# ========================
# MQTT Client
# ========================
class MASSMQTTClient:
    def __init__(self):
        self.client = mqtt.Client(client_id=f"mass_sim_{SimulatorConfig.DEVICE_SERIAL}")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.connected = False
        
        if SimulatorConfig.MQTT_USERNAME:
            self.client.username_pw_set(
                SimulatorConfig.MQTT_USERNAME,
                SimulatorConfig.MQTT_PASSWORD
            )
    
    def on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            logger.info("✅ Connected to MQTT broker")
            self.connected = True
            
            # Subscribe to server messages
            client.subscribe(SimulatorConfig.TOPIC_SERVER_TO_DEVICE)
            logger.info(f"📥 Subscribed to {SimulatorConfig.TOPIC_SERVER_TO_DEVICE}")
            
            # Send identification on connect
            self.send_identification()
        else:
            logger.error(f"❌ Connection failed with code {rc}")
    
    def on_message(self, client, userdata, msg):
        """Callback when message received"""
        try:
            raw_msg = msg.payload.decode('utf-8')
            logger.info(f"📩 Received: {raw_msg[:100]}...")
            
            parsed = MASSProtocol.parse_message(raw_msg)
            if not parsed:
                logger.error("Failed to parse message")
                return
            
            # Route to handler
            self.handle_server_message(parsed)
            
        except Exception as e:
            logger.error(f"Message handling error: {e}")
    
    def handle_server_message(self, message: Dict):
        """Route message to appropriate handler"""
        function = message.get("function")
        reference_id = message.get("referenceId")
        
        logger.info(f"🔧 Handling function: {function}")
        
        if function == "identification":
            self.send_ack(reference_id)
            self.send_identification(reference_id)
        
        elif function == "read":
            self.send_ack(reference_id)
            self.handle_read_request(message)
        
        elif function == "configuration":
            self.send_ack(reference_id)
            self.handle_configuration(message)
        
        elif function == "schedule":
            self.send_ack(reference_id)
            self.handle_schedule(message)
        
        elif function == "notification":
            self.send_ack(reference_id)
            self.handle_notification(message)
        
        elif function == "log":
            self.send_ack(reference_id)
            self.handle_log_request(message)
        
        else:
            logger.warning(f"⚠️  Unhandled function: {function}")
            self.send_ack(reference_id)
    
    def send_message(self, message: Dict):
        """Send message to server"""
        wrapped = MASSProtocol.wrap_message(message)
        result = self.client.publish(SimulatorConfig.TOPIC_DEVICE_TO_SERVER, wrapped)
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            logger.info(f"📤 Sent: {message['function']}")
        else:
            logger.error(f"❌ Send failed: {result.rc}")
    
    def send_ack(self, reference_id: str, success: bool = True, fail_code: int = None, fail_description: str = None):
        """Send ACK message"""
        msg = MASSProtocol.create_header("ack", reference_id)
        
        if not success:
            msg["response"] = {
                "failCode": fail_code,
                "failDescrition": fail_description  # Note: typo in protocol spec
            }
        
        self.send_message(msg)
    
    def send_identification(self, reference_id: str = None):
        """Send identification message"""
        msg = MASSProtocol.create_header("identification", reference_id)
        msg["response"] = {
            "registered": device_state.registered,
            "brand": SimulatorConfig.DEVICE_BRAND,
            "model": SimulatorConfig.DEVICE_MODEL,
            "protocolVersion": SimulatorConfig.PROTOCOL_VERSION,
            "manufactureDate": "2024-01-01",
            "firmware": SimulatorConfig.FIRMWARE,
            "signal": device_state.signal,
            "deviceDate": device_state.device_date.strftime("%Y-%m-%d %H:%M:%S"),
            "daylightSaving": True,
            "timezone": "+03:00",
            "restartPeriod": 8,
            "networkId": "",
            "servers": [{
                "ip": "127.0.0.1",
                "tcpPort": 1883,
                "udpPort": 0,
                "primary": True
            }],
            "ntp": {"server": "", "port": 0},
            "ipWhiteList": [],
            "retryInterval": 10,
            "retryCount": 3,
            "communicationInterfaces": [{
                "id": 1,
                "type": "gsm",
                "imei": "123456789012345",
                "phoneNumber": "5012345678",
                "ip": "10.0.0.1",
                "port": 3030,
                "apn": {"user": "", "pwd": ""},
                "simId": "",
                "imsi": ""
            }],
            "serialPorts": [
                {"id": 1, "type": "rs485", "name": "rs485-1", "port": 7000},
                {"id": 2, "type": "rs485", "name": "rs485-2", "port": 7001}
            ],
            "ioInterfaces": [
                {"id": 1, "type": "relay", "name": "relay-1"},
                {"id": 2, "type": "digitalInput", "name": "di-1"}
            ],
            "modules": [],
            "meters": device_state.meters,
            "schedules": device_state.schedules
        }
        
        self.send_message(msg)
        logger.info("🆔 Identification sent")
    
    def send_heartbeat(self):
        """Send heartbeat message"""
        msg = MASSProtocol.create_header("heartbeat")
        msg["response"] = {
            "signal": device_state.signal,
            "deviceDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cpuTemp": device_state.cpu_temp
        }
        
        self.send_message(msg)
        logger.info("💓 Heartbeat sent")
    
    def send_alarm(self, alarm_type: str, level: str, incident_code: int, description: str, meter_info: Dict = None):
        """Send alarm message"""
        msg = MASSProtocol.create_header("alarm")
        msg["messageStatus"] = "success"
        
        alarm_data = {
            "type": alarm_type,  # "alarm" | "info" | "danger"
            "level": level,      # "critical" | "warning" | "info"
            "incidentCode": incident_code,
            "description": description,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if meter_info:
            alarm_data["meter"] = meter_info
        
        msg["response"] = [alarm_data]
        
        self.send_message(msg)
        logger.info(f"🚨 Alarm sent: {description}")
    
    def handle_read_request(self, message: Dict):
        """Handle read/readout request"""
        request = message.get("request", {})
        directive = request.get("directive")
        reference_id = message.get("referenceId")
        
        # Simulate readout response
        response_msg = MASSProtocol.create_header("read", reference_id)
        response_msg["response"] = {
            "readDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data": {
                "id": "/SIM1\\2SIMULATOR01",
                "rawData": "0.0.0(12345678)\r\n0.9.2(2024-10-21)\r\n1.8.0(0000123.456*kWh)\r\n"
            }
        }
        
        # Simulate processing delay
        time.sleep(0.5)
        self.send_message(response_msg)
        logger.info(f"📖 Readout response sent for directive: {directive}")
    
    def handle_configuration(self, message: Dict):
        """Handle configuration update"""
        request = message.get("request", {})
        reference_id = message.get("referenceId")
        
        # Update state (simplified)
        if "registered" in request:
            device_state.registered = request["registered"]
        
        if "deviceDate" in request:
            device_state.device_date = datetime.now()
        
        # Send notification about config change
        notif_msg = MASSProtocol.create_header("notification")
        notif_msg["response"] = {
            "type": "info",
            "message": "Configuration updated successfully",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        time.sleep(0.2)
        self.send_message(notif_msg)
        logger.info("⚙️  Configuration updated")
    
    def handle_schedule(self, message: Dict):
        """Handle schedule operations"""
        request = message.get("request", {})
        operation = request.get("operation")
        reference_id = message.get("referenceId")
        
        if operation == "add":
            schedules = request.get("schedules", [])
            device_state.schedules.extend(schedules)
            logger.info(f"📅 Added {len(schedules)} schedule(s)")
        
        elif operation == "list":
            response_msg = MASSProtocol.create_header("schedule", reference_id)
            response_msg["response"] = {
                "schedules": device_state.schedules
            }
            self.send_message(response_msg)
            logger.info("📋 Schedule list sent")
        
        elif operation == "remove":
            # Simplified removal
            filter_id = request.get("filter", {}).get("id")
            device_state.schedules = [s for s in device_state.schedules if s.get("id") != filter_id]
            logger.info(f"🗑️  Removed schedule: {filter_id}")
    
    def handle_notification(self, message: Dict):
        """Handle notification operations"""
        request = message.get("request", {})
        operation = request.get("operation")
        reference_id = message.get("referenceId")
        
        if operation == "add":
            notifications = request.get("notifications", [])
            device_state.notifications.extend(notifications)
            logger.info(f"🔔 Added {len(notifications)} notification(s)")
        
        elif operation == "list":
            response_msg = MASSProtocol.create_header("notification", reference_id)
            response_msg["response"] = {
                "notifications": device_state.notifications
            }
            self.send_message(response_msg)
            logger.info("📋 Notification list sent")
        
        elif operation == "remove":
            filter_info = request.get("filter", [])
            # Simplified removal logic
            device_state.notifications = []
            logger.info("🗑️  Notifications removed")
    
    def handle_log_request(self, message: Dict):
        """Handle log request"""
        request = message.get("request", {})
        reference_id = message.get("referenceId")
        start_date = request.get("startDate")
        end_date = request.get("endDate")
        
        # Simulate log response
        response_msg = MASSProtocol.create_header("log", reference_id)
        response_msg["response"] = [
            {
                "incidentCode": 101,
                "description": "Connection established",
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            {
                "incidentCode": 120,
                "description": "Configuration updated",
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        ]
        
        self.send_message(response_msg)
        logger.info(f"📜 Logs sent for period: {start_date} to {end_date}")
    
    def connect(self):
        """Connect to MQTT broker"""
        try:
            logger.info(f"🔌 Connecting to MQTT broker {SimulatorConfig.MQTT_BROKER}:{SimulatorConfig.MQTT_PORT}")
            self.client.connect(SimulatorConfig.MQTT_BROKER, SimulatorConfig.MQTT_PORT, 60)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Connection error: {e}")
            raise
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("🔌 Disconnected from MQTT broker")

# ========================
# HTTP API for External Control
# ========================
app = FastAPI(title="MASS Simulator Control API")

mqtt_client: Optional[MASSMQTTClient] = None

class AlarmRequest(BaseModel):
    alarm_type: str = "alarm"  # alarm | info | danger
    level: str = "warning"     # critical | warning | info
    incident_code: int
    description: str
    meter_serial: Optional[str] = None
    meter_brand: Optional[str] = None

class MeterRequest(BaseModel):
    protocol: str
    type: str  # electricity | water | gas
    brand: str
    serialNumber: str
    serialPort: str
    initBaud: int
    fixBaud: bool
    frame: str

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "mqtt_connected": mqtt_client.connected if mqtt_client else False,
        "device_serial": SimulatorConfig.DEVICE_SERIAL
    }

@app.post("/trigger/alarm")
def trigger_alarm(alarm: AlarmRequest):
    """Trigger an alarm from simulator"""
    if not mqtt_client or not mqtt_client.connected:
        raise HTTPException(status_code=503, detail="MQTT not connected")
    
    meter_info = None
    if alarm.meter_serial:
        meter_info = {
            "brand": alarm.meter_brand or "Unknown",
            "serialNumber": alarm.meter_serial
        }
    
    mqtt_client.send_alarm(
        alarm_type=alarm.alarm_type,
        level=alarm.level,
        incident_code=alarm.incident_code,
        description=alarm.description,
        meter_info=meter_info
    )
    
    return {"status": "alarm_sent"}

@app.post("/trigger/heartbeat")
def trigger_heartbeat():
    """Trigger immediate heartbeat"""
    if not mqtt_client or not mqtt_client.connected:
        raise HTTPException(status_code=503, detail="MQTT not connected")
    
    mqtt_client.send_heartbeat()
    return {"status": "heartbeat_sent"}

@app.post("/device/meter/add")
def add_meter(meter: MeterRequest):
    """Add a meter to device state"""
    meter_dict = meter.dict()
    device_state.meters.append(meter_dict)
    logger.info(f"✅ Meter added: {meter.serialNumber}")
    return {"status": "meter_added", "meter": meter_dict}

@app.get("/device/state")
def get_device_state():
    """Get current device state"""
    return {
        "registered": device_state.registered,
        "signal": device_state.signal,
        "cpu_temp": device_state.cpu_temp,
        "meters_count": len(device_state.meters),
        "schedules_count": len(device_state.schedules),
        "notifications_count": len(device_state.notifications)
    }

@app.post("/device/config")
def update_config(signal: Optional[int] = None, cpu_temp: Optional[int] = None):
    """Update device configuration"""
    if signal is not None:
        device_state.signal = signal
    if cpu_temp is not None:
        device_state.cpu_temp = cpu_temp
    
    return {"status": "config_updated"}

# ========================
# Heartbeat Thread
# ========================
def heartbeat_loop():
    """Background thread for periodic heartbeat"""
    while True:
        time.sleep(SimulatorConfig.HEARTBEAT_INTERVAL)
        if mqtt_client and mqtt_client.connected:
            try:
                mqtt_client.send_heartbeat()
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

# ========================
# Main Application
# ========================
def main():
    global mqtt_client
    
    logger.info("=" * 60)
    logger.info("🚀 MASS Protocol Simulator Starting")
    logger.info("=" * 60)
    
    # Initialize MQTT client
    mqtt_client = MASSMQTTClient()
    mqtt_client.connect()
    
    # Start heartbeat thread
    heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    heartbeat_thread.start()
    logger.info("💓 Heartbeat thread started")
    
    # Start HTTP API
    logger.info(f"🌐 Starting HTTP API on port {SimulatorConfig.API_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=SimulatorConfig.API_PORT)

if __name__ == "__main__":
    main()