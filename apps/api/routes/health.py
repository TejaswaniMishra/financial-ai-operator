from fastapi import APIRouter, Depends
from config.settings import Settings, get_settings
from database.connection import check_db_connectivity
from packages.schemas.system import HealthResponse, ServiceStatus

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check probe",
    description="Returns service health status, environment, and database connectivity.",
)
async def get_health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    db_status = await check_db_connectivity()
    status = ServiceStatus.HEALTHY if db_status.connected else ServiceStatus.DEGRADED

    return HealthResponse(
        status=status,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV.value,
        database=db_status,
    )
