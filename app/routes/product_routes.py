from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from auth.dependencies import get_current_user
from database.dependencies import get_db
from models.user_model import User
from repositories.product_repository import ProductRepository
from schemas.product_schema import ProductCreate, ProductResponse, ProductUpdate
from services.product_service import ProductService
from services.customer_service import CustomerService
from services.transaction_service import TransactionService


router = APIRouter(prefix="/products", tags=["Products"])


@router.get("/sync", response_model=List[ProductResponse])
def get_products_for_sync(
    last_sync: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Return products updated since last_sync (used by Flutter sync service)."""
    if last_sync:
        try:
            last_sync_dt = datetime.fromisoformat(last_sync.replace("Z", "+00:00"))
            from models.product_model import Product
            products = db.query(Product).filter(
                Product.business_id == current_user.business_id,
                Product.updated_at >= last_sync_dt
            ).all()
            return products
        except Exception:
            pass
    return ProductRepository.get_all(db, current_user.business_id)


@router.post("/sync/upload")
def upload_queue(
    items: List[dict],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Process queued offline operations from Flutter.

    Accepts queue items for product, customer, and transaction entities.
    Each item is dispatched to the relevant service's handle_queue_item.
    Failures on individual items are collected and returned alongside the
    processed count so the client can surface them.
    """
    import json as _json

    processed = 0
    errors = []
    for item in items:
        try:
            entity = item.get("entity_type")
            action = item.get("action")
            payload = item.get("payload", {})

            # Flutter wraps the payload as a JSON string before enqueueing.
            if isinstance(payload, str):
                try:
                    payload = _json.loads(payload)
                except Exception:
                    payload = {}

            if entity == "product":
                ProductService.handle_queue_item(db, current_user, action, payload)
            elif entity == "customer":
                CustomerService.handle_queue_item(db, current_user, action, payload)
            elif entity == "transaction":
                TransactionService.handle_queue_item(db, current_user, action, payload)
            else:
                errors.append(f"Unknown entity_type: {entity}")
                continue

            processed += 1
        except Exception as e:
            db.rollback()
            errors.append(f"{item.get('entity_type')}/{item.get('action')}: {e}")

    return {"processed": processed, "errors": errors}


@router.get("/", response_model=List[ProductResponse])
def get_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return ProductRepository.get_all(db, current_user.business_id)


@router.post("/", response_model=ProductResponse)
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return ProductService.create_product(db, current_user, product)


@router.get("/barcode/{barcode}", response_model=ProductResponse)
def get_product_by_barcode(
    barcode: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    product = ProductRepository.get_by_barcode(db, barcode, current_user.business_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    product = ProductRepository.get_by_id(db, product_id, current_user.business_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: str,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return ProductService.update_product(db, current_user, product_id, payload)


@router.delete("/{product_id}")
def delete_product(
    product_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return ProductService.delete_product(db, current_user, product_id)
