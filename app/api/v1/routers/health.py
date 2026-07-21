from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/", response_model=HealthResponse)
async def health():
    """Basic Health check"""
    health_response = HealthResponse(status="OK", service="HEALTHY")

    return health_response
