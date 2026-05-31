from models.product_model import Product


class ProductRepository:

    @staticmethod
    def get_all(db, business_id):

        return db.query(Product).filter(
            Product.business_id == business_id,
            Product.is_deleted == False
        ).all()


    @staticmethod
    def get_by_id(
        db,
        product_id,
        business_id
    ):

        return db.query(Product).filter(
            Product.id == product_id,
            Product.business_id == business_id,
            Product.is_deleted == False
        ).first()


    @staticmethod
    def get_by_barcode(
        db,
        barcode,
        business_id
    ):

        return db.query(Product).filter(
            Product.barcode == barcode,
            Product.business_id == business_id,
            Product.is_deleted == False
        ).first()