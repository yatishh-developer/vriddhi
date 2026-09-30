from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import text

from database.dependencies import get_db


router = APIRouter(tags=["Root"])


@router.get("/")
def read_root():
    return {"message": "Vriddhi API is running"}


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint for load balancers and monitoring."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "version": "2.3.1",
    }


@router.get("/internal/health", include_in_schema=False)
def internal_health(request: Request, db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        database = "OK"
    except Exception:
        database = "ERROR"
    redis_runtime = getattr(request.app.state, "redis_runtime", None)
    publisher = getattr(request.app.state, "outbox_publisher", None)
    return {
        "database": database,
        "redis": "OK" if redis_runtime and redis_runtime.connected else "DISABLED" if redis_runtime and not redis_runtime.enabled else "ERROR",
        "outbox": "OK" if publisher and publisher.healthy else "ERROR",
        "realtime": "OK" if redis_runtime and redis_runtime.subscriber_healthy else "DISABLED" if redis_runtime and not redis_runtime.enabled else "ERROR",
    }
