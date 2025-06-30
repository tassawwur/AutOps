# AutOps Makefile
.PHONY: help install test lint format build run docker-build docker-run deploy-k8s clean

# Default target
help: ## Show this help message
	@echo "AutOps - AI-Powered DevOps Automation"
	@echo "Usage: make [target]"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Development
install: ## Install dependencies using Poetry
	@echo "Installing dependencies..."
	poetry install --with=dev,test

install-pre-commit: ## Install pre-commit hooks
	@echo "Installing pre-commit hooks..."
	poetry run pre-commit install

update: ## Update dependencies
	@echo "Updating dependencies..."
	poetry update

# Code Quality
format: ## Format code using Black
	@echo "Formatting code..."
	poetry run black src/ tests/

lint: ## Run linting checks
	@echo "Running lint checks..."
	poetry run flake8 src/ tests/
	poetry run mypy src/

type-check: ## Run type checking
	@echo "Running type checks..."
	poetry run mypy src/

validate-deps: ## Validate dependency resolution
	@echo "Validating dependencies..."
	python scripts/validate-deps.py

# Testing
test: ## Run all tests
	@echo "Running tests..."
	poetry run pytest

test-unit: ## Run unit tests only
	@echo "Running unit tests..."
	poetry run pytest tests/unit/

test-integration: ## Run integration tests only
	@echo "Running integration tests..."
	poetry run pytest tests/integration/

test-coverage: ## Run tests with coverage report
	@echo "Running tests with coverage..."
	poetry run pytest --cov=src --cov-report=html --cov-report=term

test-watch: ## Run tests in watch mode
	@echo "Running tests in watch mode..."
	poetry run pytest-watch

# Development Server
run: ## Run development server
	@echo "Starting development server..."
	poetry run uvicorn src.autops.main:app --reload --host 0.0.0.0 --port 8000

run-debug: ## Run development server with debug logging
	@echo "Starting development server with debug logging..."
	LOG_LEVEL=DEBUG poetry run uvicorn src.autops.main:app --reload --host 0.0.0.0 --port 8000

# Docker
docker-build: ## Build Docker image
	@echo "Building Docker image..."
	docker build -t autops:latest .

docker-run: ## Run Docker container
	@echo "Running Docker container..."
	docker run -d --name autops --env-file .env -p 8000:8000 autops:latest

docker-stop: ## Stop Docker container
	@echo "Stopping Docker container..."
	docker stop autops || true
	docker rm autops || true

docker-logs: ## View Docker container logs
	@echo "Viewing Docker logs..."
	docker logs -f autops

# Docker Compose
compose-up: ## Start all services with Docker Compose
	@echo "Starting services with Docker Compose..."
	docker-compose up -d

compose-down: ## Stop all services
	@echo "Stopping services..."
	docker-compose down

compose-logs: ## View Docker Compose logs
	@echo "Viewing Docker Compose logs..."
	docker-compose logs -f

compose-build: ## Build and start services
	@echo "Building and starting services..."
	docker-compose up --build -d

# Monitoring
prometheus: ## Start Prometheus monitoring
	@echo "Starting Prometheus..."
	docker-compose up -d prometheus

grafana: ## Start Grafana dashboard
	@echo "Starting Grafana..."
	docker-compose up -d grafana

monitoring: ## Start full monitoring stack
	@echo "Starting monitoring stack..."
	docker-compose up -d prometheus grafana

# Kubernetes
k8s-deploy: ## Deploy to Kubernetes
	@echo "Deploying to Kubernetes..."
	kubectl apply -f k8s/

k8s-delete: ## Delete Kubernetes deployment
	@echo "Deleting Kubernetes deployment..."
	kubectl delete -f k8s/

k8s-logs: ## View Kubernetes logs
	@echo "Viewing Kubernetes logs..."
	kubectl logs -f deployment/autops

k8s-status: ## Check Kubernetes deployment status
	@echo "Checking deployment status..."
	kubectl get pods,services,deployments -l app=autops

# Database
redis-start: ## Start Redis locally
	@echo "Starting Redis..."
	docker run -d --name redis -p 6379:6379 redis:7-alpine

