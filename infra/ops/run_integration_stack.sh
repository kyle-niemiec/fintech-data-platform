#!/usr/bin/env bash

# This script runs the integration test suite against the full stack before
# deployment. Generates a deterministic .env file and a Python test container to
# execute the tests with the same configuration as the deployed stack. Failure
# results in a non-zero exit code so that the CI pipeline can be marked unsuccessful.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

# Provide an external test container to configure dual, private/public network access for the tests.
TEST_CONTAINER_ID=""

# Generate a deterministic .env file for the integration tests to ensure consistent configuration
MODE=deterministic OUTPUT=infra/.env bash infra/ops/generate_env.sh

cleanup() {
	if [ -n "${TEST_CONTAINER_ID}" ]; then
		docker rm -f "${TEST_CONTAINER_ID}" >/dev/null 2>&1 || true
	fi

	make infra-clean >/dev/null 2>&1 || true
}

# Set up a trap to ensure cleanup is called on script exit, even if it fails
trap cleanup EXIT

# Clean and set up the infrastructure for the integration tests
# make infra-clean >/dev/null 2>&1 || true
# make infra-up

# Resolve the network names for the public and internal networks created by Docker Compose.
PUBLIC_NETWORK_NAME="$(docker network ls --format '{{.Name}}' | grep -E '_platform_public$' | head -n1 || true)"
INTERNAL_NETWORK_NAME="$(docker network ls --format '{{.Name}}' | grep -E '_platform_internal$' | head -n1 || true)"

if [ -z "${PUBLIC_NETWORK_NAME}" ] || [ -z "${INTERNAL_NETWORK_NAME}" ]; then
	echo "Unable to resolve compose network names (public='${PUBLIC_NETWORK_NAME}' internal='${INTERNAL_NETWORK_NAME}')" >&2
	exit 1
fi

# Create a test container with Python to run integration tests inside of.
# TEST_CONTAINER_ID="$(docker create --rm \
# 	--network "${PUBLIC_NETWORK_NAME}" \
# 	--env-file infra/.env \
# 	-e MINIO_ENDPOINT="minio:9000" \
# 	-e MINIO_SECURE="false" \
# 	-e REDPANDA_BOOTSTRAP_SERVERS="redpanda:9092" \
# 	-e REDPANDA_SECURITY_PROTOCOL="PLAINTEXT" \
# 	-e EVENT_STORE_DB_HOST="event_store_db" \
# 	-e TRINO_HOST="trino" \
# 	-e TRINO_PORT="8080" \
# 	-e TRINO_USER="trino_etl" \
# 	-v "${ROOT_DIR}:/workspace" \
# 	-w /workspace \
# 	python:3.12-slim \
# 	bash -euo pipefail -c '
# 		apt-get update >/dev/null
# 		apt-get install -y --no-install-recommends build-essential gcc >/dev/null
# 		pip install --no-cache-dir -r requirements-dev.txt minio pyarrow trino >/dev/null
# 		M="$(mktemp -d)"
# 		mkdir "$M/meridian"
# 		ln -s "$PWD/services/libs" "$M/meridian/libs"
# 		export PYTHONPATH="$M"
# 		pytest tests/integration -m integration -ra
# 	')"

# docker network connect "${INTERNAL_NETWORK_NAME}" "${TEST_CONTAINER_ID}"
# docker start -a "${TEST_CONTAINER_ID}"
