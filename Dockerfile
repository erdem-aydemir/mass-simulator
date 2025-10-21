FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY simulator.py .

# Expose HTTP API port
EXPOSE 8000

# Environment variables (override with docker run -e)
ENV MQTT_BROKER=localhost
ENV MQTT_PORT=1883
ENV MQTT_USERNAME=""
ENV MQTT_PASSWORD=""
ENV DEVICE_SERIAL=0123456789ABCDE
ENV HEARTBEAT_INTERVAL=60

# Run simulator
CMD ["python", "simulator.py"]