#!/bin/sh
set -eu

require_env() {
  var_name="$1"
  eval "var_value=\${$var_name:-}"
  if [ -z "$var_value" ]; then
    echo "Missing required environment variable: $var_name" >&2
    exit 1
  fi
}

split_csv() {
  printf "%s" "$1" | tr "," "\n" | sed -e "s/^[[:space:]]*//" -e "s/[[:space:]]*$//" -e "/^$/d"
}

require_env REDPANDA_BOOTSTRAP_SERVERS
require_env REDPANDA_ADMIN_HOSTS
require_env REDPANDA_INGEST_TOPIC_PARTITIONS
require_env REDPANDA_CDC_TOPIC_PARTITIONS
require_env REDPANDA_PIPELINE_TOPIC_PARTITIONS
require_env REDPANDA_ALERT_TOPIC_PARTITIONS
require_env REDPANDA_INGEST_TOPICS
require_env REDPANDA_CDC_TOPICS
require_env REDPANDA_PIPELINE_TOPICS
require_env REDPANDA_ALERT_TOPICS
require_env REDPANDA_EXCEL_SERVICE_USER
require_env REDPANDA_EXCEL_SERVICE_PASSWORD
require_env REDPANDA_EXCEL_SCANNER_USER
require_env REDPANDA_EXCEL_SCANNER_PASSWORD
require_env REDPANDA_AIRFLOW_USER
require_env REDPANDA_AIRFLOW_PASSWORD
require_env REDPANDA_EXCEL_BRONZE_USER
require_env REDPANDA_EXCEL_BRONZE_PASSWORD
require_env REDPANDA_CDC_SERVICE_USER
require_env REDPANDA_CDC_SERVICE_PASSWORD
require_env REDPANDA_FRAUD_SERVICE_USER
require_env REDPANDA_FRAUD_SERVICE_PASSWORD
require_env REDPANDA_SALESFORCE_SERVICE_USER
require_env REDPANDA_SALESFORCE_SERVICE_PASSWORD
require_env REDPANDA_SALESFORCE_BRONZE_USER
require_env REDPANDA_SALESFORCE_BRONZE_PASSWORD
require_env REDPANDA_ORCHESTRATOR_SERVICE_USER
require_env REDPANDA_ORCHESTRATOR_SERVICE_PASSWORD
require_env REDPANDA_UI_SERVICE_USER
require_env REDPANDA_UI_SERVICE_PASSWORD
require_env REDPANDA_EXCEL_SCANNER_CONSUMER_GROUP
require_env REDPANDA_AIRFLOW_CONSUMER_GROUP
require_env REDPANDA_EXCEL_BRONZE_CONSUMER_GROUP
require_env REDPANDA_SALESFORCE_BRONZE_CONSUMER_GROUP
require_env REDPANDA_FRAUD_CONSUMER_GROUP
require_env REDPANDA_ORCHESTRATOR_CONSUMER_GROUP
require_env REDPANDA_UI_ALERTS_CONSUMER_GROUP

rpk_kafka() {
  if [ -n "${REDPANDA_ADMIN_USER:-}" ] && [ -n "${REDPANDA_ADMIN_PASSWORD:-}" ]; then
    rpk "$@" \
      -X brokers="${REDPANDA_BOOTSTRAP_SERVERS}" \
      -X user="${REDPANDA_ADMIN_USER}" \
      -X pass="${REDPANDA_ADMIN_PASSWORD}" \
      -X sasl.mechanism=SCRAM-SHA-256
    return
  fi

  rpk "$@" -X brokers="${REDPANDA_BOOTSTRAP_SERVERS}"
}

rpk_admin() {
  if [ -n "${REDPANDA_ADMIN_USER:-}" ] && [ -n "${REDPANDA_ADMIN_PASSWORD:-}" ]; then
    rpk "$@" \
      -X brokers="${REDPANDA_BOOTSTRAP_SERVERS}" \
      -X admin.hosts="${REDPANDA_ADMIN_HOSTS}" \
      -X user="${REDPANDA_ADMIN_USER}" \
      -X pass="${REDPANDA_ADMIN_PASSWORD}" \
      -X sasl.mechanism=SCRAM-SHA-256
    return
  fi

  rpk "$@" \
    -X brokers="${REDPANDA_BOOTSTRAP_SERVERS}" \
    -X admin.hosts="${REDPANDA_ADMIN_HOSTS}"
}

ensure_topic() {
  topic_name="$1"
  partitions="$2"

  if rpk_kafka topic describe "${topic_name}" >/dev/null 2>&1; then
    return
  fi

  rpk_kafka topic create "${topic_name}" --partitions "${partitions}" >/dev/null
}

