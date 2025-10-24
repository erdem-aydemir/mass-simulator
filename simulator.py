#!/usr/bin/env python3
"""
MASS Protocol Simulator - Communication Unit Simulation
Optimized version: Clean, minimal, protocol-compliant
Python 3.11+ | RabbitMQ MQTT | Docker Ready
"""

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime
from typing import Dict, Optional

import paho.mqtt.client as mqtt
import uvicorn
from fastapi import FastAPI, HTTPException
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties
from pydantic import BaseModel

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MASS-Simulator")


# ============================================================================
# Configuration
# ============================================================================
class Config:
    """Simulator configuration from environment variables"""
    # Device identity
    DEVICE_FLAG = os.getenv("DEVICE_FLAG", "XYZ")
    DEVICE_SERIAL = os.getenv("DEVICE_SERIAL", "0123456789ABCDE")
    DEVICE_BRAND = os.getenv("DEVICE_BRAND", "SimulatorBrand")
    DEVICE_MODEL = os.getenv("DEVICE_MODEL", "SimV1.0")
    FIRMWARE = os.getenv("FIRMWARE", "1.01")
    PROTOCOL_VERSION = "1.0.0"
    
    # MQTT connection
    MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
    MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
    MQTT_USERNAME = os.getenv("MQTT_USERNAME") or None
    MQTT_PASSWORD = os.getenv("MQTT_PASSWORD") or None
    MQTT_KEEPALIVE = int(os.getenv("MQTT_KEEPALIVE", "60"))
    MQTT_QOS = int(os.getenv("MQTT_QOS", "1"))
    
    # Topics
    TOPIC_TO_SERVER = os.getenv("TOPIC_TO_SERVER", "mass/device/to_server")
    TOPIC_FROM_SERVER = os.getenv("TOPIC_FROM_SERVER", "mass/server/to_device")
    
    # Intervals
    HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "60"))
    API_PORT = int(os.getenv("API_PORT", "8000"))


# ============================================================================
# Device State
# ============================================================================
class DeviceState:
    """Global device state"""
    def __init__(self):
        self.registered = False
        self.signal = 13
        self.cpu_temp = 17
        self.device_date = datetime.now()
        self.meters = []
        self.schedules = []
        self.notifications = []


device_state = DeviceState()


# ============================================================================
# Protocol Utilities
# ============================================================================
class Protocol:
    """MASS protocol message utilities"""
    
    @staticmethod
    def create_header(function: str, reference_id: Optional[str] = None) -> Dict:
        """Create message header per protocol specification"""
        return {
            "device": {
                "flag": Config.DEVICE_FLAG,
                "serialNumber": Config.DEVICE_SERIAL
            },
            "function": function,
            "referenceId": reference_id or str(uuid.uuid4())
        }
    
    @staticmethod
    def create_mqtt_properties(function: str, reference_id: str) -> Properties:
        """Create MQTT v5 properties for routing"""
        props = Properties(PacketTypes.PUBLISH)
        props.UserProperty = [
            ("device.flag", Config.DEVICE_FLAG),
            ("device.serialNumber", Config.DEVICE_SERIAL),
            ("function", function),
            ("referenceId", reference_id)
        ]
        return props


