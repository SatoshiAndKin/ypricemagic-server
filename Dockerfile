FROM rust:1.98.1-slim-bookworm AS rust-toolchain

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc git libc6-dev libgmp-dev curl \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PRERELEASE=allow
ENV CARGO_HOME=/usr/local/cargo
ENV RUSTUP_HOME=/usr/local/rustup
ENV PATH="/usr/local/cargo/bin:$PATH"
COPY --from=rust-toolchain /usr/local/cargo /usr/local/cargo
COPY --from=rust-toolchain /usr/local/rustup /usr/local/rustup

COPY pyproject.toml uv.lock ./

# Install dependencies first (cached layer)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=cache,target=/usr/local/cargo/registry \
    uv sync --locked --no-install-project

# Copy the project and sync
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=cache,target=/usr/local/cargo/registry \
    uv sync --locked

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libgmp10 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /app /app

RUN mkdir -p /data/cache /app/cache

# Persist caches across standalone docker-run invocations (compiler downloads,
# brownie artifacts, ypricemagic data, and price cache).  docker-compose mounts
# named volumes over these same paths, so the directive is a no-op there.
VOLUME ["/root/.brownie", "/root/.solcx", "/root/.vvm", "/root/.ypricemagic", "/data/cache", "/app/cache"]

ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8001

ENTRYPOINT ["./setup-networks.sh"]
