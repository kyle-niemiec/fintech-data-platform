#!/bin/sh
set -eu

usage() {
  echo "Usage: run-terraform.sh <bootstrap|identity> <terraform-subcommand> [args...]" >&2
}

require_env() {
  var_name="$1"
  eval "var_value=\${$var_name:-}"
  if [ -z "$var_value" ]; then
    echo "Missing required environment variable: $var_name" >&2
    exit 1
  fi
}

if [ "$#" -lt 2 ]; then
  usage
  exit 2
fi

root="$1"
shift

case "$root" in
  bootstrap|identity)
    ;;
  *)
    usage
    exit 2
    ;;
esac

require_env POSTGRES_DB
require_env POSTGRES_ROOT_USER
require_env POSTGRES_ROOT_PASSWORD
require_env EVENT_STORE_DB
require_env EVENT_STORE_DB_ROOT_USER
require_env EVENT_STORE_DB_ROOT_PASSWORD
require_env EVENT_QUERY_DB_USER
require_env EVENT_QUERY_DB_PASSWORD
require_env EVENT_APPEND_DB_USER
require_env EVENT_APPEND_DB_PASSWORD
require_env ICEBERG_CATALOG_OWNER_USER
require_env ICEBERG_CATALOG_OWNER_PASSWORD
require_env KC_DB_USER
require_env KC_DB_PASSWORD
require_env KC_ADMIN_USER
require_env KC_ADMIN_PASSWORD
require_env KEYCLOAK_REALM
require_env KEYCLOAK_DEMO_SERVICE_CLIENT_ID
require_env KEYCLOAK_DEMO_SERVICE_CLIENT_SECRET
require_env KEYCLOAK_DEMO_USER_PASSWORD
require_env MINIO_ROOT_USER
require_env MINIO_ROOT_PASSWORD
require_env MINIO_BUCKET_NAME
require_env MINIO_INGEST_USER
require_env MINIO_INGEST_SECRET
require_env MINIO_VALIDATION_USER
require_env MINIO_VALIDATION_SECRET
require_env MINIO_TRANSFORM_USER
require_env MINIO_TRANSFORM_SECRET
require_env MINIO_TRINO_WRITE_USER
require_env MINIO_TRINO_WRITE_SECRET
require_env MINIO_TRINO_READ_USER
require_env MINIO_TRINO_READ_SECRET
require_env MINIO_KMS_KEY_ID

export TF_VAR_postgres_db="$POSTGRES_DB"
export TF_VAR_postgres_host="postgres"
export TF_VAR_postgres_port="5432"
export TF_VAR_postgres_root_user="$POSTGRES_ROOT_USER"
export TF_VAR_postgres_root_password="$POSTGRES_ROOT_PASSWORD"

export TF_VAR_event_store_db="$EVENT_STORE_DB"
export TF_VAR_event_store_db_host="event_store_db"
export TF_VAR_event_store_db_port="${EVENT_STORE_DB_PORT:-5433}"
export TF_VAR_event_store_db_root_user="$EVENT_STORE_DB_ROOT_USER"
export TF_VAR_event_store_db_root_password="$EVENT_STORE_DB_ROOT_PASSWORD"
export TF_VAR_event_query_db_user="$EVENT_QUERY_DB_USER"
export TF_VAR_event_query_db_password="$EVENT_QUERY_DB_PASSWORD"
export TF_VAR_event_append_db_user="$EVENT_APPEND_DB_USER"
export TF_VAR_event_append_db_password="$EVENT_APPEND_DB_PASSWORD"
export TF_VAR_iceberg_catalog_owner_user="$ICEBERG_CATALOG_OWNER_USER"
export TF_VAR_iceberg_catalog_owner_password="$ICEBERG_CATALOG_OWNER_PASSWORD"

export TF_VAR_kc_db_user="$KC_DB_USER"
export TF_VAR_kc_db_password="$KC_DB_PASSWORD"
export TF_VAR_keycloak_url="http://keycloak:8080"
export TF_VAR_keycloak_realm="$KEYCLOAK_REALM"
export TF_VAR_keycloak_admin_user="$KC_ADMIN_USER"
export TF_VAR_keycloak_admin_password="$KC_ADMIN_PASSWORD"
export TF_VAR_keycloak_demo_service_client_id="$KEYCLOAK_DEMO_SERVICE_CLIENT_ID"
export TF_VAR_keycloak_demo_service_client_secret="$KEYCLOAK_DEMO_SERVICE_CLIENT_SECRET"
export TF_VAR_keycloak_demo_user_password="$KEYCLOAK_DEMO_USER_PASSWORD"

