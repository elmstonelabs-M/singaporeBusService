from datetime import datetime
from typing import Any

from app.utils.time_utils import parse_singapore_time

BUS_TYPE_LABELS = {
    "SD": "Single Deck",
    "DD": "Double Deck",
    "BD": "Bendy",
}


def normalize_arrival_time(estimated_arrival: str | None, now: datetime) -> dict[str, Any]:
    if not estimated_arrival:
        return {
            "display": None,
            "minutes": None,
            "status": "NO_DATA",
            "estimated_arrival": None,
        }

    eta = parse_singapore_time(estimated_arrival)
    diff_seconds = max(0, int((eta - now).total_seconds()))
    minutes = diff_seconds // 60

    if minutes < 1:
        display = "Arr"
        status = "ARRIVING"
    else:
        display = f"{minutes}m"
        status = "ESTIMATED"

    return {
        "display": display,
        "minutes": minutes,
        "status": status,
        "estimated_arrival": eta,
    }


def map_load(load: str | None) -> dict[str, str | None]:
    mapping = {
        "SEA": ("Seats Available", "green"),
        "SDA": ("Standing Available", "yellow"),
        "LSD": ("Limited Standing", "red"),
    }
    label, color = mapping.get(load or "", ("Unknown", "gray"))
    return {
        "load": load,
        "load_label": label,
        "load_color": color,
    }


def is_wheelchair_accessible(feature: str | None) -> bool:
    return feature == "WAB"


def map_bus_type(bus_type: str | None) -> dict[str, str | None]:
    return {
        "bus_type": bus_type,
        "bus_type_label": BUS_TYPE_LABELS.get(bus_type or ""),
    }
