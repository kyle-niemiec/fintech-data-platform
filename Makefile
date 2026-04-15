.DEFAULT_GOAL := help

COMPOSE_FILES := \
	infra/docker-compose.yaml \
	infra/compose/foundation.yaml \
	infra/compose/orchestration.yaml \
	infra/compose/excel-pipeline.yaml \
	infra/compose/cdc-pipeline.yaml \
	infra/compose/api.yaml \
	infra/compose/ui.yaml
COMPOSE_FILES_DEV := \
	$(COMPOSE_FILES) \
	infra/compose/dev/minio-console-access.yaml \
	infra/compose/dev/pgadmin.yaml
INFRA_ENV_FILE := infra/.env
TERRAFORM_BOOTSTRAP_DIR := infra/terraform/bootstrap
TERRAFORM_IDENTITY_DIR := infra/terraform/identity
TF_RUNNER_SERVICE := terraform_runner
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

INFRA_UP_STEPS := 1 2 3 4 5 6 7 8 9 10
INFRA_UP_STEP := $(strip $(firstword $(filter $(INFRA_UP_STEPS),$(MAKECMDGOALS))))

.PHONY: help infra-up infra-up-dev infra-down infra-down-dev infra-ps infra-ps-dev infra-clean \
	infra-tf-init infra-pg-up infra-kc-up infra-tf-bootstrap infra-tf-apply \
	infra-excel-pipeline infra-cdc-pipeline infra-api-up infra-ui-up infra-pgadmin-up \
	terraform-plan terraform-plan-bootstrap terraform-plan-identity \
	db-psql-core db-psql-event-store db-psql-oltp \
	1 2 3 4 5 6 7 8 9 10

help:
	@printf "Available targets:\n"
	@printf "  infra-up                 Run staged startup steps 1-9\n"
	@printf "  infra-up-dev             Run staged startup steps 1-9 with dev overlays (MinIO console :9000/:9001, pgAdmin :5050)\n"
	@printf "  infra-up <1-9>           Run one startup step (e.g. make infra-up 3)\n"
	@printf "  compose stack            base + foundation + orchestration + excel-pipeline + api + ui\n"
	@printf "  infra-tf-init            Initialize Terraform providers in Docker (bootstrap + identity)\n"
	@printf "  infra-pg-up              Start Postgres + event-store DB + Vault/KES + MinIO + Redpanda containers\n"
	@printf "  infra-tf-bootstrap       Apply Terraform bootstrap phase in Docker (Postgres + MinIO + notifications)\n"
	@printf "  infra-kc-up              Start Keycloak container\n"
	@printf "  infra-tf-apply           Apply Terraform identity phase in Docker (Keycloak + Redpanda ACLs)\n"
	@printf "  infra-excel-pipeline     Start and validate Airflow + ClamAV + Excel scanner/trigger/bronze services\n"
	@printf "  infra-cdc-pipeline       Start and validate OLTP + Debezium + fraud worker + CDC bronze writer\n"
	@printf "  infra-api-up             Start and validate read-only UI query API service\n"
	@printf "  infra-ui-up              Build and start the React demo UI (nginx on :3000)\n"
	@printf "  infra-pgadmin-up         Start dev-only pgAdmin overlay on :5050 (requires dev compose files)\n"
	@printf "  infra-down               Stop infrastructure containers\n"
	@printf "  infra-down-dev           Stop infrastructure containers (dev UI access stack)\n"
	@printf "  infra-ps                 Show infrastructure container status\n"
	@printf "  infra-ps-dev             Show infrastructure container status (dev UI access stack)\n"
	@printf "  infra-clean              Stop containers and remove local Postgres/Event Store/MinIO/Redpanda volumes and Terraform state\n"
	@printf "  terraform-plan           Show Terraform plans for bootstrap + identity\n"
	@printf "  terraform-plan-bootstrap Show Terraform plan for bootstrap phase\n"
	@printf "  terraform-plan-identity  Show Terraform plan for identity phase\n"
	@printf "  db-psql-core             Open a psql shell in the core Postgres instance\n"
	@printf "  db-psql-event-store      Open a psql shell in the event-store Postgres instance\n"

infra-up:
	@if [ -z "$(INFRA_UP_STEP)" ]; then \
		$(MAKE) infra-tf-init; \
		$(MAKE) infra-pg-up; \
		$(MAKE) infra-tf-bootstrap; \
		$(MAKE) infra-kc-up; \
		$(MAKE) infra-tf-apply; \
		$(MAKE) infra-excel-pipeline; \
		$(MAKE) infra-cdc-pipeline; \
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
		$(MAKE) infra-api-up; \
	elif [ "$(INFRA_UP_STEP)" = "9" ]; then \
		$(MAKE) infra-ui-up; \
	elif [ "$(INFRA_UP_STEP)" = "10" ]; then \
		$(MAKE) infra-ps; \
	else \
		printf "Invalid infra-up step '%s'. Use 1-10.\n" "$(INFRA_UP_STEP)" >&2; \
		exit 2; \
	fi

infra-up-dev:
	@$(MAKE) COMPOSE="$(COMPOSE_DEV)" infra-up
	make infra-pgadmin-up

1 2 3 4 5 6 7 8 9 10:
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
	$(COMPOSE) up -d airflow_postgres airflow_init airflow_scheduler airflow_webserver clamav excel_scanner excel_validation_trigger excel_bronze_writer
	@attempt=1; max_attempts=60; \
	while true; do \
		airflow_health=$$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' fintech_airflow_webserver 2>/dev/null || echo missing); \
		clamav_health=$$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' fintech_clamav 2>/dev/null || echo missing); \
		if [ "$$airflow_health" = "healthy" ] && [ "$$clamav_health" = "healthy" ]; then \
			break; \
		fi; \
		if [ $$attempt -ge $$max_attempts ]; then \
			printf "infra-excel-pipeline timed out waiting for health checks (airflow_webserver=%s clamav=%s).\n" "$$airflow_health" "$$clamav_health" >&2; \
			exit 1; \
		fi; \
		attempt=$$((attempt + 1)); \
		sleep 5; \
	done; \
	for container in fintech_airflow_scheduler fintech_excel_scanner fintech_excel_validation_trigger fintech_excel_bronze_writer; do \
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

infra-api-up:
	$(call banner,Starting read-only UI query API service...)
	$(COMPOSE) up -d api
	@state=$$(docker inspect -f '{{.State.Status}}' fintech_api 2>/dev/null || echo missing); \
	if [ "$$state" != "running" ]; then \
		printf "infra-api-up service check failed: fintech_api state=%s\n" "$$state" >&2; \
		exit 1; \
	fi

infra-ui-up:
	$(call banner,Building and starting React demo UI on :3000...)
	$(COMPOSE) up -d --build ui
	@state=$$(docker inspect -f '{{.State.Status}}' fintech_ui 2>/dev/null || echo missing); \
	if [ "$$state" != "running" ]; then \
		printf "infra-ui-up service check failed: fintech_ui state=%s\n" "$$state" >&2; \
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
	$(COMPOSE) ps

infra-ps-dev:
	$(COMPOSE_DEV) ps

infra-clean:
	$(COMPOSE_DEV) down --volumes --remove-orphans
	-docker volume rm postgres_data event_store_data minio_data redpanda_data kms_shared
	-docker volume rm infra_postgres_data infra_event_store_data infra_minio_data infra_redpanda_data infra_kms_shared
	-docker volume rm oltp_data debezium_offsets infra_oltp_data infra_debezium_offsets
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
