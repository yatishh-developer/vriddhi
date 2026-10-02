from datetime import datetime, timezone
import hashlib
import json
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.authorization import require_capability, require_permission
from auth.errors import DomainError
from auth.principal import PrincipalContext
from models.business_model import Business
from models.kot_model import KitchenKotCancellation, KitchenKotSequence, KitchenOrderTicket, KitchenOrderTicketItem
from models.order_model import Order, OrderItem
from models.table_management_model import TableSessionTable
from schemas.kot_schema import (
    KOTCancellationResponse, KOTCreateRequest, KOTItemResponse, KOTListResponse,
    KOTPrintPayload, KOTResponse, KOTStatusUpdateRequest, KOTTableContext,
    OrderItemCancelQuantityRequest,
)
from services.order_service import OrderService
from services.domain_event_service import DomainEventService


KOT_SOURCE_APP = "unified_api_v1"
CREATE_KOT_OPERATION = "CREATE_KOT"


class KotService:
    """Normalized KOT lifecycle. Financial finalization remains in CheckoutService."""

    @staticmethod
    def _scope(db: Session, principal: PrincipalContext, business_id: str, branch_id: str) -> None:
        OrderService._scope(principal, business_id, branch_id)
        from services.staff_billing_service import feature_flags_for_business_type

        business = db.query(Business).filter(Business.id == business_id).first()
        if not business or not feature_flags_for_business_type(business.business_type).get("kot"):
            raise DomainError(403, "CAPABILITY_NOT_AVAILABLE", "Kitchen tickets are not enabled for this business.")
        require_capability(principal, "kot")

    @staticmethod
    def _enqueue_event(db: Session, event_type: str, kot: KitchenOrderTicket, actor_id: str) -> None:
        DomainEventService.enqueue(
            db, event_type=event_type, aggregate_type="kot", aggregate_id=kot.id,
            business_id=kot.business_id, branch_id=kot.branch_id,
            data={"order_id": kot.order_id, "kot_number": kot.kot_number, "status": kot.status, "table_session_id": kot.table_session_id}, actor_id=actor_id,
        )

    @staticmethod
    def _order(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, order_id: str, *, lock: bool = False) -> Order:
        KotService._scope(db, principal, business_id, branch_id)
        return OrderService._order(db, principal, business_id, branch_id, order_id, lock=lock)

    @staticmethod
    def _kot(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, kot_id: str, *, lock: bool = False) -> KitchenOrderTicket:
        KotService._scope(db, principal, business_id, branch_id)
        query = db.query(KitchenOrderTicket).filter(
            KitchenOrderTicket.id == kot_id, KitchenOrderTicket.business_id == business_id,
            KitchenOrderTicket.branch_id == branch_id,
        )
        if lock:
            query = query.with_for_update()
        kot = query.first()
        if not kot:
            raise DomainError(404, "KOT_NOT_FOUND", "Kitchen ticket was not found for this business and branch.")
        return kot

    @staticmethod
    def _table_context(db: Session, kot: KitchenOrderTicket) -> KOTTableContext | None:
        if not kot.table_session_id:
            return None
        if kot.table_names_snapshot is not None:
            return KOTTableContext(
                session_id=kot.table_session_id,
                table_names=json.loads(kot.table_names_snapshot),
            )
        links = db.query(TableSessionTable).filter(
            TableSessionTable.session_id == kot.table_session_id,
        ).all()
        # Session links are retained (then deactivated) at checkout, preserving
        # the table context needed by historical KOT detail and reprints.
        return KOTTableContext(session_id=kot.table_session_id, table_names=[link.table.name for link in links])

    @staticmethod
    def _table_names_snapshot(db: Session, order: Order) -> str | None:
        if not order.table_session_id:
            return None
        links = db.query(TableSessionTable).filter(
            TableSessionTable.session_id == order.table_session_id,
            TableSessionTable.is_active == True,
        ).order_by(TableSessionTable.is_primary.desc(), TableSessionTable.attached_at).all()
        return json.dumps([link.table.name for link in links], separators=(",", ":"), ensure_ascii=False)

    @staticmethod
    def _response(db: Session, kot: KitchenOrderTicket) -> KOTResponse:
        business = db.query(Business).filter(Business.id == kot.business_id).first()
        order = db.query(Order).filter(Order.id == kot.order_id).one()
        items = [KOTItemResponse.model_validate(item) for item in kot.items]
        context = KotService._table_context(db, kot)
        return KOTResponse(
            id=kot.id, business_id=kot.business_id, branch_id=kot.branch_id, order_id=kot.order_id,
            order_status=order.status, order_version=order.version,
            table_session_id=kot.table_session_id, kot_number=f"KOT-{kot.kot_number:06d}", status=kot.status,
            notes=kot.notes, created_by_principal_id=kot.created_by_principal_id, version=kot.version,
            created_at=kot.created_at, updated_at=kot.updated_at, preparing_at=kot.preparing_at,
            ready_at=kot.ready_at, served_at=kot.served_at, cancelled_at=kot.cancelled_at, items=items,
            table=context,
            print_payload=KOTPrintPayload(
                business_name=business.name if business else "", kot_number=f"KOT-{kot.kot_number:06d}",
                created_at=kot.created_at, order_type=order.order_type,
                table_names=context.table_names if context else [], notes=kot.notes, items=items,
            ),
        )

    @staticmethod
    def _next_number(db: Session, business_id: str, branch_id: str) -> int:
        sequence = db.query(KitchenKotSequence).filter(
            KitchenKotSequence.business_id == business_id, KitchenKotSequence.branch_id == branch_id,
        ).with_for_update().first()
        if not sequence:
            sequence = KitchenKotSequence(business_id=business_id, branch_id=branch_id, current_value=1)
            db.add(sequence)
            return 1
        sequence.current_value += 1
        return sequence.current_value

    @staticmethod
    def _create_fingerprint(order_id: str, payload: KOTCreateRequest) -> str:
        """Hash the stable client-visible KOT creation intent."""
        intent = {
            "operation": CREATE_KOT_OPERATION,
            "order_id": order_id,
            "notes": payload.notes,
        }
        encoded = json.dumps(intent, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @staticmethod
    def _idempotent_kot(
        db: Session,
        *,
        business_id: str,
        branch_id: str,
        order_id: str,
        idempotency_key: str,
    ) -> KitchenOrderTicket | None:
        return db.query(KitchenOrderTicket).filter(
            KitchenOrderTicket.business_id == business_id,
            KitchenOrderTicket.branch_id == branch_id,
            KitchenOrderTicket.order_id == order_id,
            KitchenOrderTicket.idempotency_key == idempotency_key,
        ).first()

    @staticmethod
    def _validate_idempotent_kot(kot: KitchenOrderTicket, request_hash: str) -> None:
        # Tickets created before this hardening revision have no stored hash;
        # preserve their historical replay behavior without inventing intent.
        if kot.request_hash and kot.request_hash != request_hash:
            raise DomainError(
                409,
                "IDEMPOTENCY_CONFLICT",
                "This KOT key was already used with different request details.",
            )

    @staticmethod
    def _unsent_quantity(item: OrderItem) -> int:
        """Return kitchen work not already sent, excluding cancellations.

        Cancelled sent units are removed from both active order quantity and
        active sent quantity, so they are never reintroduced on a later KOT.
        """
        active_quantity = max(item.quantity - item.cancelled_quantity, 0)
        active_sent_quantity = max(item.kot_sent_quantity - item.cancelled_quantity, 0)
        return max(active_quantity - active_sent_quantity, 0)

    @staticmethod
    def create(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, order_id: str, payload: KOTCreateRequest) -> KOTResponse:
        KotService._scope(db, principal, business_id, branch_id)
        require_permission(principal, "kot.create")
        request_hash = None
        if payload.idempotency_key:
            request_hash = KotService._create_fingerprint(order_id, payload)
            existing = KotService._idempotent_kot(
                db,
                business_id=business_id,
                branch_id=branch_id,
                order_id=order_id,
                idempotency_key=payload.idempotency_key,
            )
            if existing:
                # Recovery happens before stale-version or unsent-item checks.
                KotService._validate_idempotent_kot(existing, request_hash)
                return KotService._response(db, existing)
        order = KotService._order(db, principal, business_id, branch_id, order_id, lock=True)
        if payload.idempotency_key:
            # A concurrent request may have committed while this request waited
            # for the authoritative order lock.
            existing = KotService._idempotent_kot(
                db,
                business_id=business_id,
                branch_id=branch_id,
                order_id=order.id,
                idempotency_key=payload.idempotency_key,
            )
            if existing:
                KotService._validate_idempotent_kot(existing, request_hash)
                return KotService._response(db, existing)
        OrderService._check_version(order, payload.expected_order_version)
        if order.status != "ACTIVE":
            raise DomainError(409, "ORDER_NOT_ACTIVE", "Only active orders can send kitchen tickets.")
        unsent = [
            (item, KotService._unsent_quantity(item))
            for item in order.items
            if item.status == "DRAFT" and KotService._unsent_quantity(item) > 0
        ]
        if not unsent:
            raise DomainError(409, "NO_UNSENT_KOT_ITEMS", "Order has no new items to send to the kitchen.")
        try:
            kot = KitchenOrderTicket(
                id=str(uuid.uuid4()), business_id=business_id, branch_id=branch_id, order_id=order.id,
                table_session_id=order.table_session_id, kot_number=KotService._next_number(db, business_id, branch_id),
                status="PENDING", created_by_principal_id=principal.principal_id, notes=payload.notes,
                version=1, idempotency_key=payload.idempotency_key, request_hash=request_hash,
                table_names_snapshot=KotService._table_names_snapshot(db, order),
            )
            db.add(kot)
            db.flush()
            for item, quantity in unsent:
                db.add(KitchenOrderTicketItem(
                    id=str(uuid.uuid4()), kot_id=kot.id, order_item_id=item.id, product_id=item.product_id,
                    product_name_snapshot=item.product_name_snapshot, quantity=quantity, notes_snapshot=item.notes,
                ))
                item.kot_sent_quantity += quantity
                item.version += 1
            order.version += 1
            KotService._enqueue_event(db, "kot.created", kot, principal.principal_id)
            db.commit()
            db.refresh(kot)
            return KotService._response(db, kot)
        except IntegrityError as exc:
            db.rollback()
            if payload.idempotency_key:
                existing = KotService._idempotent_kot(
                    db,
                    business_id=business_id,
                    branch_id=branch_id,
                    order_id=order_id,
                    idempotency_key=payload.idempotency_key,
                )
                if existing:
                    KotService._validate_idempotent_kot(existing, request_hash)
                    return KotService._response(db, existing)
            raise DomainError(409, "KOT_OPERATION_ALREADY_PROCESSED", "KOT operation could not be completed safely.") from exc
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def list_for_order(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, order_id: str) -> list[KOTResponse]:
        KotService._scope(db, principal, business_id, branch_id)
        require_permission(principal, "kot.view")
        KotService._order(db, principal, business_id, branch_id, order_id)
        rows = db.query(KitchenOrderTicket).filter(
            KitchenOrderTicket.business_id == business_id, KitchenOrderTicket.branch_id == branch_id,
            KitchenOrderTicket.order_id == order_id,
        ).order_by(KitchenOrderTicket.kot_number).all()
        return [KotService._response(db, row) for row in rows]

    @staticmethod
    def get(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, kot_id: str) -> KOTResponse:
        KotService._scope(db, principal, business_id, branch_id)
        require_permission(principal, "kot.view")
        return KotService._response(db, KotService._kot(db, principal, business_id, branch_id, kot_id))

    @staticmethod
    def list(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, *, status: str | None, order_id: str | None, table_session_id: str | None, created_from: datetime | None, created_to: datetime | None, page: int, page_size: int) -> KOTListResponse:
        KotService._scope(db, principal, business_id, branch_id)
        require_permission(principal, "kot.view")
        query = db.query(KitchenOrderTicket).filter(KitchenOrderTicket.business_id == business_id, KitchenOrderTicket.branch_id == branch_id)
        if status:
            query = query.filter(KitchenOrderTicket.status == status)
        else:
            query = query.filter(KitchenOrderTicket.status.in_({"PENDING", "PREPARING", "READY"}))
        if order_id:
            query = query.filter(KitchenOrderTicket.order_id == order_id)
        if table_session_id:
            query = query.filter(KitchenOrderTicket.table_session_id == table_session_id)
        if created_from:
            query = query.filter(KitchenOrderTicket.created_at >= created_from)
        if created_to:
            query = query.filter(KitchenOrderTicket.created_at <= created_to)
        total = query.count()
        rows = query.order_by(KitchenOrderTicket.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return KOTListResponse(items=[KotService._response(db, row) for row in rows], total=total, page=page, page_size=page_size)

    @staticmethod
    def update_status(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, kot_id: str, payload: KOTStatusUpdateRequest) -> KOTResponse:
        kot = KotService._kot(db, principal, business_id, branch_id, kot_id, lock=True)
        if payload.expected_version is not None and payload.expected_version != kot.version:
            raise DomainError(409, "VERSION_CONFLICT", f"Current version is {kot.version}.")
        transitions = {
            ("PENDING", "PREPARING"): ("kot.prepare", "preparing_at"),
            ("PREPARING", "READY"): ("kot.mark_ready", "ready_at"),
            ("READY", "SERVED"): ("kot.serve", "served_at"),
            ("PENDING", "CANCELLED"): ("kot.cancel", "cancelled_at"),
            ("PREPARING", "CANCELLED"): ("kot.cancel", "cancelled_at"),
        }
        if kot.status == "CANCELLED":
            raise DomainError(409, "KOT_ALREADY_CANCELLED", "KOT is already cancelled.")
        transition = transitions.get((kot.status, payload.status))
        if not transition:
            raise DomainError(409, "KOT_INVALID_TRANSITION", "Kitchen status transition is not allowed.")
        require_permission(principal, transition[0])
        kot.status = payload.status
        setattr(kot, transition[1], datetime.now(timezone.utc))
        kot.version += 1
        KotService._enqueue_event(db, f"kot.{kot.status.lower()}", kot, principal.principal_id)
        db.commit()
        db.refresh(kot)
        return KotService._response(db, kot)

    @staticmethod
    def cancel_order_item_quantity(db: Session, principal: PrincipalContext, business_id: str, branch_id: str, order_id: str, item_id: str, payload: OrderItemCancelQuantityRequest) -> KOTCancellationResponse:
        KotService._scope(db, principal, business_id, branch_id)
        require_permission(principal, "kot.cancel")
        order = KotService._order(db, principal, business_id, branch_id, order_id, lock=True)
        OrderService._check_version(order, payload.expected_version)
        if order.status != "ACTIVE":
            raise DomainError(409, "ORDER_NOT_ACTIVE", "Only active orders can cancel kitchen quantities.")
        item = db.query(OrderItem).filter(OrderItem.id == item_id, OrderItem.order_id == order.id).with_for_update().first()
        if not item:
            raise DomainError(404, "ORDER_ITEM_NOT_FOUND", "Order item was not found.")
        cancellable = item.kot_sent_quantity - item.cancelled_quantity
        if payload.quantity > cancellable:
            raise DomainError(409, "KOT_CANCEL_QUANTITY_INVALID", "Cancellation exceeds quantity already sent to kitchen.")
        kot_item = db.query(KitchenOrderTicketItem).join(KitchenOrderTicket).filter(
            KitchenOrderTicketItem.order_item_id == item.id,
            KitchenOrderTicket.business_id == business_id,
        ).order_by(KitchenOrderTicket.created_at.desc()).first()
        cancellation = KitchenKotCancellation(
            id=str(uuid.uuid4()), business_id=business_id, branch_id=branch_id, order_id=order.id,
            order_item_id=item.id, kot_id=kot_item.kot_id if kot_item else None,
            quantity=payload.quantity, reason=payload.reason, created_by_principal_id=principal.principal_id,
        )
        item.cancelled_quantity += payload.quantity
        item.version += 1
        order.version += 1
        db.add(cancellation)
        DomainEventService.enqueue(
            db, event_type="kot.item_cancelled", aggregate_type="kot", aggregate_id=cancellation.kot_id or order.id,
            business_id=business_id, branch_id=branch_id,
            data={"order_id": order.id, "order_item_id": item.id, "quantity": payload.quantity, "reason": payload.reason}, actor_id=principal.principal_id,
        )
        db.commit()
        db.refresh(cancellation)
        return KOTCancellationResponse.model_validate(cancellation)
