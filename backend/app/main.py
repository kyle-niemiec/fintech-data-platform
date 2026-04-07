from fastapi import FastAPI

from app.routes.ingestion_run import router as ingestion_run_router

app = FastAPI(title="Fintech Data Platform API")
app.include_router(ingestion_run_router)
