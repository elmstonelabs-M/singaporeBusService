"""bus stop aliases

Revision ID: 0002_bus_stop_aliases
Revises: 0001_initial_schema
Create Date: 2026-05-20 11:10:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_bus_stop_aliases"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bus_stop_aliases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "bus_stop_code",
            sa.String(length=5),
            sa.ForeignKey("bus_stops.bus_stop_code", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alias", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "bus_stop_code"),
    )
    op.create_index("ix_bus_stop_aliases_user_id", "bus_stop_aliases", ["user_id"])
    op.create_index(
        "ix_bus_stop_aliases_bus_stop_code",
        "bus_stop_aliases",
        ["bus_stop_code"],
    )


def downgrade() -> None:
    op.drop_index("ix_bus_stop_aliases_bus_stop_code", table_name="bus_stop_aliases")
    op.drop_index("ix_bus_stop_aliases_user_id", table_name="bus_stop_aliases")
    op.drop_table("bus_stop_aliases")
