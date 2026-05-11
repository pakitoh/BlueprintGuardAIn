<p align="center">
    <a href="https://github.com/pakitoh/blueprintGuarAIn">
        <img src="logo.png" alt="Logo" width="200">
    </a>
</p>
<p align="center" style="color:rgb(40,82,100);font-size:44px;font-weight:bold;">
    <span style="color:rgb(23,47,88)">Blueprint</span> Guard<span style="color:white">AI</span>n
</p>

# 🛡️ Description

**Blueprint GuardAIn** is an autonomous codebase intelligence platform designed to maintain architectural integrity and documentation health. It acts as an AI-driven peer reviewer that lives in your CI/CD pipeline, ensuring your code aligns with your project's defined domain rules and helping you to maintain architectural integrity.

## 🏗️ Monorepo Architecture

This project is structured as a collection of **independent microservices**. Each service is a standalone Python project with its own dependencies and environment, communicating asynchronously via **Kafka**.

### Service Map
1.  **`ingestion-service/`**: FastAPI gateway. Receives GitHub Webhooks, validates signatures, and produces raw events to Kafka.
2.  **`analysis-worker/`**: The "Brain". Consumes events, fetches code diffs, performs AI analysis using LLMs, and stores embeddings in **pgvector**.
3.  **`action-worker/`**: The "Actuator". Consumes analysis results and interacts with external APIs (GitHub PR comments, Slack, etc.).

---

## 🚀 Core Features
*   **Asynchronous Processing:** Powered by Kafka to handle long-running AI analysis tasks without timing out webhooks.
*   **Architectural Guardrails:** Detects "architectural drift" (e.g., domain leaks) using context-aware LLM analysis.
*   **Semantic Knowledge Base:** Uses **pgvector** and RAG to allow natural language queries against your codebase history.
*   **Strict Decoupling:** Services are physically separated, allowing for independent scaling and deployment.

---

## 📦 Getting Started

### 1. Prerequisites
*   **Python 3.12+** (Managed by `uv`)
*   **Docker & Docker Compose** (For Kafka, PostgreSQL, and pgvector)
*   **OpenAI API Key** (For analysis and embeddings)

### 2. Infrastructure Setup
Launch the shared infrastructure at the root:
```bash
docker-compose up -d
```

### 3. Service Initialization
Since each service is independent, you must initialize each one:
```bash
cd ingestion-service && uv sync
cd ../analysis-worker && uv sync
cd ../action-worker && uv sync
```

### 4. Running the Platform
Open three terminal tabs to run the services:

**Tab 1 (Ingestion):**
```bash
cd ingestion-service && uv run python -m src.main
```

**Tab 2 (Analysis):**
```bash
cd analysis-worker && uv run python -m src.main
```

**Tab 3 (Action):**
```bash
cd action-worker && uv run python -m src.main
```

---

## 🛠️ Simulation & Testing

### Simulate GitHub Webhooks
Use the simulation script to generate traffic. It supports random data and continuous execution.

**Quick Test (Single Event):**
```bash
uv run scripts/simulate_webhook.py --count 1
```

**Stress Test (Indefinite Events):**
```bash
uv run scripts/simulate_webhook.py --delay 0.5
```

---

## 📊 Observability & Logging

The platform is fully instrumented using **OpenTelemetry (OTEL)** and **Structlog**, exporting data to a centralized OTLP collector.

### The "Three Pillars"
*   **Traces:** Full request/event lifecycle visible in **Tempo**.
*   **Metrics:** "Golden Signals" (latency, error rates, load) exported to **Prometheus**.
*   **Logs:** Universal JSON logging exported to **Loki**.

### Logging Standards
Every log message across the system is a **JSON object** (including library logs like Uvicorn or Kafka). We follow a strict severity hierarchy:

| Level | Usage | Example |
| :--- | :--- | :--- |
| **DEBUG** | Infrastructure, initialization, and trace details. | `starting_kafka_producer`, `received_message` |
| **INFO** | Significant **Business Events**. | `webhook_processed_successfully`, `analysis_completed` |
| **WARN** | Controlled failures or edge cases. | `webhook_unsupported_event` |
| **ERROR** | Unexpected system failures or crashes. | `kafka_connection_lost`, `unexpected_mapping_error` |

### Log-Trace Correlation
Every log entry automatically includes a `trace_id` and `span_id`. In Grafana, you can jump from a log error directly to the corresponding trace in Tempo to debug the root cause.

---

## 🧪 Development & TDD

Each service follows a **DDD** structure and strict **TDD** mandates.

*   **Validation:** Every service must pass its own quality gates:
    ```bash
    uv run ruff check .
    uv run mypy .
    uv run pytest
    ```
*   **Observability:** Integrated with **OpenTelemetry** for cross-service tracing and **Structlog** for structured JSON logging.

---

## 🏦 Data & Events

### Kafka Topics
*   `webhook-events`: Raw events from the Ingestion Service.
*   `analysis-results`: Structured reports from the Analysis Worker.

### Storage
*   **PostgreSQL + pgvector:** Stores structured metadata and high-dimensional code embeddings in the same instance for simplicity and performance.