# ============================================================================
# MQTT Client
# ============================================================================
class MQTTClient:
    """MQTT client for MASS protocol communication"""
    
    def __init__(self):
        client_id = f"mass_sim_{Config.DEVICE_SERIAL}"
        self.client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv5)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.connected = False
        
        if Config.MQTT_USERNAME:
            self.client.username_pw_set(Config.MQTT_USERNAME, Config.MQTT_PASSWORD)
    
    def connect(self):
        """Connect to MQTT broker"""
        try:
            logger.info(f"Connecting to {Config.MQTT_BROKER}:{Config.MQTT_PORT}")
            self.client.connect(Config.MQTT_BROKER, Config.MQTT_PORT, Config.MQTT_KEEPALIVE)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Connection error: {e}")
            raise
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()
    
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Handle MQTT connection"""
        if rc == 0:
            logger.info(f"✅ Connected to broker")
            self.connected = True
            client.subscribe(Config.TOPIC_FROM_SERVER, qos=Config.MQTT_QOS)
            logger.info(f"📥 Subscribed to {Config.TOPIC_FROM_SERVER}")
            self.send_identification()
        else:
            logger.error(f"❌ Connection failed with code {rc}")
            self.connected = False
    
    def _on_disconnect(self, client, userdata, rc, properties=None):
        """Handle MQTT disconnection"""
        self.connected = False
        if rc != 0:
            logger.warning(f"⚠️  Disconnected with code {rc}")
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT message"""
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            function = payload.get("function")
            reference_id = payload.get("referenceId")
            
            logger.info(f"📩 Received: {function} (ref: {reference_id})")
            self._route_message(payload)
            
        except Exception as e:
            logger.error(f"❌ Message handling error: {e}")
    
    def _route_message(self, message: Dict):
        """Route message to appropriate handler"""
        function = message.get("function")
        reference_id = message.get("referenceId")
        
        # Prevent ACK loop
        if function == "ack":
            logger.info(f"✅ ACK received for ref: {reference_id}")
            return
        
        # Route to handlers
        handlers = {
            "identification": self._handle_identification,
            "read": self._handle_read,
            "configuration": self._handle_configuration,
            "schedule": self._handle_schedule,
            "notification": self._handle_notification,
            "log": self._handle_log,
            "write": self._handle_write,
            "reset": self._handle_reset,
            "firmwareUpdate": self._handle_firmware_update,
            "profile": self._handle_profile,
            "directive": self._handle_directive,
            "relay": self._handle_relay
        }
        
        handler = handlers.get(function)
        if handler:
            self.send_ack(reference_id)
            handler(message)
        else:
            logger.warning(f"⚠️  Unhandled function: {function}")
            self.send_ack(reference_id)
    
    def send_message(self, payload: Dict):
        """Send message via MQTT"""
        function = payload.get("function")
        reference_id = payload.get("referenceId")
        
        properties = Protocol.create_mqtt_properties(function, reference_id)
        payload_json = json.dumps(payload, separators=(',', ':'))
        
        result = self.client.publish(
            Config.TOPIC_TO_SERVER,
            payload_json,
            qos=Config.MQTT_QOS,
            properties=properties
        )
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            logger.info(f"📤 Sent: {function}")
        else:
            logger.error(f"❌ Send failed with code {result.rc}")
    
    def send_ack(self, reference_id: str, success: bool = True, 
                  fail_code: int = None, fail_description: str = None):
        """Send ACK message"""
        message = Protocol.create_header("ack", reference_id)
        
        if not success:
            message["response"] = {
                "failCode": fail_code,
                "failDescrition": fail_description  # Note: typo per protocol spec
            }
        
        self.send_message(message)
    
    def send_identification(self, reference_id: str = None):
        """Send identification message"""
        message = Protocol.create_header("identification", reference_id)
        message["response"] = {
            "registered": device_state.registered,
            "brand": Config.DEVICE_BRAND,
            "model": Config.DEVICE_MODEL,
            "protocolVersion": Config.PROTOCOL_VERSION,
            "manufactureDate": "2023-05-23",
            "firmware": Config.FIRMWARE,
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
            "ntp": {"server": "", "port": 0},
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
                "apn": {"user": "osos", "pwd": ""},
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
        """Send heartbeat message"""
        message = Protocol.create_header("heartbeat")
        message["response"] = {
            "signal": device_state.signal,
            "deviceDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cpuTemp": device_state.cpu_temp
        }
        
        self.send_message(message)
        logger.info("💓 Heartbeat sent")
    
    def send_alarm(self, alarm_type: str, level: str, incident_code: int, 
                   description: str, meter_info: Dict = None):
        """Send alarm message"""
        message = Protocol.create_header("alarm")
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
        logger.info(f"🚨 Alarm: {description}")
    
    def _handle_identification(self, message: Dict):
        """Handle identification request"""
        reference_id = message.get("referenceId")
        self.send_identification(reference_id)
    
    def _handle_read(self, message: Dict):
        """Handle read request"""
        reference_id = message.get("referenceId")
        
        response = Protocol.create_header("read", reference_id)
        response["response"] = {
            "readDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data": {
                "id": "/LGZ5\\2ZMG405000b.P07",
                "rawData": "0.0.0(23660088)\r\n0.9.2(2021-06-22)\r\n0.9.1(10:18:42)\r\n1.8.0(0000004891.722)\r\n"
            }
        }
        
        time.sleep(0.5)  # Simulate meter read delay
        self.send_message(response)
        logger.info("📖 Read response sent")
    
    def _handle_configuration(self, message: Dict):
        """Handle configuration request"""
        request = message.get("request", {})
        
        # Update state
        if "registered" in request:
            device_state.registered = request["registered"]
        if "deviceDate" in request:
            device_state.device_date = datetime.now()
        
        # Send notification
        notif = Protocol.create_header("notification")
        notif["response"] = {
            "type": "info",
            "message": "Configuration updated",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        time.sleep(0.2)
        self.send_message(notif)
        logger.info("⚙️  Configuration updated")
    
    def _handle_schedule(self, message: Dict):
        """Handle schedule request"""
        request = message.get("request", {})
        operation = request.get("operation")
        reference_id = message.get("referenceId")
        
        if operation == "add":
            schedules = request.get("schedules", [])
            device_state.schedules.extend(schedules)
            logger.info(f"📅 Added {len(schedules)} schedule(s)")
        
        elif operation == "list":
            response = Protocol.create_header("schedule", reference_id)
            response["response"] = {"schedules": device_state.schedules}
            self.send_message(response)
            logger.info("📋 Schedule list sent")
        
        elif operation == "remove":
            filter_id = request.get("filter", {}).get("id")
            device_state.schedules = [
                s for s in device_state.schedules if s.get("id") != filter_id
            ]
            logger.info(f"🗑️  Removed schedule: {filter_id}")
    
    def _handle_notification(self, message: Dict):
        """Handle notification request"""
        request = message.get("request", {})
        operation = request.get("operation")
        reference_id = message.get("referenceId")
        
        if operation == "add":
            notifications = request.get("notifications", [])
            device_state.notifications.extend(notifications)
            logger.info(f"🔔 Added {len(notifications)} notification(s)")
        
        elif operation == "list":
            response = Protocol.create_header("notification", reference_id)
            response["response"] = {"notifications": device_state.notifications}
            self.send_message(response)
            logger.info("📋 Notification list sent")
        
        elif operation == "remove":
            device_state.notifications = []
            logger.info("🗑️  Notifications removed")
    
    def _handle_log(self, message: Dict):
        """Handle log request"""
        reference_id = message.get("referenceId")
        
        # Mock log data
        response = Protocol.create_header("log", reference_id)
        response["response"] = [
            {
                "incidentCode": 278,
                "description": "cover opened",
                "date": "2021-06-28 13:55:00",
                "meter": {"brand": "EMH", "serialNumber": "12345678"}
            },
            {
                "incidentCode": 439,
                "description": "relay removed",
                "date": "2021-06-28 13:55:00"
            }
        ]
        
        self.send_message(response)
        logger.info("📜 Log sent")
    
    def _handle_write(self, message: Dict):
        """Handle write request"""
        reference_id = message.get("referenceId")
        notif = Protocol.create_header("notification")
        notif["response"] = {
            "type": "info",
            "message": "Write successful",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        time.sleep(0.3)
        self.send_message(notif)
        logger.info("✍️  Write completed")
    
    def _handle_reset(self, message: Dict):
        """Handle reset request"""
        notif = Protocol.create_header("notification")
        notif["response"] = {
            "type": "info",
            "message": "Device reset successful",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        time.sleep(0.2)
        self.send_message(notif)
        logger.info("🔄 Reset completed")
    
    def _handle_firmware_update(self, message: Dict):
        """Handle firmware update request"""
        notif = Protocol.create_header("notification")
        notif["response"] = {
            "type": "info",
            "message": "Firmware update successful",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        time.sleep(1.0)
        self.send_message(notif)
        logger.info("📥 Firmware updated")
    
    def _handle_profile(self, message: Dict):
        """Handle profile request"""
        reference_id = message.get("referenceId")
        response = Protocol.create_header("profile", reference_id)
        response["response"] = {
            "profileData": [
                {"date": "2021-06-01 00:00", "value": 123.45},
                {"date": "2021-06-01 00:15", "value": 124.67}
            ]
        }
        time.sleep(0.5)
        self.send_message(response)
        logger.info("📊 Profile sent")
    
    def _handle_directive(self, message: Dict):
        """Handle directive request"""
        request = message.get("request", {})
        operation = request.get("operation")
        reference_id = message.get("referenceId")
        
        if operation == "add":
            logger.info("📝 Directive added")
        elif operation == "list":
            response = Protocol.create_header("directive", reference_id)
            response["response"] = {"directives": []}
            self.send_message(response)
            logger.info("📋 Directive list sent")
        elif operation == "remove":
            logger.info("🗑️  Directive removed")
    
    def _handle_relay(self, message: Dict):
        """Handle relay control"""
        reference_id = message.get("referenceId")
        response = Protocol.create_header("relay", reference_id)
        response["response"] = {
            "status": "success",
            "relayState": "on"
        }
        time.sleep(0.2)
        self.send_message(response)
        logger.info("💡 Relay controlled")


# ============================================================================
# HTTP API
# ============================================================================
app = FastAPI(title="MASS Simulator API", version="1.0.0")
mqtt_client: Optional[MQTTClient] = None


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
    """Health check endpoint"""
    return {
        "status": "healthy",
        "mqtt_connected": mqtt_client.connected if mqtt_client else False,
        "device": f"{Config.DEVICE_FLAG}/{Config.DEVICE_SERIAL}",
        "broker": f"{Config.MQTT_BROKER}:{Config.MQTT_PORT}"
    }


@app.post("/trigger/alarm")
def trigger_alarm(alarm: AlarmRequest):
    """Manually trigger an alarm"""
    if not mqtt_client or not mqtt_client.connected:
        raise HTTPException(503, "MQTT not connected")
    
    meter_info = None
    if alarm.meter_serial:
        meter_info = {
            "brand": alarm.meter_brand or "Unknown",
            "serialNumber": alarm.meter_serial
        }
    
    mqtt_client.send_alarm(
        alarm.alarm_type, alarm.level, alarm.incident_code, 
        alarm.description, meter_info
    )
    return {"status": "sent"}


@app.post("/trigger/heartbeat")
def trigger_heartbeat():
    """Manually trigger a heartbeat"""
    if not mqtt_client or not mqtt_client.connected:
        raise HTTPException(503, "MQTT not connected")
    
    mqtt_client.send_heartbeat()
    return {"status": "sent"}


@app.post("/device/meter/add")
def add_meter(meter: MeterRequest):
    """Add a meter to device state"""
    device_state.meters.append(meter.dict())
    return {"status": "added", "total_meters": len(device_state.meters)}


@app.get("/device/state")
def get_device_state():
    """Get current device state"""
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
    """Update device configuration"""
    if signal is not None:
        device_state.signal = signal
    if cpu_temp is not None:
        device_state.cpu_temp = cpu_temp
    return {"status": "updated"}


@app.post("/trigger/write")
def trigger_write(meter_serial: str, obis_code: str, value: str):
    """Trigger write to meter"""
    if not mqtt_client or not mqtt_client.connected:
        raise HTTPException(503, "MQTT not connected")
    
    msg = Protocol.create_header("write")
    msg["request"] = {
        "meterSerial": meter_serial,
        "obisCode": obis_code,
        "value": value
    }
    mqtt_client.send_message(msg)
    return {"status": "sent"}


@app.post("/trigger/reset")
def trigger_reset(factory_default: bool = False):
    """Trigger device reset"""
    if not mqtt_client or not mqtt_client.connected:
        raise HTTPException(503, "MQTT not connected")
    
    msg = Protocol.create_header("reset")
    msg["request"] = {"factoryDefault": factory_default}
    mqtt_client.send_message(msg)
    return {"status": "sent"}


@app.post("/trigger/relay")
def trigger_relay(relay_name: str, state: str):
    """Control relay"""
    if not mqtt_client or not mqtt_client.connected:
        raise HTTPException(503, "MQTT not connected")
    
    msg = Protocol.create_header("relay")
    msg["request"] = {"relay": relay_name, "state": state}
    mqtt_client.send_message(msg)
    return {"status": "sent"}


# ============================================================================
# Background Processes
# ============================================================================
def heartbeat_worker():
    """Background thread for periodic heartbeat"""
    while True:
        time.sleep(Config.HEARTBEAT_INTERVAL)
        if mqtt_client and mqtt_client.connected:
            try:
                mqtt_client.send_heartbeat()
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")


# ============================================================================
# Main Entry Point
# ============================================================================
def main():
    """Main entry point"""
    global mqtt_client
    
    # Banner
    logger.info("=" * 60)
    logger.info("🚀 MASS Protocol Simulator")
    logger.info(f"Device: {Config.DEVICE_FLAG}/{Config.DEVICE_SERIAL}")
    logger.info(f"Broker: {Config.MQTT_BROKER}:{Config.MQTT_PORT}")
    logger.info(f"Topics: {Config.TOPIC_TO_SERVER} / {Config.TOPIC_FROM_SERVER}")
    logger.info("=" * 60)
    
    # Initialize MQTT client
    mqtt_client = MQTTClient()
    mqtt_client.connect()
    
    # Start heartbeat thread
    heartbeat_thread = threading.Thread(target=heartbeat_worker, daemon=True)
    heartbeat_thread.start()
    logger.info("💓 Heartbeat thread started")
    
    # Start HTTP API
    logger.info(f"🌐 Starting HTTP API on port {Config.API_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=Config.API_PORT, log_level="info")


if __name__ == "__main__":
    main()