#!/usr/bin/env bash
# FinAlly — start the production container (macOS / Linux).
#
# Usage:
#   ./scripts/start_mac.sh           # start (build only if image missing)
#   ./scripts/start_mac.sh --build   # force a rebuild before starting
#   ./scripts/start_mac.sh --open    # also open the browser
#
# Idempotent: safe to run multiple times. If the container is already
# running, prints its URL and exits.

set -euo pipefail

IMAGE_NAME="finally:latest"
CONTAINER_NAME="finally-app"
VOLUME_NAME="finally-data"
HOST_PORT="${FINALLY_HOST_PORT:-8000}"

# Resolve project root (one level up from this script, regardless of cwd).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

FORCE_BUILD=false
OPEN_BROWSER=false
for arg in "$@"; do
    case "${arg}" in
        --build) FORCE_BUILD=true ;;
        --open)  OPEN_BROWSER=true ;;
        -h|--help)
            sed -n '2,11p' "$0"
            exit 0
            ;;
        *)
            echo "Unknown argument: ${arg}" >&2
            exit 2
            ;;
    esac
done

if ! command -v docker >/dev/null 2>&1; then
    echo "Error: docker is not installed or not on PATH." >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "Error: Docker daemon is not running. Start Docker Desktop and retry." >&2
    exit 1
fi

# Ensure .env exists; copy from .env.example if missing so the run flag works.
if [[ ! -f .env ]]; then
    if [[ -f .env.example ]]; then
        echo "No .env found — creating one from .env.example."
        cp .env.example .env
    else
        echo "Warning: no .env or .env.example present; container will run without env file." >&2
    fi
fi

# Build the image if missing or if --build was passed.
if ${FORCE_BUILD} || ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
    echo "Building image ${IMAGE_NAME}..."
    docker build -t "${IMAGE_NAME}" .
fi

# Ensure the volume exists (docker run -v creates it lazily, but being explicit
# lets us print friendly messages and reason about state).
if ! docker volume inspect "${VOLUME_NAME}" >/dev/null 2>&1; then
    echo "Creating volume ${VOLUME_NAME}..."
    docker volume create "${VOLUME_NAME}" >/dev/null
fi

URL="http://localhost:${HOST_PORT}"

# Build the --env-file argument list once. Safe under `set -u` because we only
# expand the array via the `${arr[@]+...}` guard below.
ENV_FILE_FLAG=()
if [[ -f .env ]]; then
    ENV_FILE_FLAG=(--env-file .env)
fi

# If a container with our name already exists, handle it gracefully.
if docker ps -a --format '{{.Names}}' | grep -Fxq "${CONTAINER_NAME}"; then
    if docker ps --format '{{.Names}}' | grep -Fxq "${CONTAINER_NAME}"; then
        echo "FinAlly is already running at ${URL}"
    else
        echo "Removing stopped container ${CONTAINER_NAME}..."
        docker rm "${CONTAINER_NAME}" >/dev/null
        echo "Starting FinAlly..."
        docker run -d \
            --name "${CONTAINER_NAME}" \
            ${ENV_FILE_FLAG[@]+"${ENV_FILE_FLAG[@]}"} \
            -p "${HOST_PORT}:8000" \
            -v "${VOLUME_NAME}:/app/data" \
            --restart unless-stopped \
            "${IMAGE_NAME}" >/dev/null
        echo "FinAlly is starting at ${URL}"
    fi
else
    echo "Starting FinAlly..."
    docker run -d \
        --name "${CONTAINER_NAME}" \
        ${ENV_FILE_FLAG[@]+"${ENV_FILE_FLAG[@]}"} \
        -p "${HOST_PORT}:8000" \
        -v "${VOLUME_NAME}:/app/data" \
        --restart unless-stopped \
        "${IMAGE_NAME}" >/dev/null
    echo "FinAlly is starting at ${URL}"
fi

if ${OPEN_BROWSER}; then
    if command -v open >/dev/null 2>&1; then
        open "${URL}"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "${URL}" >/dev/null 2>&1 || true
    fi
fi

echo "Tail logs with: docker logs -f ${CONTAINER_NAME}"
echo "Stop with:      ./scripts/stop_mac.sh"
