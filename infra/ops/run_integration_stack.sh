#!/usr/bin/env bash

# This script is the primary entry point for running the integration test suite
# against the full stack. It is intended to be run from the root of the repository
# and will handle bringing up the necessary infrastructure, running the tests, and
# tearing down the infrastructure when complete.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

# Generate a deterministic .env file for the integration tests to ensure consistent configuration
MODE=deterministic OUTPUT=infra/.env bash infra/ops/generate_env.sh

cleanup() {
	make infra-clean >/dev/null 2>&1 || true
}

# Set up a trap to ensure cleanup is called on script exit, even if it fails
trap cleanup EXIT

make infra-clean >/dev/null 2>&1 || true
make infra-up

NETWORK_NAME="$(docker network ls --format '{{.Name}}' | grep -E '_platform_internal$' | head -n1)"
if [ -z "${NETWORK_NAME}" ]; then
	echo "Unable to resolve compose internal network name" >&2
	exit 1
fi

docker run --rm \
	--network "${NETWORK_NAME}" \
	--env-file infra/.env \
	-e MINIO_ENDPOINT="minio:9000" \
	-e MINIO_SECURE="false" \
	-e REDPANDA_BOOTSTRAP_SERVERS="redpanda:9092" \
	-e REDPANDA_SECURITY_PROTOCOL="PLAINTEXT" \
	-e EVENT_STORE_DB_HOST="event_store_db" \
	-e TRINO_HOST="trino" \
	-e TRINO_PORT="8080" \
	-e TRINO_USER="trino_etl" \
	-v "${ROOT_DIR}:/workspace" \
	-w /workspace \
	python:3.12-slim \
	bash -euo pipefail -c '
		apt-get update >/dev/null
		apt-get install -y --no-install-recommends build-essential gcc >/dev/null
		pip install --no-cache-dir -r requirements-dev.txt minio pyarrow trino >/dev/null
		M="$(mktemp -d)"
		mkdir "$M/meridian"
		ln -s "$PWD/services/libs" "$M/meridian/libs"
		export PYTHONPATH="$M"
		pytest tests/integration -m integration -ra
	'
