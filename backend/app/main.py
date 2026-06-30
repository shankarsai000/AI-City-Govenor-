"""
AI City Governor — FastAPI Application Entry Point

Architecture notes:
- Lifespan context manager handles startup/shutdown cleanly (preferred over @app.on_event)
- All routers versioned under /api/v1 for future API evolution
- Exception handlers convert domain exceptions to consistent JSON responses
- Prometheus instrumentation added at startup for all routes automatically
- CORS configured per environment (strict in production)
"""
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import get_settings
from app.core.database import close_database, init_database
from app.core.exceptions import CityGovernorError
from app.core.logging import configure_logging, get_logger
from app.core.redis_client import close_redis, init_redis

settings = get_settings()

# Configure logging before anything else
configure_logging(
    log_level=settings.LOG_LEVEL,
    is_production=settings.is_production,
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Startup: Initialize all infrastructure connections.
    Shutdown: Gracefully close all connections.
    """
    logger.info(
        "AI City Governor starting",
        env=settings.APP_ENV,
        version=settings.APP_VERSION,
    )

    # Initialize infrastructure in dependency order
    await init_database()
    await init_redis()

    # Seed and initialize City State Engine
    from app.city_state.state_manager import CityStateManager
    await CityStateManager.initialize()

    # Initialize ArmorIQ intent enforcement client
    from app.armoriq.client import initialize_client as init_armoriq
    init_armoriq()  # sync — sets up singleton; logs warning if API key absent

    logger.info("All infrastructure initialized. City Governor is operational.")

    # Start domain agents (skip during testing to keep tests isolated/fast)
    if settings.APP_ENV != "test":
        from app.agents import EmergencyAgent, PowerAgent, TrafficAgent, WaterAgent
        from app.governance import GovernanceEngine
        
        # Start Governance Engine
        app.state.governance_engine = GovernanceEngine()
        await app.state.governance_engine.start()
        logger.info("Governance Engine started.")

        # Start agents
        app.state.agents = [
            TrafficAgent(),
            PowerAgent(),
            WaterAgent(),
            EmergencyAgent(),
        ]
        for agent in app.state.agents:
            await agent.start()
        logger.info("All 4 domain agents registered and running.")
    else:
        app.state.governance_engine = None
        app.state.agents = []

    yield  # Application runs here

    # Graceful shutdown
    logger.info("AI City Governor shutting down...")
    from app.armoriq.client import shutdown_client as shutdown_armoriq
    shutdown_armoriq()
    await close_redis()
    await close_database()
    logger.info("Shutdown complete.")


def create_application() -> FastAPI:
    """
    Application factory pattern — creates and configures the FastAPI app.
    Using a factory makes testing easier (can create fresh app per test).
    """
    app = FastAPI(
        title="AI City Governor",
        description=(
            "Multi-Agent Governance Platform for Smart City Infrastructure. "
            "Every agent action is authorized, policy-checked, cryptographically "
            "signed, and immutably audited before execution."
        ),
        version=settings.APP_VERSION,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── Middleware ─────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_origin_regex=r"https?://.*\.trycloudflare\.com",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception Handlers ────────────────────────────────────────────────────
    @app.exception_handler(CityGovernorError)
    async def city_governor_exception_handler(
        request: Request, exc: CityGovernorError
    ) -> JSONResponse:
        logger.warning(
            "Domain exception",
            error_code=exc.error_code,
            message=exc.message,
            path=str(request.url),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(
            "Unhandled exception",
            path=str(request.url),
            exc_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred.",
                "details": {},
            },
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    # Imported here to avoid circular imports at module load
    from app.api.v1 import auth, agents, governance, city_state, audit, approvals, armoriq, dashboard, simulator, digital_twin, decision_graph, agent_memory
    from app.api import websocket as ws

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
    app.include_router(agents.router, prefix="/api/v1/agents", tags=["Agents"])
    app.include_router(governance.router, prefix="/api/v1/actions", tags=["Governance"])
    app.include_router(city_state.router, prefix="/api/v1/city", tags=["City State"])
    app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
    app.include_router(simulator.router, prefix="/api/v1/simulator", tags=["Simulator"])
    app.include_router(audit.router, prefix="/api/v1/audit", tags=["Audit"])
    app.include_router(approvals.router, prefix="/api/v1/approvals", tags=["Approvals"])
    app.include_router(armoriq.router, prefix="/api/v1/armoriq", tags=["ArmorIQ"])
    app.include_router(digital_twin.router, prefix="/api/v1/twin", tags=["Digital Twin"])
    app.include_router(decision_graph.router, prefix="/api/v1/decisions", tags=["Decision Graph"])
    app.include_router(agent_memory.router, prefix="/api/v1", tags=["Agent Memory"])
    app.include_router(ws.router, tags=["WebSocket"])

    # ── Health & Readiness ────────────────────────────────────────────────────
    @app.get("/api/v1/health", tags=["Health"])
    async def health_check() -> dict[str, Any]:
        return {
            "status": "healthy",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
        }

    @app.get("/api/v1/ready", tags=["Health"])
    async def readiness_check() -> dict[str, Any]:
        """Readiness probe — verifies that all dependencies are reachable."""
        from app.core.database import get_db
        from app.core.redis_client import get_redis

        checks: dict[str, str] = {}

        try:
            db = get_db()
            await db.command("ping")
            checks["database"] = "ok"
        except Exception as e:
            checks["database"] = f"error: {e}"

        try:
            redis = get_redis()
            await redis.ping()
            checks["redis"] = "ok"
        except Exception as e:
            checks["redis"] = f"error: {e}"

        all_ok = all(v == "ok" for v in checks.values())
        return JSONResponse(
            status_code=200 if all_ok else 503,
            content={"status": "ready" if all_ok else "not_ready", "checks": checks},
        )

    # ── Prometheus Metrics ────────────────────────────────────────────────────
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        excluded_handlers=["/metrics", "/api/v1/health", "/api/v1/ready"],
    ).instrument(app).expose(app, endpoint="/metrics")

    return app


app = create_application()
