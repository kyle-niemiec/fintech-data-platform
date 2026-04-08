.DEFAULT_GOAL := help

COMPOSE_FILE := infra/docker-compose.yaml
INFRA_ENV_FILE := infra/.env
API_DIR := backend
API_BIN_DIR := .venv/bin

-include $(INFRA_ENV_FILE)
export POSTGRES_DB  POSTGRES_HOST  POSTGRES_PORT
export OPERATOR_DB_USER  OPERATOR_DB_PASSWORD
export OBSERVER_DB_USER  OBSERVER_DB_PASSWORD
export PIPELINE_DB_USER  PIPELINE_DB_PASSWORD  PIPELINE_PASSWORD
export AUTH_DB_USER  AUTH_DB_PASSWORD
export OPERATOR_PASSWORD  OBSERVER_PASSWORD

.PHONY: help infra-up infra-down infra-ps api-install api-dev db-psql seed-principals

help:
	@printf "Available targets:\n"
	@printf "  infra-up     Start Postgres and MinIO in the background\n"
	@printf "  infra-down   Stop infrastructure containers\n"
	@printf "  infra-ps     Show infrastructure container status\n"
	@printf "  api-install  Install backend Python dependencies into backend/.venv\n"
	@printf "  api-dev      Run the FastAPI app with reload enabled\n"
	@printf "  db-psql      Open a psql shell inside the Postgres container\n"

infra-up:
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) up -d

infra-down:
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) down

infra-ps:
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) ps

infra-clean:
	make infra-down;
	docker volume rm infra_postgres_data && docker volume rm infra_minio_data;

api-install:
	cd $(API_DIR) && $(API_BIN_DIR)/pip install -r requirements.txt pytest

api-dev:
	cd $(API_DIR) && $(API_BIN_DIR)/uvicorn app.main:app --reload

db-psql:
	docker compose -f $(COMPOSE_FILE) --env-file $(INFRA_ENV_FILE) exec postgres psql -U "$(POSTGRES_ROOT_USER)" -d "$(POSTGRES_DB)"

seed-principals:
	cd $(API_DIR) && PYTHONPATH=. $(API_BIN_DIR)/python scripts/seed_principals.py
