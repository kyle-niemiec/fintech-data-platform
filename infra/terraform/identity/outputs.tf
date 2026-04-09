output "keycloak_realm_name" {
  description = "Provisioned Keycloak realm"
  value       = keycloak_realm.meridian.realm
}

output "keycloak_api_client_id" {
  description = "OIDC client id used by API and Swagger"
  value       = keycloak_openid_client.meridian_api.client_id
}

output "keycloak_pipeline_client_id" {
  description = "OIDC client id used by pipelines"
  value       = keycloak_openid_client.meridian_pipeline.client_id
}
