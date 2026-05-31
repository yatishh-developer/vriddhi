from sqlalchemy.orm import Session
from fastapi import HTTPException

from repositories.inventory_repository import InventoryRepository
from models.inventory_movement_model import InventoryMovement
from schemas.inventory_schema import InventoryAdjustRequest


class InventoryService:

    @staticmethod
    def adjust_inventory(db: Session, payload: InventoryAdjustRequest, current_user):
        product = InventoryRepository.get_product(
            db=db,
            product_id=payload.product_id,
            business_id=current_user.business_id
        )
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        before_stock = product.stock_quantity

        if payload.movement_type in ["SALE", "MANUAL_REMOVE", "REFUND"]:
            after_stock = before_stock - payload.quantity
        else:
            after_stock = before_stock + payload.quantity

        if after_stock < 0:
            raise HTTPException(status_code=400, detail="Insufficient stock")

        product.stock_quantity = after_stock
        InventoryRepository.save_product(db=db, product=product)

        movement = InventoryMovement(
            business_id=current_user.business_id,
            product_id=product.id,
            movement_type=payload.movement_type,
            quantity=payload.quantity,
            before_stock=before_stock,
            after_stock=after_stock,
            reference_id=payload.reference_id,
            notes=payload.notes,
            created_by=current_user.id
        )
        return InventoryRepository.create_movement(db=db, movement=movement)

    @staticmethod
    def get_movements(db: Session, current_user):
        return InventoryRepository.get_movements(db=db, business_id=current_user.business_id)

    @staticmethod
    def reduce_stock(db: Session, business_id: str, product, quantity: int):
        """Reduce stock during a sale without creating an inventory movement record."""
        if product.is_stockless:
            return
        before_stock = product.stock_quantity
        after_stock = max(0, before_stock - quantity)
        product.stock_quantity = after_stock
        product.in_stock = after_stock > 0
        # No explicit commit here — caller commits after all items
