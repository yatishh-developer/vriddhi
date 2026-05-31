from fastapi import APIRouter, Depends
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
