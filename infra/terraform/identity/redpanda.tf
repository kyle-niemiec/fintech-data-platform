locals {
  redpanda_ingest_topics = [
    "ingest.excel.uploaded.v1",
    "ingest.excel.scanned.pass.v1",
    "ingest.excel.scanned.fail.v1",
    "ingest.excel.raw.ready.v1",
    "ingest.excel.quarantined.v1",
    "ingest.excel.bronze.ready.v1",
    "ingest.salesforce.raw.ready.v1",
    "ingest.salesforce.bronze.ready.v1"
  ]
  redpanda_cdc_topics = [
    "cdc.oltp.raw.v1",
    "cdc.oltp.assessed.v1",
    "cdc.oltp.bronze.ready.v1"
  ]
  redpanda_pipeline_topics = [
    "pipeline.silver.completed.v1",
    "pipeline.silver.failed.v1",
    "pipeline.gold.completed.v1",
    "pipeline.gold.failed.v1"
  ]
  redpanda_alert_topics = [
    "ui.alert.raised.v1"
  ]
}

resource "terraform_data" "redpanda_identity_and_acls" {
  triggers_replace = [
    sha256(jsonencode({
      bootstrap_servers = var.redpanda_bootstrap_servers
      admin_hosts       = var.redpanda_admin_hosts
      admin_user        = var.redpanda_admin_user
      ingest_partitions = var.redpanda_ingest_topic_partitions
      cdc_partitions    = var.redpanda_cdc_topic_partitions
      pipeline_parts    = var.redpanda_pipeline_topic_partitions
      alert_parts       = var.redpanda_alert_topic_partitions
      ingest_topics     = local.redpanda_ingest_topics
      cdc_topics        = local.redpanda_cdc_topics
      pipeline_topics   = local.redpanda_pipeline_topics
      alert_topics      = local.redpanda_alert_topics
      consumer_groups = {
        excel_scanner     = "excel-scanner-v1"
        airflow           = "excel-validation-trigger-v1"
        excel_bronze      = "excel-bronze-writer-v1"
        fraud             = "fraud-worker-v1"
        salesforce_bronze = "salesforce-bronze-writer-v1"
        orchestrator      = "curated-orchestrator-v1"
        curated_silver    = "airflow-curated-silver-v1"
        curated_gold      = "airflow-curated-gold-v1"
        ui_alerts         = "ui-alert-feed-v1"
      }
      users = {
        excel_upload      = var.redpanda_excel_service_user
        excel_scanner     = var.redpanda_excel_scanner_user
        airflow           = var.redpanda_airflow_user
        excel_bronze      = var.redpanda_excel_bronze_user
        cdc               = var.redpanda_cdc_service_user
        fraud             = var.redpanda_fraud_service_user
        salesforce        = var.redpanda_salesforce_service_user
        salesforce_bronze = var.redpanda_salesforce_bronze_user
        orchestrator      = var.redpanda_orchestrator_service_user
        ui                = var.redpanda_ui_service_user
      }
      user_password_hashes = {
        excel_upload      = sha256(var.redpanda_excel_service_password)
        excel_scanner     = sha256(var.redpanda_excel_scanner_password)
        airflow           = sha256(var.redpanda_airflow_password)
        excel_bronze      = sha256(var.redpanda_excel_bronze_password)
        cdc               = sha256(var.redpanda_cdc_service_password)
        fraud             = sha256(var.redpanda_fraud_service_password)
        salesforce        = sha256(var.redpanda_salesforce_service_password)
        salesforce_bronze = sha256(var.redpanda_salesforce_bronze_password)
        orchestrator      = sha256(var.redpanda_orchestrator_service_password)
        ui                = sha256(var.redpanda_ui_service_password)
      }
    }))
  ]

  provisioner "local-exec" {
    command     = "./scripts/apply-redpanda-identity.sh"
    working_dir = path.module
    environment = {
      REDPANDA_BOOTSTRAP_SERVERS                = var.redpanda_bootstrap_servers
      REDPANDA_ADMIN_HOSTS                      = var.redpanda_admin_hosts
      REDPANDA_ADMIN_USER                       = var.redpanda_admin_user
      REDPANDA_ADMIN_PASSWORD                   = var.redpanda_admin_password
      REDPANDA_INGEST_TOPIC_PARTITIONS          = tostring(var.redpanda_ingest_topic_partitions)
      REDPANDA_CDC_TOPIC_PARTITIONS             = tostring(var.redpanda_cdc_topic_partitions)
      REDPANDA_PIPELINE_TOPIC_PARTITIONS        = tostring(var.redpanda_pipeline_topic_partitions)
      REDPANDA_ALERT_TOPIC_PARTITIONS           = tostring(var.redpanda_alert_topic_partitions)
      REDPANDA_INGEST_TOPICS                    = join(",", local.redpanda_ingest_topics)
      REDPANDA_CDC_TOPICS                       = join(",", local.redpanda_cdc_topics)
      REDPANDA_PIPELINE_TOPICS                  = join(",", local.redpanda_pipeline_topics)
      REDPANDA_ALERT_TOPICS                     = join(",", local.redpanda_alert_topics)
      REDPANDA_EXCEL_SERVICE_USER               = var.redpanda_excel_service_user
      REDPANDA_EXCEL_SERVICE_PASSWORD           = var.redpanda_excel_service_password
      REDPANDA_EXCEL_SCANNER_USER               = var.redpanda_excel_scanner_user
      REDPANDA_EXCEL_SCANNER_PASSWORD           = var.redpanda_excel_scanner_password
      REDPANDA_AIRFLOW_USER                     = var.redpanda_airflow_user
      REDPANDA_AIRFLOW_PASSWORD                 = var.redpanda_airflow_password
      REDPANDA_EXCEL_BRONZE_USER                = var.redpanda_excel_bronze_user
      REDPANDA_EXCEL_BRONZE_PASSWORD            = var.redpanda_excel_bronze_password
      REDPANDA_CDC_SERVICE_USER                 = var.redpanda_cdc_service_user
      REDPANDA_CDC_SERVICE_PASSWORD             = var.redpanda_cdc_service_password
      REDPANDA_FRAUD_SERVICE_USER               = var.redpanda_fraud_service_user
      REDPANDA_FRAUD_SERVICE_PASSWORD           = var.redpanda_fraud_service_password
      REDPANDA_SALESFORCE_SERVICE_USER          = var.redpanda_salesforce_service_user
      REDPANDA_SALESFORCE_SERVICE_PASSWORD      = var.redpanda_salesforce_service_password
      REDPANDA_SALESFORCE_BRONZE_USER           = var.redpanda_salesforce_bronze_user
      REDPANDA_SALESFORCE_BRONZE_PASSWORD       = var.redpanda_salesforce_bronze_password
      REDPANDA_ORCHESTRATOR_SERVICE_USER        = var.redpanda_orchestrator_service_user
      REDPANDA_ORCHESTRATOR_SERVICE_PASSWORD    = var.redpanda_orchestrator_service_password
      REDPANDA_UI_SERVICE_USER                  = var.redpanda_ui_service_user
      REDPANDA_UI_SERVICE_PASSWORD              = var.redpanda_ui_service_password
      REDPANDA_FRAUD_CONSUMER_GROUP             = "fraud-worker-v1"
      REDPANDA_EXCEL_SCANNER_CONSUMER_GROUP     = "excel-scanner-v1"
      REDPANDA_AIRFLOW_CONSUMER_GROUP           = "excel-validation-trigger-v1"
      REDPANDA_EXCEL_BRONZE_CONSUMER_GROUP      = "excel-bronze-writer-v1"
      REDPANDA_SALESFORCE_BRONZE_CONSUMER_GROUP = "salesforce-bronze-writer-v1"
      REDPANDA_ORCHESTRATOR_CONSUMER_GROUP      = "curated-orchestrator-v1"
      REDPANDA_CURATED_SILVER_CONSUMER_GROUP    = "airflow-curated-silver-v1"
      REDPANDA_CURATED_GOLD_CONSUMER_GROUP      = "airflow-curated-gold-v1"
      REDPANDA_UI_ALERTS_CONSUMER_GROUP         = "ui-alert-feed-v1"
    }
  }
}
