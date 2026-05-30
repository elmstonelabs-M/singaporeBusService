from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BusStop(Base):
    __tablename__ = "bus_stops"

    bus_stop_code: Mapped[str] = mapped_column(String(5), primary_key=True)
    road_name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    latitude: Mapped[float] = mapped_column(Float, index=True)
    longitude: Mapped[float] = mapped_column(Float, index=True)
    search_text: Mapped[str] = mapped_column(Text, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
