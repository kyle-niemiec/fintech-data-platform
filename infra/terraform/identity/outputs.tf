output "keycloak_realm_name" {
  description = "Provisioned Keycloak realm"
  value       = keycloak_realm.meridian.realm
}

output "keycloak_demo_service_client_id" {
  description = "Internal client id used for demo actor selection"
  value       = keycloak_openid_client.demo_service.client_id
}

output "keycloak_finance_role_name" {
  description = "Role name assigned to demo finance personas"
  value       = keycloak_role.finance.name
}

output "redpanda_service_identities" {
  description = "Redpanda service identities managed in the identity phase"
  value = {
    excel        = var.redpanda_excel_service_user
    cdc          = var.redpanda_cdc_service_user
    fraud        = var.redpanda_fraud_service_user
    salesforce   = var.redpanda_salesforce_service_user
    orchestrator = var.redpanda_orchestrator_service_user
    ui           = var.redpanda_ui_service_user
  }
}

output "redpanda_topic_partition_defaults" {
  description = "Canonical local partition defaults applied to Redpanda topic families"
  value = {
    ingest   = var.redpanda_ingest_topic_partitions
    pipeline = var.redpanda_pipeline_topic_partitions
    cdc      = var.redpanda_cdc_topic_partitions
    alerts   = var.redpanda_alert_topic_partitions
  }
}
