FROM --platform=linux/amd64 ghcr.io/astral-sh/uv:python3.12-trixie-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc git libc6-dev curl \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PRERELEASE=allow

COPY pyproject.toml uv.lock ./

# Install dependencies first (cached layer)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project

# Copy the project and sync
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

RUN mkdir -p /data/cache

ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8001

ENTRYPOINT ["./setup-networks.sh"]
