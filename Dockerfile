FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY simulator.py .

# Expose HTTP API port
EXPOSE 8000

# Run simulator
CMD ["python", "simulator.py"]