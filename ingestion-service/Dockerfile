FROM python:3.12-slim AS base

# This is to allow the container to print unicode characters
ENV LC_ALL='C.UTF-8' \
  PYTHONIOENCODING='utf-8'

# Set the user and working directory
ENV APP_PATH="/app"
ENV USER="app"
WORKDIR ${APP_PATH}
RUN addgroup --system --gid 1000 ${USER} && \
  adduser --system --uid 1000 --shell /bin/bash --home "/home/${USER}" ${USER} && \
  chown ${USER}:${USER} ${APP_PATH} 

# Pip configuration
ENV PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=100 
# UV configuration
ENV UV_UNMANAGED_INSTALL="/bin/" \
  UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy

# Install system dependencies
ENV RUNTIME_DEPENDENCIES="curl ca-certificates libpq-dev libcairo2-dev libgirepository1.0-dev libpango-1.0-0 libpangoft2-1.0-0"
RUN apt-get update && \
  apt-get install -y --no-install-recommends ${RUNTIME_DEPENDENCIES} && \
  apt-get clean

# Install UV
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh

## Stage: app dependencies
FROM base AS deps

# Install build dependencies
ENV BUILD_DEPENDENCIES=""
RUN apt-get update && \
  if [ -n "${BUILD_DEPENDENCIES}" ]; then \
  apt-get install -y --no-install-recommends ${BUILD_DEPENDENCIES}; \
  fi
# Install python requirements
RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  uv sync --frozen --no-install-project --no-dev

## Stage: dev dependencies
FROM deps AS dev-deps

#ENV PYRIGHT_PYTHON_NODE_VERSION=system \
#  PYRIGHT_PYTHON_IGNORE_WARNINGS=true
# Install test build dependencies
ENV DEV_BUILD_DEPENDENCIES="build-essential python3-dev"
RUN apt-get update && \
  if [ -n "${DEV_BUILD_DEPENDENCIES}" ]; then \
  apt-get install -y --no-install-recommends ${DEV_BUILD_DEPENDENCIES}; \
  fi
# Install python test requirements
RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  uv sync --frozen --no-install-project --dev

## Stage: app
FROM base AS app

COPY --from=deps --chown="${USER}:${USER}" ${APP_PATH}/.venv ${APP_PATH}/.venv

# Copy application
RUN mkdir -p src logs && chown "${USER}:${USER}" src logs
COPY uv.lock pyproject.toml .env  ${APP_PATH}/
COPY src ${APP_PATH}/src

USER ${USER}

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=5 CMD [ "uv", "run", "python", ".", "health" ]
ENTRYPOINT ["uv", "run", "python", "."]
CMD ["run"]

## Stage: dev
FROM base AS dev

# Install system dependencies
ENV DEV_RUNTIME_DEPENDENCIES="nodejs npm"
RUN apt-get update && \
  apt-get install -y --no-install-recommends ${DEV_RUNTIME_DEPENDENCIES} && \
  apt-get clean && \
  rm -rf ${TMP_PATHS}

COPY --from=app --chown="${USER}:${USER}" ${APP_PATH} ${APP_PATH}
COPY --from=dev-deps --chown="${USER}:${USER}" ${APP_PATH}/.venv ${APP_PATH}/.venv

#RUN uv run pyright --version

# Copy tests
RUN mkdir -p tests && chown app:app tests
COPY tests ${APP_PATH}/tests

USER ${USER}

ENTRYPOINT ["uv", "run", "python", "-m", "src.main"]
CMD ["run"]
