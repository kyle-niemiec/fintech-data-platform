from fastapi import FastAPI

from app.routes.ui_query import router as ui_query_router

app = FastAPI(title="Fintech Data Platform API")

app.include_router(ui_query_router)
