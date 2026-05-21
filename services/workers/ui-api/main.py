from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routes.demo_oltp import router as demo_oltp_router
from routes.demo_upload import router as demo_upload_router
from routes.ui_query import router as ui_query_router

app = FastAPI(title="Fintech Data Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.ui_origin],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(ui_query_router)
app.include_router(demo_upload_router)
app.include_router(demo_oltp_router)
