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

variable "keycloak_api_client_id" {
  description = "OIDC client for API and Swagger login"
  type        = string
  default     = "meridian-api"
  nullable    = false

  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$", var.keycloak_api_client_id))
    error_message = "keycloak_api_client_id must be 2-128 chars using letters, numbers, '.', '_' or '-'."
  }
}

variable "keycloak_api_audience" {
  description = "Audience expected by the API"
  type        = string
  default     = "meridian-api"
  nullable    = false

  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$", var.keycloak_api_audience))
    error_message = "keycloak_api_audience must be 2-128 chars using letters, numbers, '.', '_' or '-'."
  }
}

variable "keycloak_swagger_client_id" {
  description = "Swagger UI OIDC client id"
  type        = string
  default     = "meridian-api"
  nullable    = false

  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$", var.keycloak_swagger_client_id))
    error_message = "keycloak_swagger_client_id must be 2-128 chars using letters, numbers, '.', '_' or '-'."
  }
}

variable "keycloak_pipeline_client_id" {
  description = "OIDC client id used by pipelines"
  type        = string
  default     = "meridian-pipeline"
  nullable    = false

  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$", var.keycloak_pipeline_client_id))
    error_message = "keycloak_pipeline_client_id must be 2-128 chars using letters, numbers, '.', '_' or '-'."
  }
}

variable "keycloak_pipeline_client_secret" {
  description = "OIDC client secret for pipeline client"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.keycloak_pipeline_client_secret)) >= 12
    error_message = "keycloak_pipeline_client_secret must be at least 12 characters."
  }
}

variable "keycloak_operator_username" {
  description = "Seed operator username for local dev"
  type        = string
  default     = "operator"
  nullable    = false

  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$", var.keycloak_operator_username))
    error_message = "keycloak_operator_username must be 2-64 chars using letters, numbers, '.', '_' or '-'."
  }
}

variable "keycloak_operator_password" {
  description = "Seed operator password for local dev"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.keycloak_operator_password)) >= 12
    error_message = "keycloak_operator_password must be at least 12 characters."
  }
}

variable "keycloak_observer_username" {
  description = "Seed observer username for local dev"
  type        = string
  default     = "observer"
  nullable    = false

  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$", var.keycloak_observer_username))
    error_message = "keycloak_observer_username must be 2-64 chars using letters, numbers, '.', '_' or '-'."
  }
}

variable "keycloak_observer_password" {
  description = "Seed observer password for local dev"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.keycloak_observer_password)) >= 12
    error_message = "keycloak_observer_password must be at least 12 characters."
  }
}
