from config.settings import Settings
from config.env import Environment
from packages.schemas.system import HealthResponse, ServiceStatus, DatabaseStatus


def test_settings_default_values():
    settings = Settings(
        APP_ENV=Environment.TEST,
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
    )
    assert settings.APP_NAME == "Financial AI Operator"
    assert settings.is_test is True
    assert settings.is_production is False
    assert "http://localhost:3000" in settings.CORS_ORIGINS


def test_health_response_schema():
    db_status = DatabaseStatus(
        connected=True,
        engine="sqlite",
        latency_ms=1.23,
    )
    health = HealthResponse(
        status=ServiceStatus.HEALTHY,
        version="0.1.0",
        environment="test",
        database=db_status,
    )
    assert health.status == ServiceStatus.HEALTHY
    assert health.database.connected is True
    assert health.database.latency_ms == 1.23
