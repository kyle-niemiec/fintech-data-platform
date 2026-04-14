variable "keycloak_url" {
  description = "Base URL for Keycloak admin API"
  type        = string
  default     = "http://keycloak:8080"
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

variable "redpanda_bootstrap_servers" {
  description = "Comma-separated Redpanda broker endpoints for topic/ACL provisioning"
  type        = string
  default     = "redpanda:9092"
  nullable    = false

  validation {
    condition     = trimspace(var.redpanda_bootstrap_servers) != ""
    error_message = "redpanda_bootstrap_servers must be set."
  }
}

variable "redpanda_admin_hosts" {
  description = "Comma-separated Redpanda Admin API endpoints for security provisioning"
  type        = string
  default     = "redpanda:9644"
  nullable    = false

  validation {
    condition     = trimspace(var.redpanda_admin_hosts) != ""
    error_message = "redpanda_admin_hosts must be set."
  }
}

variable "redpanda_admin_user" {
  description = "Optional Redpanda superuser for authenticated ACL provisioning"
  type        = string
  default     = ""
  nullable    = false
}

variable "redpanda_admin_password" {
  description = "Optional Redpanda superuser password for authenticated ACL provisioning"
  type        = string
  default     = ""
  sensitive   = true
  nullable    = false
}

variable "redpanda_ingest_topic_partitions" {
  description = "Partition count for ingest.* topics in local development"
  type        = number
  default     = 6
  nullable    = false

  validation {
    condition     = var.redpanda_ingest_topic_partitions == floor(var.redpanda_ingest_topic_partitions) && var.redpanda_ingest_topic_partitions >= 1
    error_message = "redpanda_ingest_topic_partitions must be a positive integer."
  }
}

variable "redpanda_pipeline_topic_partitions" {
  description = "Partition count for pipeline.* topics in local development"
  type        = number
  default     = 6
  nullable    = false

  validation {
    condition     = var.redpanda_pipeline_topic_partitions == floor(var.redpanda_pipeline_topic_partitions) && var.redpanda_pipeline_topic_partitions >= 1
    error_message = "redpanda_pipeline_topic_partitions must be a positive integer."
  }
}

variable "redpanda_cdc_topic_partitions" {
  description = "Partition count for cdc.* topics in local development"
  type        = number
  default     = 12
  nullable    = false

  validation {
    condition     = var.redpanda_cdc_topic_partitions == floor(var.redpanda_cdc_topic_partitions) && var.redpanda_cdc_topic_partitions >= 1
    error_message = "redpanda_cdc_topic_partitions must be a positive integer."
  }
}

variable "redpanda_alert_topic_partitions" {
  description = "Partition count for ui.alert.* topics in local development"
  type        = number
  default     = 3
  nullable    = false

  validation {
    condition     = var.redpanda_alert_topic_partitions == floor(var.redpanda_alert_topic_partitions) && var.redpanda_alert_topic_partitions >= 1
    error_message = "redpanda_alert_topic_partitions must be a positive integer."
  }
}

variable "redpanda_excel_service_user" {
  description = "Redpanda service identity for Excel ingress/scanner/validator emissions"
  type        = string
  default     = "rp_excel_service"
  nullable    = false

  validation {
    condition     = can(regex("^[A-Za-z0-9._-]{3,64}$", var.redpanda_excel_service_user))
    error_message = "redpanda_excel_service_user must be 3-64 chars using letters, numbers, '.', '_' or '-'."
  }
}

variable "redpanda_excel_service_password" {
  description = "Password for redpanda_excel_service_user"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.redpanda_excel_service_password)) >= 12
    error_message = "redpanda_excel_service_password must be at least 12 characters."
  }
}

variable "redpanda_excel_scanner_user" {
  description = "Redpanda service identity for Excel scanner consume/produce path"
  type        = string
  default     = "rp_excel_scanner"
  nullable    = false

  validation {
    condition     = can(regex("^[A-Za-z0-9._-]{3,64}$", var.redpanda_excel_scanner_user))
    error_message = "redpanda_excel_scanner_user must be 3-64 chars using letters, numbers, '.', '_' or '-'."
  }
}

variable "redpanda_excel_scanner_password" {
  description = "Password for redpanda_excel_scanner_user"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.redpanda_excel_scanner_password)) >= 12
    error_message = "redpanda_excel_scanner_password must be at least 12 characters."
  }
}

