"""
MASS Protocol Simulator - Haberleşme Ünitesi Simülasyonu
Python 3.11+ | RabbitMQ MQTT | Docker Ready
Format: Header in properties (routing) + Full JSON in payload (protocol)
"""

import json
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import paho.mqtt.client as mqtt
from paho.mqtt.properties import Properties
from paho.mqtt.packettypes import PacketTypes
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import uuid
import threading
import os

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MASS-Simulator")

# ========================
# Configuration
# ========================
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
    MQTT_USERNAME = os.getenv("MQTT_USERNAME", None) or None
    MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", None) or None
    MQTT_KEEPALIVE = int(os.getenv("MQTT_KEEPALIVE", "60"))
    MQTT_QOS = int(os.getenv("MQTT_QOS", "1"))
    
    # Topics
    TOPIC_TO_SERVER = os.getenv("TOPIC_TO_SERVER", "mass/device/to_server")
    TOPIC_FROM_SERVER = os.getenv("TOPIC_FROM_SERVER", "mass/server/to_device")
    
    # Heartbeat interval
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

device_state = DeviceState()

# ========================
# Protocol Message Builder
# ========================
class MASSProtocol:
    @staticmethod
    def create_header(function: str, reference_id: Optional[str] = None, streaming: bool = False) -> Dict:
        """Create message header"""
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
    def create_properties(function: str, reference_id: str) -> Properties:
        """Create MQTT properties with routing info"""
        properties = Properties(PacketTypes.PUBLISH)
        properties.UserProperty = [
            ("device.flag", SimulatorConfig.DEVICE_FLAG),
            ("device.serialNumber", SimulatorConfig.DEVICE_SERIAL),
            ("function", function),
            ("referenceId", reference_id)
        ]
        return properties

