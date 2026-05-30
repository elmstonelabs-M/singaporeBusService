import asyncio
import hashlib
import json
import shutil
import sqlite3
import zipfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.static_data_service import StaticDataService


def _safe_version(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Unsupported type for JSON encoding: {type(value)!r}")


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE bus_stops (
            bus_stop_code TEXT PRIMARY KEY,
            road_name TEXT NOT NULL,
            description TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            search_text TEXT NOT NULL,
            updated_at TEXT
        );

        CREATE TABLE bus_routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_no TEXT NOT NULL,
            operator TEXT,
            direction INTEGER,
            stop_sequence INTEGER,
            bus_stop_code TEXT NOT NULL,
            distance_km REAL,
            wd_first_bus TEXT,
            wd_last_bus TEXT,
            sat_first_bus TEXT,
            sat_last_bus TEXT,
            sun_first_bus TEXT,
            sun_last_bus TEXT
        );

        CREATE TABLE bus_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_no TEXT NOT NULL,
            operator TEXT,
            direction INTEGER,
            category TEXT,
            origin_code TEXT,
            destination_code TEXT,
            am_peak_freq TEXT,
            am_offpeak_freq TEXT,
            pm_peak_freq TEXT,
            pm_offpeak_freq TEXT,
            loop_desc TEXT
        );

        CREATE INDEX idx_bus_stops_search_text ON bus_stops(search_text);
        CREATE INDEX idx_bus_routes_service_no ON bus_routes(service_no);
        CREATE INDEX idx_bus_routes_bus_stop_code ON bus_routes(bus_stop_code);
        CREATE INDEX idx_bus_routes_service_stop ON bus_routes(service_no, bus_stop_code);
        CREATE INDEX idx_bus_services_service_no ON bus_services(service_no);
        """
    )


def _write_sqlite_database(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        path.unlink()

    with sqlite3.connect(path) as connection:
        _create_schema(connection)
        connection.executemany(
            """
            INSERT INTO bus_stops (
                bus_stop_code, road_name, description, latitude, longitude, search_text, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["bus_stop_code"],
                    item["road_name"],
                    item["description"],
                    item["latitude"],
                    item["longitude"],
                    item["search_text"],
                    payload["generated_at"],
                )
                for item in payload["bus_stops"]
            ],
        )
        connection.executemany(
            """
            INSERT INTO bus_routes (
                service_no, operator, direction, stop_sequence, bus_stop_code, distance_km,
                wd_first_bus, wd_last_bus, sat_first_bus, sat_last_bus, sun_first_bus, sun_last_bus
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["service_no"],
                    item["operator"],
                    item["direction"],
                    item["stop_sequence"],
                    item["bus_stop_code"],
                    float(item["distance_km"]) if item["distance_km"] is not None else None,
                    item["wd_first_bus"],
                    item["wd_last_bus"],
                    item["sat_first_bus"],
                    item["sat_last_bus"],
                    item["sun_first_bus"],
                    item["sun_last_bus"],
                )
                for item in payload["bus_routes"]
            ],
        )
        connection.executemany(
            """
            INSERT INTO bus_services (
                service_no, operator, direction, category, origin_code, destination_code,
                am_peak_freq, am_offpeak_freq, pm_peak_freq, pm_offpeak_freq, loop_desc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["service_no"],
                    item["operator"],
                    item["direction"],
                    item["category"],
                    item["origin_code"],
                    item["destination_code"],
                    item["am_peak_freq"],
                    item["am_offpeak_freq"],
                    item["pm_peak_freq"],
                    item["pm_offpeak_freq"],
                    item["loop_desc"],
                )
                for item in payload["bus_services"]
            ],
        )
        connection.commit()


def _write_zip(database_path: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(database_path, arcname=database_path.name)


async def generate_sqlite_dataset() -> dict[str, Any]:
    settings = get_settings()
    output_dir = Path(settings.dataset_storage_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    async with SessionLocal() as session:
        service = StaticDataService(session)
        package = await service.get_package_payload()

    payload = package.model_dump(mode="json")
    version = payload["version"]
    safe_version = _safe_version(version)
    initial_db_path = output_dir / "sg_bus_initial.db"
    versioned_db_path = output_dir / f"sg_bus_{safe_version}.db"
    zip_path = output_dir / f"sg_bus_{safe_version}.db.zip"
    manifest_path = output_dir / "manifest.json"

    with NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        temp_path = Path(temp_file.name)
    try:
        _write_sqlite_database(temp_path, payload)
        shutil.copyfile(temp_path, initial_db_path)
        shutil.copyfile(temp_path, versioned_db_path)
    finally:
        temp_path.unlink(missing_ok=True)

    _write_zip(versioned_db_path, zip_path)
    manifest = {
        "version": version,
        "database_file": zip_path.name,
        "sha256": _sha256(zip_path),
        "generated_at": payload["generated_at"],
        "force_update": False,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    manifest = asyncio.run(generate_sqlite_dataset())
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
