import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1 import arrivals, bus_stop_aliases, bus_stops, favorites, feedback, home, static_data
from app.core.cache import get_cache_service
from app.core.config import get_settings
from app.core.database import SessionLocal, init_database
from app.core.errors import AppError
from app.core.logging import configure_logging, http_logging_middleware
from app.services.bus_stop_catalog import bus_stop_catalog

settings = get_settings()
configure_logging(settings.log_level, settings.log_file_path)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await init_database()
    await bus_stop_catalog.load()
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

app.middleware("http")(http_logging_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bus_stops.router, prefix="/v1")
app.include_router(arrivals.router, prefix="/v1")
app.include_router(bus_stop_aliases.router, prefix="/v1")
app.include_router(favorites.router, prefix="/v1")
app.include_router(favorites.group_router, prefix="/v1")
app.include_router(home.router, prefix="/v1")
app.include_router(static_data.router, prefix="/v1")
app.include_router(static_data.dataset_router, prefix="/v1")
app.include_router(feedback.router, prefix="/v1")


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = request.headers.get("x-request-id", f"req_{uuid.uuid4().hex[:12]}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": request_id,
            }
        },
    )


@app.get("/health")
async def health() -> dict[str, str]:
    database_status = "ok"
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"

    redis_status = "ok" if await get_cache_service().ping() else "error"

    if database_status == "error" or redis_status == "error":
        raise HTTPException(
            status_code=503,
            detail={"status": "degraded", "database": database_status, "redis": redis_status},
        )
    return {"status": "ok", "database": database_status, "redis": redis_status}
