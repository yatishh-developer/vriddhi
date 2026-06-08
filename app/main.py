import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from core.config import settings
from database.database import Base, engine
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
from middleware.logging_middleware import LoggingMiddleware
from middleware.rate_limit_middleware import rate_limit_middleware
from exception_handlers.global_exception_handler import global_exception_handler
from services.staff_billing_migration import run_staff_billing_migrations


logger = logging.getLogger("vriddhi")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: create tables on startup, cleanup on shutdown."""
    try:
        Base.metadata.create_all(bind=engine)
        run_staff_billing_migrations(engine)
        logger.info("Database tables verified/created successfully.")
    except Exception as e:
        logger.error(f"Could not create database tables: {e}")
        if settings.ENVIRONMENT.lower() == "production":
            raise
        logger.warning("Application will continue, but database operations may fail.")
    yield
    # Shutdown: dispose engine connections
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

app.middleware("http")(rate_limit_middleware)

app.add_exception_handler(Exception, global_exception_handler)


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
