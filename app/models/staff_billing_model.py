from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text

from core.base_model import TimestampMixin
from database.database import Base


class StaffInvite(Base, TimestampMixin):
    __tablename__ = "staff_invites"

    id = Column(String, primary_key=True, index=True)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    branch_id = Column(String, nullable=False, default="main", index=True)

    staff_name = Column(String, nullable=False)
    staff_role = Column(String, nullable=False, default="cashier")
    invite_code_hash = Column(String, nullable=False, unique=True, index=True)
    code_length = Column(Integer, nullable=False, default=6)

    allowed_apps = Column(Text, nullable=False, default='["staff_billing_app"]')
    permissions_json = Column(Text, nullable=False, default="{}")
    feature_flags_snapshot = Column(Text, nullable=False, default="{}")
    business_type_snapshot = Column(String, nullable=True)
    business_name = Column(String, nullable=True)

    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    max_uses = Column(Integer, nullable=False, default=1)
    used_count = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="active", index=True)

    created_by = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    created_by_staff_id = Column(String, nullable=True, index=True)
    source_app = Column(String, nullable=False, default="admin_app", index=True)
    sync_status = Column(String, nullable=False, default="pending", index=True)


class StaffProfile(Base, TimestampMixin):
    __tablename__ = "staff_profiles"

    id = Column(String, primary_key=True, index=True)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    branch_id = Column(String, nullable=False, default="main", index=True)
    invite_id = Column(String, ForeignKey("staff_invites.id"), nullable=True, index=True)

    staff_name = Column(String, nullable=False)
    role = Column(String, nullable=False, default="cashier")
    permissions_json = Column(Text, nullable=False, default="{}")
    allowed_apps = Column(Text, nullable=False, default='["staff_billing_app"]')
    status = Column(String, nullable=False, default="active", index=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    firebase_uid = Column(String, nullable=True, unique=True, index=True)
    auth_provider = Column(String, nullable=True)
    auth_email = Column(String, nullable=True, index=True)
    auth_display_name = Column(String, nullable=True)
    auth_phone_number = Column(String, nullable=True)

    created_by = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    created_by_staff_id = Column(String, nullable=True, index=True)
    source_app = Column(String, nullable=False, default="admin_app", index=True)
    sync_status = Column(String, nullable=False, default="synced", index=True)


class StaffKot(Base, TimestampMixin):
    __tablename__ = "staff_kots"

    id = Column(String, primary_key=True, index=True)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    branch_id = Column(String, nullable=False, default="main", index=True)
    staff_id = Column(String, ForeignKey("staff_profiles.id"), nullable=True, index=True)
    staff_name = Column(String, nullable=True)

    status = Column(String, nullable=False, default="pending", index=True)
    order_type = Column(String, nullable=True)
    table_token = Column(String, nullable=True)
    items_json = Column(Text, nullable=False, default="[]")
    subtotal = Column(Float, nullable=False, default=0.0)
    total_tax = Column(Float, nullable=False, default=0.0)
    total_amount = Column(Float, nullable=False, default=0.0)
    bill_transaction_id = Column(String, ForeignKey("transactions.id"), nullable=True, index=True)

    idempotency_key = Column(String, nullable=True, index=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    created_by_staff_id = Column(String, nullable=True, index=True)
    source_app = Column(String, nullable=False, default="staff_billing_app", index=True)
    sync_status = Column(String, nullable=False, default="pending", index=True)


class StaffHeldBill(Base, TimestampMixin):
    __tablename__ = "staff_held_bills"

    id = Column(String, primary_key=True, index=True)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    branch_id = Column(String, nullable=False, default="main", index=True)
    staff_id = Column(String, ForeignKey("staff_profiles.id"), nullable=True, index=True)
    staff_name = Column(String, nullable=True)

    status = Column(String, nullable=False, default="held", index=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=True, index=True)
    customer_name = Column(String, nullable=True)
    items_json = Column(Text, nullable=False, default="[]")
    subtotal = Column(Float, nullable=False, default=0.0)
    total_tax = Column(Float, nullable=False, default=0.0)
    total_amount = Column(Float, nullable=False, default=0.0)
    bill_transaction_id = Column(String, ForeignKey("transactions.id"), nullable=True, index=True)

    idempotency_key = Column(String, nullable=True, index=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    created_by_staff_id = Column(String, nullable=True, index=True)
    source_app = Column(String, nullable=False, default="staff_billing_app", index=True)
    sync_status = Column(String, nullable=False, default="pending", index=True)


class StaffPayment(Base, TimestampMixin):
    __tablename__ = "staff_payments"

    id = Column(String, primary_key=True, index=True)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    branch_id = Column(String, nullable=False, default="main", index=True)
    staff_id = Column(String, ForeignKey("staff_profiles.id"), nullable=True, index=True)
    staff_name = Column(String, nullable=True)
    bill_transaction_id = Column(String, ForeignKey("transactions.id"), nullable=True, index=True)

    cash_amount = Column(Float, nullable=False, default=0.0)
    upi_amount = Column(Float, nullable=False, default=0.0)
    card_amount = Column(Float, nullable=False, default=0.0)
    other_paid_amount = Column(Float, nullable=False, default=0.0)
    credit_amount = Column(Float, nullable=False, default=0.0)
    total_paid_amount = Column(Float, nullable=False, default=0.0)
    payment_json = Column(Text, nullable=False, default="{}")

    created_by = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    created_by_staff_id = Column(String, nullable=True, index=True)
    source_app = Column(String, nullable=False, default="staff_billing_app", index=True)
    sync_status = Column(String, nullable=False, default="pending", index=True)


class StaffProcessLock(Base, TimestampMixin):
    __tablename__ = "staff_process_locks"

    process_id = Column(String, primary_key=True, index=True)
    process_type = Column(String, nullable=False, index=True)
    entity_id = Column(String, nullable=False, index=True)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    branch_id = Column(String, nullable=False, default="main", index=True)

    handled_by_staff_id = Column(String, ForeignKey("staff_profiles.id"), nullable=True, index=True)
    handled_by_staff_name = Column(String, nullable=True)
    status = Column(String, nullable=False, default="active", index=True)
    locked_at = Column(DateTime(timezone=True), nullable=False)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    created_by = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    created_by_staff_id = Column(String, nullable=True, index=True)
    source_app = Column(String, nullable=False, default="staff_billing_app", index=True)
    sync_status = Column(String, nullable=False, default="pending", index=True)


class StaffRealtimeEvent(Base, TimestampMixin):
    __tablename__ = "staff_realtime_events"

    event_id = Column(String, primary_key=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    entity_type = Column(String, nullable=False, index=True)
    entity_id = Column(String, nullable=False, index=True)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    branch_id = Column(String, nullable=False, default="main", index=True)
    staff_id = Column(String, ForeignKey("staff_profiles.id"), nullable=True, index=True)
    device_id = Column(String, nullable=True, index=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    payload_json = Column(Text, nullable=False, default="{}")
    processed = Column(Boolean, nullable=False, default=False)

    created_by = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    created_by_staff_id = Column(String, nullable=True, index=True)
    source_app = Column(String, nullable=False, default="staff_billing_app", index=True)
    sync_status = Column(String, nullable=False, default="pending", index=True)
