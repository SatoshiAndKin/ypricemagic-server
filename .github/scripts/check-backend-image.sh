#!/usr/bin/env bash
set -euo pipefail

image=$1
revision=$2

test "$(docker image inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$image")" = "$revision"
docker run --rm --network none --entrypoint sh "$image" -c 'test ! -e /app/.git'
docker run --rm --network none --entrypoint python "$image" -c 'import brownie, dank_mids, cachebox'
docker run --rm --network none --env SENTRY_DSN=https://public@example.invalid/1 \
    --env "EXPECTED_RELEASE=$revision" --entrypoint python "$image" \
    -c 'import os, sentry_sdk; from src.server import _init_sentry; _init_sentry(); assert sentry_sdk.get_client().options["release"] == os.environ["EXPECTED_RELEASE"]'
docker run --rm --network none --entrypoint python "$image" -m unittest src.tests.test_sentry_transport
