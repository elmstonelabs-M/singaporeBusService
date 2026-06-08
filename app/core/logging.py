from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path
from time import perf_counter
from typing import Any
import uuid

from fastapi import Request, Response

from app.utils.request import get_client_ip

MAX_LOG_LINE_LENGTH = 20_000
LOGGER_NAME = "app.http"


def configure_logging(log_level: str, log_file_path: str | None = None) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    if log_file_path:
        path = Path(log_file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)


def _decode_payload(payload: bytes, content_type: str | None) -> Any:
    if not payload:
        return None

    text = payload.decode("utf-8", errors="replace")
    if content_type and "application/json" in content_type.lower():
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text


def _truncate_log_line(record: dict[str, Any]) -> str:
    line = json.dumps(record, ensure_ascii=False, default=str)
    if len(line) <= MAX_LOG_LINE_LENGTH:
        return line
    return f"{line[:MAX_LOG_LINE_LENGTH]}... [truncated {len(line) - MAX_LOG_LINE_LENGTH} chars]"


async def http_logging_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    logger = logging.getLogger(LOGGER_NAME)
    request_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:12]}"
    client_ip = get_client_ip(request)
    started_at = perf_counter()
    request_body = _decode_payload(await request.body(), request.headers.get("content-type"))

    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        logger.exception(
            _truncate_log_line(
                {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "query": request.url.query or None,
                    "client": client_ip,
                    "request_body": request_body,
                    "error": {
                        "type": exc.__class__.__name__,
                        "message": str(exc),
                    },
                    "duration_ms": duration_ms,
                }
            )
        )
        raise

    response_body_bytes = bytearray()
    async for chunk in response.body_iterator:
        response_body_bytes.extend(chunk)

    response_body = _decode_payload(bytes(response_body_bytes), response.headers.get("content-type"))
    duration_ms = round((perf_counter() - started_at) * 1000, 2)

    logger.info(
        _truncate_log_line(
            {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query": request.url.query or None,
                "client": client_ip,
                "request_body": request_body,
                "status_code": response.status_code,
                "response_body": response_body,
                "duration_ms": duration_ms,
            }
        )
    )

    new_response = Response(
        content=bytes(response_body_bytes),
        status_code=response.status_code,
        media_type=response.media_type,
        background=response.background,
    )
    for header_name, header_value in response.headers.items():
        if header_name.lower() in {"content-length", "content-type"}:
            continue
        new_response.headers[header_name] = header_value
    return new_response
