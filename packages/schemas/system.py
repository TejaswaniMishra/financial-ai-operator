from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional
from pydantic import BaseModel, Field


class ServiceStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class DatabaseStatus(BaseModel):
    connected: bool = Field(..., description="Whether database connection is active")
    engine: str = Field(..., description="Database engine type (e.g. postgresql, sqlite)")
    latency_ms: Optional[float] = Field(None, description="Database ping latency in milliseconds")
    error: Optional[str] = Field(None, description="Error message if connection failed")


class HealthResponse(BaseModel):
    status: ServiceStatus = Field(default=ServiceStatus.HEALTHY)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Application deployment environment")
    database: DatabaseStatus = Field(..., description="Database connectivity status")


class SystemInfoResponse(BaseModel):
    name: str = Field(..., description="System application name")
    version: str = Field(..., description="Current system version")
    environment: str = Field(..., description="Operating environment")
    uptime_seconds: float = Field(..., description="System uptime in seconds")
    active_services: Dict[str, ServiceStatus] = Field(..., description="Status of core services")
    architecture_phase: str = Field(default="Milestone 1: Monorepo Foundation")
