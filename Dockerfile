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

# Download Uniswap default tokenlist (not in repo due to Droid-Shield false positives on addresses)
# Validate JSON structure: must have a 'tokens' array
RUN mkdir -p /app/static/tokenlists && \
    curl -sf https://tokens.uniswap.org -o /app/static/tokenlists/uniswap-default.json && \
    python3 -c "import json; d=json.load(open('/app/static/tokenlists/uniswap-default.json')); \
    assert 'tokens' in d, 'Missing tokens array'; \
    assert isinstance(d['tokens'], list), 'tokens must be an array'; \
    print(f'Valid tokenlist: {len(d[\"tokens\"])} tokens')"

RUN mkdir -p /data/cache

ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8001

ENTRYPOINT ["./setup-networks.sh"]
