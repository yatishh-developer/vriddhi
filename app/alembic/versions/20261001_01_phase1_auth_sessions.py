"""Add server-side session state for Phase 1 auth tokens.

Revision ID: 20261001_01
Revises: None
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa


revision = "20261001_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("actor_type", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("staff_id", sa.String(), nullable=True),
        sa.Column("business_id", sa.String(), nullable=False),
        sa.Column("device_id", sa.String(), nullable=True),
        sa.Column("refresh_token_hash", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="ACTIVE"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["staff_id"], ["staff_profiles.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("ix_auth_sessions_actor_type", ["actor_type"]),
        ("ix_auth_sessions_user_id", ["user_id"]),
        ("ix_auth_sessions_staff_id", ["staff_id"]),
        ("ix_auth_sessions_business_id", ["business_id"]),
        ("ix_auth_sessions_device_id", ["device_id"]),
        ("ix_auth_sessions_refresh_token_hash", ["refresh_token_hash"]),
        ("ix_auth_sessions_status", ["status"]),
        ("ix_auth_sessions_expires_at", ["expires_at"]),
    ):
        op.create_index(name, "auth_sessions", columns)


def downgrade() -> None:
    op.drop_table("auth_sessions")
