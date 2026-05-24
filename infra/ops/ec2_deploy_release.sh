#!/usr/bin/env bash
set -euo pipefail

TAG=""
DOMAIN="meridian.codeflower.io"
MAX_HEALTH_RETRIES=30

usage() {
  cat <<'EOF'
Usage: ec2_deploy_release.sh --tag <vX.Y.Z> [--domain <fqdn>]
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --tag)
      TAG="${2:?missing value for --tag}"
      shift 2
      ;;
    --domain)
      DOMAIN="${2:?missing value for --domain}"
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

if [ -z "$TAG" ]; then
  printf 'Missing required --tag\n' >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

make infra-clean

bash infra/ops/generate_env.sh \
  --mode random \
  --output infra/.env \
  --ui-origin "https://${DOMAIN}" \
  --release-tag "$TAG"

make infra-up
make infra-ps

health_check() {
  local name="$1"
  local path="$2"
  local attempt=1

  while true; do
    if curl -fsS -H "Host: ${DOMAIN}" "http://127.0.0.1:443${path}" >/dev/null; then
      echo "health check passed: ${name} (${path})"
      return 0
    fi

    if [ "$attempt" -ge "$MAX_HEALTH_RETRIES" ]; then
      echo "health check failed after ${attempt} attempts: ${name} (${path})" >&2
      return 1
    fi

    attempt="$((attempt + 1))"
    sleep 5
  done
}

health_check "hosted-ui" "/"
health_check "hosted-api" "/ui/runs?limit=1"
