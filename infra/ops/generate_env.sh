#!/usr/bin/env bash

# This script is utilized by the primary release deployment script to generate
# a .env file with appropriate values for deploying a release build to EC2. It
# can also be used independently to generate .env files for other purposes, such
# as local development or CI.

set -euo pipefail

TEMPLATE="infra/.env.example"
OUTPUT="infra/.env"
MODE="deterministic"
UI_ORIGIN=""
UI_API_URL=""
RELEASE_TAG=""

usage() {
  cat <<'EOF'
Usage: generate_env.sh [options]

Options:
  --template <path>      Source template file (default: infra/.env.example)
  --output <path>        Output env file (default: infra/.env)
  --mode <mode>          deterministic|random (default: deterministic)
  --ui-origin <url>      Override UI_ORIGIN
  --ui-api-url <url>     Override UI_API_URL
  --release-tag <tag>    Override VITE_RELEASE_TAG
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --template)
      TEMPLATE="${2:?missing value for --template}"
      shift 2
      ;;
    --output)
      OUTPUT="${2:?missing value for --output}"
      shift 2
      ;;
    --mode)
      MODE="${2:?missing value for --mode}"
      shift 2
      ;;
    --ui-origin)
      UI_ORIGIN="${2:?missing value for --ui-origin}"
      shift 2
      ;;
    --ui-api-url)
      UI_API_URL="${2:?missing value for --ui-api-url}"
      shift 2
      ;;
    --release-tag)
      RELEASE_TAG="${2:?missing value for --release-tag}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ "$MODE" != "deterministic" ] && [ "$MODE" != "random" ]; then
  printf 'Unsupported mode: %s\n' "$MODE" >&2
  exit 2
fi

if [ ! -f "$TEMPLATE" ]; then
  printf 'Template not found: %s\n' "$TEMPLATE" >&2
  exit 1
fi

KES_API_KEY=""
KES_IDENTITY=""
if [ "$MODE" = "deterministic" ]; then
  KES_API_KEY="kes:v1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
  if command -v docker >/dev/null 2>&1; then
    KES_IDENTITY="$(docker run --rm minio/kes:latest identity of "$KES_API_KEY" | tr -d '\r')"
  else
    KES_IDENTITY="339e2ff917630507b6a423b5ce084e285d1fa65d93b3e27a6195d3bbebc9ae23"
  fi
else
  if ! command -v docker >/dev/null 2>&1; then
    printf 'random mode requires docker for KES identity generation\n' >&2
    exit 1
  fi
  KES_OUTPUT="$(docker run --rm minio/kes:latest identity new)"
  KES_API_KEY="$(printf '%s\n' "$KES_OUTPUT" | sed -n 's/^[[:space:]]*\(kes:v1:[^[:space:]]*\)$/\1/p' | head -n1)"
  KES_IDENTITY="$(printf '%s\n' "$KES_OUTPUT" | sed -n 's/^[[:space:]]*\([0-9a-f]\{64\}\)$/\1/p' | head -n1)"
  if [ -z "$KES_API_KEY" ] || [ -z "$KES_IDENTITY" ]; then
    printf 'Unable to parse KES identity output\n' >&2
    exit 1
  fi
fi

python3 - "$TEMPLATE" "$OUTPUT" "$MODE" "$UI_ORIGIN" "$UI_API_URL" "$RELEASE_TAG" "$KES_API_KEY" "$KES_IDENTITY" <<'PY'
import base64
import hashlib
import os
import secrets
import sys
from pathlib import Path

template_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
mode = sys.argv[3]
ui_origin = sys.argv[4]
ui_api_url = sys.argv[5]
release_tag = sys.argv[6]
kes_api_key = sys.argv[7]
kes_identity = sys.argv[8]

seed = "meridian-ci-seed-v1"


def deterministic_value(key: str) -> str:
    digest = hashlib.sha256(f"{seed}:{key}".encode("utf-8")).hexdigest()
    return f"ci_{digest[:40]}"


def random_value(key: str) -> str:
    del key
    return secrets.token_hex(24)


def fernet_key_random() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")


def fernet_key_deterministic(key: str) -> str:
    raw = hashlib.sha256(f"{seed}:{key}".encode("utf-8")).digest()
    return base64.urlsafe_b64encode(raw).decode("ascii")


lines = template_path.read_text(encoding="utf-8").splitlines()
result = []

for raw in lines:
    if not raw or raw.lstrip().startswith("#") or "=" not in raw:
        result.append(raw)
        continue

    key, value = raw.split("=", 1)
    key = key.strip()
    value = value.strip()

    if key == "MINIO_KMS_KES_API_KEY":
        result.append(f"{key}={kes_api_key}")
        continue
    if key == "MINIO_KMS_KES_IDENTITY":
        result.append(f"{key}={kes_identity}")
        continue
    if key == "AIRFLOW_FERNET_KEY":
        if mode == "random":
            result.append(f"{key}={fernet_key_random()}")
        else:
            result.append(f"{key}={fernet_key_deterministic(key)}")
        continue

    if key == "UI_ORIGIN" and ui_origin:
        result.append(f"{key}={ui_origin}")
        continue
    if key == "UI_API_URL" and ui_api_url:
        result.append(f"{key}={ui_api_url}")
        continue
    if key == "VITE_RELEASE_TAG":
        # Keep this key available in generated env files for production deploy builds.
        if release_tag:
            result.append(f"{key}={release_tag}")
        continue

    if value.startswith("replace_with_"):
        if mode == "random":
            result.append(f"{key}={random_value(key)}")
        else:
            result.append(f"{key}={deterministic_value(key)}")
        continue

    result.append(f"{key}={value}")

if release_tag:
    if not any(line.startswith("VITE_RELEASE_TAG=") for line in result):
        result.append(f"VITE_RELEASE_TAG={release_tag}")

output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text("\n".join(result) + "\n", encoding="utf-8")
PY

printf 'Wrote %s using %s mode\n' "$OUTPUT" "$MODE"
