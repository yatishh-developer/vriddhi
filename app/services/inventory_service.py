from sqlalchemy.orm import Session

from auth.errors import DomainError
from models.inventory_movement_model import InventoryMovement, InventoryMovementType
from models.product_model import Product
from repositories.inventory_repository import InventoryRepository
from schemas.inventory_schema import InventoryAdjustRequest


class InventoryService:
    """Only service allowed to mutate sale-related stock quantities."""

    @staticmethod
    def _locked_product(db: Session, product_id: str, business_id: str) -> Product:
        product = (
            db.query(Product)
            .filter(
                Product.id == product_id,
                Product.business_id == business_id,
                Product.is_deleted == False,
            )
            .with_for_update()
            .first()
        )
        if not product:
            raise DomainError(404, "PRODUCT_NOT_FOUND", "Product was not found.")
        return product

    @staticmethod
    def locked_products(db: Session, product_ids: list[str], business_id: str) -> dict[str, Product]:
        """Lock in stable id order to reduce checkout deadlock risk."""
        return {
            product_id: InventoryService._locked_product(db, product_id, business_id)
            for product_id in sorted(set(product_ids))
        }

    @staticmethod
    def deduct_sale(
        db: Session,
        *,
        product: Product,
        quantity: int,
        business_id: str,
        branch_id: str,
        reference_id: str,
        created_by: str,
        created_by_staff_id: str | None,
        source_app: str,
    ) -> None:
        if quantity <= 0:
            raise DomainError(400, "INVALID_QUANTITY", "Item quantity must be positive.")
        if product.is_stockless:
            return
        before_stock = product.stock_quantity
        if before_stock < quantity:
            raise DomainError(409, "INSUFFICIENT_STOCK", "Insufficient stock for checkout.")
        after_stock = before_stock - quantity
        product.stock_quantity = after_stock
        product.in_stock = after_stock > 0
        db.add(
            InventoryMovement(
                business_id=business_id,
                branch_id=branch_id,
                product_id=product.id,
                movement_type=InventoryMovementType.SALE,
                quantity=quantity,
                before_stock=before_stock,
                after_stock=after_stock,
                reference_id=reference_id,
                notes="Checkout sale",
                created_by=created_by,
                created_by_staff_id=created_by_staff_id,
                source_app=source_app,
                sync_status="pending",
            )
        )

    @staticmethod
    def set_stock_with_movement(
        db: Session,
        *,
        product: Product,
        target_quantity: int,
        business_id: str,
        created_by: str,
        branch_id: str = "main",
        notes: str = "Product stock update",
    ) -> None:
        if target_quantity < 0:
            raise DomainError(400, "INVALID_QUANTITY", "Stock quantity cannot be negative.")
        locked = InventoryService._locked_product(db, product.id, business_id)
        before_stock = locked.stock_quantity
        locked.stock_quantity = target_quantity
        locked.in_stock = target_quantity > 0
        if target_quantity == before_stock:
            return
        db.add(
            InventoryMovement(
                business_id=business_id,
                branch_id=branch_id,
                product_id=locked.id,
                movement_type=(InventoryMovementType.MANUAL_ADD if target_quantity > before_stock else InventoryMovementType.MANUAL_REMOVE),
                quantity=abs(target_quantity - before_stock),
                before_stock=before_stock,
                after_stock=target_quantity,
                notes=notes,
                created_by=created_by,
                source_app="admin_app",
                sync_status="pending",
            )
        )

    @staticmethod
    def adjust_inventory(db: Session, payload: InventoryAdjustRequest, current_user):
        """Manual adjustment is one atomic product-plus-movement transaction."""
        try:
            product = InventoryService._locked_product(db, payload.product_id, current_user.business_id)
            before_stock = product.stock_quantity
            removes = {InventoryMovementType.SALE, InventoryMovementType.MANUAL_REMOVE}
            after_stock = before_stock - payload.quantity if payload.movement_type in removes else before_stock + payload.quantity
            if after_stock < 0:
                raise DomainError(409, "INSUFFICIENT_STOCK", "Insufficient stock for this adjustment.")
            product.stock_quantity = after_stock
            product.in_stock = after_stock > 0
            movement = InventoryMovement(
                business_id=current_user.business_id,
                branch_id="main",
                product_id=product.id,
                movement_type=InventoryMovementType(payload.movement_type.value),
                quantity=payload.quantity,
                before_stock=before_stock,
                after_stock=after_stock,
                reference_id=payload.reference_id,
                notes=payload.notes,
                created_by=current_user.id,
                source_app="admin_app",
                sync_status="synced",
            )
            db.add(movement)
            db.commit()
            db.refresh(movement)
            return movement
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def get_movements(db: Session, current_user):
        return InventoryRepository.get_movements(db=db, business_id=current_user.business_id)
