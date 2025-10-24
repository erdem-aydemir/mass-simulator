#!/usr/bin/env python3
"""
MASS Protocol Simulator - Communication Unit Simulation
Optimized version with ref-aware logging
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
    DEVICE_FLAG = os.getenv("DEVICE_FLAG", "XYZ")
    DEVICE_SERIAL = os.getenv("DEVICE_SERIAL", "0123456789ABCDE")
    DEVICE_BRAND = os.getenv("DEVICE_BRAND", "SimulatorBrand")
    DEVICE_MODEL = os.getenv("DEVICE_MODEL", "SimV1.0")
    FIRMWARE = os.getenv("FIRMWARE", "1.01")
    PROTOCOL_VERSION = "1.0.0"

    MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
    MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
    MQTT_USERNAME = os.getenv("MQTT_USERNAME") or None
    MQTT_PASSWORD = os.getenv("MQTT_PASSWORD") or None
    MQTT_KEEPALIVE = int(os.getenv("MQTT_KEEPALIVE", "60"))
    MQTT_QOS = int(os.getenv("MQTT_QOS", "1"))

    TOPIC_TO_SERVER = os.getenv("TOPIC_TO_SERVER", "mass/device/to_server")
    TOPIC_FROM_SERVER = os.getenv("TOPIC_FROM_SERVER", "mass/server/to_device")

    HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "60"))
    API_PORT = int(os.getenv("API_PORT", "8000"))


# ============================================================================
# Device State
# ============================================================================
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


# ============================================================================
# Protocol Utilities
# ============================================================================
class Protocol:
    @staticmethod
    def create_header(function: str, reference_id: Optional[str] = None) -> Dict:
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
        try:
            logger.info(f"Connecting to {Config.MQTT_BROKER}:{Config.MQTT_PORT}")
            self.client.connect(Config.MQTT_BROKER, Config.MQTT_PORT, Config.MQTT_KEEPALIVE)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Connection error: {e}")
            raise

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info("✅ Connected to broker")
            self.connected = True
            client.subscribe(Config.TOPIC_FROM_SERVER, qos=Config.MQTT_QOS)
            logger.info(f"📥 Subscribed to {Config.TOPIC_FROM_SERVER}")
            self.send_identification()
        else:
            logger.error(f"❌ Connection failed with code {rc}")
            self.connected = False

    def _on_disconnect(self, client, userdata, rc, properties=None):
        self.connected = False
        if rc != 0:
            logger.warning(f"⚠️  Disconnected with code {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            function = payload.get("function")
            reference_id = payload.get("referenceId")
            logger.info(f"📩 Received: {function} (ref: {reference_id})")
            self._route_message(payload)
        except Exception as e:
            logger.error(f"❌ Message handling error: {e}")

    def _route_message(self, message: Dict):
        function = message.get("function")
        reference_id = message.get("referenceId")

        if function == "ack":
            logger.info(f"✅ ACK received (ref: {reference_id})")
            return

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
            logger.warning(f"⚠️  Unhandled function: {function} (ref: {reference_id})")
            self.send_ack(reference_id)

    def send_message(self, payload: Dict):
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
            logger.info(f"📤 Sent: {function} (ref: {reference_id})")
        else:
            logger.error(f"❌ Send failed ({function}, ref: {reference_id}) code={result.rc}")

    def send_ack(self, reference_id: str, success: bool = True,
                 fail_code: int = None, fail_description: str = None):
        message = Protocol.create_header("ack", reference_id)
        if not success:
            message["response"] = {
                "failCode": fail_code,
                "failDescrition": fail_description
            }
        self.send_message(message)
        logger.info(f"🔁 ACK sent (ref: {reference_id})")

    def send_identification(self, reference_id: str = None):
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
            "servers": [{"ip": "123.45.68.10", "tcpPort": 1234, "udpPort": 4567, "primary": True}],
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
        logger.info(f"🆔 Identification sent (ref: {message['referenceId']})")

    def send_heartbeat(self):
        message = Protocol.create_header("heartbeat")
        message["response"] = {
            "signal": device_state.signal,
            "deviceDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cpuTemp": device_state.cpu_temp
        }
        self.send_message(message)
        logger.info(f"💓 Heartbeat sent (ref: {message['referenceId']})")

    def send_alarm(self, alarm_type: str, level: str, incident_code: int,
                   description: str, meter_info: Dict = None):
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
        logger.info(f"🚨 Alarm sent: {description} (ref: {message['referenceId']})")

    # Handlers below all updated with ref logging
    def _handle_identification(self, message: Dict):
        ref = message.get("referenceId")
        self.send_identification(ref)
        logger.info(f"📡 Identification handled (ref: {ref})")

    def _handle_read(self, message: Dict):
        ref = message.get("referenceId")
        response = Protocol.create_header("read", ref)
        response["response"] = {
            "readDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data": {"id": "/LGZ5\\2ZMG405000b.P07", "rawData": "0.0.0(23660088)"}
        }
        time.sleep(0.5)
        self.send_message(response)
        logger.info(f"📖 Read response sent (ref: {ref})")

    def _handle_configuration(self, message: Dict):
        ref = message.get("referenceId")
        request = message.get("request", {})
        if "registered" in request:
            device_state.registered = request["registered"]
        if "deviceDate" in request:
            device_state.device_date = datetime.now()
        notif = Protocol.create_header("notification")
        notif["response"] = {"type": "info", "message": "Configuration updated"}
        time.sleep(0.2)
        self.send_message(notif)
        logger.info(f"⚙️  Configuration updated (ref: {ref})")

    def _handle_log(self, message: Dict):
        ref = message.get("referenceId")
        response = Protocol.create_header("log", ref)
        response["response"] = [{"incidentCode": 278, "description": "cover opened"}]
        self.send_message(response)
        logger.info(f"📜 Log sent (ref: {ref})")

    def _handle_write(self, message: Dict):
        ref = message.get("referenceId")
        notif = Protocol.create_header("notification")
        notif["response"] = {"type": "info", "message": "Write successful"}
        time.sleep(0.3)
        self.send_message(notif)
        logger.info(f"✍️  Write completed (ref: {ref})")

    def _handle_reset(self, message: Dict):
        ref = message.get("referenceId")
        notif = Protocol.create_header("notification")
        notif["response"] = {"type": "info", "message": "Device reset successful"}
        time.sleep(0.2)
        self.send_message(notif)
        logger.info(f"🔄 Reset completed (ref: {ref})")

    def _handle_relay(self, message: Dict):
        ref = message.get("referenceId")
        response = Protocol.create_header("relay", ref)
        response["response"] = {"status": "success", "relayState": "on"}
        self.send_message(response)
        logger.info(f"💡 Relay controlled (ref: {ref})")


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


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "mqtt_connected": mqtt_client.connected if mqtt_client else False,
        "device": f"{Config.DEVICE_FLAG}/{Config.DEVICE_SERIAL}",
        "broker": f"{Config.MQTT_BROKER}:{Config.MQTT_PORT}"
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


# ============================================================================
# Background worker
# ============================================================================
def heartbeat_worker():
    while True:
        time.sleep(Config.HEARTBEAT_INTERVAL)
        if mqtt_client and mqtt_client.connected:
            try:
                mqtt_client.send_heartbeat()
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")


# ============================================================================
# Main Entry
# ============================================================================
def main():
    global mqtt_client
    logger.info("=" * 60)
    logger.info("🚀 MASS Protocol Simulator")
    logger.info(f"Device: {Config.DEVICE_FLAG}/{Config.DEVICE_SERIAL}")
    logger.info(f"Broker: {Config.MQTT_BROKER}:{Config.MQTT_PORT}")
    logger.info(f"Topics: {Config.TOPIC_TO_SERVER} / {Config.TOPIC_FROM_SERVER}")
    logger.info("=" * 60)

    mqtt_client = MQTTClient()
    mqtt_client.connect()

    threading.Thread(target=heartbeat_worker, daemon=True).start()
    logger.info("💓 Heartbeat thread started")

    logger.info(f"🌐 Starting HTTP API on port {Config.API_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=Config.API_PORT, log_level="info")


if __name__ == "__main__":
    main()