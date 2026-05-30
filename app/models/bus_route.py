from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BusRoute(Base):
    __tablename__ = "bus_routes"
    __table_args__ = (
        UniqueConstraint("service_no", "direction", "stop_sequence", "bus_stop_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    service_no: Mapped[str] = mapped_column(String(10), index=True)
    operator: Mapped[str | None] = mapped_column(String(10), nullable=True)
    direction: Mapped[int] = mapped_column(SmallInteger)
    stop_sequence: Mapped[int] = mapped_column()
    bus_stop_code: Mapped[str] = mapped_column(ForeignKey("bus_stops.bus_stop_code"), index=True)
    distance_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    wd_first_bus: Mapped[str | None] = mapped_column(String(4), nullable=True)
    wd_last_bus: Mapped[str | None] = mapped_column(String(4), nullable=True)
    sat_first_bus: Mapped[str | None] = mapped_column(String(4), nullable=True)
    sat_last_bus: Mapped[str | None] = mapped_column(String(4), nullable=True)
    sun_first_bus: Mapped[str | None] = mapped_column(String(4), nullable=True)
    sun_last_bus: Mapped[str | None] = mapped_column(String(4), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
