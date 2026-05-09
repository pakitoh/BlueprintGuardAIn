# Project Instructions: BlueprintGuardAIn (Python DDD Service)

This project follows Domain-Driven Design (DDD), strict Test-Driven Development (TDD), and prioritizes observability and API-first development with OpenAPI.

## Tech Stack & Conventions
- **Language:** Python 3.12+ with strict type hinting.
- **Framework:** FastAPI for the web layer.
- **Dependency Management:** `uv` (for Python versioning, deps, and environments).
- **Linting/Formatting:** `Ruff` for both linting and formatting.

## Architectural Rules (Domain-Driven Design)
- **Layered Architecture:** 
  - `domain/`: Pure business logic, entities, value objects, and repository interfaces. No external dependencies.
  - `application/`: Use cases, orchestrating domain objects and ports.
  - `infrastructure/`: Implementations of repositories, external API clients, and database configurations.
  - `interface/`: API routes (FastAPI), CLI commands, and entry points.
- **Encapsulation:** Dependencies must point inwards. Infrastructure depends on Application/Domain, never the reverse.

## Development Workflow (TDD & API-First)
- **TDD:** No production code should be written without a failing test first.
  - Use `pytest` and `pytest-mock`.
  - Aim for high branch coverage in the `domain` and `application` layers.
- **API-First:** The OpenAPI specification (`openapi.yaml` or generated via FastAPI) is the source of truth for the contract.
  - Validate request/response models against the schema.

## Observability
- **Logging:** Use structured logging (JSON format) with `structlog`.
- **Tracing:** Instrument all entry points and external calls with OpenTelemetry.
- **Metrics:** Export Prometheus-compatible metrics for request latency, error rates, and domain-specific events.
- **Context:** Every log and trace must include a `correlation_id` passed through headers.

## Validation Mandates
- Before completing any task, ensure:
  1. `uv run ruff check .` passes.
  2. `uv run mypy .` passes.
  3. `uv run pytest` passes.
