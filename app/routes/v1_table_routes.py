from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth.dependencies import get_principal_context
from auth.principal import PrincipalContext
from database.dependencies import get_db
from schemas.table_management_schema import (
    RestaurantTableCreate,
    RestaurantTableResponse,
    RestaurantTableUpdate,
    TableSessionAttachTableRequest,
    TableSessionBillRequest,
    TableSessionCancelRequest,
    TableSessionCreate,
    TableSessionMoveRequest,
    TableSessionOpenResponse,
    TableSessionResponse,
    TableSessionUpdate,
)
from services.table_management_service import TableManagementService


router = APIRouter(prefix="/api/v1/businesses/{business_id}/branches/{branch_id}")


@router.get("/tables", response_model=list[RestaurantTableResponse], tags=["v1-tables"])
def list_tables(business_id: str, branch_id: str, db: Session = Depends(get_db), principal: PrincipalContext = Depends(get_principal_context)):
    return TableManagementService.list_tables(db, principal, business_id, branch_id)


@router.post("/tables", response_model=RestaurantTableResponse, tags=["v1-tables"])
def create_table(business_id: str, branch_id: str, payload: RestaurantTableCreate, db: Session = Depends(get_db), principal: PrincipalContext = Depends(get_principal_context)):
    return TableManagementService.create_table(db, principal, business_id, branch_id, payload)


@router.get("/tables/{table_id}", response_model=RestaurantTableResponse, tags=["v1-tables"])
def get_table(business_id: str, branch_id: str, table_id: str, db: Session = Depends(get_db), principal: PrincipalContext = Depends(get_principal_context)):
    return TableManagementService.get_table(db, principal, business_id, branch_id, table_id)


@router.patch("/tables/{table_id}", response_model=RestaurantTableResponse, tags=["v1-tables"])
def update_table(business_id: str, branch_id: str, table_id: str, payload: RestaurantTableUpdate, db: Session = Depends(get_db), principal: PrincipalContext = Depends(get_principal_context)):
    return TableManagementService.update_table(db, principal, business_id, branch_id, table_id, payload)


@router.post("/tables/{table_id}/sessions", response_model=TableSessionOpenResponse, tags=["v1-tables"])
def open_table_session(business_id: str, branch_id: str, table_id: str, payload: TableSessionCreate, db: Session = Depends(get_db), principal: PrincipalContext = Depends(get_principal_context)):
    return TableManagementService.open_session(db, principal, business_id, branch_id, table_id, payload)


@router.get("/tables/{table_id}/active-session", response_model=TableSessionResponse, tags=["v1-tables"])
def get_active_session(business_id: str, branch_id: str, table_id: str, db: Session = Depends(get_db), principal: PrincipalContext = Depends(get_principal_context)):
    return TableManagementService.active_session(db, principal, business_id, branch_id, table_id)


@router.get("/table-sessions/{session_id}", response_model=TableSessionResponse, tags=["v1-tables"])
def get_table_session(business_id: str, branch_id: str, session_id: str, db: Session = Depends(get_db), principal: PrincipalContext = Depends(get_principal_context)):
    return TableManagementService.get_session(db, principal, business_id, branch_id, session_id)


@router.patch("/table-sessions/{session_id}", response_model=TableSessionResponse, tags=["v1-tables"])
def update_table_session(business_id: str, branch_id: str, session_id: str, payload: TableSessionUpdate, db: Session = Depends(get_db), principal: PrincipalContext = Depends(get_principal_context)):
    return TableManagementService.update_session(db, principal, business_id, branch_id, session_id, payload)


@router.post("/table-sessions/{session_id}/request-bill", response_model=TableSessionResponse, tags=["v1-tables"])
def request_bill(business_id: str, branch_id: str, session_id: str, payload: TableSessionBillRequest, db: Session = Depends(get_db), principal: PrincipalContext = Depends(get_principal_context)):
    return TableManagementService.request_bill(db, principal, business_id, branch_id, session_id, payload)


@router.post("/table-sessions/{session_id}/cancel", response_model=TableSessionResponse, tags=["v1-tables"])
def cancel_session(business_id: str, branch_id: str, session_id: str, payload: TableSessionCancelRequest, db: Session = Depends(get_db), principal: PrincipalContext = Depends(get_principal_context)):
    return TableManagementService.cancel_session(db, principal, business_id, branch_id, session_id, payload)


@router.post("/table-sessions/{session_id}/move", response_model=TableSessionResponse, tags=["v1-tables"])
def move_session(business_id: str, branch_id: str, session_id: str, payload: TableSessionMoveRequest, db: Session = Depends(get_db), principal: PrincipalContext = Depends(get_principal_context)):
    return TableManagementService.move_session(db, principal, business_id, branch_id, session_id, payload)


@router.post("/table-sessions/{session_id}/tables", response_model=TableSessionResponse, tags=["v1-tables"])
def attach_table(business_id: str, branch_id: str, session_id: str, payload: TableSessionAttachTableRequest, db: Session = Depends(get_db), principal: PrincipalContext = Depends(get_principal_context)):
    return TableManagementService.attach_table(db, principal, business_id, branch_id, session_id, payload)


@router.delete("/table-sessions/{session_id}/tables/{table_id}", response_model=TableSessionResponse, tags=["v1-tables"])
def detach_table(business_id: str, branch_id: str, session_id: str, table_id: str, expected_version: Optional[int] = Query(default=None, ge=1), db: Session = Depends(get_db), principal: PrincipalContext = Depends(get_principal_context)):
    return TableManagementService.detach_table(db, principal, business_id, branch_id, session_id, table_id, expected_version)
