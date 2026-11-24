FROM ghcr.io/astral-sh/uv:0.13.9@sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d AS uv

FROM rust:1.100.0-slim-bookworm AS rust-toolchain

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58 AS build

COPY --from=uv /uv /uvx /usr/local/bin/
WORKDIR /app

ARG DEBIAN_ARCHIVE_SNAPSHOT
ARG DEBIAN_SECURITY_SNAPSHOT

COPY scripts/debian.sources /tmp/debian-snapshot.sources
RUN if [ -n "${DEBIAN_ARCHIVE_SNAPSHOT}${DEBIAN_SECURITY_SNAPSHOT}" ]; then \
        test -n "$DEBIAN_ARCHIVE_SNAPSHOT" && test -n "$DEBIAN_SECURITY_SNAPSHOT" \
        && sed -e "s/@ARCHIVE@/$DEBIAN_ARCHIVE_SNAPSHOT/g" -e "s/@SECURITY@/$DEBIAN_SECURITY_SNAPSHOT/g" \
            /tmp/debian-snapshot.sources > /etc/apt/sources.list.d/debian.sources; \
    fi \
    && rm /tmp/debian-snapshot.sources \
    && apt-get update --error-on=any \
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

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58
COPY --from=uv /uv /uvx /usr/local/bin/
WORKDIR /app
ARG DEBIAN_ARCHIVE_SNAPSHOT
ARG DEBIAN_SECURITY_SNAPSHOT

COPY scripts/debian.sources /tmp/debian-snapshot.sources
RUN if [ -n "${DEBIAN_ARCHIVE_SNAPSHOT}${DEBIAN_SECURITY_SNAPSHOT}" ]; then \
        test -n "$DEBIAN_ARCHIVE_SNAPSHOT" && test -n "$DEBIAN_SECURITY_SNAPSHOT" \
        && sed -e "s/@ARCHIVE@/$DEBIAN_ARCHIVE_SNAPSHOT/g" -e "s/@SECURITY@/$DEBIAN_SECURITY_SNAPSHOT/g" \
            /tmp/debian-snapshot.sources > /etc/apt/sources.list.d/debian.sources; \
    fi \
    && rm /tmp/debian-snapshot.sources \
    && apt-get update --error-on=any \
    && apt-get install -y --no-install-recommends curl libgmp10 ca-certificates \
    && sed -i -e 's|^mozilla/emSign_ECC_Root_CA_-_G3.crt|!&|' \
       -e 's|^mozilla/Comodo_AAA_Services_root.crt|!&|' /etc/ca-certificates.conf \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# Keep compiled dependencies reusable when only application code changes.
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/src /app/src
COPY --from=build /app/setup-networks.sh /app/setup-networks.sh
COPY --from=build /app/pyproject.toml /app/pyproject.toml

RUN mkdir -p /data/cache /app/cache

# Persist caches across standalone docker-run invocations (compiler downloads,
# brownie artifacts, ypricemagic data, and price cache).  docker-compose mounts
# named volumes over these same paths, so the directive is a no-op there.
VOLUME ["/root/.brownie", "/root/.solcx", "/root/.vvm", "/root/.ypricemagic", "/data/cache", "/app/cache"]

ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

# Check the release schema in the final image without starting the RPC client.
RUN --network=none python -c '\
import tomllib; from pathlib import Path; from src.server import app; \
expected = tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]; \
actual = app.openapi()["info"]["version"]; assert actual == expected, (actual, expected)'

ARG SENTRY_RELEASE=""
ENV SENTRY_RELEASE=${SENTRY_RELEASE}

EXPOSE 8001

ENTRYPOINT ["./setup-networks.sh"]
