# BlueprintGuardAIn

**BlueprintGuardAIn** is an autonomous codebase intelligence engine designed to maintain architectural integrity and documentation health. It acts as an AI-driven peer reviewer that lives in your CI/CD pipeline, ensuring your code aligns with your project's defined domain rules and architectural vision.

## 🚀 Key Features
- **Async Processing (Level 3):** Powered by Kafka to handle high-volume repository events without timeouts.
- **Architectural Guardrails:** Uses LLMs to detect "architectural drift" (e.g., domain leaks, pattern violations).
- **Self-Healing Docs:** Automatically keeps `README` and architectural documentation in sync with code changes.
- **Knowledge Oracle (RAG):** Exposes an API for developers to query the codebase using natural language.

## 🏗️ Architecture
The project follows **Domain-Driven Design (DDD)** principles:
- **Domain:** Pure business logic and AI analysis rules.
- **Application:** Orchestration of Kafka events and RAG workflows.
- **Infrastructure:** Implementation of Kafka producers/consumers, PostgreSQL + pgvector, and LLM clients.
- **Interface:** FastAPI for webhooks and the developer query API.

## 🛠️ Prerequisites
- **Python 3.12+**
- **uv** (Dependency and Python manager)
- **Docker** (For Kafka and PostgreSQL/pgvector)

## 📦 Getting Started

### 1. Environment Setup
```bash
# Clone the repository (or enter the directory)
cd archivist-ai

# Initialize the environment and install dependencies
uv sync
```

### 2. Infrastructure
Launch the required services (Kafka, Postgres, pgvector) using Docker Compose:
```bash
docker-compose up -d
```

### 3. Running the Application
```bash
# Start the Ingestion Service (FastAPI)
uv run uvicorn src.interface.api.main:app --reload

# Start the Analysis Worker (Kafka Consumer)
uv run python -m src.infrastructure.workers.analysis
```

## 🧪 Testing
We follow strict **TDD**. No feature is implemented without a failing test first.
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src
```

## 🛡️ Validation
Before committing, ensure all quality gates pass:
```bash
uv run ruff check .
uv run mypy .
uv run pytest
```
