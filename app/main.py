"""Main orchestrator of routers"""

from fastapi import FastAPI

from app.api.v1.api import api_router

# main app route instance
app = FastAPI()

# This is version v1 endpoints(router paths)
app.include_router(api_router, prefix="/api/v1")