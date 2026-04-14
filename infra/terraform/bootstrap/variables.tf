variable "postgres_host" {
  description = "Postgres service host reachable from Terraform runner"
  type        = string
  default     = "postgres"
  nullable    = false

  validation {
    condition     = trimspace(var.postgres_host) != ""
    error_message = "postgres_host must be set."
  }
}

variable "postgres_port" {
  description = "Postgres port"
  type        = number
  default     = 5432
  nullable    = false

  validation {
    condition     = var.postgres_port == floor(var.postgres_port) && var.postgres_port >= 1 && var.postgres_port <= 65535
    error_message = "postgres_port must be an integer between 1 and 65535."
  }
}

variable "postgres_db" {
  description = "Postgres database name"
  type        = string
  nullable    = false

  validation {
    condition     = trimspace(var.postgres_db) != ""
    error_message = "postgres_db must be set."
  }
}

variable "postgres_root_user" {
  description = "Postgres superuser used for provisioning"
  type        = string
  nullable    = false

  validation {
    condition     = trimspace(var.postgres_root_user) != ""
    error_message = "postgres_root_user must be set."
  }
}

variable "postgres_root_password" {
  description = "Postgres superuser password"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.postgres_root_password)) >= 12
    error_message = "postgres_root_password must be at least 12 characters."
  }
}

variable "event_store_db_host" {
  description = "Event-store Postgres service host reachable from Terraform runner"
  type        = string
  default     = "event_store_db"
  nullable    = false

  validation {
    condition     = trimspace(var.event_store_db_host) != ""
    error_message = "event_store_db_host must be set."
  }
}

variable "event_store_db_port" {
  description = "Event-store Postgres port"
  type        = number
  default     = 5433
  nullable    = false

  validation {
    condition     = var.event_store_db_port == floor(var.event_store_db_port) && var.event_store_db_port >= 1 && var.event_store_db_port <= 65535
    error_message = "event_store_db_port must be an integer between 1 and 65535."
  }
}

variable "event_store_db" {
  description = "Event-store database name"
  type        = string
  nullable    = false

  validation {
    condition     = trimspace(var.event_store_db) != ""
    error_message = "event_store_db must be set."
  }
}

variable "event_store_db_root_user" {
  description = "Event-store Postgres superuser used for provisioning"
  type        = string
  nullable    = false

  validation {
    condition     = trimspace(var.event_store_db_root_user) != ""
    error_message = "event_store_db_root_user must be set."
  }
}

variable "event_store_db_root_password" {
  description = "Event-store Postgres superuser password"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.event_store_db_root_password)) >= 12
    error_message = "event_store_db_root_password must be at least 12 characters."
  }
}

variable "event_query_db_user" {
  description = "DB login for UI query API runtime"
  type        = string
  nullable    = false

  validation {
    condition     = trimspace(var.event_query_db_user) != ""
    error_message = "event_query_db_user must be set."
  }
}

variable "event_query_db_password" {
  description = "DB password for UI query API runtime"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.event_query_db_password)) >= 12
    error_message = "event_query_db_password must be at least 12 characters."
  }
}

variable "event_append_db_user" {
  description = "DB login for append-only event-store runtime"
  type        = string
  nullable    = false

  validation {
    condition     = trimspace(var.event_append_db_user) != ""
    error_message = "event_append_db_user must be set."
  }
}

variable "event_append_db_password" {
  description = "DB password for append-only event-store runtime"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.event_append_db_password)) >= 12
    error_message = "event_append_db_password must be at least 12 characters."
  }
}

variable "kc_db_user" {
  description = "DB login for Keycloak runtime"
  type        = string
  nullable    = false

  validation {
    condition     = trimspace(var.kc_db_user) != ""
    error_message = "kc_db_user must be set."
  }
}

variable "kc_db_password" {
  description = "DB password for Keycloak runtime"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.kc_db_password)) >= 12
    error_message = "kc_db_password must be at least 12 characters."
  }
}

