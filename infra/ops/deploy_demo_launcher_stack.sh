#!/usr/bin/env bash
set -euo pipefail

# This script deploys the demo launcher CloudFormation stack, which provides a
# simple UI for starting and stopping EC2-based demos. It also syncs the static
# assets for the launcher UI to the appropriate S3 bucket after deployment.
#
# Usage:
#   bash infra/ops/deploy_demo_launcher_stack.sh
#
# Configuration is driven by environment variables:
#   MERIDIAN_LAUNCHER_STACK_NAME      (default: meridian-fintech-demo)
#   AWS_REGION                        (default: us-east-2)
#   MERIDIAN_LAUNCHER_ARTIFACT_BUCKET
#   MERIDIAN_HOSTED_DOMAIN            (default: meridian.codeflower.io)
#   MERIDIAN_ORIGIN_DOMAIN
#   MERIDIAN_ACM_CERT_ARN
#   MERIDIAN_EC2_INSTANCE_ID
#   MERIDIAN_DEMO_TTL_MINUTES         (default: 30)
#   MERIDIAN_HOSTED_ZONE_ID           (optional)
#   MERIDIAN_ORIGIN_HEALTHCHECK_URL   (optional)
#   MERIDIAN_SCHEDULER_GROUP          (default: default)

STACK_NAME="${MERIDIAN_LAUNCHER_STACK_NAME:-meridian-fintech-demo}"
REGION="${AWS_REGION:-us-east-2}"
TEMPLATE_FILE="infra/cloudformation/demo-launcher.yaml"
ASSETS_DIR="infra/cloudformation/launcher-site"
ARTIFACT_BUCKET="${MERIDIAN_LAUNCHER_ARTIFACT_BUCKET:-}"
DOMAIN="${MERIDIAN_HOSTED_DOMAIN:-meridian.codeflower.io}"
ORIGIN_DOMAIN="${MERIDIAN_ORIGIN_DOMAIN:-}"
ACM_CERT_ARN="${MERIDIAN_ACM_CERT_ARN:-}"
INSTANCE_ID="${MERIDIAN_EC2_INSTANCE_ID:-}"
TTL_MINUTES="${MERIDIAN_DEMO_TTL_MINUTES:-30}"
HOSTED_ZONE_ID="${MERIDIAN_HOSTED_ZONE_ID:-}"
HEALTH_CHECK_URL="${MERIDIAN_ORIGIN_HEALTHCHECK_URL:-}"
SCHEDULER_GROUP="${MERIDIAN_SCHEDULER_GROUP:-default}"

printf 'Target Bucket Name: %s\n' "$MERIDIAN_LAUNCHER_ARTIFACT_BUCKET"

if [ -z "$HEALTH_CHECK_URL" ]; then
	HEALTH_CHECK_URL="http://${ORIGIN_DOMAIN}:443/"
fi

if [ ! -f "$TEMPLATE_FILE" ]; then
	printf 'Template file not found: %s\n' "$TEMPLATE_FILE" >&2
	exit 1
fi

if [ ! -d "$ASSETS_DIR" ]; then
	printf 'Assets directory not found: %s\n' "$ASSETS_DIR" >&2
	exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
	printf 'aws CLI is required\n' >&2
	exit 1
fi

packaged_template="$(mktemp "${TMPDIR:-/tmp}/demo-launcher-packaged.XXXXXX.yaml")"
asset_stage_dir="$(mktemp -d "${TMPDIR:-/tmp}/demo-launcher-assets.XXXXXX")"

cleanup() {
	rm -f "$packaged_template"
	rm -rf "$asset_stage_dir"
}

trap cleanup EXIT

# Package the CloudFormation template, uploading assets to S3 as needed.
printf 'Packaging CloudFormation template...\n'

aws --region "$REGION" cloudformation package \
	--template-file "$TEMPLATE_FILE" \
	--s3-bucket "$ARTIFACT_BUCKET" \
	--output-template-file "$packaged_template"

aws --region "$REGION" cloudformation validate-template --template-body "file://$packaged_template" >/dev/null

params=(
	"DomainName=$DOMAIN"
	"OriginDomainName=$ORIGIN_DOMAIN"
	"AcmCertificateArn=$ACM_CERT_ARN"
	"Ec2InstanceId=$INSTANCE_ID"
	"DemoTtlMinutes=$TTL_MINUTES"
	"SchedulerGroupName=$SCHEDULER_GROUP"
	"HealthCheckUrl=$HEALTH_CHECK_URL"
)

if [ -n "$HOSTED_ZONE_ID" ]; then
	params+=("HostedZoneId=$HOSTED_ZONE_ID")
fi

# Deploy the CloudFormation stack using the packaged template and specified parameters.
printf '\nDeploying CloudFormation stack "%s" in region "%s"...' "$STACK_NAME" "$REGION"

aws --region "$REGION" cloudformation deploy \
	--stack-name "$STACK_NAME" \
	--template-file "$packaged_template" \
	--capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
	--parameter-overrides "${params[@]}"

# Programmatically resolve the S3 bucket name and API URL from the stack outputs for asset syncing.
landing_bucket="$(aws --region "$REGION" cloudformation describe-stacks \
	--stack-name "$STACK_NAME" \
	--query "Stacks[0].Outputs[?OutputKey=='LauncherLandingBucketName'].OutputValue" \
	--output text)"

printf 'Resolved landing bucket: %s\n' "$landing_bucket"

control_api_url="$(aws --region "$REGION" cloudformation describe-stacks \
	--stack-name "$STACK_NAME" \
	--query "Stacks[0].Outputs[?OutputKey=='LauncherControlFunctionUrl'].OutputValue" \
	--output text)"

# Trim trailing slash, if present
control_api_url="${control_api_url%/}"
printf 'Resolved control API URL: %s\n' "$control_api_url"

# Copy the launcher UI assets to the temporary staging directory for processing.
cp -R "$ASSETS_DIR"/. "$asset_stage_dir"/

# Replace placeholders in the static assets with the resolved API URL and domain.
sed -i "s|__CONTROL_API_BASE__|${control_api_url}|g" "$asset_stage_dir/app.js"
sed -i "s|__DEMO_HOST__|https://${DOMAIN}|g" "$asset_stage_dir/app.js"

# Sync the processed assets to the S3 bucket.
printf 'Syncing launcher UI assets to S3 bucket "%s"...\n' "$landing_bucket"

aws --region "$REGION" s3 sync "$asset_stage_dir" "s3://${landing_bucket}" \
	--delete \
	--cache-control "public, max-age=60"

# Copy index.html separately with no-cache headers.
printf 'Uploading index.html with no-cache headers...\n'

aws --region "$REGION" s3 cp "$asset_stage_dir/index.html" "s3://${landing_bucket}/index.html" \
	--cache-control "no-cache, no-store, must-revalidate" \
	--content-type "text/html"

printf 'Demo launcher stack deployed successfully!\n'
