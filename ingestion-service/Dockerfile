FROM python:3.12-slim AS base

ENV LC_ALL='C.UTF-8' \
  PYTHONIOENCODING='utf-8'

ENV APP_PATH="/app"
ENV USER="app"
WORKDIR ${APP_PATH}
RUN addgroup --system --gid 1000 ${USER} && \
  adduser --system --uid 1000 --shell /bin/bash --home "/home/${USER}" ${USER} && \
  chown ${USER}:${USER} ${APP_PATH}

ENV PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=100
ENV UV_UNMANAGED_INSTALL="/bin/" \
  UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy

ENV RUNTIME_DEPENDENCIES="curl ca-certificates"
RUN apt-get update && \
  apt-get install -y --no-install-recommends ${RUNTIME_DEPENDENCIES} && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh

## Stage: app dependencies
FROM base AS deps

ENV BUILD_DEPENDENCIES=""
RUN apt-get update && \
  if [ -n "${BUILD_DEPENDENCIES}" ]; then \
  apt-get install -y --no-install-recommends ${BUILD_DEPENDENCIES}; \
  fi
RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=ingestion-service/uv.lock,target=uv.lock \
  --mount=type=bind,source=ingestion-service/pyproject.toml,target=pyproject.toml \
  uv sync --frozen --no-install-project --no-dev

## Stage: dev dependencies
FROM deps AS dev-deps

ENV DEV_BUILD_DEPENDENCIES="build-essential python3-dev"
RUN apt-get update && \
  if [ -n "${DEV_BUILD_DEPENDENCIES}" ]; then \
  apt-get install -y --no-install-recommends ${DEV_BUILD_DEPENDENCIES}; \
  fi
RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=ingestion-service/uv.lock,target=uv.lock \
  --mount=type=bind,source=ingestion-service/pyproject.toml,target=pyproject.toml \
  uv sync --frozen --no-install-project --dev

## Stage: app
FROM base AS app

COPY --from=deps --chown="${USER}:${USER}" ${APP_PATH}/.venv ${APP_PATH}/.venv

RUN mkdir -p src logs && chown "${USER}:${USER}" src logs
COPY ingestion-service/uv.lock ingestion-service/pyproject.toml ${APP_PATH}/
COPY ingestion-service/src ${APP_PATH}/src
COPY schemas /schemas

USER ${USER}

HEALTHCHECK --interval=60s --timeout=5s --start-period=5s --retries=5 \
  CMD curl -f http://localhost:8000/ready || exit 1
ENTRYPOINT ["uv", "run", "python", "-m", "src.main"]

## Stage: dev
FROM base AS dev

COPY --from=app --chown="${USER}:${USER}" ${APP_PATH} ${APP_PATH}
COPY --from=dev-deps --chown="${USER}:${USER}" ${APP_PATH}/.venv ${APP_PATH}/.venv

RUN mkdir -p tests && chown app:app tests
COPY ingestion-service/tests ${APP_PATH}/tests

USER ${USER}

ENTRYPOINT ["uv", "run", "python", "-m", "src.main"]
