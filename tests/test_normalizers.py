from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.normalizers import (
    is_wheelchair_accessible,
    map_bus_type,
    map_load,
    normalize_arrival_time,
)


def test_normalize_arrival_time_arriving() -> None:
    now = datetime(2026, 5, 19, 21, 10, 0, tzinfo=ZoneInfo("Asia/Singapore"))
    result = normalize_arrival_time("2026-05-19T21:10:59+08:00", now)
    assert result["display"] == "Arr"
    assert result["minutes"] == 0
    assert result["status"] == "ARRIVING"


def test_normalize_arrival_time_one_minute() -> None:
    now = datetime(2026, 5, 19, 21, 10, 0, tzinfo=ZoneInfo("Asia/Singapore"))
    result = normalize_arrival_time("2026-05-19T21:11:59+08:00", now)
    assert result["display"] == "1m"
    assert result["minutes"] == 1


def test_map_load() -> None:
    assert map_load("SEA")["load_color"] == "green"
    assert map_load("SDA")["load_color"] == "yellow"
    assert map_load("LSD")["load_color"] == "red"


def test_wheelchair_and_bus_type() -> None:
    assert is_wheelchair_accessible("WAB") is True
    assert map_bus_type("DD")["bus_type_label"] == "Double Deck"
