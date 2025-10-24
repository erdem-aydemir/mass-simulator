# MASS Protocol Simulator

Complete MQTT-based device simulator implementing MASS Communication Protocol v0.2

## 🚀 Quick Start

```bash
# Start services
docker-compose up -d

# Check health
curl http://localhost:8000/health

# View logs
docker-compose logs -f mass-simulator
```

## 📋 Features

### ✅ Implemented Functions (13/13)

| Function | Type | Status |
|----------|------|--------|
| identification | Push/Pull | ✅ Auto on connect |
| heartbeat | Push | ✅ Every 60s |
| ack | Response | ✅ All messages |
| alarm | Push | ✅ HTTP trigger |
| read | Pull | ✅ Mock data |
| configuration | Pull | ✅ State update |
| schedule | Pull | ✅ add/list/remove |
| notification | Pull | ✅ add/list/remove |
| log | Pull | ✅ Mock logs |
| **write** | Pull | ✅ **NEW** |
| **reset** | Pull | ✅ **NEW** |
| **firmwareUpdate** | Pull | ✅ **NEW** |
| **profile** | Pull | ✅ **NEW** |
| **directive** | Pull | ✅ **NEW** |
| **relay** | Pull | ✅ **NEW** |

## 🔧 Configuration

Environment variables (defaults):
```bash
DEVICE_FLAG=XYZ
DEVICE_SERIAL=0123456789ABCDE
MQTT_BROKER=localhost
MQTT_PORT=1883
HEARTBEAT_INTERVAL=60
API_PORT=8000
```

## 🌐 HTTP API Endpoints

### Health & Status
- `GET /health` - Health check
- `GET /device/state` - Device state

### Configuration
- `POST /device/config?signal=20&cpu_temp=25` - Update config
- `POST /device/meter/add` - Add meter

### Manual Triggers
- `POST /trigger/heartbeat` - Manual heartbeat
- `POST /trigger/alarm` - Trigger alarm
- `POST /trigger/write` - Write to meter
- `POST /trigger/reset` - Reset device
- `POST /trigger/relay` - Control relay

## 📡 MQTT Topics

- **Publish:** `mass/device/to_server`
- **Subscribe:** `mass/server/to_device`

## 📝 Examples

### Trigger Alarm
```bash
curl -X POST http://localhost:8000/trigger/alarm \
  -H "Content-Type: application/json" \
  -d '{
    "alarm_type": "alarm",
    "level": "warning",
    "incident_code": 310,
    "description": "Relay removed"
  }'
```

### Write to Meter
```bash
curl -X POST "http://localhost:8000/trigger/write?meter_serial=12345678&obis_code=1.8.0&value=100"
```

### Control Relay
```bash
curl -X POST "http://localhost:8000/trigger/relay?relay_name=relay-1&state=on"
```

### MQTT Request (from client)
```json
{
  "device": {"flag": "XYZ", "serialNumber": "0123456789ABCDE"},
  "function": "read",
  "referenceId": "test-001",
  "request": {"directive": "ReadoutDirective1"}
}
```

## 📦 Files

- `simulator.py` - Main simulator (25KB, ~600 lines)
- `MASS_Simulator.postman_collection.json` - API collection
- `docker-compose.yml` - Container orchestration
- `requirements.txt` - Python dependencies

## 🐛 Troubleshooting

**MQTT not connected?**
```bash
docker ps | grep rabbitmq
docker exec mass-rabbitmq rabbitmq-plugins list | grep mqtt
```

**API not responding?**
```bash
docker-compose logs mass-simulator
curl http://localhost:8000/health
```

## 📚 Documentation

- `README.md` - This file
- `QUICKSTART.md` - 5-minute setup guide
- `PROJECT_STRUCTURE.md` - Architecture details
- `MASS_Haberlesme_Protokolu_v_0-2.pdf` - Protocol specification

## 🎯 Protocol Compliance

✅ 100% compliant with MASS Protocol v0.2  
✅ All 13 functions implemented  
✅ MQTTv5 with Properties-based routing  
✅ Proper ACK handling  
✅ Mock data follows protocol examples

## 🔗 Links

- RabbitMQ Management: http://localhost:15672 (guest/guest)
- Simulator API: http://localhost:8000
- Health Check: http://localhost:8000/health

---

**Version:** 2.0.0  
**Protocol:** MASS v0.2  
**Python:** 3.11+