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

resource "keycloak_openid_client" "demo_service" {
  realm_id  = keycloak_realm.meridian.id
  client_id = var.keycloak_demo_service_client_id
  name      = "Meridian Demo Service Client"
  enabled   = true

  access_type                  = "CONFIDENTIAL"
  standard_flow_enabled        = false
  direct_access_grants_enabled = false
  service_accounts_enabled     = true
  full_scope_allowed           = false

  client_secret = var.keycloak_demo_service_client_secret
}

resource "keycloak_role" "finance" {
  realm_id    = keycloak_realm.meridian.id
  name        = "finance"
  description = "Can upload finance source files in demo workflows"
}

locals {
  finance_demo_users = toset([
    "james.beringer@meridian.example.com",
    "kathy.winston@meridian.example.com",
    "alex.ortiz@meridian.example.com",
  ])
}

resource "keycloak_user" "finance_demo" {
  for_each = local.finance_demo_users
  realm_id = keycloak_realm.meridian.id
  username = each.value
  enabled  = true

  initial_password {
    value     = var.keycloak_demo_user_password
    temporary = false
  }
}

resource "keycloak_user_roles" "finance_demo" {
  for_each = keycloak_user.finance_demo
  realm_id = keycloak_realm.meridian.id
  user_id  = each.value.id

  role_ids = [
    keycloak_role.finance.id,
  ]
}

# The demo service account resolves finance-role uploaders at runtime via the
# Admin API GET /admin/realms/{realm}/roles/{role}/users. That endpoint requires
# BOTH `view-users` (read users) and `view-realm` (read the realm role) — verified
# against Keycloak 26; `view-users` alone (and even `manage-users`) returns 403.
# Because demo_service has `full_scope_allowed = false`, assigning these roles to
# the service account is not enough: roles outside the client scope are stripped
# from the issued token. Each role is therefore both assigned to the service
# account and added to the client scope (keycloak_generic_client_role_mapper).
data "keycloak_openid_client" "realm_management" {
  realm_id  = keycloak_realm.meridian.id
  client_id = "realm-management"
}

data "keycloak_role" "view_users" {
  realm_id  = keycloak_realm.meridian.id
  client_id = data.keycloak_openid_client.realm_management.id
  name      = "view-users"
}

data "keycloak_role" "view_realm" {
  realm_id  = keycloak_realm.meridian.id
  client_id = data.keycloak_openid_client.realm_management.id
  name      = "view-realm"
}

resource "keycloak_openid_client_service_account_role" "demo_service_view_users" {
  realm_id                = keycloak_realm.meridian.id
  service_account_user_id = keycloak_openid_client.demo_service.service_account_user_id
  client_id               = data.keycloak_openid_client.realm_management.id
  role                    = data.keycloak_role.view_users.name
}

resource "keycloak_openid_client_service_account_role" "demo_service_view_realm" {
  realm_id                = keycloak_realm.meridian.id
  service_account_user_id = keycloak_openid_client.demo_service.service_account_user_id
  client_id               = data.keycloak_openid_client.realm_management.id
  role                    = data.keycloak_role.view_realm.name
}

# full_scope_allowed = false on demo_service ⇒ roles must be in the client scope
# to appear in the service-account token.
resource "keycloak_generic_client_role_mapper" "demo_service_scope_view_users" {
  realm_id  = keycloak_realm.meridian.id
  client_id = keycloak_openid_client.demo_service.id
  role_id   = data.keycloak_role.view_users.id
}

resource "keycloak_generic_client_role_mapper" "demo_service_scope_view_realm" {
  realm_id  = keycloak_realm.meridian.id
  client_id = keycloak_openid_client.demo_service.id
  role_id   = data.keycloak_role.view_realm.id
}
