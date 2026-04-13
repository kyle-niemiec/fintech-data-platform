.DEFAULT_GOAL := help

COMPOSE_FILE := infra/docker-compose.yaml
INFRA_ENV_FILE := infra/.env
TERRAFORM_BOOTSTRAP_DIR := infra/terraform/bootstrap
TERRAFORM_IDENTITY_DIR := infra/terraform/identity
TF_RUNNER_SERVICE := terraform_runner

include $(INFRA_ENV_FILE)

INFRA_UP_STEPS := 1 2 3 4 5 6
INFRA_UP_STEP := $(strip $(firstword $(filter $(INFRA_UP_STEPS),$(MAKECMDGOALS))))

.PHONY: help infra-up infra-down infra-ps infra-clean \
	infra-tf-init infra-pg-up infra-kc-up infra-tf-bootstrap infra-tf-apply \
	terraform-plan terraform-plan-bootstrap terraform-plan-identity api-install api-dev \
	db-psql-core db-psql-event-store \
	1 2 3 4 5 6

help:
	@printf "Available targets:\n"
	@printf "  infra-up                 Show the staged infra startup sequence\n"
	@printf "  infra-up <1-6>           Run one startup step (e.g. make infra-up 3)\n"
	@printf "  infra-tf-init            Initialize Terraform providers in Docker (bootstrap + identity)\n"
	@printf "  infra-pg-up              Start Postgres + event-store DB + MinIO + Redpanda containers\n"
	@printf "  infra-tf-bootstrap       Apply Terraform bootstrap phase in Docker (Postgres + MinIO)\n"
	@printf "  infra-kc-up              Start Keycloak container\n"
	@printf "  infra-tf-apply           Apply Terraform identity phase in Docker (Keycloak)\n"
	@printf "  infra-down               Stop infrastructure containers\n"
	@printf "  infra-ps                 Show infrastructure container status\n"
	@printf "  infra-clean              Stop containers and remove local Postgres/Event Store/MinIO/Redpanda volumes and Terraform state\n"
	@printf "  terraform-plan           Show Terraform plans for bootstrap + identity\n"
	@printf "  terraform-plan-bootstrap Show Terraform plan for bootstrap phase\n"
	@printf "  terraform-plan-identity  Show Terraform plan for identity phase\n"
	@printf "  api-install              Build the API Docker image\n"
	@printf "  api-dev                  Start the API container with reload enabled\n"
	@printf "  db-psql-core             Open a psql shell in the core Postgres instance\n"
	@printf "  db-psql-event-store      Open a psql shell in the event-store Postgres instance\n"

infra-up:
	@if [ -z "$(INFRA_UP_STEP)" ]; then \
		printf "Run these commands in order:\n"; \
		printf "  1) make infra-tf-init\n"; \
		printf "  2) make infra-pg-up\n"; \
		printf "  3) make infra-tf-bootstrap\n"; \
		printf "  4) make infra-kc-up\n"; \
		printf "  5) make infra-tf-apply\n"; \
		printf "  6) make infra-ps\n"; \
		printf "\nRun a single step:\n"; \
		printf "  make infra-up <1-6>\n"; \
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
		$(MAKE) infra-ps; \
	else \
		printf "Invalid infra-up step '%s'. Use 1-6.\n" "$(INFRA_UP_STEP)" >&2; \
		exit 2; \
	fi

1 2 3 4 5 6:
	@:

infra-tf-init:
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) run --rm --no-deps $(TF_RUNNER_SERVICE) bootstrap init
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) run --rm --no-deps $(TF_RUNNER_SERVICE) identity init

infra-pg-up:
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) up -d postgres event_store_db minio redpanda

infra-tf-bootstrap:
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) run --rm --no-deps $(TF_RUNNER_SERVICE) bootstrap apply -auto-approve

infra-kc-up:
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) up -d keycloak

infra-tf-apply:
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) run --rm --no-deps $(TF_RUNNER_SERVICE) identity apply -auto-approve

infra-down:
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) down

infra-ps:
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) ps

infra-clean:
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) down --volumes --remove-orphans
	-docker volume rm postgres_data event_store_data minio_data redpanda_data
	-docker volume rm infra_postgres_data infra_event_store_data infra_minio_data infra_redpanda_data
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
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) run --rm --no-deps $(TF_RUNNER_SERVICE) bootstrap plan

terraform-plan-identity:
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) run --rm --no-deps $(TF_RUNNER_SERVICE) identity plan

api-install:
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) build api

api-dev:
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) up -d api

db-psql-core:
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) exec postgres psql -U '$(value POSTGRES_ROOT_USER)' -d '$(value POSTGRES_DB)'

db-psql-event-store:
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) exec event_store_db psql -U '$(value EVENT_STORE_DB_ROOT_USER)' -d '$(value EVENT_STORE_DB)' -p '$(value EVENT_STORE_DB_PORT)'
