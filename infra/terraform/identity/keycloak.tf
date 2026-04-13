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
