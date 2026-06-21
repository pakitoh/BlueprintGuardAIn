.DEFAULT_GOAL := help

.PHONY: help start start-observability dev install lint test coverage infra infra-down observability observability-down seed build up down chaos-kafka chaos-infra chaos-recover

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  start       Full Docker setup: install, lint, infra, seed, build and run all services"
	@echo "  start-observability  Same as start, but also brings up the local embedded observability stack"
	@echo "  dev         Local dev setup: install, lint, infra and seed (then run services manually)"
	@echo ""
	@echo "  install     Install dependencies for all services"
	@echo "  lint        Run ruff and mypy across all services"
	@echo "  test        Run the test suite for all services"
	@echo "  coverage    Run the test suite with a coverage report for all services"
	@echo "  infra       Start infrastructure (Kafka, PostgreSQL, OTEL stack)"
	@echo "  infra-down  Stop infrastructure"
	@echo "  observability       Start the local embedded observability stack (Grafana/Loki/Tempo/Prometheus)"
	@echo "  observability-down  Stop the local embedded observability stack"
	@echo "  seed        Seed the analysis knowledge base"
	@echo "  build       Build all service Docker images"
	@echo "  up          Start all services via Docker"
	@echo "  down        Stop all services"
	@echo ""
	@echo "  chaos-kafka    Inject a malformed/mismatched-schema Kafka message (MODE=garbage|truncated|wrong-schema, COUNT=1)"
	@echo "  chaos-infra    Fault-inject a running container via Pumba (ACTION=pause|kill|delay|loss, CONTAINER=guardain_kafka, VALUE, DURATION)"
	@echo "  chaos-recover  Unpause/restart any containers affected by chaos-infra"

start: install lint infra seed build up

start-observability: install lint infra observability seed build up

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

coverage:
	cd analysis-worker     && uv run python -m pytest --cov
	cd dashboard-service   && uv run python -m pytest --cov
	cd ingestion-service   && uv run python -m pytest --cov
	cd notification-worker && uv run python -m pytest --cov

infra:
	docker compose up -d

infra-down:
	docker compose down

observability:
	docker compose -f docker-compose-grafana.yaml up -d

observability-down:
	docker compose -f docker-compose-grafana.yaml down

seed:
	cd analysis-worker && uv run python ../scripts/seed_findings.py

build:
	GIT_SHA=$$(git rev-parse HEAD) docker compose --profile app build

up:
	docker compose --profile app up -d

down:
	docker compose --profile app down

chaos-kafka:
	uv run scripts/chaos_kafka.py --mode $(or $(MODE),garbage) --count $(or $(COUNT),1)

chaos-infra:
	scripts/chaos_infra.sh $(or $(ACTION),pause) $(or $(CONTAINER),guardain_kafka) $(VALUE) $(DURATION)

chaos-recover:
	-docker unpause $$(docker ps -aq --filter "name=guardain_") 2>/dev/null
	docker compose up -d
	docker compose --profile app up -d