ensure_user() {
  username="$1"
  password="$2"

  users_output="$(rpk_admin security user list 2>/dev/null || true)"
  if printf "%s\n" "${users_output}" | awk "NR>1 {print \$1}" | grep -Fx "${username}" >/dev/null 2>&1; then
    return
  fi

  rpk_admin security user create "${username}" \
    -p "${password}" \
    --mechanism SCRAM-SHA-256 >/dev/null
}

ensure_acl() {
  principal="$1"
  operation="$2"
  resource_type="$3"
  resource_name="${4:-}"
  acl_output=""
  acl_status=0

  case "${resource_type}" in
    topic)
      set +e
      acl_output="$(rpk_admin security acl create \
        --allow-principal "User:${principal}" \
        --operation "${operation}" \
        --topic "${resource_name}" 2>&1)"
      acl_status=$?
      set -e
      ;;
    group)
      set +e
      acl_output="$(rpk_admin security acl create \
        --allow-principal "User:${principal}" \
        --operation "${operation}" \
        --group "${resource_name}" 2>&1)"
      acl_status=$?
      set -e
      ;;
    cluster)
      set +e
      acl_output="$(rpk_admin security acl create \
        --allow-principal "User:${principal}" \
        --operation "${operation}" \
        --cluster 2>&1)"
      acl_status=$?
      set -e
      ;;
    *)
      echo "Unsupported ACL resource type: ${resource_type}" >&2
      exit 1
      ;;
  esac

  if [ "${acl_status}" -eq 0 ]; then
    return
  fi

  if printf "%s" "${acl_output}" | grep -Eiq "already exists|no changes"; then
    return
  fi

  printf "%s\n" "${acl_output}" >&2
  exit 1
}

for topic_name in $(split_csv "${REDPANDA_INGEST_TOPICS}"); do
  ensure_topic "${topic_name}" "${REDPANDA_INGEST_TOPIC_PARTITIONS}"
done

for topic_name in $(split_csv "${REDPANDA_CDC_TOPICS}"); do
  ensure_topic "${topic_name}" "${REDPANDA_CDC_TOPIC_PARTITIONS}"
done

for topic_name in $(split_csv "${REDPANDA_PIPELINE_TOPICS}"); do
  ensure_topic "${topic_name}" "${REDPANDA_PIPELINE_TOPIC_PARTITIONS}"
done

for topic_name in $(split_csv "${REDPANDA_ALERT_TOPICS}"); do
  ensure_topic "${topic_name}" "${REDPANDA_ALERT_TOPIC_PARTITIONS}"
done

ensure_user "${REDPANDA_EXCEL_SERVICE_USER}" "${REDPANDA_EXCEL_SERVICE_PASSWORD}"
ensure_user "${REDPANDA_EXCEL_SCANNER_USER}" "${REDPANDA_EXCEL_SCANNER_PASSWORD}"
ensure_user "${REDPANDA_AIRFLOW_USER}" "${REDPANDA_AIRFLOW_PASSWORD}"
ensure_user "${REDPANDA_EXCEL_BRONZE_USER}" "${REDPANDA_EXCEL_BRONZE_PASSWORD}"
ensure_user "${REDPANDA_CDC_SERVICE_USER}" "${REDPANDA_CDC_SERVICE_PASSWORD}"
ensure_user "${REDPANDA_FRAUD_SERVICE_USER}" "${REDPANDA_FRAUD_SERVICE_PASSWORD}"
ensure_user "${REDPANDA_SALESFORCE_SERVICE_USER}" "${REDPANDA_SALESFORCE_SERVICE_PASSWORD}"
ensure_user "${REDPANDA_SALESFORCE_BRONZE_USER}" "${REDPANDA_SALESFORCE_BRONZE_PASSWORD}"
ensure_user "${REDPANDA_ORCHESTRATOR_SERVICE_USER}" "${REDPANDA_ORCHESTRATOR_SERVICE_PASSWORD}"
ensure_user "${REDPANDA_UI_SERVICE_USER}" "${REDPANDA_UI_SERVICE_PASSWORD}"

# Excel upload ingress (kept for demo upload generation only).
ensure_acl "${REDPANDA_EXCEL_SERVICE_USER}" "write" "topic" "ingest.excel.uploaded.v1"

# Excel scanner consume uploaded, emit scanned outcomes.
ensure_acl "${REDPANDA_EXCEL_SCANNER_USER}" "read" "topic" "ingest.excel.uploaded.v1"
ensure_acl "${REDPANDA_EXCEL_SCANNER_USER}" "read" "group" "${REDPANDA_EXCEL_SCANNER_CONSUMER_GROUP}"
ensure_acl "${REDPANDA_EXCEL_SCANNER_USER}" "write" "topic" "ingest.excel.scanned.pass.v1"
ensure_acl "${REDPANDA_EXCEL_SCANNER_USER}" "write" "topic" "ingest.excel.scanned.fail.v1"

