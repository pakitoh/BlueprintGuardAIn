.DEFAULT_GOAL := help

.PHONY: help start dev install infra infra-down seed build up down

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  start       Full Docker setup: install, infra, seed, build and run all services"
	@echo "  dev         Local dev setup: install, infra and seed (then run services manually)"
	@echo ""
	@echo "  install     Install dependencies for all services"
	@echo "  infra       Start infrastructure (Kafka, PostgreSQL, OTEL stack)"
	@echo "  infra-down  Stop infrastructure"
	@echo "  seed        Seed the analysis knowledge base"
	@echo "  build       Build all service Docker images"
	@echo "  up          Start all services via Docker"
	@echo "  down        Stop all services"

start: install infra seed build up

dev: install infra seed

install:
	cd ingestion-service  && uv sync
	cd analysis-worker    && uv sync
	cd notification-worker && uv sync
	cd dashboard-service  && uv sync

infra:
	docker compose up -d

infra-down:
	docker compose down

seed:
	cd analysis-worker && uv run python ../scripts/seed_findings.py

build:
	docker compose --profile app build

up:
	docker compose --profile app up -d

down:
	docker compose --profile app down
