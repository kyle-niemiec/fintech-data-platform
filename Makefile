.DEFAULT_GOAL := help

COMPOSE_FILE := infra/docker-compose.yaml
INFRA_ENV_FILE := infra/.env
TERRAFORM_BOOTSTRAP_DIR := infra/terraform/bootstrap
TERRAFORM_IDENTITY_DIR := infra/terraform/identity
API_DIR := backend
API_BIN_DIR := .venv/bin

include $(INFRA_ENV_FILE)

export POSTGRES_DB POSTGRES_HOST POSTGRES_PORT
export EVENT_STORE_DB EVENT_STORE_DB_HOST EVENT_STORE_DB_PORT
export EVENT_STORE_DB_ROOT_USER EVENT_STORE_DB_ROOT_PASSWORD
export EVENT_QUERY_DB_USER EVENT_QUERY_DB_PASSWORD
export KEYCLOAK_URL KEYCLOAK_REALM KEYCLOAK_DEMO_SERVICE_CLIENT_ID

include infra/make/terraform-env.mk

.PHONY: help infra-up infra-down infra-ps infra-clean \
	infra-tf-init infra-pg-up infra-kc-up infra-tf-bootstrap infra-tf-apply \
	terraform-plan terraform-plan-bootstrap terraform-plan-identity api-install api-dev db-psql

help:
	@printf "Available targets:\n"
	@printf "  infra-up                 Show the manual staged infra startup sequence\n"
	@printf "  infra-tf-init            Initialize Terraform providers (bootstrap + identity)\n"
	@printf "  infra-pg-up              Start Postgres + event-store DB + MinIO + Redpanda containers\n"
	@printf "  infra-tf-bootstrap       Apply Terraform bootstrap phase (Postgres + MinIO)\n"
	@printf "  infra-kc-up              Start Keycloak container\n"
	@printf "  infra-tf-apply           Apply Terraform identity phase (Keycloak)\n"
	@printf "  infra-down               Stop infrastructure containers\n"
	@printf "  infra-ps                 Show infrastructure container status\n"
	@printf "  infra-clean              Stop containers and remove local Postgres/Event Store/MinIO/Redpanda volumes and Terraform state\n"
	@printf "  terraform-plan           Show Terraform plans for bootstrap + identity\n"
	@printf "  terraform-plan-bootstrap Show Terraform plan for bootstrap phase\n"
	@printf "  terraform-plan-identity  Show Terraform plan for identity phase\n"
	@printf "  api-install              Install backend Python dependencies into backend/.venv\n"
	@printf "  api-dev                  Run the FastAPI app with reload enabled\n"
	@printf "  db-psql                  Open a psql shell inside the Postgres container\n"

infra-up:
	@printf "Run these commands in order:\n"
	@printf "  1) make infra-tf-init\n"
	@printf "  2) make infra-pg-up\n"
	@printf "  3) make infra-tf-bootstrap\n"
	@printf "  4) make infra-kc-up\n"
	@printf "  5) make infra-tf-apply\n"

infra-tf-init:
	cd $(TERRAFORM_BOOTSTRAP_DIR) && KEYCLOAK_REALM=master terraform init
	cd $(TERRAFORM_IDENTITY_DIR) && KEYCLOAK_REALM=master terraform init

infra-pg-up:
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) up -d postgres event_store_db minio redpanda

infra-tf-bootstrap:
	cd $(TERRAFORM_BOOTSTRAP_DIR) && KEYCLOAK_REALM=master terraform apply -auto-approve

infra-kc-up:
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) up -d keycloak

infra-tf-apply:
	cd $(TERRAFORM_IDENTITY_DIR) && KEYCLOAK_REALM=master terraform apply -auto-approve

infra-down:
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) down

infra-ps:
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) ps

infra-clean:
	$(MAKE) infra-down
	-docker volume rm infra_postgres_data
	-docker volume rm infra_event_store_data
	-docker volume rm infra_minio_data
	-docker volume rm infra_redpanda_data
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
	cd $(TERRAFORM_BOOTSTRAP_DIR) && KEYCLOAK_REALM=master terraform plan

terraform-plan-identity:
	cd $(TERRAFORM_IDENTITY_DIR) && KEYCLOAK_REALM=master terraform plan

api-install:
	cd $(API_DIR) && $(API_BIN_DIR)/pip install -r requirements.txt pytest

api-dev:
	cd $(API_DIR) && $(API_BIN_DIR)/uvicorn app.main:app --reload

db-psql:
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) exec postgres psql -U '$(value POSTGRES_ROOT_USER)' -d '$(value POSTGRES_DB)'
