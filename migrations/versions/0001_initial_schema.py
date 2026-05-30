"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-19 22:10:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bus_stops",
        sa.Column("bus_stop_code", sa.String(length=5), primary_key=True),
        sa.Column("road_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_bus_stops_search_text", "bus_stops", ["search_text"])
    op.create_index("ix_bus_stops_latitude", "bus_stops", ["latitude"])
    op.create_index("ix_bus_stops_longitude", "bus_stops", ["longitude"])

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("device_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_users_device_id", "users", ["device_id"], unique=True)

    op.create_table(
        "bus_routes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("service_no", sa.String(length=10), nullable=False),
        sa.Column("operator", sa.String(length=10), nullable=True),
        sa.Column("direction", sa.SmallInteger(), nullable=False),
        sa.Column("stop_sequence", sa.Integer(), nullable=False),
        sa.Column(
            "bus_stop_code",
            sa.String(length=5),
            sa.ForeignKey("bus_stops.bus_stop_code"),
            nullable=False,
        ),
        sa.Column("distance_km", sa.Numeric(7, 2), nullable=True),
        sa.Column("wd_first_bus", sa.String(length=4), nullable=True),
        sa.Column("wd_last_bus", sa.String(length=4), nullable=True),
        sa.Column("sat_first_bus", sa.String(length=4), nullable=True),
        sa.Column("sat_last_bus", sa.String(length=4), nullable=True),
        sa.Column("sun_first_bus", sa.String(length=4), nullable=True),
        sa.Column("sun_last_bus", sa.String(length=4), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("service_no", "direction", "stop_sequence", "bus_stop_code"),
    )
    op.create_index("ix_bus_routes_bus_stop_code", "bus_routes", ["bus_stop_code"])
    op.create_index("ix_bus_routes_service_no", "bus_routes", ["service_no"])

    op.create_table(
        "bus_services",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("service_no", sa.String(length=10), nullable=False),
        sa.Column("operator", sa.String(length=10), nullable=True),
        sa.Column("direction", sa.Integer(), nullable=False),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("origin_code", sa.String(length=5), nullable=True),
        sa.Column("destination_code", sa.String(length=5), nullable=True),
        sa.Column("am_peak_freq", sa.Text(), nullable=True),
        sa.Column("am_offpeak_freq", sa.Text(), nullable=True),
        sa.Column("pm_peak_freq", sa.Text(), nullable=True),
        sa.Column("pm_offpeak_freq", sa.Text(), nullable=True),
        sa.Column("loop_desc", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("service_no", "direction"),
    )
    op.create_index("ix_bus_services_service_no", "bus_services", ["service_no"])

    op.create_table(
        "favorite_groups",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("emoji", sa.String(length=20), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_favorite_groups_user_id", "favorite_groups", ["user_id"])

    op.create_table(
        "favorite_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "group_id",
            sa.Uuid(),
            sa.ForeignKey("favorite_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "bus_stop_code",
            sa.String(length=5),
            sa.ForeignKey("bus_stops.bus_stop_code"),
            nullable=False,
        ),
        sa.Column("service_no", sa.String(length=10), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("group_id", "bus_stop_code", "service_no"),
    )
    op.create_index("ix_favorite_items_group_id", "favorite_items", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_favorite_items_group_id", table_name="favorite_items")
    op.drop_table("favorite_items")
    op.drop_index("ix_favorite_groups_user_id", table_name="favorite_groups")
    op.drop_table("favorite_groups")
    op.drop_index("ix_bus_services_service_no", table_name="bus_services")
    op.drop_table("bus_services")
    op.drop_index("ix_bus_routes_service_no", table_name="bus_routes")
    op.drop_index("ix_bus_routes_bus_stop_code", table_name="bus_routes")
    op.drop_table("bus_routes")
    op.drop_index("ix_users_device_id", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_bus_stops_longitude", table_name="bus_stops")
    op.drop_index("ix_bus_stops_latitude", table_name="bus_stops")
    op.drop_index("ix_bus_stops_search_text", table_name="bus_stops")
    op.drop_table("bus_stops")
