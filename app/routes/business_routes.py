from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from database.dependencies import get_db
from models.business_model import Business
from schemas.business_schema import BusinessResponse, BusinessUpdate


router = APIRouter(prefix="/business", tags=["Business"])


@router.get("/", response_model=BusinessResponse)
def get_business(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    business = db.query(Business).filter(
        Business.id == current_user.business_id
    ).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


@router.put("/", response_model=BusinessResponse)
def update_business(
    payload: BusinessUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    business = db.query(Business).filter(
        Business.id == current_user.business_id
    ).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    if payload.name is not None:
        business.name = payload.name
    if payload.gst_number is not None:
        business.gst_number = payload.gst_number
    if payload.owner_name is not None:
        business.owner_name = payload.owner_name
    if payload.phone is not None:
        business.phone = payload.phone
    if payload.email is not None:
        business.email = payload.email
    if payload.address is not None:
        business.address = payload.address
    if payload.city is not None:
        business.city = payload.city
    if payload.state is not None:
        business.state = payload.state
    if payload.pincode is not None:
        business.pincode = payload.pincode
    if payload.upi_id is not None:
        business.upi_id = payload.upi_id
    if payload.is_intra_state is not None:
        business.is_intra_state = payload.is_intra_state

    db.commit()
    db.refresh(business)
    return business
