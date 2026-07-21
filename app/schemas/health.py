from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Model for healthcheck"""
    status: str | None = "OK"
    service: str = "HEALTHY"