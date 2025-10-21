#!/bin/bash

# MASS Simulator Test Script
# Bu script simülatörün düzgün çalıştığını test eder

set -e

SIMULATOR_API="http://localhost:8000"
MQTT_BROKER="localhost"
MQTT_PORT="1883"

echo "================================================"
echo "🧪 MASS Simulator Test Suite"
echo "================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
PASSED=0
FAILED=0

# Helper function
test_endpoint() {
    local name=$1
    local method=$2
    local endpoint=$3
    local data=$4
    
    echo -n "Testing: $name ... "
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "$SIMULATOR_API$endpoint")
    else
        response=$(curl -s -w "\n%{http_code}" -X POST "$SIMULATOR_API$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" = "200" ]; then
        echo -e "${GREEN}✓ PASSED${NC}"
        ((PASSED++))
        echo "   Response: $body"
    else
        echo -e "${RED}✗ FAILED${NC} (HTTP $http_code)"
        ((FAILED++))
        echo "   Response: $body"
    fi
    echo ""
}

# Wait for simulator to be ready
echo "⏳ Waiting for simulator to be ready..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s "$SIMULATOR_API/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Simulator is ready!${NC}"
        break
    fi
    sleep 1
    ((attempt++))
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "${RED}✗ Simulator did not start in time${NC}"
    exit 1
fi

echo ""
echo "================================================"
echo "Running Tests"
echo "================================================"
echo ""

# Test 1: Health Check
test_endpoint "Health Check" "GET" "/health"

# Test 2: Get Device State
test_endpoint "Get Device State" "GET" "/device/state"

# Test 3: Update Config
test_endpoint "Update Device Config" "POST" "/device/config?signal=20&cpu_temp=25"

# Test 4: Add Meter
test_endpoint "Add Meter" "POST" "/device/meter/add" '{
    "protocol": "IEC62056",
    "type": "electricity",
    "brand": "TEST",
    "serialNumber": "TEST001",
    "serialPort": "rs485-1",
    "initBaud": 300,
    "fixBaud": false,
    "frame": "7E1"
}'

# Test 5: Trigger Heartbeat
test_endpoint "Trigger Heartbeat" "POST" "/trigger/heartbeat"

# Test 6: Trigger Alarm - Info
test_endpoint "Trigger Info Alarm" "POST" "/trigger/alarm" '{
    "alarm_type": "info",
    "level": "info",
    "incident_code": 104,
    "description": "Enerji geldi"
}'

# Test 7: Trigger Alarm - Warning
test_endpoint "Trigger Warning Alarm" "POST" "/trigger/alarm" '{
    "alarm_type": "alarm",
    "level": "warning",
    "incident_code": 310,
    "description": "Röle söküldü",
    "meter_serial": "TEST001",
    "meter_brand": "TEST"
}'

# Test 8: Trigger Alarm - Critical
test_endpoint "Trigger Critical Alarm" "POST" "/trigger/alarm" '{
    "alarm_type": "danger",
    "level": "critical",
    "incident_code": 302,
    "description": "Enerji kesintisi oldu"
}'

# Summary
echo "================================================"
echo "Test Summary"
echo "================================================"
echo -e "Total Tests: $((PASSED + FAILED))"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
fi