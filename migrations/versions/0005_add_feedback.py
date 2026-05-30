"""add feedback

Revision ID: 0005_add_feedback
Revises: 0004_remove_postgis_dependency
Create Date: 2026-05-21 13:20:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_add_feedback"
down_revision = "0004_remove_postgis_dependency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_device_id", sa.String(length=255), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("app_version", sa.String(length=50), nullable=True),
        sa.Column("device_info", sa.Text(), nullable=True),
        sa.Column("email_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("email_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_feedback_user_device_id", "feedback", ["user_device_id"])


def downgrade() -> None:
    op.drop_index("ix_feedback_user_device_id", table_name="feedback")
    op.drop_table("feedback")
