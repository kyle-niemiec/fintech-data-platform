provider "postgresql" {
  host            = var.postgres_host
  port            = var.postgres_port
  database        = var.postgres_db
  username        = var.postgres_root_user
  password        = var.postgres_root_password
  sslmode         = "disable"
  connect_timeout = 15
  superuser       = true
}

provider "minio" {
  minio_server   = var.minio_server
  minio_user     = var.minio_root_user
  minio_password = var.minio_root_password
  minio_ssl      = false
}
