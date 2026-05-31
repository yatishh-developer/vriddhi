from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from auth.dependencies import get_current_user
from database.dependencies import get_db
from repositories.transaction_repository import TransactionRepository
from schemas.transaction_schema import CreateTransactionRequest, TransactionResponse
from services.transaction_service import TransactionService


router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.get("/", response_model=List[TransactionResponse])
def get_transactions(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return TransactionRepository.get_all(db, current_user.business_id)


@router.post("/", response_model=TransactionResponse)
def create_transaction(
    payload: CreateTransactionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return TransactionService.create_transaction(db, current_user, payload)


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    transaction = TransactionRepository.get_by_id(db, transaction_id, current_user.business_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.delete("/{transaction_id}")
def delete_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    transaction = TransactionRepository.get_by_id(db, transaction_id, current_user.business_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    TransactionRepository.delete(db, transaction)
    return {"message": "Transaction deleted"}
