#!/usr/bin/env bash
# FinAlly — stop the production container (macOS / Linux).
#
# Stops and removes the running container. The named volume `finally-data`
# is intentionally preserved so portfolio state survives restarts.

set -euo pipefail

CONTAINER_NAME="finally-app"

if ! command -v docker >/dev/null 2>&1; then
    echo "Error: docker is not installed or not on PATH." >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "Error: Docker daemon is not running." >&2
    exit 1
fi

if ! docker ps -a --format '{{.Names}}' | grep -Fxq "${CONTAINER_NAME}"; then
    echo "FinAlly is not running. Nothing to stop."
    exit 0
fi

if docker ps --format '{{.Names}}' | grep -Fxq "${CONTAINER_NAME}"; then
    echo "Stopping ${CONTAINER_NAME}..."
    docker stop "${CONTAINER_NAME}" >/dev/null
fi

echo "Removing ${CONTAINER_NAME}..."
docker rm "${CONTAINER_NAME}" >/dev/null

echo "FinAlly stopped. (Volume 'finally-data' preserved — your portfolio is safe.)"
