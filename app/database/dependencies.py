from sqlalchemy.orm import Session
from database.database import SessionLocal


def get_db():
    """Yield a database session and ensure it is closed after use."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
