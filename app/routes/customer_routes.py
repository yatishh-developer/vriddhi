from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from auth.dependencies import get_current_user
from database.dependencies import get_db
from repositories.customer_repository import CustomerRepository
from schemas.customer_schema import CustomerCreate, CustomerUpdate, CustomerResponse
from services.customer_service import CustomerService


router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("/", response_model=List[CustomerResponse])
def get_customers(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return CustomerRepository.get_all(db, current_user.business_id)


@router.post("/", response_model=CustomerResponse)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return CustomerService.create_customer(db, current_user, payload)


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    customer = CustomerRepository.get_by_id(db, customer_id, current_user.business_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return CustomerService.update_customer(db, current_user, customer_id, payload)


@router.delete("/{customer_id}")
def delete_customer(
    customer_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return CustomerService.delete_customer(db, current_user, customer_id)
