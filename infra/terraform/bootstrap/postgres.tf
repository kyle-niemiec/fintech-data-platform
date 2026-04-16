resource "postgresql_role" "event_query_runtime" {
  provider = postgresql.event_store
  name     = var.event_query_db_user
  login    = true
  password = var.event_query_db_password
  roles    = ["event_store_reader"]
}

resource "postgresql_role" "event_append_runtime" {
  provider = postgresql.event_store
  name     = var.event_append_db_user
  login    = true
  password = var.event_append_db_password
  roles    = ["event_store_appender"]
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

resource "postgresql_role" "iceberg_catalog_owner" {
  name     = var.iceberg_catalog_owner_user
  login    = true
  password = var.iceberg_catalog_owner_password
}

resource "postgresql_schema" "iceberg_catalog" {
  database = var.postgres_db
  name     = "iceberg"
  owner    = postgresql_role.iceberg_catalog_owner.name
}
