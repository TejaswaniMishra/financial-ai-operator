import time
from fastapi import APIRouter, Depends
from config.settings import Settings, get_settings
from database.connection import check_db_connectivity
from packages.schemas.system import ServiceStatus, SystemInfoResponse

router = APIRouter(prefix="/system", tags=["System"])
_app_start_time = time.time()


@router.get(
    "/info",
    response_model=SystemInfoResponse,
    summary="System information and service status",
    description="Returns detailed platform status, active service modules, and uptime.",
)
async def get_system_info(settings: Settings = Depends(get_settings)) -> SystemInfoResponse:
    db_status = await check_db_connectivity()
    db_service_status = ServiceStatus.HEALTHY if db_status.connected else ServiceStatus.DEGRADED

    active_services = {
        "api_gateway": ServiceStatus.HEALTHY,
        "database_layer": db_service_status,
        "schema_validator": ServiceStatus.HEALTHY,
        "deterministic_engine": ServiceStatus.HEALTHY,
    }

    uptime = time.time() - _app_start_time

    return SystemInfoResponse(
        name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV.value,
        uptime_seconds=round(uptime, 2),
        active_services=active_services,
        architecture_phase="Milestone 1: Monorepo Foundation",
    )
