#!/usr/bin/env bash
set -euo pipefail

artifact_name=debian-apt-snapshot
timestamp_pattern='^[0-9]{8}T[0-9]{6}Z$'

latest() {
    local requested archive_url security_url
    requested=$(date -u +%Y%m%dT%H%M%SZ)
    archive_url=$(canonical_url debian "$requested")
    security_url=$(canonical_url debian-security "$requested")
    emit "${archive_url#https://snapshot.debian.org/archive/debian/}" \
        "${security_url#https://snapshot.debian.org/archive/debian-security/}"
}

canonical_url() {
    curl --fail --silent --show-error --location --max-redirs 2 \
        --proto '=https' --proto-redir '=https' --connect-timeout 5 --max-time 20 --retry 2 \
        --output /dev/null --write-out '%{url_effective}' "https://snapshot.debian.org/archive/$1/$2/"
}

emit() {
    local archive=${1%/} security=${2%/}
    [[ "$archive" =~ $timestamp_pattern && "$security" =~ $timestamp_pattern ]] || return 1
    printf 'archive=%s\nsecurity=%s\n' "$archive" "$security" >> "$GITHUB_OUTPUT"
    printf 'Debian snapshots: %s and %s (security)\n' "$archive" "$security"
}

record() {
    local tree
    tree=$(git rev-parse 'HEAD^{tree}')
    [[ "$1" =~ $timestamp_pattern && "$2" =~ $timestamp_pattern ]] || return 1
    jq -n --arg tree "$tree" --arg archive "$1" --arg security "$2" \
        '{tree: $tree, archive: $archive, security: $security}' > "$3"
}

for_release() {
    local job_name=$1
    local revision tree source head repository runs run jobs artifact http_file receipt
    revision=$(git rev-parse HEAD)
    tree=$(git rev-parse 'HEAD^{tree}')
    source=$(gh api "repos/$GITHUB_REPOSITORY/commits/$revision/pulls?per_page=100" |
        jq -cr --arg commit "$revision" --arg repo "$GITHUB_REPOSITORY_ID" '
          [.[] | select(.merged_at and .base.ref == "main" and .merge_commit_sha == $commit
                        and (.base.repo.id | tostring) == $repo and .head.repo.id)
           | {sha: .head.sha, repository: .head.repo.id}]
          | unique | if length > 1 then error("Ambiguous merged pull request") else .[0] // empty end')
    if [[ -n "$source" ]]; then
        head=$(jq -r .sha <<< "$source")
        repository=$(jq -r .repository <<< "$source")
        [[ "$head" =~ ^[0-9a-f]{40}$ && "$repository" =~ ^[0-9]+$ ]] || return 1
        runs=$(gh api "repos/$GITHUB_REPOSITORY/actions/workflows/ci.yml/runs?event=pull_request&status=success&head_sha=$head&per_page=50" |
            jq -r --arg head "$head" --arg repo "$repository" '
              .workflow_runs[] | select(.event == "pull_request" and .head_sha == $head
                and .conclusion == "success" and (.head_repository.id | tostring) == $repo) | .id')
        while IFS= read -r run; do
            [[ "$run" =~ ^[0-9]+$ ]] || continue
            jobs=$(gh api "repos/$GITHUB_REPOSITORY/actions/runs/$run/jobs?filter=all&per_page=100")
            if ! jq -e --arg job "$job_name" 'any(.jobs[]; .name == $job and .conclusion == "success")' <<< "$jobs" > /dev/null; then
                continue
            fi
            artifact=$(gh api "repos/$GITHUB_REPOSITORY/actions/runs/$run/artifacts?name=$artifact_name" |
                jq -er --arg name "$artifact_name" '
                  [.artifacts[] | select(.name == $name and .expired == false and .size_in_bytes <= 4096)]
                  | if length == 1 then .[0].id else "" end')
            [[ "$artifact" =~ ^[0-9]+$ ]] || continue
            http_file=$(mktemp)
            # Read one bounded JSON member without extracting the PR archive.
            if ! gh api "repos/$GITHUB_REPOSITORY/actions/artifacts/$artifact/zip" > "$http_file"; then
                rm -f "$http_file"
                return 1
            fi
            if receipt=$(unzip -p "$http_file" snapshot.json | head -c 2048 |
                jq -scr --arg tree "$tree" --arg pattern "$timestamp_pattern" '
                  select(length == 1) | .[0]
                  | select(.tree == $tree and (.archive | strings | test($pattern)) and (.security | strings | test($pattern)))'); then
                rm -f "$http_file"
                [[ -n "$receipt" ]] || continue
                printf 'Reusing the APT snapshots from successful CI run %s.\n' "$run"
                emit "$(jq -r .archive <<< "$receipt")" "$(jq -r .security <<< "$receipt")"
                return
            fi
            rm -f "$http_file"
        done <<< "$runs"
    fi

    printf '%s\n' 'No matching CI receipt. Resolve a fresh snapshot and validate the release image before tagging.'
    latest
}

case "$1" in
    latest) latest ;;
    record) shift; record "$@" ;;
    for-release) for_release "$2" ;;
    *) exit 2 ;;
esac
