"""add feedback client ip and daily limit support

Revision ID: 0007_feedback_ip_limit
Revises: 0006_add_static_data_state
Create Date: 2026-05-31 00:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_feedback_ip_limit"
down_revision = "0006_add_static_data_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "feedback",
        sa.Column("client_ip", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_feedback_client_ip", "feedback", ["client_ip"])


def downgrade() -> None:
    op.drop_index("ix_feedback_client_ip", table_name="feedback")
    op.drop_column("feedback", "client_ip")