# Airflow trigger worker consume scanned.pass, emit raw/quarantine outcomes.
ensure_acl "${REDPANDA_AIRFLOW_USER}" "read" "topic" "ingest.excel.scanned.pass.v1"
ensure_acl "${REDPANDA_AIRFLOW_USER}" "read" "group" "${REDPANDA_AIRFLOW_CONSUMER_GROUP}"
ensure_acl "${REDPANDA_AIRFLOW_USER}" "write" "topic" "ingest.excel.raw.ready.v1"
ensure_acl "${REDPANDA_AIRFLOW_USER}" "write" "topic" "ingest.excel.quarantined.v1"

# Bronze writer consume raw.ready, emit bronze.ready.
ensure_acl "${REDPANDA_EXCEL_BRONZE_USER}" "read" "topic" "ingest.excel.raw.ready.v1"
ensure_acl "${REDPANDA_EXCEL_BRONZE_USER}" "read" "group" "${REDPANDA_EXCEL_BRONZE_CONSUMER_GROUP}"
ensure_acl "${REDPANDA_EXCEL_BRONZE_USER}" "write" "topic" "ingest.excel.bronze.ready.v1"

# CDC source publication.
ensure_acl "${REDPANDA_CDC_SERVICE_USER}" "write" "topic" "cdc.oltp.raw.v1"

# Fraud worker consume raw CDC and emit assessed + bronze-ready.
ensure_acl "${REDPANDA_FRAUD_SERVICE_USER}" "read" "topic" "cdc.oltp.raw.v1"
ensure_acl "${REDPANDA_FRAUD_SERVICE_USER}" "read" "group" "${REDPANDA_FRAUD_CONSUMER_GROUP}"
ensure_acl "${REDPANDA_FRAUD_SERVICE_USER}" "write" "topic" "cdc.oltp.assessed.v1"
ensure_acl "${REDPANDA_FRAUD_SERVICE_USER}" "write" "topic" "cdc.oltp.bronze.ready.v1"

# Salesforce incremental pull: Airflow DAG produces raw.ready; salesforce_bronze consumes
# raw.ready and produces bronze.ready. The legacy rp_salesforce_service principal is
# retained in the users map for the mock service identity but holds no topic ACLs today.
ensure_acl "${REDPANDA_AIRFLOW_USER}" "write" "topic" "ingest.salesforce.raw.ready.v1"
ensure_acl "${REDPANDA_SALESFORCE_BRONZE_USER}" "read" "topic" "ingest.salesforce.raw.ready.v1"
ensure_acl "${REDPANDA_SALESFORCE_BRONZE_USER}" "read" "group" "${REDPANDA_SALESFORCE_BRONZE_CONSUMER_GROUP}"
ensure_acl "${REDPANDA_SALESFORCE_BRONZE_USER}" "write" "topic" "ingest.salesforce.bronze.ready.v1"

# Curated orchestrator consume bronze-ready and emit pipeline + alert events.
ensure_acl "${REDPANDA_ORCHESTRATOR_SERVICE_USER}" "read" "topic" "ingest.excel.bronze.ready.v1"
ensure_acl "${REDPANDA_ORCHESTRATOR_SERVICE_USER}" "read" "topic" "cdc.oltp.bronze.ready.v1"
ensure_acl "${REDPANDA_ORCHESTRATOR_SERVICE_USER}" "read" "topic" "ingest.salesforce.bronze.ready.v1"
ensure_acl "${REDPANDA_ORCHESTRATOR_SERVICE_USER}" "read" "group" "${REDPANDA_ORCHESTRATOR_CONSUMER_GROUP}"
ensure_acl "${REDPANDA_ORCHESTRATOR_SERVICE_USER}" "write" "topic" "pipeline.silver.completed.v1"
ensure_acl "${REDPANDA_ORCHESTRATOR_SERVICE_USER}" "write" "topic" "pipeline.silver.failed.v1"
ensure_acl "${REDPANDA_ORCHESTRATOR_SERVICE_USER}" "write" "topic" "pipeline.gold.completed.v1"
ensure_acl "${REDPANDA_ORCHESTRATOR_SERVICE_USER}" "write" "topic" "pipeline.gold.failed.v1"
ensure_acl "${REDPANDA_ORCHESTRATOR_SERVICE_USER}" "write" "topic" "ui.alert.raised.v1"

# UI alert feed consumer identity.
ensure_acl "${REDPANDA_UI_SERVICE_USER}" "read" "topic" "ui.alert.raised.v1"
ensure_acl "${REDPANDA_UI_SERVICE_USER}" "read" "group" "${REDPANDA_UI_ALERTS_CONSUMER_GROUP}"
