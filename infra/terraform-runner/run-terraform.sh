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
export TF_VAR_minio_transform_user="$MINIO_TRANSFORM_USER"
export TF_VAR_minio_transform_secret="$MINIO_TRANSFORM_SECRET"
export TF_VAR_minio_trino_write_user="$MINIO_TRINO_WRITE_USER"
export TF_VAR_minio_trino_write_secret="$MINIO_TRINO_WRITE_SECRET"
export TF_VAR_minio_trino_read_user="$MINIO_TRINO_READ_USER"
export TF_VAR_minio_trino_read_secret="$MINIO_TRINO_READ_SECRET"
export TF_VAR_minio_kms_key_id="$MINIO_KMS_KEY_ID"
export TF_VAR_minio_enforce_kms_write_prefixes="${MINIO_ENFORCE_KMS_WRITE_PREFIXES:-true}"

exec terraform -chdir="/workspace/infra/terraform/${root}" "$@"
