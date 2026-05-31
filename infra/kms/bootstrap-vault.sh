#!/bin/sh
set -eu

: "${VAULT_ADDR:=http://vault:8200}"
: "${VAULT_KV_ENGINE:=kv}"
: "${VAULT_TRANSIT_ENGINE:=transit}"
: "${VAULT_TRANSIT_KEY_NAME:=fintech-minio-kms-root}"
: "${KES_VAULT_APPROLE:=kes-minio}"
: "${KES_VAULT_POLICY:=kes-minio-policy}"
: "${KES_VAULT_CREDS_FILE:=/kms/vault-kes-approle.env}"
: "${VAULT_STATE_FILE:=/vault/data/vault-init.env}"

export VAULT_ADDR

# Attempt to gain the Vault token from the state file or environment.
if [ -z "${VAULT_TOKEN:-}" ]; then
  if [ -f "${VAULT_STATE_FILE}" ]; then
    # Source the state file to set VAULT_UNSEAL_KEY and VAULT_ROOT_TOKEN for unsealing and export.
    # shellcheck disable=SC1090
    . "${VAULT_STATE_FILE}"
    : "${VAULT_ROOT_TOKEN:?VAULT_ROOT_TOKEN missing from ${VAULT_STATE_FILE}}"

    export VAULT_TOKEN="${VAULT_ROOT_TOKEN}"
  elif [ -n "${VAULT_DEV_ROOT_TOKEN_ID:-}" ]; then
    # Set the Vault token to the development root token if available.
    export VAULT_TOKEN="${VAULT_DEV_ROOT_TOKEN_ID}"
  else
    echo "VAULT_TOKEN is required (or provide VAULT_STATE_FILE with VAULT_ROOT_TOKEN)." >&2
    exit 1
  fi
fi

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

# Create a policy file with the necessary permissions for the KES AppRole.
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

# Write the policy to Vault.
vault policy write "${KES_VAULT_POLICY}" "${tmp_policy_file}" >/dev/null
rm -f "${tmp_policy_file}"

# Create the AppRole with the policy.
vault write "auth/approle/role/${KES_VAULT_APPROLE}" \
  token_policies="${KES_VAULT_POLICY}" \
  token_ttl="1h" \
  token_max_ttl="4h" \
  secret_id_ttl="0" >/dev/null

# Read out the AppRole credentials from Vault.
role_id="$(vault read -field=role_id "auth/approle/role/${KES_VAULT_APPROLE}/role-id")"
secret_id="$(vault write -field=secret_id -f "auth/approle/role/${KES_VAULT_APPROLE}/secret-id")"

mkdir -p "$(dirname "${KES_VAULT_CREDS_FILE}")"

# Write AppRole credentials to a file for use by `bootstrap-kes.sh` and `kes-start.sh`.
cat > "${KES_VAULT_CREDS_FILE}" <<EOF
KES_VAULT_APPROLE_ID=${role_id}
KES_VAULT_APPROLE_SECRET=${secret_id}
EOF
