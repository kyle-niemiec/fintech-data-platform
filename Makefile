.DEFAULT_GOAL := help

COMPOSE_FILES_BASE := \
	infra/docker-compose.yaml \
	infra/compose/foundation.yaml \
	infra/compose/orchestration.yaml \
	infra/compose/excel-pipeline.yaml \
	infra/compose/cdc-pipeline.yaml \
	infra/compose/salesforce-pipeline.yaml \
	infra/compose/curated-pipeline.yaml \
	infra/compose/api.yaml \
	infra/compose/ui.yaml
COMPOSE_FILES := \
	$(COMPOSE_FILES_BASE)
COMPOSE_FILES_DEV := \
	$(COMPOSE_FILES_BASE) \
	infra/compose/dev/build-network-host.yaml \
	infra/compose/dev/demo-ui-access.yaml \
	infra/compose/dev/minio-console-access.yaml \
	infra/compose/dev/pgadmin.yaml
INFRA_ENV_FILE := infra/.env
TERRAFORM_BOOTSTRAP_DIR := infra/terraform/bootstrap
TERRAFORM_IDENTITY_DIR := infra/terraform/identity
TF_RUNNER_SERVICE := terraform_runner
# Use the caller's host UID/GID so bind-mounted Terraform state files remain writable.
HOST_UID ?= $(shell id -u)
HOST_GID ?= $(shell id -g)
export HOST_UID HOST_GID
COMPOSE := docker compose $(foreach file,$(COMPOSE_FILES),-f $(file)) --env-file $(INFRA_ENV_FILE)
COMPOSE_DEV := docker compose $(foreach file,$(COMPOSE_FILES_DEV),-f $(file)) --env-file $(INFRA_ENV_FILE)

include $(INFRA_ENV_FILE)

