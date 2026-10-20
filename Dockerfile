FROM ghcr.io/astral-sh/uv:0.13.4@sha256:9f130421e930bfbdc563c00740466603f8723158e90297d07957c2294640262b AS uv

FROM rust:1.98.1-slim-bookworm AS rust-toolchain

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build

COPY --from=uv /uv /uvx /usr/local/bin/
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
COPY --from=uv /uv /uvx /usr/local/bin/
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libgmp10 ca-certificates \
    && sed -i -e 's|^mozilla/emSign_ECC_Root_CA_-_G3.crt|!&|' \
       -e 's|^mozilla/Comodo_AAA_Services_root.crt|!&|' /etc/ca-certificates.conf \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# Keep compiled dependencies reusable when only application code changes.
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/src /app/src
COPY --from=build /app/setup-networks.sh /app/setup-networks.sh

RUN mkdir -p /data/cache /app/cache

# Persist caches across standalone docker-run invocations (compiler downloads,
# brownie artifacts, ypricemagic data, and price cache).  docker-compose mounts
# named volumes over these same paths, so the directive is a no-op there.
VOLUME ["/root/.brownie", "/root/.solcx", "/root/.vvm", "/root/.ypricemagic", "/data/cache", "/app/cache"]

ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8001

ENTRYPOINT ["./setup-networks.sh"]
