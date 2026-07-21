"""Collector for all router paths under version v1"""

from fastapi import APIRouter

# All the router imports go here
from app.api.v1.routers.health import router as health_router
from app.api.v1.routers.parser import router as parser_router   # ← НОВОЕ

api_router = APIRouter()

# All router paths go here
api_router.include_router(health_router)
api_router.include_router(parser_router)                        # ← НОВОЕ
# Includes other paths
