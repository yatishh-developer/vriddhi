from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.dependencies import get_db
from auth.dependencies import get_current_user

from services.inventory_service import InventoryService

from schemas.inventory_schema import (
    InventoryAdjustRequest,
    InventoryMovementResponse
)

router = APIRouter(
    prefix="/inventory",
    tags=["Inventory"]
)


@router.get(
    "/movements",
    response_model=list[InventoryMovementResponse]
)
def get_inventory_movements(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return InventoryService.get_movements(
        db=db,
        current_user=current_user
    )


@router.post(
    "/adjust",
    response_model=InventoryMovementResponse
)
def adjust_inventory(
    payload: InventoryAdjustRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return InventoryService.adjust_inventory(
        db=db,
        payload=payload,
        current_user=current_user
    )