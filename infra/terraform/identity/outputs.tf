output "keycloak_realm_name" {
  description = "Provisioned Keycloak realm"
  value       = keycloak_realm.meridian.realm
}

output "keycloak_demo_service_client_id" {
  description = "Internal client id used for demo actor selection"
  value       = keycloak_openid_client.demo_service.client_id
}

output "keycloak_finance_role_name" {
  description = "Role name assigned to demo finance personas"
  value       = keycloak_role.finance.name
}
