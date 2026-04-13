#!/bin/sh
set -eu

: "${MINIO_KMS_KEY_ID:=fintech-lakehouse-kms-key}"
: "${MINIO_KMS_KES_IDENTITY:?MINIO_KMS_KES_IDENTITY is required}"
: "${VAULT_ADDR:=http://vault:8200}"
: "${VAULT_KV_ENGINE:=kv}"
: "${VAULT_TRANSIT_ENGINE:=transit}"
: "${VAULT_TRANSIT_KEY_NAME:=fintech-minio-kms-root}"
: "${KES_VAULT_PREFIX:=fintech-kes}"
: "${KES_VAULT_CREDS_FILE:=/kms/vault-kes-approle.env}"
: "${KES_CONFIG_FILE:=/kms/config/kes-server-config.yaml}"
: "${KES_CERT_DIR:=/kms/certs}"

if [ ! -f "${KES_VAULT_CREDS_FILE}" ]; then
  echo "Missing Vault AppRole credentials file: ${KES_VAULT_CREDS_FILE}" >&2
  exit 1
fi

# shellcheck disable=SC1090
. "${KES_VAULT_CREDS_FILE}"

mkdir -p "${KES_CERT_DIR}" "$(dirname "${KES_CONFIG_FILE}")"

if [ ! -f "${KES_CERT_DIR}/ca.crt" ] || [ ! -f "${KES_CERT_DIR}/ca.key" ]; then
  openssl req -x509 -newkey rsa:4096 -sha256 -nodes \
    -keyout "${KES_CERT_DIR}/ca.key" \
    -out "${KES_CERT_DIR}/ca.crt" \
    -days 3650 \
    -subj "/CN=fintech-kes-ca" >/dev/null 2>&1
fi

if [ ! -f "${KES_CERT_DIR}/server.crt" ] || [ ! -f "${KES_CERT_DIR}/server.key" ]; then
  cat > /tmp/kes-server.cnf <<'EOF'
[req]
default_bits=4096
prompt=no
default_md=sha256
distinguished_name=dn
req_extensions=req_ext

[dn]
CN=kes

[req_ext]
subjectAltName=@alt_names

[alt_names]
DNS.1=kes
DNS.2=localhost
IP.1=127.0.0.1
EOF

  openssl req -new -newkey rsa:4096 -nodes \
    -keyout "${KES_CERT_DIR}/server.key" \
    -out /tmp/kes-server.csr \
    -config /tmp/kes-server.cnf >/dev/null 2>&1

  openssl x509 -req \
    -in /tmp/kes-server.csr \
    -CA "${KES_CERT_DIR}/ca.crt" \
    -CAkey "${KES_CERT_DIR}/ca.key" \
    -CAcreateserial \
    -out "${KES_CERT_DIR}/server.crt" \
    -days 3650 \
    -sha256 \
    -extensions req_ext \
    -extfile /tmp/kes-server.cnf >/dev/null 2>&1

  rm -f /tmp/kes-server.cnf /tmp/kes-server.csr
fi

cat > "${KES_CONFIG_FILE}" <<EOF
version: v1
address: 0.0.0.0:7373
admin:
  identity: disabled
tls:
  cert: /kms/certs/server.crt
  key: /kms/certs/server.key
  auth: off
policy:
  minio:
    allow:
      - /v1/key/create/${MINIO_KMS_KEY_ID}
      - /v1/key/generate/${MINIO_KMS_KEY_ID}
      - /v1/key/decrypt/${MINIO_KMS_KEY_ID}
      - /v1/key/bulk/decrypt/${MINIO_KMS_KEY_ID}
      - /v1/status
      - /v1/api
      - /v1/metrics
    identities:
      - ${MINIO_KMS_KES_IDENTITY}
keys:
  - name: ${MINIO_KMS_KEY_ID}
keystore:
  vault:
    endpoint: ${VAULT_ADDR}
    engine: ${VAULT_KV_ENGINE}
    version: v1
    prefix: ${KES_VAULT_PREFIX}
    transit:
      engine: ${VAULT_TRANSIT_ENGINE}
      key: ${VAULT_TRANSIT_KEY_NAME}
    approle:
      engine: approle
      id: ${KES_VAULT_APPROLE_ID}
      secret: ${KES_VAULT_APPROLE_SECRET}
EOF
