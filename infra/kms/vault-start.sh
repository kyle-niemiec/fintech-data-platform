#!/bin/sh
set -eu

: "${VAULT_ADDR:=http://127.0.0.1:8200}"
: "${VAULT_CONFIG_FILE:=/vault/config/vault.hcl}"
: "${VAULT_STATE_FILE:=/vault/data/vault-init.env}"
: "${VAULT_BOOTSTRAP_SCRIPT:=/bootstrap-vault.sh}"

vault server -config="${VAULT_CONFIG_FILE}" &
vault_pid=$!

# Ensure the Vault server is terminated when this script exits.
cleanup() {
  if kill -0 "${vault_pid}" >/dev/null 2>&1; then
    kill "${vault_pid}" >/dev/null 2>&1 || true
  fi
}

trap cleanup INT TERM

# A function to wait for the Vault API to become reachable, handling both
# uninitialized and initialized states. Sets a status code for checking vault
# initialization status before unsealing.
wait_for_vault_api() {
  attempts=0

  while true; do
    status=0
    vault status >/dev/null 2>&1 || status="$?"

    if [ "${status}" -eq 0 ] || [ "${status}" -eq 2 ]; then
      return 0
    fi

    attempts=$((attempts + 1))

    if [ "${attempts}" -ge 60 ]; then
      echo "Vault API did not become reachable within 60 attempts." >&2
      return 1
    fi

    sleep 1
  done
}

# Wait for the Vault API to be reachable before proceeding with initialization.
wait_for_vault_api

init_status=0
vault operator init -status >/dev/null 2>&1 || init_status="$?"
if [ "${init_status}" -eq 2 ]; then

  # Initialize Vault, capturing the unseal key and root token.
  init_output="$(vault operator init -key-shares=1 -key-threshold=1)"

  # Extract the unseal key and root token from the initialization output
  unseal_key="$(printf '%s\n' "${init_output}" | awk -F': ' '/Unseal Key 1/ {print $2; exit}')"
  root_token="$(printf '%s\n' "${init_output}" | awk -F': ' '/Initial Root Token/ {print $2; exit}')"

  if [ -z "${unseal_key}" ] || [ -z "${root_token}" ]; then
    echo "Failed to parse unseal key or root token from Vault initialization output." >&2
    exit 1
  fi


  mkdir -p "$(dirname "${VAULT_STATE_FILE}")"
  umask 077

  # Write the unseal key and root token to the state file for later use by `vault-start.sh`.
  cat > "${VAULT_STATE_FILE}" <<EOF
VAULT_UNSEAL_KEY=${unseal_key}
VAULT_ROOT_TOKEN=${root_token}
EOF

elif [ "${init_status}" -ne 0 ]; then
  echo "Failed to read Vault initialization status (exit=${init_status})." >&2
  exit 1
fi

if [ ! -f "${VAULT_STATE_FILE}" ]; then
  echo "Missing Vault state file: ${VAULT_STATE_FILE}" >&2
  exit 1
fi

# Source the state file to set VAULT_UNSEAL_KEY and VAULT_ROOT_TOKEN for unsealing.
# shellcheck disable=SC1090
. "${VAULT_STATE_FILE}"
: "${VAULT_UNSEAL_KEY:?VAULT_UNSEAL_KEY missing from state file}"
: "${VAULT_ROOT_TOKEN:?VAULT_ROOT_TOKEN missing from state file}"

status=0
vault status >/dev/null 2>&1 || status="$?"

# Unseal the Vault server using the unseal key.
if [ "${status}" -eq 2 ]; then
  vault operator unseal "${VAULT_UNSEAL_KEY}" >/dev/null
elif [ "${status}" -ne 0 ]; then
  echo "Vault status failed with unexpected exit code ${status}." >&2
  exit 1
fi

attempts=0

# Ensure the Vault is unsealed and ready before proceeding with bootstrapping.
until vault status >/dev/null 2>&1; do
  status="$?"

  if [ "${status}" -ne 2 ]; then
    echo "Vault did not become unsealed (exit=${status})." >&2
    exit 1
  fi

  attempts=$((attempts + 1))

  if [ "${attempts}" -ge 60 ]; then
    echo "Vault remained sealed after 60 attempts." >&2
    exit 1
  fi

  sleep 1
done

# Export the root token for use by the bootstrap script.
export VAULT_TOKEN="${VAULT_ROOT_TOKEN}"
"/bin/sh" "${VAULT_BOOTSTRAP_SCRIPT}"

wait "${vault_pid}"
