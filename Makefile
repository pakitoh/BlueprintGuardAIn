.DEFAULT_GOAL := help

.PHONY: help start dev install lint test infra infra-down seed build up down

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  start       Full Docker setup: install, lint, infra, seed, build and run all services"
	@echo "  dev         Local dev setup: install, lint, infra and seed (then run services manually)"
	@echo ""
	@echo "  install     Install dependencies for all services"
	@echo "  lint        Run ruff and mypy across all services"
	@echo "  test        Run the test suite for all services"
	@echo "  infra       Start infrastructure (Kafka, PostgreSQL, OTEL stack)"
	@echo "  infra-down  Stop infrastructure"
	@echo "  seed        Seed the analysis knowledge base"
	@echo "  build       Build all service Docker images"
	@echo "  up          Start all services via Docker"
	@echo "  down        Stop all services"

start: install lint infra seed build up

dev: install lint infra seed

install:
	cd ingestion-service  && uv sync
	cd analysis-worker    && uv sync
	cd notification-worker && uv sync
	cd dashboard-service  && uv sync

lint:
	cd analysis-worker     && uv run ruff check . && uv run mypy src/
	cd dashboard-service   && uv run ruff check . && uv run mypy src/
	cd ingestion-service   && uv run ruff check . && uv run mypy src/
	cd notification-worker && uv run ruff check . && uv run mypy src/

test:
	cd analysis-worker     && uv run python -m pytest
	cd dashboard-service   && uv run python -m pytest
	cd ingestion-service   && uv run python -m pytest
	cd notification-worker && uv run python -m pytest

infra:
	docker compose up -d

infra-down:
	docker compose down

seed:
	cd analysis-worker && uv run python ../scripts/seed_findings.py

build:
	GIT_SHA=$$(git rev-parse HEAD) docker compose --profile app build

up:
	docker compose --profile app up -d

down:
	docker compose --profile app down
