from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.settings import get_settings
from database.connection import async_engine
from apps.api.routes.health import router as health_router
from apps.api.routes.system import router as system_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: can initialize connection pools or verify tables
    yield
    # Shutdown: dispose database engine connections
    await async_engine.dispose()


def create_app() -> FastAPI:
    """FastAPI Application Factory."""
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Enterprise AI-powered Financial Operations and Reconciliation Platform",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Root health endpoint (standard for Kubernetes / load balancers)
    application.include_router(health_router)

    # Versioned API routes under /api/v1
    application.include_router(health_router, prefix=settings.API_V1_PREFIX)
    from apps.api.routes.transactions import router as transactions_router
    from apps.api.routes.metrics import router as metrics_router
    from apps.api.routes.reconciliation import router as reconciliation_router
    from apps.api.routes.investigations import router as investigations_router
    from apps.api.routes.policies import router as policies_router
    from apps.api.routes.action_requests import router as action_requests_router
    application.include_router(transactions_router, prefix=settings.API_V1_PREFIX)
    application.include_router(metrics_router, prefix=settings.API_V1_PREFIX)
    application.include_router(reconciliation_router, prefix=settings.API_V1_PREFIX)
    application.include_router(investigations_router, prefix=settings.API_V1_PREFIX)
    application.include_router(policies_router, prefix=settings.API_V1_PREFIX)
    application.include_router(action_requests_router, prefix=settings.API_V1_PREFIX)
    application.include_router(system_router, prefix=settings.API_V1_PREFIX)

    @application.get("/", tags=["Root"])
    async def root():
        return {
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "health": "/health",
        }

    return application


app = create_app()
