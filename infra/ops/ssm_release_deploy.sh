#!/usr/bin/env bash
set -euo pipefail

INSTANCE_ID=""
TAG=""
REPO_URL=""
DOMAIN="meridian.codeflower.io"
AWS_REGION="${AWS_REGION:-us-east-1}"
CURRENT_PARAM="/meridian/demo/current_tag"
LAST_GOOD_PARAM="/meridian/demo/last_good_tag"

usage() {
  cat <<'EOF'
Usage: ssm_release_deploy.sh --instance-id <id> --tag <vX.Y.Z> --repo-url <url> [options]

Options:
  --domain <fqdn>            Hosted domain (default: meridian.codeflower.io)
  --region <aws-region>      AWS region (default: AWS_REGION or us-east-1)
  --current-param <name>     SSM parameter for current tag
  --last-good-param <name>   SSM parameter for last successful tag
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --instance-id)
      INSTANCE_ID="${2:?missing value for --instance-id}"
      shift 2
      ;;
    --tag)
      TAG="${2:?missing value for --tag}"
      shift 2
      ;;
    --repo-url)
      REPO_URL="${2:?missing value for --repo-url}"
      shift 2
      ;;
    --domain)
      DOMAIN="${2:?missing value for --domain}"
      shift 2
      ;;
    --region)
      AWS_REGION="${2:?missing value for --region}"
      shift 2
      ;;
    --current-param)
      CURRENT_PARAM="${2:?missing value for --current-param}"
      shift 2
      ;;
    --last-good-param)
      LAST_GOOD_PARAM="${2:?missing value for --last-good-param}"
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

for req in INSTANCE_ID TAG REPO_URL; do
  if [ -z "${!req}" ]; then
    printf 'Missing required option for %s\n' "$req" >&2
    usage >&2
    exit 2
  fi
done

if ! [[ "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  printf 'Invalid semantic tag: %s\n' "$TAG" >&2
  exit 2
fi

aws_cmd() {
  aws --region "$AWS_REGION" "$@"
}

get_parameter_if_present() {
  local name="$1"
  aws_cmd ssm get-parameter --name "$name" --query 'Parameter.Value' --output text 2>/dev/null || true
}

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
\"bash infra/ops/ec2_deploy_release.sh --tag \\\"${deploy_tag}\\\" --domain \\\"${DOMAIN}\\\"\"
]" \
      --query 'Command.CommandId' \
      --output text
  )"
  echo "$cmd_id"
}

previous_tag="$(get_parameter_if_present "$LAST_GOOD_PARAM")"

aws_cmd ssm put-parameter \
  --name "$CURRENT_PARAM" \
  --type String \
  --value "$TAG" \
  --overwrite >/dev/null

deploy_command_id="$(send_deploy_command "$TAG")"
if wait_for_command "$deploy_command_id"; then
  aws_cmd ssm put-parameter \
    --name "$LAST_GOOD_PARAM" \
    --type String \
    --value "$TAG" \
    --overwrite >/dev/null
  exit 0
fi

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
