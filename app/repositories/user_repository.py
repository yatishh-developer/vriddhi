from models.user_model import User


class UserRepository:

    @staticmethod
    def get_by_email(db, email):

        return db.query(User).filter(
            User.email == email
        ).first()