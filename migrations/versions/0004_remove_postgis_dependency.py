"""remove postgis dependency

Revision ID: 0004_remove_postgis_dependency
Revises: 0003_bus_stop_alias_updated_at
Create Date: 2026-05-21 00:45:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_remove_postgis_dependency"
down_revision = "0003_bus_stop_alias_updated_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_bus_stops_location")
    op.execute("ALTER TABLE bus_stops DROP COLUMN IF EXISTS location")
    op.execute("CREATE INDEX IF NOT EXISTS ix_bus_stops_latitude ON bus_stops (latitude)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_bus_stops_longitude ON bus_stops (longitude)")
    op.execute("DROP EXTENSION IF EXISTS postgis_tiger_geocoder CASCADE")
    op.execute("DROP EXTENSION IF EXISTS postgis_topology CASCADE")
    op.execute("DROP EXTENSION IF EXISTS postgis CASCADE")


def downgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.add_column("bus_stops", sa.Column("location", sa.Text(), nullable=True))
    op.execute(
        """
        ALTER TABLE bus_stops
        ALTER COLUMN location TYPE GEOGRAPHY(POINT, 4326)
        USING ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
        """
    )
    op.execute(
        """
        UPDATE bus_stops
        SET location = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
        """
    )
    op.execute(
        """
        CREATE INDEX idx_bus_stops_location
        ON bus_stops USING GIST(location)
        """
    )
    op.drop_index("ix_bus_stops_longitude", table_name="bus_stops")
    op.drop_index("ix_bus_stops_latitude", table_name="bus_stops")
