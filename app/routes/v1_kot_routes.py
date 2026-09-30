from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth.dependencies import get_principal_context
from auth.principal import PrincipalContext
from database.dependencies import get_db
from schemas.kot_schema import KOTCancellationResponse, KOTCreateRequest, KOTListResponse, KOTResponse, KOTStatusUpdateRequest, OrderItemCancelQuantityRequest
from services.kot_service import KotService


router = APIRouter(prefix="/api/v1/businesses/{business_id}/branches/{branch_id}")


@router.post("/orders/{order_id}/kots", response_model=KOTResponse, tags=["v1-kots"])
def create_kot(business_id: str, branch_id: str, order_id: str, payload: KOTCreateRequest, db: Session = Depends(get_db), principal: PrincipalContext = Depends(get_principal_context)):
    return KotService.create(db, principal, business_id, branch_id, order_id, payload)


@router.get("/orders/{order_id}/kots", response_model=list[KOTResponse], tags=["v1-kots"])
def list_order_kots(business_id: str, branch_id: str, order_id: str, db: Session = Depends(get_db), principal: PrincipalContext = Depends(get_principal_context)):
    return KotService.list_for_order(db, principal, business_id, branch_id, order_id)


@router.get("/kots", response_model=KOTListResponse, tags=["v1-kots"])
def list_kots(business_id: str, branch_id: str, status: Optional[str] = None, order_id: Optional[str] = None, table_session_id: Optional[str] = None, created_from: Optional[datetime] = None, created_to: Optional[datetime] = None, page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100), db: Session = Depends(get_db), principal: PrincipalContext = Depends(get_principal_context)):
    return KotService.list(db, principal, business_id, branch_id, status=status, order_id=order_id, table_session_id=table_session_id, created_from=created_from, created_to=created_to, page=page, page_size=page_size)


@router.get("/kots/{kot_id}", response_model=KOTResponse, tags=["v1-kots"])
def get_kot(business_id: str, branch_id: str, kot_id: str, db: Session = Depends(get_db), principal: PrincipalContext = Depends(get_principal_context)):
    return KotService.get(db, principal, business_id, branch_id, kot_id)


@router.post("/kots/{kot_id}/status", response_model=KOTResponse, tags=["v1-kots"])
def update_kot_status(business_id: str, branch_id: str, kot_id: str, payload: KOTStatusUpdateRequest, db: Session = Depends(get_db), principal: PrincipalContext = Depends(get_principal_context)):
    return KotService.update_status(db, principal, business_id, branch_id, kot_id, payload)


@router.post("/orders/{order_id}/items/{item_id}/cancel-quantity", response_model=KOTCancellationResponse, tags=["v1-kots"])
def cancel_order_item_quantity(business_id: str, branch_id: str, order_id: str, item_id: str, payload: OrderItemCancelQuantityRequest, db: Session = Depends(get_db), principal: PrincipalContext = Depends(get_principal_context)):
    return KotService.cancel_order_item_quantity(db, principal, business_id, branch_id, order_id, item_id, payload)
