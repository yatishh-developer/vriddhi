from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.dependencies import get_db
from auth.dependencies import get_current_user

from services.dashboard_service import DashboardService

from schemas.dashboard_schema import (
    DashboardSummaryResponse
)

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse
)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return DashboardService.get_summary(
        db=db,
        current_user=current_user
    )