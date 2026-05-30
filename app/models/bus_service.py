from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BusService(Base):
    __tablename__ = "bus_services"
    __table_args__ = (UniqueConstraint("service_no", "direction"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    service_no: Mapped[str] = mapped_column(String(10), index=True)
    operator: Mapped[str | None] = mapped_column(String(10), nullable=True)
    direction: Mapped[int] = mapped_column()
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    origin_code: Mapped[str | None] = mapped_column(String(5), nullable=True)
    destination_code: Mapped[str | None] = mapped_column(String(5), nullable=True)
    am_peak_freq: Mapped[str | None] = mapped_column(Text, nullable=True)
    am_offpeak_freq: Mapped[str | None] = mapped_column(Text, nullable=True)
    pm_peak_freq: Mapped[str | None] = mapped_column(Text, nullable=True)
    pm_offpeak_freq: Mapped[str | None] = mapped_column(Text, nullable=True)
    loop_desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
