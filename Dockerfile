# syntax=docker/dockerfile:1

# Builder Image
FROM python:3.12-slim AS builder

ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-editable

# Install project
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

# Distribution Image
FROM python:3.12-slim

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv /app/.venv

EXPOSE 8000

CMD ["untrakkd", "serve", "--host", "0.0.0.0", "--port", "8000"]
