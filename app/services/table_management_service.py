from datetime import datetime, timezone
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.authorization import require_capability, require_permission
from auth.errors import DomainError
from auth.principal import PrincipalContext
from models.order_model import Order
from models.business_model import Business
from models.table_management_model import RestaurantTable, TableSession, TableSessionTable
from models.transaction_model import Transaction
from schemas.table_management_schema import (
    RestaurantTableCreate,
    RestaurantTableResponse,
    RestaurantTableUpdate,
    TableActiveSessionSummary,
    TableSessionAttachTableRequest,
    TableSessionBillRequest,
    TableSessionCancelRequest,
    TableSessionCreate,
    TableSessionMoveRequest,
    TableSessionOpenResponse,
    TableSessionResponse,
    TableSessionTableResponse,
    TableSessionUpdate,
)
from services.order_service import OrderService
from services.domain_event_service import DomainEventService


ACTIVE_SESSION_STATUSES = {"OPEN", "BILL_REQUESTED", "PAYMENT_PENDING"}


class TableManagementService:
    """Table context only; OrderService and CheckoutService remain authoritative for sales."""

    @staticmethod
    def _scope(db: Session, principal: PrincipalContext, business_id: str, branch_id: str) -> None:
        OrderService._scope(principal, business_id, branch_id)
        from services.staff_billing_service import feature_flags_for_business_type

        business = db.query(Business).filter(Business.id == business_id).first()
        if not business or not feature_flags_for_business_type(business.business_type).get("table_management"):
            raise DomainError(403, "CAPABILITY_NOT_AVAILABLE", "Table management is not enabled for this business.")
        require_capability(principal, "table_management")

    @staticmethod
    def _table(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, table_id: str, *, lock: bool = False) -> RestaurantTable:
        TableManagementService._scope(db, principal, business_id, branch_id)
        query = db.query(RestaurantTable).filter(
            RestaurantTable.id == table_id,
            RestaurantTable.business_id == business_id,
            RestaurantTable.branch_id == branch_id,
        )
        if lock:
            query = query.with_for_update()
        table = query.first()
        if not table:
            raise DomainError(404, "TABLE_NOT_FOUND", "Restaurant table was not found for this business and branch.")
        return table

    @staticmethod
    def _session(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, session_id: str, *, lock: bool = False) -> TableSession:
        TableManagementService._scope(db, principal, business_id, branch_id)
        query = db.query(TableSession).filter(
            TableSession.id == session_id,
            TableSession.business_id == business_id,
            TableSession.branch_id == branch_id,
        )
        if lock:
            query = query.with_for_update()
        session = query.first()
        if not session:
            raise DomainError(404, "TABLE_SESSION_NOT_FOUND", "Table session was not found for this business and branch.")
        return session

    @staticmethod
    def _check_version(entity, expected_version: int | None) -> None:
        if expected_version is not None and expected_version != entity.version:
            raise DomainError(409, "VERSION_CONFLICT", f"Current version is {entity.version}.")

    @staticmethod
    def _active_link(db: Session, table_id: str) -> TableSessionTable | None:
        return db.query(TableSessionTable).join(TableSession).filter(
            TableSessionTable.table_id == table_id,
            TableSessionTable.is_active == True,
            TableSession.status.in_(ACTIVE_SESSION_STATUSES),
        ).first()

    @staticmethod
    def _order(db: Session, session: TableSession) -> Order | None:
        return db.query(Order).filter(Order.table_session_id == session.id).order_by(Order.created_at.desc()).first()

    @staticmethod
    def _table_response(db: Session, table: RestaurantTable) -> RestaurantTableResponse:
        link = TableManagementService._active_link(db, table.id)
        active_session = None
        state = "INACTIVE" if not table.is_active else "AVAILABLE"
        if link:
            session = link.session
            order = TableManagementService._order(db, session)
            active_session = TableActiveSessionSummary(
                id=session.id,
                guest_count=session.guest_count,
                opened_at=session.opened_at,
                order_id=order.id if order else None,
                item_count=len(order.items) if order else 0,
            )
            state = "OCCUPIED"
        return RestaurantTableResponse(
            id=table.id, business_id=table.business_id, branch_id=table.branch_id,
            name=table.name, code=table.code, capacity=table.capacity, section=table.section,
            is_active=table.is_active, sort_order=table.sort_order, x_position=table.x_position,
            y_position=table.y_position, shape=table.shape, state=state,
            active_session=active_session, version=table.version,
            created_at=table.created_at, updated_at=table.updated_at,
        )

    @staticmethod
    def _session_response(db: Session, session: TableSession) -> TableSessionResponse:
        links = db.query(TableSessionTable).filter(
            TableSessionTable.session_id == session.id,
            TableSessionTable.is_active == True,
        ).order_by(TableSessionTable.is_primary.desc(), TableSessionTable.attached_at).all()
        order = TableManagementService._order(db, session)
        return TableSessionResponse(
            id=session.id, business_id=session.business_id, branch_id=session.branch_id,
            primary_table_id=session.primary_table_id, status=session.status, guest_count=session.guest_count,
            customer_id=session.customer_id, opened_by_principal_id=session.opened_by_principal_id,
            opened_at=session.opened_at, closed_at=session.closed_at, notes=session.notes, version=session.version,
            tables=[TableSessionTableResponse(table_id=link.table_id, name=link.table.name, is_primary=link.is_primary, attached_at=link.attached_at) for link in links],
            order=OrderService._response(db, order) if order else None,
        )

    @staticmethod
    def create_table(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, payload: RestaurantTableCreate) -> RestaurantTableResponse:
        TableManagementService._scope(db, principal, business_id, branch_id)
        require_permission(principal, "tables.create")
        table = RestaurantTable(
            id=str(uuid.uuid4()), business_id=business_id, branch_id=branch_id,
            name=payload.name, code=payload.code, capacity=payload.capacity, section=payload.section,
            sort_order=payload.sort_order, x_position=payload.x_position, y_position=payload.y_position,
            shape=payload.shape, is_active=True, version=1,
        )
        db.add(table)
        DomainEventService.enqueue(db, event_type="table.created", aggregate_type="table", aggregate_id=table.id, business_id=business_id, branch_id=branch_id, data={"name": table.name}, actor_id=principal.principal_id)
        db.commit()
        db.refresh(table)
        return TableManagementService._table_response(db, table)

    @staticmethod
    def list_tables(db: Session, principal: PrincipalContext, business_id: str, branch_id: str) -> list[RestaurantTableResponse]:
        TableManagementService._scope(db, principal, business_id, branch_id)
        require_permission(principal, "tables.view")
        tables = db.query(RestaurantTable).filter(
            RestaurantTable.business_id == business_id,
            RestaurantTable.branch_id == branch_id,
        ).order_by(RestaurantTable.sort_order, RestaurantTable.name).all()
        return [TableManagementService._table_response(db, table) for table in tables]

    @staticmethod
    def get_table(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, table_id: str) -> RestaurantTableResponse:
        TableManagementService._scope(db, principal, business_id, branch_id)
        require_permission(principal, "tables.view")
        return TableManagementService._table_response(db, TableManagementService._table(db, principal, business_id, branch_id, table_id))

    @staticmethod
    def update_table(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, table_id: str, payload: RestaurantTableUpdate) -> RestaurantTableResponse:
        require_permission(principal, "tables.update")
        table = TableManagementService._table(db, principal, business_id, branch_id, table_id, lock=True)
        TableManagementService._check_version(table, payload.expected_version)
        if payload.is_active is False and TableManagementService._active_link(db, table.id):
            raise DomainError(409, "TABLE_ALREADY_OCCUPIED", "An occupied table cannot be deactivated.")
        for field in ("name", "code", "capacity", "section", "is_active", "sort_order", "x_position", "y_position", "shape"):
            if field in payload.model_fields_set:
                setattr(table, field, getattr(payload, field))
        table.version += 1
        DomainEventService.enqueue(db, event_type="table.updated", aggregate_type="table", aggregate_id=table.id, business_id=business_id, branch_id=branch_id, data={"is_active": table.is_active}, actor_id=principal.principal_id)
        db.commit()
        db.refresh(table)
        return TableManagementService._table_response(db, table)

    @staticmethod
    def open_session(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, table_id: str, payload: TableSessionCreate) -> TableSessionOpenResponse:
        require_permission(principal, "tables.open")
        table = TableManagementService._table(db, principal, business_id, branch_id, table_id, lock=True)
        if not table.is_active:
            raise DomainError(409, "TABLE_INACTIVE", "Table is inactive.")
        if TableManagementService._active_link(db, table.id):
            raise DomainError(409, "TABLE_ALREADY_OCCUPIED", "Table already has an active session.")
        OrderService._customer(db, business_id, payload.customer_id)
        now = datetime.now(timezone.utc)
        session = TableSession(
            id=str(uuid.uuid4()), business_id=business_id, branch_id=branch_id, primary_table_id=table.id,
            status="OPEN", guest_count=payload.guest_count, customer_id=payload.customer_id,
            opened_by_principal_id=principal.principal_id, opened_at=now, notes=payload.notes, version=1,
        )
        try:
            db.add(session)
            db.add(TableSessionTable(
                id=str(uuid.uuid4()), session_id=session.id, table_id=table.id,
                is_primary=True, is_active=True, attached_at=now,
            ))
            order = OrderService.create_dine_in_for_session(
                db, principal, business_id, branch_id, table_session_id=session.id, customer_id=payload.customer_id,
            )
            DomainEventService.enqueue(
                db, event_type="table.session_opened", aggregate_type="table_session", aggregate_id=session.id,
                business_id=business_id, branch_id=branch_id,
                data={"table_id": table.id, "order_id": order.id, "guest_count": session.guest_count}, actor_id=principal.principal_id,
            )
            db.commit()
            db.refresh(session)
            return TableSessionOpenResponse(session=TableManagementService._session_response(db, session), order=OrderService._response(db, order))
        except IntegrityError as exc:
            db.rollback()
            if TableManagementService._active_link(db, table.id):
                raise DomainError(409, "TABLE_ALREADY_OCCUPIED", "Table already has an active session.") from exc
            raise
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def active_session(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, table_id: str) -> TableSessionResponse:
        TableManagementService._scope(db, principal, business_id, branch_id)
        require_permission(principal, "tables.view")
        TableManagementService._table(db, principal, business_id, branch_id, table_id)
        link = TableManagementService._active_link(db, table_id)
        if not link:
            raise DomainError(404, "TABLE_NOT_OCCUPIED", "Table does not have an active session.")
        return TableManagementService._session_response(db, link.session)

    @staticmethod
    def get_session(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, session_id: str) -> TableSessionResponse:
        TableManagementService._scope(db, principal, business_id, branch_id)
        require_permission(principal, "tables.view")
        return TableManagementService._session_response(db, TableManagementService._session(db, principal, business_id, branch_id, session_id))

    @staticmethod
    def update_session(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, session_id: str, payload: TableSessionUpdate) -> TableSessionResponse:
        require_permission(principal, "tables.update")
        session = TableManagementService._session(db, principal, business_id, branch_id, session_id, lock=True)
        TableManagementService._check_version(session, payload.expected_version)
        if session.status in {"CLOSED", "CANCELLED"}:
            raise DomainError(409, "TABLE_SESSION_CLOSED", "Table session is no longer open.")
        if "customer_id" in payload.model_fields_set:
            OrderService._customer(db, business_id, payload.customer_id)
            session.customer_id = payload.customer_id
            order = TableManagementService._order(db, session)
            if order:
                order.customer_id = payload.customer_id
        if "guest_count" in payload.model_fields_set:
            session.guest_count = payload.guest_count
        if "notes" in payload.model_fields_set:
            session.notes = payload.notes
        session.version += 1
        DomainEventService.enqueue(db, event_type="table.session_updated", aggregate_type="table_session", aggregate_id=session.id, business_id=business_id, branch_id=branch_id, data={"status": session.status}, actor_id=principal.principal_id)
        db.commit()
        db.refresh(session)
        return TableManagementService._session_response(db, session)

    @staticmethod
    def request_bill(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, session_id: str, payload: TableSessionBillRequest) -> TableSessionResponse:
        require_permission(principal, "tables.close")
        session = TableManagementService._session(db, principal, business_id, branch_id, session_id, lock=True)
        TableManagementService._check_version(session, payload.expected_version)
        if session.status != "OPEN":
            raise DomainError(409, "TABLE_SESSION_CLOSED", "Only open sessions can request a bill.")
        session.status = "BILL_REQUESTED"
        session.version += 1
        DomainEventService.enqueue(db, event_type="table.bill_requested", aggregate_type="table_session", aggregate_id=session.id, business_id=business_id, branch_id=branch_id, data={"table_id": session.primary_table_id}, actor_id=principal.principal_id)
        db.commit()
        db.refresh(session)
        return TableManagementService._session_response(db, session)

    @staticmethod
    def cancel_session(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, session_id: str, payload: TableSessionCancelRequest) -> TableSessionResponse:
        require_permission(principal, "tables.close")
        session = TableManagementService._session(db, principal, business_id, branch_id, session_id, lock=True)
        TableManagementService._check_version(session, payload.expected_version)
        if session.status in {"CLOSED", "CANCELLED"}:
            raise DomainError(409, "TABLE_SESSION_CLOSED", "Table session is no longer open.")
        order = TableManagementService._order(db, session)
        if not order or order.items or db.query(Transaction).filter(Transaction.order_id == order.id).first():
            raise DomainError(409, "TABLE_SESSION_NOT_EMPTY", "Only an empty unbilled table session can be cancelled.")
        now = datetime.now(timezone.utc)
        order.status = "CANCELLED"
        order.cancellation_reason = payload.reason
        order.cancelled_at = now
        order.version += 1
        session.status = "CANCELLED"
        session.closed_at = now
        session.version += 1
        db.query(TableSessionTable).filter(TableSessionTable.session_id == session.id, TableSessionTable.is_active == True).update({"is_active": False}, synchronize_session=False)
        DomainEventService.enqueue(db, event_type="table.session_cancelled", aggregate_type="table_session", aggregate_id=session.id, business_id=business_id, branch_id=branch_id, data={"reason": payload.reason}, actor_id=principal.principal_id)
        db.commit()
        db.refresh(session)
        return TableManagementService._session_response(db, session)

    @staticmethod
    def move_session(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, session_id: str, payload: TableSessionMoveRequest) -> TableSessionResponse:
        require_permission(principal, "tables.move")
        session = TableManagementService._session(db, principal, business_id, branch_id, session_id, lock=True)
        TableManagementService._check_version(session, payload.expected_version)
        if session.status not in ACTIVE_SESSION_STATUSES:
            raise DomainError(409, "TABLE_SESSION_CLOSED", "Table session is no longer open.")
        table_ids = sorted({session.primary_table_id, payload.destination_table_id})
        tables = {
            table.id: table for table in db.query(RestaurantTable).filter(
                RestaurantTable.id.in_(table_ids), RestaurantTable.business_id == business_id,
                RestaurantTable.branch_id == branch_id,
            ).with_for_update().all()
        }
        destination = tables.get(payload.destination_table_id)
        if not destination:
            raise DomainError(404, "TABLE_NOT_FOUND", "Destination table was not found.")
        if not destination.is_active:
            raise DomainError(409, "TABLE_INACTIVE", "Destination table is inactive.")
        if payload.destination_table_id == session.primary_table_id:
            return TableManagementService._session_response(db, session)
        if TableManagementService._active_link(db, destination.id):
            raise DomainError(409, "DESTINATION_TABLE_OCCUPIED", "Destination table is already occupied.")
        current_link = db.query(TableSessionTable).filter(
            TableSessionTable.session_id == session.id, TableSessionTable.table_id == session.primary_table_id,
            TableSessionTable.is_active == True,
        ).with_for_update().one()
        current_link.is_active = False
        current_link.is_primary = False
        db.add(TableSessionTable(id=str(uuid.uuid4()), session_id=session.id, table_id=destination.id, is_primary=True, is_active=True, attached_at=datetime.now(timezone.utc)))
        session.primary_table_id = destination.id
        session.version += 1
        DomainEventService.enqueue(db, event_type="table.session_moved", aggregate_type="table_session", aggregate_id=session.id, business_id=business_id, branch_id=branch_id, data={"table_id": destination.id}, actor_id=principal.principal_id)
        db.commit()
        db.refresh(session)
        return TableManagementService._session_response(db, session)

    @staticmethod
    def attach_table(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, session_id: str, payload: TableSessionAttachTableRequest) -> TableSessionResponse:
        require_permission(principal, "tables.merge")
        session = TableManagementService._session(db, principal, business_id, branch_id, session_id, lock=True)
        TableManagementService._check_version(session, payload.expected_version)
        if session.status not in ACTIVE_SESSION_STATUSES:
            raise DomainError(409, "TABLE_SESSION_CLOSED", "Table session is no longer open.")
        table = TableManagementService._table(db, principal, business_id, branch_id, payload.table_id, lock=True)
        if not table.is_active:
            raise DomainError(409, "TABLE_INACTIVE", "Table is inactive.")
        link = TableManagementService._active_link(db, table.id)
        if link and link.session_id == session.id:
            raise DomainError(409, "TABLE_ALREADY_ATTACHED", "Table is already attached to this session.")
        if link:
            raise DomainError(409, "DESTINATION_TABLE_OCCUPIED", "Table is already occupied.")
        db.add(TableSessionTable(id=str(uuid.uuid4()), session_id=session.id, table_id=table.id, is_primary=False, is_active=True, attached_at=datetime.now(timezone.utc)))
        session.version += 1
        DomainEventService.enqueue(db, event_type="table.session_tables_changed", aggregate_type="table_session", aggregate_id=session.id, business_id=business_id, branch_id=branch_id, data={"attached_table_id": table.id}, actor_id=principal.principal_id)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise DomainError(409, "DESTINATION_TABLE_OCCUPIED", "Table is already occupied.") from exc
        db.refresh(session)
        return TableManagementService._session_response(db, session)

    @staticmethod
    def detach_table(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, session_id: str, table_id: str, expected_version: int | None) -> TableSessionResponse:
        require_permission(principal, "tables.merge")
        session = TableManagementService._session(db, principal, business_id, branch_id, session_id, lock=True)
        TableManagementService._check_version(session, expected_version)
        link = db.query(TableSessionTable).filter(
            TableSessionTable.session_id == session.id, TableSessionTable.table_id == table_id,
            TableSessionTable.is_active == True,
        ).with_for_update().first()
        if not link:
            raise DomainError(404, "TABLE_NOT_ATTACHED", "Table is not attached to this session.")
        if link.is_primary:
            raise DomainError(409, "TABLE_NOT_ATTACHED", "Primary table must be moved before it can be detached.")
        link.is_active = False
        session.version += 1
        DomainEventService.enqueue(db, event_type="table.session_tables_changed", aggregate_type="table_session", aggregate_id=session.id, business_id=business_id, branch_id=branch_id, data={"detached_table_id": table_id}, actor_id=principal.principal_id)
        db.commit()
        db.refresh(session)
        return TableManagementService._session_response(db, session)
