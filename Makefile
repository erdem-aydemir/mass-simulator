.PHONY: help build up down logs restart clean test install dev rabbitmq-enable

help: ## Show this help message
	@echo "MASS Simulator - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

rabbitmq-enable: ## Create RabbitMQ MQTT plugin config
	@echo "[rabbitmq_mqtt,rabbitmq_management]." > rabbitmq_enabled_plugins
	@echo "✅ RabbitMQ MQTT plugin config created"

build: rabbitmq-enable ## Build Docker containers
	@echo "🔨 Building containers..."
	docker-compose build

up: rabbitmq-enable ## Start all services
	@echo "🚀 Starting services..."
	docker-compose up -d
	@echo ""
	@echo "✅ Services started!"
	@echo "   - Simulator API: http://localhost:8000"
	@echo "   - RabbitMQ Management: http://localhost:15672 (guest/guest)"
	@echo "   - MQTT Broker: localhost:1883"

up-logs: rabbitmq-enable ## Start services with logs
	@echo "🚀 Starting services with logs..."
	docker-compose up

down: ## Stop all services
	@echo "⏹️  Stopping services..."
	docker-compose down

logs: ## Show logs
	docker-compose logs -f

logs-sim: ## Show simulator logs only
	docker-compose logs -f mass-simulator

logs-rabbit: ## Show RabbitMQ logs only
	docker-compose logs -f rabbitmq

restart: ## Restart all services
	@echo "🔄 Restarting services..."
	docker-compose restart

restart-sim: ## Restart simulator only
	@echo "🔄 Restarting simulator..."
	docker-compose restart mass-simulator

clean: ## Stop and remove all containers, volumes
	@echo "🧹 Cleaning up..."
	docker-compose down -v
	rm -f rabbitmq_enabled_plugins
	@echo "✅ Cleanup complete"

test: ## Run test script
	@echo "🧪 Running tests..."
	@chmod +x test_simulator.sh
	./test_simulator.sh

install: ## Install Python dependencies locally
	@echo "📦 Installing dependencies..."
	pip install -r requirements.txt

dev: install ## Run simulator locally (for development)
	@echo "🔧 Starting simulator in development mode..."
	@echo "⚠️  Make sure RabbitMQ is running!"
	python simulator.py

client: install ## Run example Python client
	@echo "🔌 Starting example client..."
	python example_client.py

status: ## Show service status
	@docker-compose ps

shell-sim: ## Shell into simulator container
	docker exec -it mass-simulator /bin/bash

shell-rabbit: ## Shell into RabbitMQ container
	docker exec -it mass-rabbitmq /bin/bash

health: ## Check simulator health
	@curl -s http://localhost:8000/health | python -m json.tool || echo "❌ Simulator not responding"

trigger-heartbeat: ## Trigger manual heartbeat
	@curl -s -X POST http://localhost:8000/trigger/heartbeat | python -m json.tool

trigger-alarm: ## Trigger test alarm
	@curl -s -X POST http://localhost:8000/trigger/alarm \
		-H "Content-Type: application/json" \
		-d '{"alarm_type":"alarm","level":"warning","incident_code":310,"description":"Test alarm from Makefile"}' \
		| python -m json.tool

state: ## Show device state
	@curl -s http://localhost:8000/device/state | python -m json.tool

rabbitmq-ui: ## Open RabbitMQ management UI
	@echo "🌐 Opening RabbitMQ Management UI..."
	@echo "   URL: http://localhost:15672"
	@echo "   Username: guest"
	@echo "   Password: guest"
	@open http://localhost:15672 2>/dev/null || xdg-open http://localhost:15672 2>/dev/null || echo "Please open: http://localhost:15672"

# Development workflow
dev-setup: ## Complete development setup
	@echo "🔧 Setting up development environment..."
	@make rabbitmq-enable
	@make build
	@make up
	@echo ""
	@echo "⏳ Waiting for services to start (30s)..."
	@sleep 30
	@make health
	@echo ""
	@echo "✅ Development environment ready!"
	@echo "   Run 'make test' to verify"

# CI/CD helpers
ci-test: ## Run tests in CI environment
	@make build
	@make up
	@sleep 20
	@make test
	@make down

# Quick commands
quick-start: dev-setup ## Quick start (setup + verify)

quick-test: ## Quick test without full setup
	@make up
	@sleep 15
	@make test