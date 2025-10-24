# MASS Simulator - Quick Start (5 Minutes)

## Prerequisites

- Docker & Docker Compose
- curl (for testing)

## Step 1: Start (30 seconds)

```bash
docker-compose up -d
```

Services starting:
- ✅ RabbitMQ (MQTT broker) on port 1883
- ✅ Simulator API on port 8000

## Step 2: Verify (10 seconds)

```bash
# Health check
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "mqtt_connected": true,
  "device": "XYZ/0123456789ABCDE",
  "broker": "localhost:1883"
}
```

## Step 3: Test Functions (2 minutes)

### Test 1: Manual Heartbeat
```bash
curl -X POST http://localhost:8000/trigger/heartbeat
# Response: {"status":"sent"}
```

### Test 2: Trigger Alarm
```bash
curl -X POST http://localhost:8000/trigger/alarm \
  -H "Content-Type: application/json" \
  -d '{"alarm_type":"alarm","level":"warning","incident_code":310,"description":"Test alarm"}'
```

### Test 3: Write to Meter
```bash
curl -X POST "http://localhost:8000/trigger/write?meter_serial=12345678&obis_code=1.8.0&value=100"
```

### Test 4: Control Relay
```bash
curl -X POST "http://localhost:8000/trigger/relay?relay_name=relay-1&state=on"
```

## Step 4: Monitor (30 seconds)

```bash
# View logs
docker-compose logs -f mass-simulator

# Check device state
curl http://localhost:8000/device/state
```

## Step 5: Import Postman Collection (1 minute)

1. Open Postman
2. File → Import
3. Select `MASS_Simulator.postman_collection.json`
4. Run requests from collection

## Quick Commands

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# Restart
docker-compose restart

# Logs
docker-compose logs -f

# RabbitMQ UI
open http://localhost:15672
# Login: guest/guest
```

## What's Running?

- **Simulator:** http://localhost:8000
- **RabbitMQ Management:** http://localhost:15672
- **MQTT Broker:** localhost:1883

## All Functions

✅ identification, heartbeat, ack, alarm  
✅ read, configuration, schedule, notification, log  
✅ write, reset, firmwareUpdate, profile, directive, relay

**Total: 13/13 functions implemented**

## Troubleshooting

**Problem:** Health check fails  
**Solution:** 
```bash
docker-compose ps  # Check services
docker-compose logs  # Check logs
```

**Problem:** MQTT not connected  
**Solution:**
```bash
docker exec mass-rabbitmq rabbitmq-plugins list | grep mqtt
# Should show: [E*] rabbitmq_mqtt
```

---

🎉 **Done! Simulator is ready in 5 minutes**