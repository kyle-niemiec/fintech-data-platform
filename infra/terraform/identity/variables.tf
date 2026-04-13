variable "keycloak_url" {
  description = "Base URL for Keycloak admin API"
  type        = string
  default     = "http://localhost:8180"
  nullable    = false

  validation {
    condition     = can(regex("^https?://[^[:space:]]+$", var.keycloak_url))
    error_message = "keycloak_url must be a valid http(s) URL."
  }
}

variable "keycloak_realm" {
  description = "Target Keycloak realm name"
  type        = string
  default     = "meridian"
  nullable    = false

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9_-]{1,62}$", var.keycloak_realm))
    error_message = "keycloak_realm must be 2-63 chars using lowercase letters, numbers, '_' or '-'."
  }
}

variable "keycloak_admin_user" {
  description = "Bootstrap Keycloak admin username"
  type        = string
  nullable    = false

  validation {
    condition     = trimspace(var.keycloak_admin_user) != ""
    error_message = "keycloak_admin_user must be set."
  }
}

variable "keycloak_admin_password" {
  description = "Bootstrap Keycloak admin password"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.keycloak_admin_password)) >= 12
    error_message = "keycloak_admin_password must be at least 12 characters."
  }
}

variable "keycloak_demo_service_client_id" {
  description = "Internal client id used by demo actor selector services"
  type        = string
  default     = "meridian-demo-service"
  nullable    = false

  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$", var.keycloak_demo_service_client_id))
    error_message = "keycloak_demo_service_client_id must be 2-128 chars using letters, numbers, '.', '_' or '-'."
  }
}

variable "keycloak_demo_service_client_secret" {
  description = "Internal client secret used by demo actor selector services"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.keycloak_demo_service_client_secret)) >= 12
    error_message = "keycloak_demo_service_client_secret must be at least 12 characters."
  }
}

variable "keycloak_demo_user_password" {
  description = "Password used for seeded demo personas in local development"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.keycloak_demo_user_password)) >= 12
    error_message = "keycloak_demo_user_password must be at least 12 characters."
  }
}
