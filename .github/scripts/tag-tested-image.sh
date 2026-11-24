#!/usr/bin/env bash
set -euo pipefail

image=$1
digest=$2
[[ "$digest" =~ ^sha256:[a-f0-9]{64}$ && -n "$IMAGE_TAGS" ]] || exit 1
tags=()
while IFS= read -r tag; do
    [[ "$tag" == "$image":* ]] || exit 1
    tags+=("$tag")
done <<< "$IMAGE_TAGS"

options=()
for tag in "${tags[@]}"; do
    options+=(--tag "$tag")
done
docker buildx imagetools create --prefer-index=false "${options[@]}" "$image@$digest"
for tag in "${tags[@]}"; do
    actual=$(docker buildx imagetools inspect "$tag" | awk '/^Digest:/ {print $2}')
    test "$actual" = "$digest" || exit 1
done
