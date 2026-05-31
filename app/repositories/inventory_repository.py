from sqlalchemy.orm import Session
from models.inventory_movement_model import InventoryMovement
from models.product_model import Product


class InventoryRepository:

    @staticmethod
    def create_movement(
        db: Session,
        movement: InventoryMovement
    ):
        db.add(movement)
        db.commit()
        db.refresh(movement)
        return movement

    @staticmethod
    def get_movements(
        db: Session,
        business_id: str
    ):
        return (
            db.query(InventoryMovement)
            .filter(
                InventoryMovement.business_id == business_id
            )
            .order_by(InventoryMovement.created_at.desc())
            .all()
        )

    @staticmethod
    def get_product(
        db: Session,
        product_id: str,
        business_id: str
    ):
        return (
            db.query(Product)
            .filter(
                Product.id == product_id,
                Product.business_id == business_id,
                Product.is_deleted == False
            )
            .first()
        )

    @staticmethod
    def save_product(
        db: Session,
        product: Product
    ):
        db.commit()
        db.refresh(product)
        return product