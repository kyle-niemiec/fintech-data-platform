#!/usr/bin/env bash

# This script is utilized by the primary release deployment script to generate
# a .env file with appropriate values for deploying a release build to EC2. It
# can also be used independently to generate .env files for other purposes, such
# as local development or CI.
#
# Usage:
#   TEMPLATE=<path> OUTPUT=<path> MODE=<deterministic|random> \
#   UI_ORIGIN=<url> UI_API_URL=<url> RELEASE_TAG=<tag> \
#   bash infra/ops/generate_env.sh

set -euo pipefail

TEMPLATE="${TEMPLATE:-infra/.env.example}"
OUTPUT="${OUTPUT:-infra/.env}"
MODE="${MODE:-deterministic}"
UI_ORIGIN="${UI_ORIGIN:-}"
UI_API_URL="${UI_API_URL:-}"
RELEASE_TAG="${RELEASE_TAG:-}"

if [ ! -f "$TEMPLATE" ]; then
	printf 'Template not found: %s\n' "$TEMPLATE" >&2
	exit 1
fi

KES_API_KEY=""
KES_IDENTITY=""

# If deterministic mode is selected, use fixed values for KES API key and identity.
if [ "$MODE" = "deterministic" ]; then
	KES_API_KEY="kes:v1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
	KES_IDENTITY="339e2ff917630507b6a423b5ce084e285d1fa65d93b3e27a6195d3bbebc9ae23"
# Else, in random mode, generate a new KES identity using the MinIO KES Docker image.
else
	KES_OUTPUT="$(docker run --rm minio/kes:latest identity new)"
	KES_API_KEY="$(printf '%s\n' "$KES_OUTPUT" | sed -n 's/^[[:space:]]*\(kes:v1:[^[:space:]]*\)$/\1/p' | head -n1)"
	KES_IDENTITY="$(printf '%s\n' "$KES_OUTPUT" | sed -n 's/^[[:space:]]*\([0-9a-f]\{64\}\)$/\1/p' | head -n1)"
fi

if [ -z "$KES_API_KEY" ] || [ -z "$KES_IDENTITY" ]; then
	printf 'Unable to parse KES identity output\n' >&2
	exit 1
fi

python3 "$(dirname "${BASH_SOURCE[0]}")/generate_env/index.py" \
  "$TEMPLATE" \
  "$OUTPUT" \
  "$MODE" \
	"$UI_ORIGIN" \
	"$UI_API_URL" \
	"$RELEASE_TAG" \
	"$KES_API_KEY" \
	"$KES_IDENTITY"

printf 'Wrote %s using %s mode\n' "$OUTPUT" "$MODE"