# ========================
# MQTT Client
# ========================
class MASSMQTTClient:
    def __init__(self):
        client_id = f"mass_sim_{SimulatorConfig.DEVICE_SERIAL}"
        self.client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv5)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.connected = False
        
        if SimulatorConfig.MQTT_USERNAME:
            self.client.username_pw_set(
                SimulatorConfig.MQTT_USERNAME,
                SimulatorConfig.MQTT_PASSWORD
            )
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info(f"✅ Connected to {SimulatorConfig.MQTT_BROKER}:{SimulatorConfig.MQTT_PORT}")
            self.connected = True
            client.subscribe(SimulatorConfig.TOPIC_FROM_SERVER, qos=SimulatorConfig.MQTT_QOS)
            logger.info(f"📥 Subscribed to {SimulatorConfig.TOPIC_FROM_SERVER}")
            self.send_identification()
        else:
            logger.error(f"❌ Connection failed: {rc}")
            self.connected = False
    
    def on_disconnect(self, client, userdata, rc, properties=None):
        self.connected = False
        if rc != 0:
            logger.warning(f"⚠️  Disconnected (code: {rc})")
    
    def on_message(self, client, userdata, msg):
        try:
            payload_str = msg.payload.decode('utf-8')
            message = json.loads(payload_str)
            
            function = message.get("function")
            reference_id = message.get("referenceId")
            
            logger.info(f"📩 Received: {function} (ref: {reference_id})")
            logger.debug(f"   Payload: {json.dumps(message, indent=2)}")
            
            self.handle_server_message(message)
            
        except Exception as e:
            logger.error(f"❌ Message error: {e}")
    
    def handle_server_message(self, message: Dict):
        function = message.get("function")
        reference_id = message.get("referenceId")
        
        # ACK'dan ACK üretme! (sonsuz döngü olur)
        if function == "ack":
            logger.info(f"✅ ACK received for ref: {reference_id}")
            return
        
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
            logger.warning(f"⚠️  Unhandled: {function}")
            self.send_ack(reference_id)
    
    def send_message(self, payload: Dict):
        """Send message with header in properties + full JSON in payload"""
        function = payload.get("function")
        reference_id = payload.get("referenceId")
        
        # Properties for routing
        properties = MASSProtocol.create_properties(function, reference_id)
        
        # Full JSON as payload
        payload_json = json.dumps(payload, separators=(',', ':'))
        
        result = self.client.publish(
            SimulatorConfig.TOPIC_TO_SERVER,
            payload_json,
            qos=SimulatorConfig.MQTT_QOS,
            properties=properties
        )
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            logger.info(f"📤 Sent: {function}")
        else:
            logger.error(f"❌ Send failed: {result.rc}")
    
    def send_ack(self, reference_id: str, success: bool = True, fail_code: int = None, fail_description: str = None):
        """Send ACK - PDF format"""
        message = MASSProtocol.create_header("ack", reference_id)
        
        if not success:
            message["response"] = {
                "failCode": fail_code,
                "failDescrition": fail_description  # PDF'deki typo
            }
        
        self.send_message(message)
    
    def send_identification(self, reference_id: str = None):
        """Send identification - PDF format"""
        message = MASSProtocol.create_header("identification", reference_id)
        message["response"] = {
            "registered": device_state.registered,
            "brand": SimulatorConfig.DEVICE_BRAND,
            "model": SimulatorConfig.DEVICE_MODEL,
            "protocolVersion": SimulatorConfig.PROTOCOL_VERSION,
            "manufactureDate": "2023-05-23",
            "firmware": SimulatorConfig.FIRMWARE,
            "signal": device_state.signal,
            "deviceDate": device_state.device_date.strftime("%Y-%m-%d %H:%M:%S"),
            "daylightSaving": True,
            "timezone": "+03:00",
            "restartPeriod": 8,
            "networkId": "",
            "servers": [{
                "ip": "123.45.68.10",
                "tcpPort": 1234,
                "udpPort": 4567,
                "primary": True
            }],
            "ntp": {
                "server": "",
                "port": 0
            },
            "ipWhiteList": ["123.45.68.10"],
            "retryInterval": 10,
            "retryCount": 3,
            "communicationInterfaces": [{
                "id": 1,
                "type": "gsm",
                "imei": "123456789012345",
                "phoneNumber": "5012345678",
                "ip": "123.45.68.9",
                "port": 3030,
                "apn": {
                    "user": "osos",
                    "pwd": ""
                },
                "simId": "",
                "imsi": ""
            }],
            "serialPorts": [
                {"id": 1, "type": "rs485", "name": "rs485-1", "port": 7000},
                {"id": 2, "type": "rs485", "name": "rs485-2", "port": 7001},
                {"id": 3, "type": "rs232", "name": "rs232", "port": 7002}
            ],
            "ioInterfaces": [
                {"id": 1, "type": "relay", "name": "relay-1"},
                {"id": 2, "type": "relay", "name": "relay-2"},
                {"id": 3, "type": "dryContact", "name": "dry-1"},
                {"id": 4, "type": "digitalInput", "name": "panoKapagi"},
                {"id": 5, "type": "digitalInput", "name": "digitalInput-2"}
            ],
            "modules": [],
            "meters": device_state.meters,
            "schedules": device_state.schedules
        }
        
        self.send_message(message)
        logger.info("🆔 Identification sent")
    
    def send_heartbeat(self):
        """Send heartbeat - PDF format"""
        message = MASSProtocol.create_header("heartbeat")
        message["response"] = {
            "signal": device_state.signal,
            "deviceDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cpuTemp": device_state.cpu_temp
        }
        
        self.send_message(message)
        logger.info("💓 Heartbeat sent")
    
    def send_alarm(self, alarm_type: str, level: str, incident_code: int, description: str, meter_info: Dict = None):
        """Send alarm - PDF format"""
        message = MASSProtocol.create_header("alarm")
        message["messageStatus"] = "success"
        
        alarm_data = {
            "type": alarm_type,
            "level": level,
            "incidentCode": incident_code,
            "description": description,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if meter_info:
            alarm_data["meter"] = meter_info
        
        message["response"] = [alarm_data]
        
        self.send_message(message)
        logger.info(f"🚨 Alarm sent: {description}")
    
    def handle_read_request(self, message: Dict):
        """Handle read - PDF format"""
        request = message.get("request", {})
        directive = request.get("directive")
        reference_id = message.get("referenceId")
        
        response_msg = MASSProtocol.create_header("read", reference_id)
        response_msg["response"] = {
            "readDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data": {
                "id": "/LGZ5\\2ZMG405000b.P07",
                "rawData": "0.0.0(23660088)\r\n0.9.2(2021-06-22)\r\n0.9.1(10:18:42)\r\n1.8.0(0000004891.722)\r\n"
            }
        }
        
        time.sleep(0.5)
        self.send_message(response_msg)
        logger.info(f"📖 Read response sent")
    
    def handle_configuration(self, message: Dict):
        """Handle configuration - PDF format"""
        request = message.get("request", {})
        
        if "registered" in request:
            device_state.registered = request["registered"]
        if "deviceDate" in request:
            device_state.device_date = datetime.now()
        
        # Send notification about success
        notif_msg = MASSProtocol.create_header("notification")
        notif_msg["response"] = {
            "type": "info",
            "message": "Configuration updated",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        time.sleep(0.2)
        self.send_message(notif_msg)
        logger.info("⚙️  Configuration updated")
    
    def handle_schedule(self, message: Dict):
        """Handle schedule - PDF format"""
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
            filter_id = request.get("filter", {}).get("id")
            device_state.schedules = [s for s in device_state.schedules if s.get("id") != filter_id]
            logger.info(f"🗑️  Removed schedule: {filter_id}")
    
    def handle_notification(self, message: Dict):
        """Handle notification - PDF format"""
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
            device_state.notifications = []
            logger.info("🗑️  Notifications removed")
    
    def handle_log_request(self, message: Dict):
        """Handle log - PDF format"""
        request = message.get("request", {})
        reference_id = message.get("referenceId")
        start_date = request.get("startDate")
        end_date = request.get("endDate")
        
        response_msg = MASSProtocol.create_header("log", reference_id)
        response_msg["response"] = [
            {
                "incidentCode": 278,
                "description": "cover opened",
                "date": "2021-06-28 13:55:00",
                "meter": {
                    "brand": "EMH",
                    "serialNumber": "12345678"
                }
            },
            {
                "incidentCode": 439,
                "description": "relay removed",
                "date": "2021-06-28 13:55:00"
            }
        ]
        
        self.send_message(response_msg)
        logger.info(f"📜 Logs sent")
    
    def connect(self):
        try:
            logger.info(f"🔌 Connecting to {SimulatorConfig.MQTT_BROKER}:{SimulatorConfig.MQTT_PORT}")
            self.client.connect(
                SimulatorConfig.MQTT_BROKER,
                SimulatorConfig.MQTT_PORT,
                SimulatorConfig.MQTT_KEEPALIVE
            )
            self.client.loop_start()
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            raise
    
    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

# ========================
# HTTP API
# ========================
app = FastAPI(title="MASS Simulator API")
mqtt_client: Optional[MASSMQTTClient] = None

class AlarmRequest(BaseModel):
    alarm_type: str = "alarm"
    level: str = "warning"
    incident_code: int
    description: str
    meter_serial: Optional[str] = None
    meter_brand: Optional[str] = None

class MeterRequest(BaseModel):
    protocol: str
    type: str
    brand: str
    serialNumber: str
    serialPort: str
    initBaud: int
    fixBaud: bool
    frame: str

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "mqtt_connected": mqtt_client.connected if mqtt_client else False,
        "device": f"{SimulatorConfig.DEVICE_FLAG}/{SimulatorConfig.DEVICE_SERIAL}",
        "broker": f"{SimulatorConfig.MQTT_BROKER}:{SimulatorConfig.MQTT_PORT}"
    }

@app.post("/trigger/alarm")
def trigger_alarm(alarm: AlarmRequest):
    if not mqtt_client or not mqtt_client.connected:
        raise HTTPException(503, "MQTT not connected")
    
    meter_info = None
    if alarm.meter_serial:
        meter_info = {"brand": alarm.meter_brand or "Unknown", "serialNumber": alarm.meter_serial}
    
    mqtt_client.send_alarm(alarm.alarm_type, alarm.level, alarm.incident_code, alarm.description, meter_info)
    return {"status": "sent"}

@app.post("/trigger/heartbeat")
def trigger_heartbeat():
    if not mqtt_client or not mqtt_client.connected:
        raise HTTPException(503, "MQTT not connected")
    mqtt_client.send_heartbeat()
    return {"status": "sent"}

@app.post("/device/meter/add")
def add_meter(meter: MeterRequest):
    device_state.meters.append(meter.dict())
    return {"status": "added"}

@app.get("/device/state")
def get_state():
    return {
        "registered": device_state.registered,
        "signal": device_state.signal,
        "cpu_temp": device_state.cpu_temp,
        "meters": len(device_state.meters),
        "schedules": len(device_state.schedules),
        "notifications": len(device_state.notifications)
    }

@app.post("/device/config")
def update_config(signal: Optional[int] = None, cpu_temp: Optional[int] = None):
    if signal: device_state.signal = signal
    if cpu_temp: device_state.cpu_temp = cpu_temp
    return {"status": "updated"}

# ========================
# Heartbeat Thread
# ========================
def heartbeat_loop():
    while True:
        time.sleep(SimulatorConfig.HEARTBEAT_INTERVAL)
        if mqtt_client and mqtt_client.connected:
            try:
                mqtt_client.send_heartbeat()
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

# ========================
# Main
# ========================
def main():
    global mqtt_client
    
    logger.info("=" * 60)
    logger.info("🚀 MASS Protocol Simulator")
    logger.info(f"Device: {SimulatorConfig.DEVICE_FLAG}/{SimulatorConfig.DEVICE_SERIAL}")
    logger.info(f"Broker: {SimulatorConfig.MQTT_BROKER}:{SimulatorConfig.MQTT_PORT}")
    logger.info(f"Topics: {SimulatorConfig.TOPIC_TO_SERVER} / {SimulatorConfig.TOPIC_FROM_SERVER}")
    logger.info("=" * 60)
    
    mqtt_client = MASSMQTTClient()
    mqtt_client.connect()
    
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    
    uvicorn.run(app, host="0.0.0.0", port=SimulatorConfig.API_PORT, log_level="info")

if __name__ == "__main__":
    main()