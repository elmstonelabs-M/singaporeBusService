"""add updated_at to bus_stop_aliases

Revision ID: 0003_bus_stop_alias_updated_at
Revises: 0002_bus_stop_aliases
Create Date: 2026-05-20 15:20:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_bus_stop_alias_updated_at"
down_revision = "0002_bus_stop_aliases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bus_stop_aliases",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("bus_stop_aliases", "updated_at")