variable "redpanda_airflow_user" {
  description = "Redpanda service identity for Excel validation trigger worker"
  type        = string
  default     = "rp_airflow"
  nullable    = false

  validation {
    condition     = can(regex("^[A-Za-z0-9._-]{3,64}$", var.redpanda_airflow_user))
    error_message = "redpanda_airflow_user must be 3-64 chars using letters, numbers, '.', '_' or '-'."
  }
}

variable "redpanda_airflow_password" {
  description = "Password for redpanda_airflow_user"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.redpanda_airflow_password)) >= 12
    error_message = "redpanda_airflow_password must be at least 12 characters."
  }
}

variable "redpanda_excel_bronze_user" {
  description = "Redpanda service identity for Excel bronze writer consume/produce path"
  type        = string
  default     = "rp_excel_bronze"
  nullable    = false

  validation {
    condition     = can(regex("^[A-Za-z0-9._-]{3,64}$", var.redpanda_excel_bronze_user))
    error_message = "redpanda_excel_bronze_user must be 3-64 chars using letters, numbers, '.', '_' or '-'."
  }
}

variable "redpanda_excel_bronze_password" {
  description = "Password for redpanda_excel_bronze_user"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.redpanda_excel_bronze_password)) >= 12
    error_message = "redpanda_excel_bronze_password must be at least 12 characters."
  }
}

variable "redpanda_cdc_service_user" {
  description = "Redpanda service identity for CDC source publication"
  type        = string
  default     = "rp_cdc_service"
  nullable    = false

  validation {
    condition     = can(regex("^[A-Za-z0-9._-]{3,64}$", var.redpanda_cdc_service_user))
    error_message = "redpanda_cdc_service_user must be 3-64 chars using letters, numbers, '.', '_' or '-'."
  }
}

variable "redpanda_cdc_service_password" {
  description = "Password for redpanda_cdc_service_user"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.redpanda_cdc_service_password)) >= 12
    error_message = "redpanda_cdc_service_password must be at least 12 characters."
  }
}

variable "redpanda_fraud_service_user" {
  description = "Redpanda service identity for fraud worker consume/produce path"
  type        = string
  default     = "rp_fraud_service"
  nullable    = false

  validation {
    condition     = can(regex("^[A-Za-z0-9._-]{3,64}$", var.redpanda_fraud_service_user))
    error_message = "redpanda_fraud_service_user must be 3-64 chars using letters, numbers, '.', '_' or '-'."
  }
}

variable "redpanda_fraud_service_password" {
  description = "Password for redpanda_fraud_service_user"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.redpanda_fraud_service_password)) >= 12
    error_message = "redpanda_fraud_service_password must be at least 12 characters."
  }
}

variable "redpanda_salesforce_service_user" {
  description = "Redpanda service identity for Salesforce pull event emissions"
  type        = string
  default     = "rp_salesforce_service"
  nullable    = false

  validation {
    condition     = can(regex("^[A-Za-z0-9._-]{3,64}$", var.redpanda_salesforce_service_user))
    error_message = "redpanda_salesforce_service_user must be 3-64 chars using letters, numbers, '.', '_' or '-'."
  }
}

variable "redpanda_salesforce_service_password" {
  description = "Password for redpanda_salesforce_service_user"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.redpanda_salesforce_service_password)) >= 12
    error_message = "redpanda_salesforce_service_password must be at least 12 characters."
  }
}

variable "redpanda_orchestrator_service_user" {
  description = "Redpanda service identity for bronze->silver->gold orchestration events"
  type        = string
  default     = "rp_orchestrator_service"
  nullable    = false

  validation {
    condition     = can(regex("^[A-Za-z0-9._-]{3,64}$", var.redpanda_orchestrator_service_user))
    error_message = "redpanda_orchestrator_service_user must be 3-64 chars using letters, numbers, '.', '_' or '-'."
  }
}

variable "redpanda_orchestrator_service_password" {
  description = "Password for redpanda_orchestrator_service_user"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.redpanda_orchestrator_service_password)) >= 12
    error_message = "redpanda_orchestrator_service_password must be at least 12 characters."
  }
}

variable "redpanda_ui_service_user" {
  description = "Redpanda service identity for UI notification feed consumption"
  type        = string
  default     = "rp_ui_service"
  nullable    = false

  validation {
    condition     = can(regex("^[A-Za-z0-9._-]{3,64}$", var.redpanda_ui_service_user))
    error_message = "redpanda_ui_service_user must be 3-64 chars using letters, numbers, '.', '_' or '-'."
  }
}

variable "redpanda_ui_service_password" {
  description = "Password for redpanda_ui_service_user"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.redpanda_ui_service_password)) >= 12
    error_message = "redpanda_ui_service_password must be at least 12 characters."
  }
}
