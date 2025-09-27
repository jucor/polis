.PHONY: help install install-dev test test-unit test-integration test-slow lint format type-check security quality pre-commit clean build docs docker-build docker-run

# Default target
help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	pip install -e .

install-dev: ## Install development dependencies
	pip install -e ".[dev,notebook]"
	pre-commit install

# Testing
test: ## Run all tests
	pytest -v

test-unit: ## Run unit tests only
	pytest tests/ -v -m "not slow and not real_data and not integration"

test-integration: ## Run integration tests
	pytest tests/ -v -m "integration"

test-slow: ## Run slow tests (real data tests)
	pytest tests/ -v -m "slow or real_data"

test-cov: ## Run tests with coverage
	pytest tests/ -v --cov=polismath --cov=umap_narrative --cov-report=html --cov-report=term-missing

# Code Quality - Streamlined Modern Tools
lint: ## Run all linters (Ruff replaces flake8, isort, and more)
	ruff check .
	black --check .

format: ## Format code (Black + Ruff auto-fix)
	black .
	ruff check --fix .

type-check: ## Run type checking
	mypy polismath umap_narrative

security: ## Run security checks
	bandit -r polismath umap_narrative -f json -o bandit-report.json
	@echo "Security report generated: bandit-report.json"

quality: ## Run all quality checks
	lint type-check security test-unit

# Setup and maintenance
setup-dev: install-dev ## Set up development environment
	@echo "Setting up development environment..."
	@if [ ! -f .env ]; then cp example.env .env; echo "Created .env from example.env"; fi
	@echo "Don't forget to:"
	@echo "1. Update .env with your specific configuration"
	@echo "2. Set up your database connection"
	@echo "3. Create DynamoDB tables: make setup-dynamodb"

venv: ## Create canonical virtual environment (delphi-dev-env)
	@echo "Creating canonical virtual environment: delphi-dev-env"
	@if [ ! -d "delphi-dev-env" ]; then \
		python3 -m venv delphi-dev-env; \
		echo "✓ Virtual environment created"; \
	else \
		echo "✓ Virtual environment already exists"; \
	fi
	@echo "To activate: source delphi-dev-env/bin/activate"
	@echo "Then run: make install-dev"

venv-check: ## Check virtual environment status
	@echo "Virtual environment status:"
	@if [ -n "$$VIRTUAL_ENV" ]; then \
		echo "✓ Active virtual environment: $$VIRTUAL_ENV"; \
		python --version; \
		echo "Python location: $$(which python)"; \
	else \
		echo "❌ No virtual environment active"; \
		echo "Run: source delphi-dev-env/bin/activate"; \
	fi

setup-dynamodb: ## Create local DynamoDB tables
	@echo "Creating DynamoDB tables..."
	python create_dynamodb_tables.py --endpoint-url http://localhost:8000

# Cleanup
clean: ## Clean build artifacts
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf htmlcov/
	rm -f coverage.xml
	rm -f .coverage
	rm -f bandit-report.json

# Build
build: ## Build package
	python -m build

# Docker commands
docker-build: ## Build Docker image
	docker build -t polis/delphi:latest .

docker-run: ## Run Docker container
	docker run --rm --name delphi-app --env-file .env polis/delphi:latest

docker-logs: ## Show Docker logs
	docker logs delphi-app

docker-stop: ## Stop Docker containers
	docker stop delphi-app

# Database operations
reset-db: ## Reset all DynamoDB tables
	./scripts/reset_database.sh

reset-conversation: ## Reset specific conversation (requires ZID=conversation_id)
	@if [ -z "$(ZID)" ]; then echo "Usage: make reset-conversation ZID=12345"; exit 1; fi
	./reset_conversation.sh $(ZID)

# CLI helpers
cli: ## Run Delphi CLI in interactive mode
	./delphi

submit-job: ## Submit processing job (requires ZID=conversation_id)
	@if [ -z "$(ZID)" ]; then echo "Usage: make submit-job ZID=12345"; exit 1; fi
	./delphi submit --zid=$(ZID)

job-status: ## Show job queue status
	./delphi list

# Environment management
env-check: ## Check environment configuration
	@echo "Checking environment configuration..."
	@python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('✓ Environment loaded successfully')"
	@python -c "import sys; print(f'Python version: {sys.version}')"
	@python -c "import torch; print(f'PyTorch version: {torch.__version__}')"

# Pipeline commands
process: ## Process conversation (requires ZID=conversation_id)
	@if [ -z "$(ZID)" ]; then echo "Usage: make process ZID=12345"; exit 1; fi
	./run_delphi.py --zid=$(ZID)

process-verbose: ## Process conversation with verbose output (requires ZID=conversation_id)
	@if [ -z "$(ZID)" ]; then echo "Usage: make process-verbose ZID=12345"; exit 1; fi
	./run_delphi.py --zid=$(ZID) --verbose

# Dependency management
generate-requirements: ## Generate requirements files from pyproject.toml
	@echo "Generating deployment requirements files from pyproject.toml..."
	pip-compile --output-file requirements-prod.txt pyproject.toml
	pip-compile --extra dev --output-file requirements-dev.txt pyproject.toml
	@echo "✓ Generated requirements-prod.txt (production dependencies)"
	@echo "✓ Generated requirements-dev.txt (development dependencies)"

generate-requirements-upgrade: ## Generate requirements files with dependency upgrades
	@echo "Generating requirements files with latest versions..."
	pip-compile --upgrade --output-file requirements-prod.txt pyproject.toml
	pip-compile --upgrade --extra dev --output-file requirements-dev.txt pyproject.toml

check-deps: ## Check for dependency updates
	@echo "Checking for dependency updates..."
	@if command -v pip-compile >/dev/null 2>&1; then \
		pip-compile --dry-run --upgrade pyproject.toml; \
	else \
		echo "Install pip-tools first: pip install pip-tools"; \
	fi

# Development workflow
dev-workflow: format lint type-check test-unit ## Complete development workflow check