redis-stop: ## Stop Redis
	@echo "Stopping Redis..."
	docker stop redis || true
	docker rm redis || true

redis-cli: ## Connect to Redis CLI
	@echo "Connecting to Redis CLI..."
	docker exec -it redis redis-cli

# Security
security-scan: ## Run security vulnerability scan
	@echo "Running security scan..."
	poetry run safety check

secrets-check: ## Check for secrets in code
	@echo "Checking for secrets..."
	poetry run detect-secrets scan --all-files

# Utilities
clean: ## Clean up build artifacts and caches
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .coverage htmlcov/ .pytest_cache/

env-template: ## Create .env template file
	@echo "Creating .env template..."
	@echo "# AutOps Environment Configuration" > .env.template
	@echo "ENVIRONMENT=development" >> .env.template
	@echo "LOG_LEVEL=INFO" >> .env.template
	@echo "DEBUG=true" >> .env.template
	@echo "" >> .env.template
	@echo "# OpenAI" >> .env.template
	@echo "OPENAI_API_KEY=your_openai_api_key" >> .env.template
	@echo "OPENAI_MODEL=gpt-4o" >> .env.template
	@echo "" >> .env.template
	@echo "# Slack" >> .env.template
	@echo "SLACK_BOT_TOKEN=xoxb-your-slack-bot-token" >> .env.template
	@echo "SLACK_SIGNING_SECRET=your_slack_signing_secret" >> .env.template
	@echo "" >> .env.template
	@echo "# GitHub" >> .env.template
	@echo "GITHUB_TOKEN=your_github_personal_access_token" >> .env.template
	@echo "GITHUB_OWNER=your_github_organization" >> .env.template
	@echo "" >> .env.template
	@echo "# Datadog (optional)" >> .env.template
	@echo "DATADOG_API_KEY=your_datadog_api_key" >> .env.template
	@echo "DATADOG_APP_KEY=your_datadog_app_key" >> .env.template
	@echo "" >> .env.template
	@echo "# PagerDuty (optional)" >> .env.template
	@echo "PAGERDUTY_API_KEY=your_pagerduty_api_key" >> .env.template
	@echo "PAGERDUTY_EMAIL=your_email@company.com" >> .env.template
	@echo "" >> .env.template
	@echo "# Redis" >> .env.template
	@echo "REDIS_URL=redis://localhost:6379/0" >> .env.template
	@echo "Template created: .env.template"

check-env: ## Check environment configuration
	@echo "Checking environment configuration..."
	@poetry run python -c "from src.autops.config import get_settings; print('✅ Configuration loaded successfully')"

# Documentation
docs-serve: ## Serve API documentation
	@echo "Starting API documentation server..."
	@echo "API docs will be available at: http://localhost:8000/docs"
	make run

# CI/CD helpers
ci-test: ## Run CI test suite
	@echo "Running CI test suite..."
	make lint
	make type-check
	make test-coverage

ci-build: ## Build for CI/CD
	@echo "Building for CI/CD..."
	make docker-build

# Health checks
health-check: ## Check application health
	@echo "Checking application health..."
	@curl -f http://localhost:8000/health || echo "❌ Health check failed"

metrics: ## View application metrics
	@echo "Viewing application metrics..."
	@curl -s http://localhost:8000/metrics | head -20

# All-in-one commands
dev-setup: ## Complete development setup
	@echo "Setting up development environment..."
	make install
	make install-pre-commit
	make env-template
	@echo "✅ Development setup complete!"
	@echo "Next steps:"
	@echo "1. Copy .env.template to .env and fill in your credentials"
	@echo "2. Run 'make run' to start the development server"
	@echo "3. Visit http://localhost:8000/docs for API documentation"

prod-build: ## Build production-ready application
	@echo "Building production application..."
	make clean
	make lint
	make test
	make docker-build
	@echo "✅ Production build complete!"

# Version info
version: ## Show version information
	@echo "AutOps v0.1.0"
	@echo "Python: $(shell python --version)"
	@echo "Poetry: $(shell poetry --version)"
	@echo "Docker: $(shell docker --version)" 