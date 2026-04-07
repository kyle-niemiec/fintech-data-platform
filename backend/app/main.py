from fastapi import FastAPI

from app.routes.auth import router as auth_router
from app.routes.ingestion_run import router as ingestion_run_router

app = FastAPI(title="Fintech Data Platform API")

# Auth router has no prefix — /token must be at root for OAuth2 spec compliance
app.include_router(auth_router)
app.include_router(ingestion_run_router)
