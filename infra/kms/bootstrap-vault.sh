#!/bin/sh
set -eu

: "${VAULT_ADDR:=http://vault:8200}"
: "${VAULT_DEV_ROOT_TOKEN_ID:?VAULT_DEV_ROOT_TOKEN_ID is required}"
: "${VAULT_KV_ENGINE:=kv}"
: "${VAULT_TRANSIT_ENGINE:=transit}"
: "${VAULT_TRANSIT_KEY_NAME:=fintech-minio-kms-root}"
: "${KES_VAULT_APPROLE:=kes-minio}"
: "${KES_VAULT_POLICY:=kes-minio-policy}"
: "${KES_VAULT_CREDS_FILE:=/kms/vault-kes-approle.env}"

export VAULT_ADDR
export VAULT_TOKEN="${VAULT_DEV_ROOT_TOKEN_ID}"

attempts=0
until vault status >/dev/null 2>&1; do
  attempts=$((attempts + 1))
  if [ "$attempts" -ge 60 ]; then
    echo "Vault did not become ready within 60 attempts." >&2
    exit 1
  fi
  sleep 1
done

if ! vault auth list | awk '{print $1}' | grep -qx "approle/"; then
  vault auth enable approle >/dev/null
fi

if ! vault secrets list | awk '{print $1}' | grep -qx "${VAULT_KV_ENGINE}/"; then
  vault secrets enable -path="${VAULT_KV_ENGINE}" kv-v1 >/dev/null
fi

if ! vault secrets list | awk '{print $1}' | grep -qx "${VAULT_TRANSIT_ENGINE}/"; then
  vault secrets enable -path="${VAULT_TRANSIT_ENGINE}" transit >/dev/null
fi

if ! vault read "${VAULT_TRANSIT_ENGINE}/keys/${VAULT_TRANSIT_KEY_NAME}" >/dev/null 2>&1; then
  vault write -f "${VAULT_TRANSIT_ENGINE}/keys/${VAULT_TRANSIT_KEY_NAME}" >/dev/null
fi

tmp_policy_file="$(mktemp)"
cat > "${tmp_policy_file}" <<EOF
path "${VAULT_KV_ENGINE}/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "${VAULT_TRANSIT_ENGINE}/encrypt/${VAULT_TRANSIT_KEY_NAME}" {
  capabilities = ["update"]
}

path "${VAULT_TRANSIT_ENGINE}/decrypt/${VAULT_TRANSIT_KEY_NAME}" {
  capabilities = ["update"]
}

path "${VAULT_TRANSIT_ENGINE}/rewrap/${VAULT_TRANSIT_KEY_NAME}" {
  capabilities = ["update"]
}

path "${VAULT_TRANSIT_ENGINE}/keys/${VAULT_TRANSIT_KEY_NAME}" {
  capabilities = ["read"]
}

path "${VAULT_TRANSIT_ENGINE}/keys/${VAULT_TRANSIT_KEY_NAME}/*" {
  capabilities = ["read", "update"]
}
EOF

vault policy write "${KES_VAULT_POLICY}" "${tmp_policy_file}" >/dev/null
rm -f "${tmp_policy_file}"

vault write "auth/approle/role/${KES_VAULT_APPROLE}" \
  token_policies="${KES_VAULT_POLICY}" \
  token_ttl="1h" \
  token_max_ttl="4h" \
  secret_id_ttl="0" >/dev/null

role_id="$(vault read -field=role_id "auth/approle/role/${KES_VAULT_APPROLE}/role-id")"
secret_id="$(vault write -field=secret_id -f "auth/approle/role/${KES_VAULT_APPROLE}/secret-id")"

mkdir -p "$(dirname "${KES_VAULT_CREDS_FILE}")"
cat > "${KES_VAULT_CREDS_FILE}" <<EOF
KES_VAULT_APPROLE_ID=${role_id}
KES_VAULT_APPROLE_SECRET=${secret_id}
EOF
