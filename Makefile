.PHONY: help init keys up down restart logs status shell test lint format clean

# Detect OS
ifeq ($(OS),Windows_NT)
	SHELL := powershell.exe
	.SHELLFLAGS := -NoProfile -Command
endif

help:
	@echo "AI City Governor Management Commands:"
	@echo "  init         Initialize project, generate keys, install deps"
	@echo "  keys         Generate RSA key pairs for signing"
	@echo "  up           Start all services in Docker Compose (detached)"
	@echo "  down         Stop all services"
	@echo "  restart      Restart all services"
	@echo "  logs         Tail Docker logs"
	@echo "  status       Check status of Docker containers"
	@echo "  shell        Open backend shell"
	@echo "  test         Run backend tests"
	@echo "  lint         Run ruff linting"
	@echo "  format       Run ruff format"
	@echo "  clean        Clean temporary files and caches"

init: keys
	pip install -r backend/requirements.txt -r backend/requirements-dev.txt

keys:
	python backend/scripts/generate_keys.py

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

status:
	docker compose ps

shell:
	docker compose exec backend /bin/bash

test:
	pytest backend/tests/

lint:
	ruff check backend/app/

format:
	ruff format backend/app/

clean:
	Get-ChildItem -Path . -Filter "__pycache__" -Recurse | Remove-Item -Force -Recurse
	Get-ChildItem -Path . -Filter ".pytest_cache" -Recurse | Remove-Item -Force -Recurse
	Get-ChildItem -Path . -Filter ".ruff_cache" -Recurse | Remove-Item -Force -Recurse
