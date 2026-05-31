from fastapi import HTTPException

from models.product_model import Product

from repositories.product_repository import ProductRepository


class ProductService:

    @staticmethod
    def create_product(
        db,
        current_user,
        product_data
    ):

        existing = ProductRepository.get_by_id(
            db,
            product_data.id,
            current_user.business_id
        )

        if existing:
            raise HTTPException(
                status_code=400,
                detail="Product already exists"
            )

        barcode_exists = ProductRepository.get_by_barcode(
            db,
            product_data.barcode,
            current_user.business_id
        )
        
        if barcode_exists:
            raise HTTPException(
                status_code=400,
                detail="Barcode already exists"
            )

        stock_quantity = max(
            product_data.stock_quantity,
            0
        )

        in_stock = stock_quantity > 0

        product = Product(
            id=product_data.id,
            business_id=current_user.business_id,
            name=product_data.name,
            barcode=product_data.barcode,
            price=product_data.price,
            gst_percentage=product_data.gst_percentage or 0,
            hsn_code=product_data.hsn_code or "",
            image_url=product_data.image_url,
            category=product_data.category,
            in_stock=in_stock,
            is_stockless=product_data.is_stockless,
            stock_quantity=stock_quantity,
            description=product_data.description,
            ingredients=product_data.ingredients,
        )

        db.add(product)

        db.commit()

        db.refresh(product)

        return product

    @staticmethod
    def update_product(
        db,
        current_user,
        product_id,
        payload
    ):

        product = ProductRepository.get_by_id(
            db,
            product_id,
            current_user.business_id
        )

        if not product:
            raise HTTPException(
                status_code=404,
                detail="Product not found"
            )
        
        update_data = payload.model_dump(
            exclude_unset=True
        )

        for key, value in update_data.items():
            setattr(product, key, value)

        if payload.stock_quantity is not None:
            product.stock_quantity = max(
                payload.stock_quantity,
                0
            )

        product.in_stock = (
            product.stock_quantity > 0
        )

        db.commit()

        db.refresh(product)

        return product
    
    @staticmethod
    def delete_product(
        db,
        current_user,
        product_id
    ):

        product = ProductRepository.get_by_id(
            db,
            product_id,
            current_user.business_id
        )
        if not product:
            raise HTTPException(
                status_code=404,
                detail="Product not found"
            )

        product.is_deleted = True

        db.commit()

        return {
            "message": "Product deleted successfully"
        }
    @staticmethod
    def handle_queue_item(db, current_user, action: str, payload: dict):
        """Handle a queued offline product operation.

        `create` is treated as an UPSERT: if a product with the same id
        already exists (e.g. the client re-syncs, or stock was decremented
        after a sale), we update it instead of silently dropping the change.
        Genuine validation errors propagate so the upload route can report
        them back to the client instead of losing data.
        """
        from schemas.product_schema import ProductCreate, ProductUpdate

        if action == "create":
            existing = ProductRepository.get_by_id(
                db, payload.get("id"), current_user.business_id
            )
            if existing:
                # Upsert: apply the incoming fields as an update.
                update_fields = {
                    k: v for k, v in payload.items() if k != "id"
                }
                data = ProductUpdate(**update_fields)
                ProductService.update_product(
                    db, current_user, payload["id"], data
                )
            else:
                data = ProductCreate(**payload)
                ProductService.create_product(db, current_user, data)

        elif action == "update":
            product_id = payload.get("id")
            if product_id:
                data = ProductUpdate(
                    **{k: v for k, v in payload.items() if k != "id"}
                )
                # Tolerate updates that arrive before the create (offline
                # ordering) by falling back to an upsert.
                existing = ProductRepository.get_by_id(
                    db, product_id, current_user.business_id
                )
                if existing:
                    ProductService.update_product(
                        db, current_user, product_id, data
                    )
                else:
                    create_data = ProductCreate(**payload)
                    ProductService.create_product(db, current_user, create_data)

        elif action == "delete":
            product_id = payload.get("id")
            if product_id:
                existing = ProductRepository.get_by_id(
                    db, product_id, current_user.business_id
                )
                if existing:
                    ProductService.delete_product(db, current_user, product_id)
