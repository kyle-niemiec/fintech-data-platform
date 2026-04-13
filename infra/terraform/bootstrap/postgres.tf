resource "postgresql_role" "event_query_runtime" {
  provider = postgresql.event_store
  name     = var.event_query_db_user
  login    = true
  password = var.event_query_db_password
  roles    = ["event_store_reader"]
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
