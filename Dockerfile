FROM playcourt/jenkins:python-3.11.0 AS builder

USER root

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apk add --no-cache wget curl git build-base python3-dev \
    libffi-dev \
    build-base \
    sqlite \
    sqlite-dev

ENV UV_COMPILE_BYTECODE=true \
    UV_SYSTEM_PYTHON=true \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock ./

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --compile-bytecode --no-install-project

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --compile-bytecode && \
    uv pip uninstall setuptools wheel pip --system

FROM playcourt/jenkins:python-3.11.0

USER root

RUN apk update && apk upgrade \
    && rm -rf /var/cache/apk/*

# Install a shell
RUN apk add --no-cache bash

WORKDIR /app
COPY lib ./lib
COPY *.py ./
COPY entrypoints.sh ./

RUN chmod +x /app/entrypoints.sh
RUN mkdir -p /app/log /app/data \
    && addgroup -S user \
    && adduser -S user -G user \
    && chown -R user:user /app /app/log /app/data \
    && chmod -R 777 /app/log /app/data \
    && pip uninstall -y setuptools wheel pip

# Copy the environment, but not the source code
COPY --from=minio/mc --chown=user:user /usr/bin/mc /usr/bin/mc
COPY --from=builder --chown=user:user /app/.venv /app/.venv

USER user

ENTRYPOINT ["/bin/bash", "/app/entrypoints.sh"]
