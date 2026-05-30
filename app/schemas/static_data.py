from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class StaticDataVersionPayload(BaseModel):
    version: str = Field(description="Opaque version string for the current static dataset.")
    package_url: str = Field(description="Relative API path for the full static data package.")
    checksum: str = Field(description="Checksum for the full package payload.")
    min_supported_app_version: str = Field(
        default="1.0.0",
        description="Minimum frontend app version supported by this static package.",
    )


class DatasetVersionPayload(BaseModel):
    version: str = Field(description="Version string for the current static dataset.")
    database_url: str = Field(description="URL or relative API path for the dataset download.")
    sha256: str = Field(description="SHA-256 checksum for the dataset package.")
    force_update: bool = Field(
        default=False,
        description="Whether the frontend should force the static dataset update.",
    )
    updated_at: datetime = Field(description="Timestamp when the dataset was generated.")


class StaticBusStopItem(BaseModel):
    bus_stop_code: str = Field(description="5-digit bus stop code.")
    road_name: str = Field(description="Road name of the bus stop.")
    description: str = Field(description="Official LTA bus stop name.")
    latitude: float = Field(description="Bus stop latitude.")
    longitude: float = Field(description="Bus stop longitude.")
    search_text: str = Field(description="Normalized search text used for local search.")


class StaticBusRouteItem(BaseModel):
    service_no: str = Field(description="Bus service number.")
    operator: str | None = Field(default=None, description="Bus operator code.")
    direction: int = Field(description="Direction number for the route.")
    stop_sequence: int = Field(description="Stop sequence within the route direction.")
    bus_stop_code: str = Field(description="5-digit bus stop code.")
    distance_km: Decimal | None = Field(default=None, description="Distance in kilometers.")
    wd_first_bus: str | None = Field(default=None, description="Weekday first bus time.")
    wd_last_bus: str | None = Field(default=None, description="Weekday last bus time.")
    sat_first_bus: str | None = Field(default=None, description="Saturday first bus time.")
    sat_last_bus: str | None = Field(default=None, description="Saturday last bus time.")
    sun_first_bus: str | None = Field(default=None, description="Sunday first bus time.")
    sun_last_bus: str | None = Field(default=None, description="Sunday last bus time.")


class StaticBusServiceItem(BaseModel):
    service_no: str = Field(description="Bus service number.")
    operator: str | None = Field(default=None, description="Bus operator code.")
    direction: int = Field(description="Direction number for the service.")
    category: str | None = Field(default=None, description="Service category.")
    origin_code: str | None = Field(default=None, description="Origin bus stop code.")
    destination_code: str | None = Field(default=None, description="Destination bus stop code.")
    am_peak_freq: str | None = Field(default=None, description="AM peak frequency.")
    am_offpeak_freq: str | None = Field(default=None, description="AM off-peak frequency.")
    pm_peak_freq: str | None = Field(default=None, description="PM peak frequency.")
    pm_offpeak_freq: str | None = Field(default=None, description="PM off-peak frequency.")
    loop_desc: str | None = Field(default=None, description="Loop service description.")


class StaticDataPackagePayload(BaseModel):
    version: str = Field(description="Version string for this package.")
    generated_at: datetime = Field(description="Timestamp when the package was generated.")
    bus_stops: list[StaticBusStopItem]
    bus_routes: list[StaticBusRouteItem]
    bus_services: list[StaticBusServiceItem]