export TF_VAR_minio_server="minio:9000"
export TF_VAR_minio_root_user="$MINIO_ROOT_USER"
export TF_VAR_minio_root_password="$MINIO_ROOT_PASSWORD"
export TF_VAR_minio_bucket_name="$MINIO_BUCKET_NAME"
export TF_VAR_minio_ingest_user="$MINIO_INGEST_USER"
export TF_VAR_minio_ingest_secret="$MINIO_INGEST_SECRET"
export TF_VAR_minio_validation_user="$MINIO_VALIDATION_USER"
export TF_VAR_minio_validation_secret="$MINIO_VALIDATION_SECRET"
export TF_VAR_minio_transform_user="$MINIO_TRANSFORM_USER"
export TF_VAR_minio_transform_secret="$MINIO_TRANSFORM_SECRET"
export TF_VAR_minio_trino_write_user="$MINIO_TRINO_WRITE_USER"
export TF_VAR_minio_trino_write_secret="$MINIO_TRINO_WRITE_SECRET"
export TF_VAR_minio_trino_read_user="$MINIO_TRINO_READ_USER"
export TF_VAR_minio_trino_read_secret="$MINIO_TRINO_READ_SECRET"
export TF_VAR_minio_kms_key_id="$MINIO_KMS_KEY_ID"
export TF_VAR_minio_enforce_kms_write_prefixes="${MINIO_ENFORCE_KMS_WRITE_PREFIXES:-true}"
export TF_VAR_minio_ingest_upload_topic="${MINIO_INGEST_UPLOAD_TOPIC:-ingest.excel.uploaded.v1}"

export TF_VAR_redpanda_bootstrap_servers="redpanda:9092"
export TF_VAR_redpanda_admin_hosts="${REDPANDA_ADMIN_HOSTS:-redpanda:9644}"
export TF_VAR_redpanda_admin_user="${REDPANDA_ADMIN_USER:-}"
export TF_VAR_redpanda_admin_password="${REDPANDA_ADMIN_PASSWORD:-}"
export TF_VAR_redpanda_ingest_topic_partitions="${REDPANDA_INGEST_TOPIC_PARTITIONS:-6}"
export TF_VAR_redpanda_pipeline_topic_partitions="${REDPANDA_PIPELINE_TOPIC_PARTITIONS:-6}"
export TF_VAR_redpanda_cdc_topic_partitions="${REDPANDA_CDC_TOPIC_PARTITIONS:-12}"
export TF_VAR_redpanda_alert_topic_partitions="${REDPANDA_ALERT_TOPIC_PARTITIONS:-3}"
export TF_VAR_redpanda_excel_service_user="${REDPANDA_EXCEL_SERVICE_USER:-rp_excel_service}"
export TF_VAR_redpanda_excel_service_password="${REDPANDA_EXCEL_SERVICE_PASSWORD:-replace_with_redpanda_excel_service_password}"
export TF_VAR_redpanda_excel_scanner_user="${REDPANDA_EXCEL_SCANNER_USER:-rp_excel_scanner}"
export TF_VAR_redpanda_excel_scanner_password="${REDPANDA_EXCEL_SCANNER_PASSWORD:-replace_with_redpanda_excel_scanner_password}"
export TF_VAR_redpanda_airflow_user="${REDPANDA_AIRFLOW_USER:-rp_airflow}"
export TF_VAR_redpanda_airflow_password="${REDPANDA_AIRFLOW_PASSWORD:-replace_with_redpanda_airflow_password}"
export TF_VAR_redpanda_excel_bronze_user="${REDPANDA_EXCEL_BRONZE_USER:-rp_excel_bronze}"
export TF_VAR_redpanda_excel_bronze_password="${REDPANDA_EXCEL_BRONZE_PASSWORD:-replace_with_redpanda_excel_bronze_password}"
export TF_VAR_redpanda_cdc_service_user="${REDPANDA_CDC_SERVICE_USER:-rp_cdc_service}"
export TF_VAR_redpanda_cdc_service_password="${REDPANDA_CDC_SERVICE_PASSWORD:-replace_with_redpanda_cdc_service_password}"
export TF_VAR_redpanda_fraud_service_user="${REDPANDA_FRAUD_SERVICE_USER:-rp_fraud_service}"
export TF_VAR_redpanda_fraud_service_password="${REDPANDA_FRAUD_SERVICE_PASSWORD:-replace_with_redpanda_fraud_service_password}"
export TF_VAR_redpanda_salesforce_service_user="${REDPANDA_SALESFORCE_SERVICE_USER:-rp_salesforce_service}"
export TF_VAR_redpanda_salesforce_service_password="${REDPANDA_SALESFORCE_SERVICE_PASSWORD:-replace_with_redpanda_salesforce_service_password}"
export TF_VAR_redpanda_salesforce_bronze_user="${REDPANDA_SALESFORCE_BRONZE_USER:-rp_salesforce_bronze}"
export TF_VAR_redpanda_salesforce_bronze_password="${REDPANDA_SALESFORCE_BRONZE_PASSWORD:-replace_with_redpanda_salesforce_bronze_password}"
export TF_VAR_redpanda_orchestrator_service_user="${REDPANDA_ORCHESTRATOR_SERVICE_USER:-rp_orchestrator_service}"
export TF_VAR_redpanda_orchestrator_service_password="${REDPANDA_ORCHESTRATOR_SERVICE_PASSWORD:-replace_with_redpanda_orchestrator_service_password}"
export TF_VAR_redpanda_ui_service_user="${REDPANDA_UI_SERVICE_USER:-rp_ui_service}"
export TF_VAR_redpanda_ui_service_password="${REDPANDA_UI_SERVICE_PASSWORD:-replace_with_redpanda_ui_service_password}"

exec terraform -chdir="/workspace/infra/terraform/${root}" "$@"
