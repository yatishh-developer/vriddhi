import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from middleware.logging_middleware import LoggingMiddleware
from middleware.rate_limit_middleware import rate_limit_middleware
from exception_handlers.global_exception_handler import global_exception_handler


logger = logging.getLogger("vriddhi")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: create tables on startup, cleanup on shutdown."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified/created successfully.")
    except Exception as e:
        logger.error(f"Could not create database tables: {e}")
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
