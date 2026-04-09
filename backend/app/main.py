from fastapi import FastAPI

from app.config import settings
from app.routes.artifact import router as artifact_router
from app.routes.ingestion_run import router as ingestion_run_router
from app.routes.lineage_record import router as lineage_record_router

app = FastAPI(
    title="Fintech Data Platform API",
    swagger_ui_init_oauth={
        "clientId": settings.keycloak_swagger_client_id,
        "usePkceWithAuthorizationCodeGrant": True,
    },
)

app.include_router(ingestion_run_router)
app.include_router(artifact_router)
app.include_router(lineage_record_router)
