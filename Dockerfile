# syntax=docker/dockerfile:1

# Builder Image
FROM python:3.12-alpine AS builder

ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install dependencies
RUN --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-editable

# Install project
COPY src src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

# Distribution Image
FROM python:3.12-alpine

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apk add --no-cache ca-certificates

COPY --from=builder /app/.venv /app/.venv

EXPOSE 8000

CMD ["***tracker", "serve", "--host", "0.0.0.0", "--port", "8000"]
