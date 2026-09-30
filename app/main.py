import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from core.config import settings
from database.database import engine
from routes.root_routes import router as root_router
from routes.auth_routes import router as auth_router
from routes.product_routes import router as product_router
from routes.customer_routes import router as customer_router
from routes.transaction_routes import router as transaction_router
from routes.dashboard_routes import router as dashboard_router
from routes.inventory_routes import router as inventory_router
from routes.business_routes import router as business_router
from routes.subscription_routes import router as subscription_router
from routes.staff_billing_routes import router as staff_billing_router
from routes.v1_business_routes import router as v1_business_router
from routes.v1_table_routes import router as v1_table_router
from routes.v1_kot_routes import router as v1_kot_router
from routes.realtime_routes import router as realtime_router
from middleware.logging_middleware import LoggingMiddleware
from middleware.rate_limit_middleware import rate_limit_middleware
from exception_handlers.global_exception_handler import global_exception_handler
from auth.errors import ApiError, api_error_handler
from middleware.request_id_middleware import RequestIdMiddleware
from realtime.connection_manager import ConnectionManager
from realtime.redis_runtime import RedisRuntime
from services.outbox_publisher import OutboxPublisher
import asyncio


logger = logging.getLogger("vriddhi")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage runtime connections; schema changes are Alembic-only."""
    runtime = RedisRuntime()
    manager = ConnectionManager()
    publisher = OutboxPublisher(runtime)
    stopping = asyncio.Event()
    app.state.redis_runtime = runtime
    app.state.realtime_manager = manager
    app.state.outbox_publisher = publisher
    app.state.outbox_stopping = stopping
    try:
        await runtime.start(manager)
        # Without Redis there is no transport to publish to.  The outbox stays
        # durable and pending; enabling Redis later drains it safely.
        app.state.outbox_task = (
            asyncio.create_task(publisher.run(stopping)) if runtime.connected else None
        )
        logger.info("Runtime services started.")
    except Exception as e:
        logger.error("Could not start realtime runtime: %s", e)
        if settings.ENVIRONMENT.lower() == "production":
            raise
        logger.warning("Application will continue with realtime unavailable.")
    yield
    stopping.set()
    task = getattr(app.state, "outbox_task", None)
    if task:
        await task
    await runtime.stop()
    engine.dispose()
    logger.info("Database connections closed.")


app = FastAPI(
    title="Vriddhi POS API",
    version="2.3.1",
    description="Backend API for Vriddhi Point-of-Sale application",
    lifespan=lifespan,
)


# ── CORS ──────────────────────────────────────────────────────────────────
if settings.allowed_hosts_list != ["*"]:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts_list,
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers_middleware(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=()",
    )
    return response

app.add_middleware(LoggingMiddleware)
app.add_middleware(RequestIdMiddleware)

app.middleware("http")(rate_limit_middleware)

app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(ApiError, api_error_handler)


# ── Routes ────────────────────────────────────────────────────────────────
app.include_router(root_router)
app.include_router(auth_router)
app.include_router(product_router)
app.include_router(customer_router)
app.include_router(transaction_router)
app.include_router(dashboard_router)
app.include_router(inventory_router)
app.include_router(business_router)
app.include_router(subscription_router)
app.include_router(staff_billing_router)
app.include_router(v1_business_router)
app.include_router(v1_table_router)
app.include_router(v1_kot_router)
app.include_router(realtime_router)
