resource "keycloak_realm" "meridian" {
  realm                    = var.keycloak_realm
  enabled                  = true
  ssl_required             = "none"
  registration_allowed     = false
  login_with_email_allowed = false
  duplicate_emails_allowed = false
  reset_password_allowed   = false
  remember_me              = false
}

resource "keycloak_openid_client" "meridian_api" {
  realm_id  = keycloak_realm.meridian.id
  client_id = var.keycloak_api_client_id
  name      = "Meridian API Swagger"
  enabled   = true

  access_type                  = "PUBLIC"
  standard_flow_enabled        = true
  direct_access_grants_enabled = false
  service_accounts_enabled     = false
  full_scope_allowed           = true

  valid_redirect_uris = [
    "http://127.0.0.1:8000/docs/oauth2-redirect",
    "http://localhost:8000/docs/oauth2-redirect",
  ]

  web_origins = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
  ]

  pkce_code_challenge_method = "S256"
}

resource "keycloak_openid_client_default_scopes" "meridian_api_defaults" {
  realm_id  = keycloak_realm.meridian.id
  client_id = keycloak_openid_client.meridian_api.id

  default_scopes = [
    "profile",
    "email",
    "roles",
  ]
}

resource "keycloak_openid_audience_protocol_mapper" "meridian_api_audience" {
  realm_id  = keycloak_realm.meridian.id
  client_id = keycloak_openid_client.meridian_api.id
  name      = "aud-meridian-api"

  included_client_audience = var.keycloak_api_audience
  add_to_access_token      = true
  add_to_id_token          = false
}

resource "keycloak_openid_client" "meridian_pipeline" {
  realm_id  = keycloak_realm.meridian.id
  client_id = var.keycloak_pipeline_client_id
  name      = "Meridian Pipeline Service"
  enabled   = true

  access_type                  = "CONFIDENTIAL"
  standard_flow_enabled        = false
  direct_access_grants_enabled = false
  service_accounts_enabled     = true
  full_scope_allowed           = false

  client_secret = var.keycloak_pipeline_client_secret
}

resource "keycloak_openid_client_default_scopes" "meridian_pipeline_defaults" {
  realm_id  = keycloak_realm.meridian.id
  client_id = keycloak_openid_client.meridian_pipeline.id

  default_scopes = [
    "profile",
    "email",
    "roles",
  ]
}

resource "keycloak_openid_audience_protocol_mapper" "meridian_pipeline_audience" {
  realm_id  = keycloak_realm.meridian.id
  client_id = keycloak_openid_client.meridian_pipeline.id
  name      = "aud-meridian-api"

  included_client_audience = var.keycloak_api_audience
  add_to_access_token      = true
  add_to_id_token          = false
}

resource "keycloak_role" "operator" {
  realm_id    = keycloak_realm.meridian.id
  client_id   = keycloak_openid_client.meridian_api.id
  name        = "operator"
  description = "Read + write access to control plane"
}

resource "keycloak_role" "observer" {
  realm_id    = keycloak_realm.meridian.id
  client_id   = keycloak_openid_client.meridian_api.id
  name        = "observer"
  description = "Read-only access to control plane"
}

resource "keycloak_role" "pipeline" {
  realm_id    = keycloak_realm.meridian.id
  client_id   = keycloak_openid_client.meridian_api.id
  name        = "pipeline"
  description = "Pipeline service write access"
}

resource "keycloak_user" "operator" {
  realm_id = keycloak_realm.meridian.id
  username = var.keycloak_operator_username
  enabled  = true

  initial_password {
    value     = var.keycloak_operator_password
    temporary = false
  }
}

resource "keycloak_user" "observer" {
  realm_id = keycloak_realm.meridian.id
  username = var.keycloak_observer_username
  enabled  = true

  initial_password {
    value     = var.keycloak_observer_password
    temporary = false
  }
}

resource "keycloak_user_roles" "operator" {
  realm_id = keycloak_realm.meridian.id
  user_id  = keycloak_user.operator.id

  role_ids = [
    keycloak_role.operator.id,
  ]
}

resource "keycloak_user_roles" "observer" {
  realm_id = keycloak_realm.meridian.id
  user_id  = keycloak_user.observer.id

  role_ids = [
    keycloak_role.observer.id,
  ]
}

resource "keycloak_openid_client_service_account_role" "pipeline_role_binding" {
  realm_id = keycloak_realm.meridian.id

  service_account_user_id = keycloak_openid_client.meridian_pipeline.service_account_user_id
  client_id               = keycloak_openid_client.meridian_api.id
  role                    = keycloak_role.pipeline.name
}
