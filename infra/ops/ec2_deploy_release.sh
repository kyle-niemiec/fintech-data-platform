#!/usr/bin/env bash
set -euo pipefail

# This script deploys a release of the Meridian EC2-based demo environment. It
# assumes that the release artifacts have already been built and are available
# in the appropriate S3 bucket.
#
# Usage:
#   TAG=<vX.Y.Z> DOMAIN=<fqdn> bash infra/ops/ec2_deploy_release.sh

TAG="${TAG:-}"
DOMAIN="${DOMAIN:-meridian.codeflower.io}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

cd "$ROOT_DIR"

# Configure environment variables for `generate_env.sh`.
MODE=random \
OUTPUT=infra/.env \
UI_ORIGIN="https://${DOMAIN}" \
RELEASE_TAG="$TAG" \

# Generate the .env file.
bash infra/ops/generate_env.sh

# Clean and redeploy the infrastructure for the demo.
make infra-clean

# Start the workers and services for the demo.
make infra-up
