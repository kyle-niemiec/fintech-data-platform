#!/usr/bin/env bash
set -euo pipefail

: "${KC_ADMIN_USER:?KC_ADMIN_USER is required}"
: "${KC_ADMIN_PASSWORD:?KC_ADMIN_PASSWORD is required}"
: "${KC_PIPELINE_CLIENT_SECRET:?KC_PIPELINE_CLIENT_SECRET is required}"

KEYCLOAK_REALM="${KEYCLOAK_REALM:-meridian}"
PIPELINE_CLIENT_ID="${PIPELINE_CLIENT_ID:-meridian-pipeline}"
KEYCLOAK_CONTAINER="${KEYCLOAK_CONTAINER:-fintech_keycloak}"

if ! docker ps --format '{{.Names}}' | grep -Fxq "$KEYCLOAK_CONTAINER"; then
  echo "Keycloak container '$KEYCLOAK_CONTAINER' is not running"
  exit 1
fi

for _ in $(seq 1 30); do
  if docker exec "$KEYCLOAK_CONTAINER" \
      /opt/keycloak/bin/kcadm.sh config credentials \
      --server http://localhost:8080 \
      --realm master \
      --user "$KC_ADMIN_USER" \
      --password "$KC_ADMIN_PASSWORD" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

CLIENT_UUID="$(
  docker exec "$KEYCLOAK_CONTAINER" \
    /opt/keycloak/bin/kcadm.sh get clients \
      -r "$KEYCLOAK_REALM" \
      -q "clientId=$PIPELINE_CLIENT_ID" \
      --fields id \
      --format csv \
      --noquotes | tr -d '\r' | tail -n 1
)"

if [ -z "$CLIENT_UUID" ] || [ "$CLIENT_UUID" = "id" ]; then
  echo "Client $PIPELINE_CLIENT_ID not found in realm $KEYCLOAK_REALM"
  exit 1
fi

docker exec "$KEYCLOAK_CONTAINER" \
  /opt/keycloak/bin/kcadm.sh update "clients/$CLIENT_UUID" \
    -r "$KEYCLOAK_REALM" \
    -s "secret=$KC_PIPELINE_CLIENT_SECRET" >/dev/null

echo "Keycloak pipeline client secret updated"
