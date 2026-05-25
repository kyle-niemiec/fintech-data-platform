#!/usr/bin/env bash
set -euo pipefail

# This script deploys a new release of the Meridian application to the EC2 instance
# using SSM Run Command. It also updates SSM parameters to track the currently
# deployed release and the last known good release for automatic rollback in case
# of deployment failure.
#
# Usage:
#   INSTANCE_ID=<id> TAG=<vX.Y.Z> REPO_URL=<url> DOMAIN=<fqdn> \
#   AWS_REGION=<region> CURRENT_PARAM=<name> LAST_GOOD_PARAM=<name> \
#   bash infra/ops/ssm_release_deploy.sh

INSTANCE_ID="${INSTANCE_ID:-${MERIDIAN_EC2_INSTANCE_ID:-}}"
TAG="${TAG:-${GITHUB_REF_NAME:-}}"
REPO_URL="${REPO_URL:-}"
DOMAIN="${DOMAIN:-meridian.codeflower.io}"
AWS_REGION="${AWS_REGION:-us-east-1}"
CURRENT_PARAM="${CURRENT_PARAM:-/meridian/demo/current_tag}"
LAST_GOOD_PARAM="${LAST_GOOD_PARAM:-/meridian/demo/last_good_tag}"

aws_cmd() {
	aws --region "$AWS_REGION" "$@"
}

get_parameter_if_present() {
	local name="$1"
	aws_cmd ssm get-parameter --name "$name" --query 'Parameter.Value' --output text 2>/dev/null || true
}

# Helper function to wait for an SSM command to complete and return success or failure.
wait_for_command() {
	local command_id="$1"
	local status=""
	while true; do
		status="$(aws_cmd ssm get-command-invocation \
			--command-id "$command_id" \
			--instance-id "$INSTANCE_ID" \
			--query 'Status' \
			--output text)"

		case "$status" in
			Pending|InProgress|Delayed)
				sleep 5
				;;
			Success)
				aws_cmd ssm get-command-invocation \
					--command-id "$command_id" \
					--instance-id "$INSTANCE_ID" \
					--query 'StandardOutputContent' \
					--output text || true
				return 0
				;;
			*)
				echo "SSM command $command_id ended with status: $status" >&2

				aws_cmd ssm get-command-invocation \
					--command-id "$command_id" \
					--instance-id "$INSTANCE_ID" \
					--query 'StandardErrorContent' \
					--output text >&2 || true
				return 1
				;;
		esac
	done
}

# Helper function to send the deploy command with a given tag and return the command ID.
send_deploy_command() {
	local deploy_tag="$1"
	local cmd_id

	cmd_id="$(
		aws_cmd ssm send-command \
			--instance-ids "$INSTANCE_ID" \
			--document-name "AWS-RunShellScript" \
			--comment "Meridian release deploy ${deploy_tag}" \
			--parameters "commands=[
\"set -euo pipefail\",
\"REPO_DIR=/opt/meridian-demo\",
\"if [ ! -d \\\"${REPO_DIR}/.git\\\" ]; then rm -rf \\\"${REPO_DIR}\\\"; git clone \\\"${REPO_URL}\\\" \\\"${REPO_DIR}\\\"; fi\",
\"cd \\\"${REPO_DIR}\\\"\",
\"git fetch --tags origin\",
\"git checkout \\\"${deploy_tag}\\\"\",
\"git reset --hard \\\"${deploy_tag}\\\"\",
\"git clean -fdx\",
\"TAG=\\\"${deploy_tag}\\\" DOMAIN=\\\"${DOMAIN}\\\" bash infra/ops/ec2_deploy_release.sh\"
]" \
			--query 'Command.CommandId' \
			--output text
	)"

	echo "$cmd_id"
}

# Get previous release tag info if available for potential rollback before
# updating the current release tag in SSM. This ensures we have the correct
# previous tag even if the current deployment fails before it can update the
# last good tag.
previous_tag="$(get_parameter_if_present "$LAST_GOOD_PARAM")"

# Add the new release tag to SSM so it's available for the deploy command
aws_cmd ssm put-parameter \
	--name "$CURRENT_PARAM" \
	--type String \
	--value "$TAG" \
	--overwrite >/dev/null


# Deploy the new release using SSM Run Command and wait for it to complete.
deploy_command_id="$(send_deploy_command "$TAG")"

if wait_for_command "$deploy_command_id"; then
	aws_cmd ssm put-parameter \
		--name "$LAST_GOOD_PARAM" \
		--type String \
		--value "$TAG" \
		--overwrite >/dev/null

	exit 0
fi

# If deployment failed and we have a previous tag, attempt automatic rollback to the last known good release.
if [ -n "$previous_tag" ]; then
	echo "Deploy failed. Attempting automatic rollback to ${previous_tag}..." >&2
	rollback_command_id="$(send_deploy_command "$previous_tag")"

	if wait_for_command "$rollback_command_id"; then
		aws_cmd ssm put-parameter \
			--name "$CURRENT_PARAM" \
			--type String \
			--value "$previous_tag" \
			--overwrite >/dev/null
		exit 1
	fi
fi

exit 1
