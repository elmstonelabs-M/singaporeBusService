import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.api.deps import get_static_data_service
from app.core.config import get_settings
from app.schemas.common import ApiResponse, MetaResponse
from app.schemas.static_data import (
    DatasetVersionPayload,
    StaticDataPackagePayload,
    StaticDataVersionPayload,
)
from app.services.static_data_service import StaticDataService

router = APIRouter(prefix="/static-data", tags=["static-data"])
dataset_router = APIRouter(prefix="/dataset", tags=["dataset"])
settings = get_settings()


@router.get(
    "/version",
    response_model=ApiResponse[StaticDataVersionPayload],
    summary="Get static data package version",
    description=(
        "Returns the current static transit dataset version so the client can decide "
        "whether to refresh its local SQLite package."
    ),
    responses={
        200: {
            "description": "Current static data version metadata.",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "version": "2026-05-21T00:00:00+08:00",
                            "package_url": "/v1/static-data/package",
                            "checksum": "sha256:demo",
                            "min_supported_app_version": "1.0.0",
                        },
                        "meta": {
                            "request_id": None,
                            "updated_at": "2026-05-21T00:00:00+08:00",
                            "stale": False,
                        },
                    }
                }
            },
        }
    },
)
async def get_static_data_version(
    service: StaticDataService = Depends(get_static_data_service),
) -> ApiResponse[StaticDataVersionPayload]:
    payload, generated_at = await service.get_version_payload()
    return ApiResponse(data=payload, meta=MetaResponse(updated_at=generated_at))


@router.get(
    "/package",
    response_model=ApiResponse[StaticDataPackagePayload],
    summary="Get full static data package",
    description=(
        "Returns the full static transit dataset intended for first-launch bootstrap "
        "or package refresh into client-side SQLite."
    ),
    responses={
        200: {
            "description": "Full static data package.",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "version": "2026-05-21T00:00:00+08:00",
                            "generated_at": "2026-05-21T00:00:00+08:00",
                            "bus_stops": [
                                {
                                    "bus_stop_code": "83139",
                                    "road_name": "Marine Parade Rd",
                                    "description": "Opp Example Stop",
                                    "latitude": 1.3001,
                                    "longitude": 103.9001,
                                    "search_text": "83139 marine parade rd opp example stop",
                                }
                            ],
                            "bus_routes": [
                                {
                                    "service_no": "36",
                                    "operator": "SBST",
                                    "direction": 1,
                                    "stop_sequence": 1,
                                    "bus_stop_code": "83139",
                                    "distance_km": "0.00",
                                    "wd_first_bus": "0500",
                                    "wd_last_bus": "2300",
                                    "sat_first_bus": "0500",
                                    "sat_last_bus": "2300",
                                    "sun_first_bus": "0600",
                                    "sun_last_bus": "2300",
                                }
                            ],
                            "bus_services": [
                                {
                                    "service_no": "36",
                                    "operator": "SBST",
                                    "direction": 1,
                                    "category": "TRUNK",
                                    "origin_code": "83139",
                                    "destination_code": "65009",
                                    "am_peak_freq": "8-10",
                                    "am_offpeak_freq": "12-15",
                                    "pm_peak_freq": "8-10",
                                    "pm_offpeak_freq": "12-15",
                                    "loop_desc": None,
                                }
                            ],
                        },
                        "meta": {
                            "request_id": None,
                            "updated_at": "2026-05-21T00:00:00+08:00",
                            "stale": False,
                        },
                    }
                }
            },
        }
    },
)
async def get_static_data_package(
    service: StaticDataService = Depends(get_static_data_service),
) -> ApiResponse[StaticDataPackagePayload]:
    payload = await service.get_package_payload()
    return ApiResponse(data=payload, meta=MetaResponse(updated_at=payload.generated_at))


@dataset_router.get(
    "/version",
    response_model=ApiResponse[DatasetVersionPayload],
    summary="Get client dataset version",
    description=(
        "Compatibility endpoint for the Flutter static dataset flow. It exposes "
        "the same underlying static data version with field names expected by "
        "the client-side package updater."
    ),
)
async def get_dataset_version(
    service: StaticDataService = Depends(get_static_data_service),
) -> ApiResponse[DatasetVersionPayload]:
    payload, generated_at = await service.get_version_payload()
    checksum = payload.checksum.removeprefix("sha256:")
    return ApiResponse(
        data=DatasetVersionPayload(
            version=payload.version,
            database_url="/v1/static-data/package",
            sha256=checksum,
            force_update=False,
            updated_at=generated_at,
        ),
        meta=MetaResponse(updated_at=generated_at),
    )


@dataset_router.get(
    "/download",
    response_model=None,
    summary="Download static dataset package",
    description=(
        "Downloads the generated SQLite zip package when available. If no "
        "generated package exists yet, returns the existing full static JSON "
        "package using the standard API envelope as a compatibility fallback."
    ),
)
async def download_dataset(
    service: StaticDataService = Depends(get_static_data_service),
) -> Any:
    manifest = _read_dataset_manifest()
    if manifest is not None:
        package_path = Path(settings.dataset_storage_dir) / manifest["database_file"]
        if package_path.exists():
            return FileResponse(
                package_path,
                media_type="application/zip",
                filename=package_path.name,
                headers={
                    "ETag": manifest["sha256"],
                    "Cache-Control": "public, max-age=3600",
                },
            )

    payload = await service.get_package_payload()
    return ApiResponse(data=payload, meta=MetaResponse(updated_at=payload.generated_at))


def _read_dataset_manifest() -> dict[str, Any] | None:
    manifest_path = Path(settings.dataset_storage_dir) / "manifest.json"
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))
