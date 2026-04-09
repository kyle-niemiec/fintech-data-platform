resource "postgresql_role" "operator_runtime" {
  name     = var.operator_db_user
  login    = true
  password = var.operator_db_password
  roles    = ["control_plane_writer"]
}

resource "postgresql_role" "observer_runtime" {
  name     = var.observer_db_user
  login    = true
  password = var.observer_db_password
  roles    = ["control_plane_reader"]
}

resource "postgresql_role" "pipeline_runtime" {
  name     = var.pipeline_db_user
  login    = true
  password = var.pipeline_db_password
  roles    = ["ingestion_writer"]
}

resource "postgresql_role" "keycloak_runtime" {
  name     = var.kc_db_user
  login    = true
  password = var.kc_db_password
}

resource "postgresql_schema" "keycloak" {
  database = var.postgres_db
  name     = "keycloak"
  owner    = postgresql_role.keycloak_runtime.name
}