NO_FORMAT=\033[0m
F_BOLD=\033[1m
C_HOTPINK=\033[38;5;206m
C_AQUA=\033[38;5;14m

define banner
@printf "\n${F_BOLD}${C_HOTPINK}🭪 Fintech Demo 🭨${NO_FORMAT} ${F_BOLD}${C_AQUA}🭬%s🭮${NO_FORMAT}\n\n" "$(1)"
endef

INFRA_UP_STEPS := 1 2 3 4 5 6 7 8 9 10 11 12
INFRA_UP_STEP := $(strip $(firstword $(filter $(INFRA_UP_STEPS),$(MAKECMDGOALS))))

.PHONY: help infra-up infra-up-dev infra-down infra-down-dev infra-ps infra-ps-dev infra-ps-watch infra-ps-watch-dev infra-clean \
	infra-tf-init infra-pg-up infra-kc-up infra-tf-bootstrap infra-tf-apply \
	infra-excel-pipeline infra-cdc-pipeline infra-salesforce-pipeline infra-curated-pipeline \
	infra-api-up infra-ui-up infra-pgadmin-up \
	terraform-plan terraform-plan-bootstrap terraform-plan-identity \
	db-psql-core db-psql-event-store db-psql-oltp \
	replay-group consumer-lag \
	1 2 3 4 5 6 7 8 9 10 11 12

help:
	@printf "Available targets:\n"
	@printf "  infra-up                 Run staged startup steps 1-12 (production demo UI on :443)\n"
	@printf "  infra-up-dev             Run staged startup steps 1-12 with dev overlays (UI/API/admin local ports, MinIO console :9000/:9001, pgAdmin :5050)\n"
	@printf "  infra-up <1-12>          Run one startup step (e.g. make infra-up 3)\n"
	@printf "  compose stack            base + foundation + orchestration + excel-pipeline + api + ui\n"
	@printf "  infra-tf-init            Initialize Terraform providers in Docker (bootstrap + identity)\n"
	@printf "  infra-pg-up              Start Postgres + event-store DB + Vault/KES + MinIO + Redpanda containers\n"
	@printf "  infra-tf-bootstrap       Apply Terraform bootstrap phase in Docker (Postgres + MinIO + notifications)\n"
	@printf "  infra-kc-up              Start Keycloak container\n"
	@printf "  infra-tf-apply           Apply Terraform identity phase in Docker (Keycloak + Redpanda ACLs)\n"
	@printf "  infra-excel-pipeline     Start and validate Airflow + ClamAV + Excel scanner/trigger/bronze services\n"
	@printf "  infra-cdc-pipeline       Start and validate OLTP + Debezium + fraud worker + CDC bronze writer\n"
	@printf "  infra-salesforce-pipeline Start and validate Salesforce mock + bronze writer\n"
	@printf "  infra-curated-pipeline   Start Iceberg REST catalog + Trino coordinator for silver/gold transforms\n"
	@printf "  infra-api-up             Start and validate read-only UI query API service\n"
	@printf "  infra-ui-up              Build and start the React demo UI service (nginx)\n"
	@printf "  infra-pgadmin-up         Start dev-only pgAdmin overlay on :5050 (requires dev compose files)\n"
	@printf "  infra-down               Stop infrastructure containers\n"
	@printf "  infra-down-dev           Stop infrastructure containers (dev UI access stack)\n"
	@printf "  infra-ps                 Show infrastructure container status\n"
	@printf "  infra-ps-dev             Show infrastructure container status (dev UI access stack)\n"
	@printf "  infra-ps-watch           Show a refreshing view of infrastructure container logs\n"
	@printf "  infra-ps-watch-dev       Show a refreshing view of infrastructure container logs (dev UI access stack)\n"
	@printf "  infra-clean              Stop containers, remove local data volumes (incl. Airflow metadata), and clear Terraform state\n"
	@printf "  terraform-plan           Show Terraform plans for bootstrap + identity\n"
	@printf "  terraform-plan-bootstrap Show Terraform plan for bootstrap phase\n"
	@printf "  terraform-plan-identity  Show Terraform plan for identity phase\n"
	@printf "  db-psql-core             Open a psql shell in the core Postgres instance\n"
	@printf "  db-psql-event-store      Open a psql shell in the event-store Postgres instance\n"
	@printf "  consumer-lag             Show live consumer group lag for all known groups (rpk)\n"
	@printf "  replay-group             Seek a consumer group back to offset 0 — usage: make replay-group GROUP=<name>\n"

infra-up:
	@if [ -z "$(INFRA_UP_STEP)" ]; then \
		set -e; \
		$(MAKE) infra-tf-init; \
		$(MAKE) infra-pg-up; \
		$(MAKE) infra-tf-bootstrap; \
		$(MAKE) infra-kc-up; \
		$(MAKE) infra-tf-apply; \
		$(MAKE) infra-excel-pipeline; \
		$(MAKE) infra-cdc-pipeline; \
		$(MAKE) infra-salesforce-pipeline; \
		$(MAKE) infra-curated-pipeline; \
		$(MAKE) infra-api-up; \
		$(MAKE) infra-ui-up; \
		$(MAKE) infra-ps; \
	elif [ "$(INFRA_UP_STEP)" = "1" ]; then \
		$(MAKE) infra-tf-init; \
	elif [ "$(INFRA_UP_STEP)" = "2" ]; then \
		$(MAKE) infra-pg-up; \
	elif [ "$(INFRA_UP_STEP)" = "3" ]; then \
		$(MAKE) infra-tf-bootstrap; \
	elif [ "$(INFRA_UP_STEP)" = "4" ]; then \
		$(MAKE) infra-kc-up; \
	elif [ "$(INFRA_UP_STEP)" = "5" ]; then \
		$(MAKE) infra-tf-apply; \
	elif [ "$(INFRA_UP_STEP)" = "6" ]; then \
		$(MAKE) infra-excel-pipeline; \
	elif [ "$(INFRA_UP_STEP)" = "7" ]; then \
		$(MAKE) infra-cdc-pipeline; \
	elif [ "$(INFRA_UP_STEP)" = "8" ]; then \
		$(MAKE) infra-salesforce-pipeline; \
	elif [ "$(INFRA_UP_STEP)" = "9" ]; then \
		$(MAKE) infra-curated-pipeline; \
	elif [ "$(INFRA_UP_STEP)" = "10" ]; then \
		$(MAKE) infra-api-up; \
	elif [ "$(INFRA_UP_STEP)" = "11" ]; then \
		$(MAKE) infra-ui-up; \
	elif [ "$(INFRA_UP_STEP)" = "12" ]; then \
		$(MAKE) infra-ps; \
	else \
		printf "Invalid infra-up step '%s'. Use 1-12.\n" "$(INFRA_UP_STEP)" >&2; \
		exit 2; \
	fi

infra-up-dev:
	@$(MAKE) COMPOSE="$(COMPOSE_DEV)" infra-up
	make infra-pgadmin-up

1 2 3 4 5 6 7 8 9 10 11 12:
	@:

infra-tf-init:
	$(call banner,Initializing Terraform providers for bootstrap and identity phases...)
	$(COMPOSE) run --rm --build --no-deps $(TF_RUNNER_SERVICE) bootstrap init
	$(COMPOSE) run --rm --build --no-deps $(TF_RUNNER_SERVICE) identity init

infra-pg-up:
	$(call banner,Starting platform and event PostgreSQL instances plus Vault/KES/MinIO/Redpanda...)
	$(COMPOSE) up -d postgres event_store_db vault kes minio redpanda

infra-tf-bootstrap:
	$(call banner,Applying Terraform bootstrap phase (Postgres + MinIO + notifications)...)
	$(COMPOSE) run --rm --build --no-deps $(TF_RUNNER_SERVICE) bootstrap apply -auto-approve

infra-kc-up:
	$(call banner,Starting Keycloak identity provider...)
	$(COMPOSE) up -d keycloak

infra-tf-apply:
	$(call banner,Applying Terraform identity phase (Keycloak realm + Redpanda ACLs)...)
	@attempt=1; max_attempts=12; \
	while true; do \
		if $(COMPOSE) run --rm --build --no-deps $(TF_RUNNER_SERVICE) identity apply -auto-approve; then \
			break; \
		fi; \
		if [ $$attempt -ge $$max_attempts ]; then \
			printf "infra-tf-apply failed after %s attempts.\n" "$$attempt" >&2; \
			exit 1; \
		fi; \
		attempt=$$((attempt + 1)); \
		printf "infra-tf-apply attempt %s/%s failed, retrying in 5s...\n" "$$attempt" "$$max_attempts" >&2; \
		sleep 5; \
	done

infra-excel-pipeline:
	$(call banner,Starting Airflow + ClamAV + Excel scanner/trigger/bronze writer services...)
	$(COMPOSE) up -d --build airflow_postgres airflow_init airflow_dag_processor airflow_scheduler airflow_triggerer airflow_api_server clamav excel_scanner excel_validation_trigger excel_bronze_writer
	@attempt=1; max_attempts=60; \
	while true; do \
		airflow_health=$$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' fintech_airflow_api_server 2>/dev/null || echo missing); \
		clamav_health=$$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' fintech_clamav 2>/dev/null || echo missing); \
		if [ "$$airflow_health" = "healthy" ] && [ "$$clamav_health" = "healthy" ]; then \
			break; \
		fi; \
		if [ $$attempt -ge $$max_attempts ]; then \
			printf "infra-excel-pipeline timed out waiting for health checks (airflow_api_server=%s clamav=%s).\n" "$$airflow_health" "$$clamav_health" >&2; \
			exit 1; \
		fi; \
		attempt=$$((attempt + 1)); \
		sleep 5; \
	done; \
	for container in fintech_airflow_dag_processor fintech_airflow_scheduler fintech_airflow_triggerer fintech_excel_scanner fintech_excel_validation_trigger fintech_excel_bronze_writer; do \
		state=$$(docker inspect -f '{{.State.Status}}' $$container 2>/dev/null || echo missing); \
		if [ "$$state" != "running" ]; then \
			printf "infra-excel-pipeline service check failed: %s state=%s\n" "$$container" "$$state" >&2; \
			exit 1; \
		fi; \
	done

infra-cdc-pipeline:
	$(call banner,Starting OLTP + Debezium + fraud worker + CDC bronze writer services...)
	$(COMPOSE) up -d --build oltp_db oltp_load_generator debezium_server fraud_worker cdc_bronze_writer
	@attempt=1; max_attempts=60; \
	while true; do \
		oltp_health=$$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' fintech_oltp_db 2>/dev/null || echo missing); \
		if [ "$$oltp_health" = "healthy" ]; then \
			break; \
		fi; \
		if [ $$attempt -ge $$max_attempts ]; then \
			printf "infra-cdc-pipeline timed out waiting for oltp_db (status=%s).\n" "$$oltp_health" >&2; \
			exit 1; \
		fi; \
		attempt=$$((attempt + 1)); \
		sleep 5; \
	done; \
	for container in fintech_oltp_load_generator fintech_debezium_server fintech_fraud_worker fintech_cdc_bronze_writer; do \
		state=$$(docker inspect -f '{{.State.Status}}' $$container 2>/dev/null || echo missing); \
		if [ "$$state" != "running" ]; then \
			printf "infra-cdc-pipeline service check failed: %s state=%s\n" "$$container" "$$state" >&2; \
			exit 1; \
		fi; \
	done

infra-salesforce-pipeline:
	$(call banner,Starting Salesforce mock + bronze writer services...)
	$(COMPOSE) up -d --build salesforce_mock salesforce_bronze_writer
	@attempt=1; max_attempts=60; \
	while true; do \
		mock_health=$$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' fintech_salesforce_mock 2>/dev/null || echo missing); \
		if [ "$$mock_health" = "healthy" ]; then \
			break; \
		fi; \
		if [ $$attempt -ge $$max_attempts ]; then \
			printf "infra-salesforce-pipeline timed out waiting for salesforce_mock (status=%s).\n" "$$mock_health" >&2; \
			exit 1; \
		fi; \
		attempt=$$((attempt + 1)); \
		sleep 5; \
	done; \
	state=$$(docker inspect -f '{{.State.Status}}' fintech_salesforce_bronze_writer 2>/dev/null || echo missing); \
	if [ "$$state" != "running" ]; then \
		printf "infra-salesforce-pipeline service check failed: fintech_salesforce_bronze_writer state=%s\n" "$$state" >&2; \
		exit 1; \
	fi

infra-curated-pipeline:
	$(call banner,Starting Iceberg REST catalog + Trino coordinator for curated transforms...)
	$(COMPOSE) up -d iceberg_rest trino trino_curated_init
	@attempt=1; max_attempts=60; \
	while true; do \
		iceberg_health=$$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' fintech_iceberg_rest 2>/dev/null || echo missing); \
		trino_health=$$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' fintech_trino 2>/dev/null || echo missing); \
		trino_init_status=$$(docker inspect -f '{{.State.Status}}' fintech_trino_curated_init 2>/dev/null || echo missing); \
		trino_init_exit_code=$$(docker inspect -f '{{.State.ExitCode}}' fintech_trino_curated_init 2>/dev/null || echo -1); \
		if [ "$$iceberg_health" = "healthy" ] && [ "$$trino_health" = "healthy" ] && [ "$$trino_init_status" = "exited" ] && [ "$$trino_init_exit_code" = "0" ]; then \
			break; \
		fi; \
		if [ "$$trino_init_status" = "exited" ] && [ "$$trino_init_exit_code" != "0" ]; then \
			printf "infra-curated-pipeline failed: trino_curated_init exited with code %s.\n" "$$trino_init_exit_code" >&2; \
			exit 1; \
		fi; \
		if [ $$attempt -ge $$max_attempts ]; then \
			printf "infra-curated-pipeline timed out waiting for readiness (iceberg_rest=%s trino=%s trino_curated_init=%s exit=%s).\n" "$$iceberg_health" "$$trino_health" "$$trino_init_status" "$$trino_init_exit_code" >&2; \
			exit 1; \
		fi; \
		attempt=$$((attempt + 1)); \
		sleep 5; \
	done

infra-api-up:
	$(call banner,Starting read-only UI query API service...)
	$(COMPOSE) up -d api
	@state=$$(docker inspect -f '{{.State.Status}}' fintech_api 2>/dev/null || echo missing); \
	if [ "$$state" != "running" ]; then \
		printf "infra-api-up service check failed: fintech_api state=%s\n" "$$state" >&2; \
		exit 1; \
	fi

infra-ui-up:
	$(call banner,Building and starting React demo UI service...)
	$(COMPOSE) up -d --build ui
	@ui_state=$$(docker inspect -f '{{.State.Status}}' fintech_ui 2>/dev/null || echo missing); \
	if [ "$$ui_state" != "running" ]; then \
		printf "infra-ui-up service check failed: fintech_ui state=%s\n" "$$ui_state" >&2; \
		exit 1; \
	fi

infra-pgadmin-up:
	$(COMPOSE_DEV) up -d pgadmin

infra-down:
	$(COMPOSE) down

infra-down-dev:
	$(COMPOSE_DEV) down

infra-ps:
	$(call banner,Showing infrastructure container status...)
	@$(COMPOSE) ps --format 'table {{.Name}}\t\t{{.Service}}\t\t{{.Status}}\t\t{{.Ports}}'

infra-ps-dev:
	$(call banner,Showing infrastructure container status...)
	@$(COMPOSE_DEV) ps --format 'table {{.Name}}\t{{.Service}}\t{{.CreatedAt}}\t{{.Status}}\t{{.Ports}}'

infra-watch:
	@clear
	@while true; do \
		clear; \
		make --no-print-directory infra-ps; \
		sleep 5; \
	done

infra-watch-dev:
	@clear
	@while true; do \
		clear; \
		make --no-print-directory infra-ps-dev; \
		sleep 5; \
	done

infra-clean:
	@$(COMPOSE_DEV) down --volumes --remove-orphans
	@set -e; \
	for suffix in postgres_data event_store_data minio_data redpanda_data kms_shared airflow_postgres_data oltp_data debezium_offsets; do \
		volumes=$$(docker volume ls --format '{{.Name}}' | grep -E "(^|_)$${suffix}$$" || true); \
		if [ -n "$$volumes" ]; then \
			docker volume rm $$volumes >/dev/null; \
		fi; \
	done
	rm -rf $(TERRAFORM_BOOTSTRAP_DIR)/.terraform
	rm -f $(TERRAFORM_BOOTSTRAP_DIR)/.terraform.lock.hcl
	rm -f $(TERRAFORM_BOOTSTRAP_DIR)/terraform.tfstate
	rm -f $(TERRAFORM_BOOTSTRAP_DIR)/terraform.tfstate.backup
	rm -rf $(TERRAFORM_IDENTITY_DIR)/.terraform
	rm -f $(TERRAFORM_IDENTITY_DIR)/.terraform.lock.hcl
	rm -f $(TERRAFORM_IDENTITY_DIR)/terraform.tfstate
	rm -f $(TERRAFORM_IDENTITY_DIR)/terraform.tfstate.backup

terraform-plan: terraform-plan-bootstrap terraform-plan-identity

terraform-plan-bootstrap:
	$(COMPOSE) run --rm --build --no-deps $(TF_RUNNER_SERVICE) bootstrap plan

terraform-plan-identity:
	$(COMPOSE) run --rm --build --no-deps $(TF_RUNNER_SERVICE) identity plan

db-psql-core:
	$(COMPOSE) exec postgres psql -U '$(value POSTGRES_ROOT_USER)' -d '$(value POSTGRES_DB)'

db-psql-event-store:
	$(COMPOSE) exec event_store_db psql -U '$(value EVENT_STORE_DB_ROOT_USER)' -d '$(value EVENT_STORE_DB)' -p '$(value EVENT_STORE_DB_PORT)'

db-psql-oltp:
	$(COMPOSE) exec oltp_db psql -U '$(value OLTP_ROOT_USER)' -d '$(value OLTP_DB)' -p '$(value OLTP_DB_PORT)'

consumer-lag:
	$(call banner,Showing consumer group lag for all known groups...)
	docker exec fintech_redpanda rpk group describe \
		excel-scanner-v1 excel-trigger-v1 excel-bronze-writer-v1 \
		cdc-fraud-worker-v1 cdc-bronze-writer-v1 \
		salesforce-bronze-writer-v1 \
		airflow-curated-silver-v1 airflow-curated-gold-v1

replay-group:
	$(call banner,Seeking consumer group $(GROUP) back to offset 0...)
	@if [ -z "$(GROUP)" ]; then printf "Usage: make replay-group GROUP=<consumer-group-name>\n" >&2; exit 1; fi
	docker exec fintech_redpanda rpk group seek $(GROUP) --to start
