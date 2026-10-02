from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from auth.authorization import require_permission
from auth.dependencies import get_principal_context
from auth.principal import PrincipalContext
from database.dependencies import get_db
from repositories.customer_repository import CustomerRepository
from repositories.product_repository import ProductRepository
from schemas.customer_schema import CustomerResponse, V1CustomerCreate
from schemas.order_schema import (
    OrderCancelRequest,
    OrderCheckoutRequest,
    OrderCheckoutResponse,
    OrderCreate,
    OrderHoldRequest,
    OrderItemUpdate,
    OrderItemsCreate,
    OrderListResponse,
    OrderResponse,
)
from schemas.product_schema import ProductResponse
from services.order_service import OrderService
from services.customer_service import CustomerService


router = APIRouter(prefix="/api/v1/businesses/{business_id}/branches/{branch_id}")


@router.get("/products", response_model=list[ProductResponse], tags=["v1-products"])
def list_products(
    business_id: str,
    branch_id: str,
    db: Session = Depends(get_db),
    principal: PrincipalContext = Depends(get_principal_context),
):
    OrderService._scope(principal, business_id, branch_id)
    require_permission(principal, "products.view")
    return ProductRepository.get_all(db, business_id)


@router.get("/customers", response_model=list[CustomerResponse], tags=["v1-customers"])
def list_customers(
    business_id: str,
    branch_id: str,
    db: Session = Depends(get_db),
    principal: PrincipalContext = Depends(get_principal_context),
):
    OrderService._scope(principal, business_id, branch_id)
    require_permission(principal, "customers.view")
    return CustomerRepository.get_all(db, business_id)


@router.post("/customers", response_model=CustomerResponse, tags=["v1-customers"])
def create_customer(
    business_id: str,
    branch_id: str,
    payload: V1CustomerCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: PrincipalContext = Depends(get_principal_context),
):
    # Customers are business-owned; branch scope is authorization/audit context.
    return CustomerService.create_scoped_v1(
        db,
        principal,
        business_id,
        branch_id,
        payload,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/orders", response_model=OrderResponse, tags=["v1-orders"])
def create_order(
    business_id: str,
    branch_id: str,
    payload: OrderCreate,
    db: Session = Depends(get_db),
    principal: PrincipalContext = Depends(get_principal_context),
):
    return OrderService.create(db, principal, business_id, branch_id, payload)


@router.get("/orders", response_model=OrderListResponse, tags=["v1-orders"])
def list_orders(
    business_id: str,
    branch_id: str,
    status: Optional[str] = None,
    order_type: Optional[str] = None,
    customer_id: Optional[str] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: PrincipalContext = Depends(get_principal_context),
):
    return OrderService.list(
        db, principal, business_id, branch_id, status=status, order_type=order_type,
        customer_id=customer_id, created_from=created_from, created_to=created_to,
        page=page, page_size=page_size,
    )


@router.get("/orders/{order_id}", response_model=OrderResponse, tags=["v1-orders"])
def get_order(
    business_id: str,
    branch_id: str,
    order_id: str,
    db: Session = Depends(get_db),
    principal: PrincipalContext = Depends(get_principal_context),
):
    return OrderService.get(db, principal, business_id, branch_id, order_id)


@router.post("/orders/{order_id}/items", response_model=OrderResponse, tags=["v1-orders"])
def add_order_items(
    business_id: str,
    branch_id: str,
    order_id: str,
    payload: OrderItemsCreate,
    db: Session = Depends(get_db),
    principal: PrincipalContext = Depends(get_principal_context),
):
    return OrderService.add_items(db, principal, business_id, branch_id, order_id, payload)


@router.patch("/orders/{order_id}/items/{item_id}", response_model=OrderResponse, tags=["v1-orders"])
def update_order_item(
    business_id: str,
    branch_id: str,
    order_id: str,
    item_id: str,
    payload: OrderItemUpdate,
    db: Session = Depends(get_db),
    principal: PrincipalContext = Depends(get_principal_context),
):
    return OrderService.update_item(db, principal, business_id, branch_id, order_id, item_id, payload)


@router.post("/orders/{order_id}/hold", response_model=OrderResponse, tags=["v1-orders"])
def hold_order(
    business_id: str,
    branch_id: str,
    order_id: str,
    payload: OrderHoldRequest,
    db: Session = Depends(get_db),
    principal: PrincipalContext = Depends(get_principal_context),
):
    return OrderService.hold(db, principal, business_id, branch_id, order_id, payload)


@router.post("/orders/{order_id}/resume", response_model=OrderResponse, tags=["v1-orders"])
def resume_order(
    business_id: str,
    branch_id: str,
    order_id: str,
    payload: OrderHoldRequest,
    db: Session = Depends(get_db),
    principal: PrincipalContext = Depends(get_principal_context),
):
    return OrderService.resume(db, principal, business_id, branch_id, order_id, payload)


@router.post("/orders/{order_id}/cancel", response_model=OrderResponse, tags=["v1-orders"])
def cancel_order(
    business_id: str,
    branch_id: str,
    order_id: str,
    payload: OrderCancelRequest,
    db: Session = Depends(get_db),
    principal: PrincipalContext = Depends(get_principal_context),
):
    return OrderService.cancel(db, principal, business_id, branch_id, order_id, payload)


@router.post("/orders/{order_id}/checkout", response_model=OrderCheckoutResponse, tags=["v1-orders"])
def checkout_order(
    business_id: str,
    branch_id: str,
    order_id: str,
    payload: OrderCheckoutRequest,
    db: Session = Depends(get_db),
    principal: PrincipalContext = Depends(get_principal_context),
):
    return OrderService.checkout(db, principal, business_id, branch_id, order_id, payload)
