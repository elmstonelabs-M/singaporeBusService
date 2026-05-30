"""add static data state

Revision ID: 0006_add_static_data_state
Revises: 0005_add_feedback
Create Date: 2026-05-23 00:30:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_add_static_data_state"
down_revision = "0005_add_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "static_data_state",
        sa.Column("key", sa.String(length=50), primary_key=True),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("static_data_state")