variable "minio_server" {
  description = "MinIO endpoint in host:port format reachable from Terraform runner"
  type        = string
  default     = "minio:9000"
  nullable    = false

  validation {
    condition     = can(regex("^[A-Za-z0-9.-]+:[0-9]{1,5}$", var.minio_server))
    error_message = "minio_server must be in host:port format."
  }
}

variable "minio_ingest_upload_topic" {
  description = "Kafka topic used for MinIO upload notifications"
  type        = string
  default     = "ingest.excel.uploaded.v1"
  nullable    = false

  validation {
    condition     = can(regex("^[a-z0-9._-]+$", var.minio_ingest_upload_topic))
    error_message = "minio_ingest_upload_topic must use lowercase Kafka topic-safe characters."
  }
}

variable "minio_root_user" {
  description = "MinIO root user for provisioning"
  type        = string
  nullable    = false

  validation {
    condition     = trimspace(var.minio_root_user) != ""
    error_message = "minio_root_user must be set."
  }
}

variable "minio_root_password" {
  description = "MinIO root password for provisioning"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.minio_root_password)) >= 12
    error_message = "minio_root_password must be at least 12 characters."
  }
}

variable "minio_bucket_name" {
  description = "Lakehouse bucket name"
  type        = string
  default     = "fintech-lakehouse"
  nullable    = false

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$", var.minio_bucket_name))
    error_message = "minio_bucket_name must follow S3-style naming (3-63 chars, lowercase, numbers, '.' or '-')."
  }
}

variable "minio_kms_key_id" {
  description = "MinIO KMS key ID used for SSE-KMS on enforced lakehouse prefixes"
  type        = string
  default     = "fintech-lakehouse-kms-key"
  nullable    = false

  validation {
    condition     = trimspace(var.minio_kms_key_id) != ""
    error_message = "minio_kms_key_id must be set."
  }
}

variable "minio_enforce_kms_write_prefixes" {
  description = "Enable deny-by-policy enforcement for SSE-KMS headers on protected prefixes"
  type        = bool
  default     = true
  nullable    = false
}

variable "minio_ingest_user" {
  description = "MinIO user for ingest services"
  type        = string
  default     = "minio_ingest"
  nullable    = false

  validation {
    condition     = trimspace(var.minio_ingest_user) != ""
    error_message = "minio_ingest_user must be set."
  }
}

variable "minio_ingest_secret" {
  description = "MinIO secret for ingest user"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.minio_ingest_secret)) >= 12
    error_message = "minio_ingest_secret must be at least 12 characters."
  }
}

variable "minio_transform_user" {
  description = "MinIO user for transform services"
  type        = string
  default     = "minio_transform"
  nullable    = false

  validation {
    condition     = trimspace(var.minio_transform_user) != ""
    error_message = "minio_transform_user must be set."
  }
}

variable "minio_transform_secret" {
  description = "MinIO secret for transform user"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.minio_transform_secret)) >= 12
    error_message = "minio_transform_secret must be at least 12 characters."
  }
}

variable "minio_trino_write_user" {
  description = "MinIO user for Trino write connector"
  type        = string
  default     = "minio_trino_write"
  nullable    = false

  validation {
    condition     = trimspace(var.minio_trino_write_user) != ""
    error_message = "minio_trino_write_user must be set."
  }
}

variable "minio_trino_write_secret" {
  description = "MinIO secret for Trino write user"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.minio_trino_write_secret)) >= 12
    error_message = "minio_trino_write_secret must be at least 12 characters."
  }
}

variable "minio_trino_read_user" {
  description = "MinIO user for Trino read path"
  type        = string
  default     = "minio_trino_read"
  nullable    = false

  validation {
    condition     = trimspace(var.minio_trino_read_user) != ""
    error_message = "minio_trino_read_user must be set."
  }
}

variable "minio_trino_read_secret" {
  description = "MinIO secret for Trino read user"
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.minio_trino_read_secret)) >= 12
    error_message = "minio_trino_read_secret must be at least 12 characters."
  }
}
