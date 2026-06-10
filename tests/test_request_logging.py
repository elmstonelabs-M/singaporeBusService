import asyncio
import logging
import tempfile
from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.logging import configure_logging, http_logging_middleware


def test_http_logging_writes_request_and_response() -> None:
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp_dir:
        log_path = Path(tmp_dir) / "app.log"
        configure_logging("INFO", str(log_path))

        app = FastAPI()
        app.middleware("http")(http_logging_middleware)

        @app.post("/echo")
        async def echo(payload: dict[str, str]) -> dict[str, str]:
            return {"received": payload["message"]}

        async def _run() -> None:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post("/echo?q=1", json={"message": "hello"})

            assert response.status_code == 200
            assert response.json() == {"received": "hello"}

        asyncio.run(_run())

        log_text = log_path.read_text(encoding="utf-8")
        assert '"path": "/echo"' in log_text
        assert '"query": "q=1"' in log_text
        assert '"client": "127.0.0.1"' in log_text
        assert '"request_body": {"message": "hello"}' in log_text
        assert '"response_body": {"received": "hello"}' in log_text
        assert '"status_code": 200' in log_text
        assert '"duration_ms":' in log_text

        logging.shutdown()


def test_http_logging_prefers_forwarded_client_ip() -> None:
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp_dir:
        log_path = Path(tmp_dir) / "app.log"
        configure_logging("INFO", str(log_path))

        app = FastAPI()
        app.middleware("http")(http_logging_middleware)

        @app.get("/ping")
        async def ping() -> dict[str, str]:
            return {"status": "ok"}

        async def _run() -> None:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.get(
                    "/ping?user_device_id=query-device",
                    headers={
                        "x-forwarded-for": "203.0.113.10, 10.0.0.2",
                        "x-device-id": "header-device",
                    },
                )

            assert response.status_code == 200

        asyncio.run(_run())

        log_text = log_path.read_text(encoding="utf-8")
        assert '"client": "203.0.113.10"' in log_text
        assert '"device_id": "header-device"' in log_text

        logging.shutdown()


def test_http_logging_summarizes_bus_stop_arrivals_response() -> None:
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp_dir:
        log_path = Path(tmp_dir) / "app.log"
        configure_logging("INFO", str(log_path))

        app = FastAPI()
        app.middleware("http")(http_logging_middleware)

        @app.get("/v1/bus-stops/{bus_stop_code}/arrivals")
        async def arrivals(bus_stop_code: str) -> dict[str, object]:
            return {
                "data": {
                    "bus_stop_code": bus_stop_code,
                    "description": "Nan Hua Pr Sch",
                    "services": [{"service_no": "105"}],
                },
                "meta": {"stale": False},
            }

        async def _run() -> None:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.get("/v1/bus-stops/20101/arrivals")

            assert response.status_code == 200
            assert response.json()["data"]["services"] == [{"service_no": "105"}]

        asyncio.run(_run())

        log_text = log_path.read_text(encoding="utf-8")
        assert '"response_body": {"data": {"bus_stop_code": "20101"}}' in log_text
        assert '"description": "Nan Hua Pr Sch"' not in log_text
        assert '"service_no": "105"' not in log_text

        logging.shutdown()


def test_http_logging_excludes_health_and_ops_logs() -> None:
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp_dir:
        log_path = Path(tmp_dir) / "app.log"
        configure_logging("INFO", str(log_path))

        app = FastAPI()
        app.middleware("http")(http_logging_middleware)

        @app.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "ok"}

        @app.get("/health/full")
        async def full_health() -> dict[str, str]:
            return {"status": "ok"}

        @app.get("/ops/logs")
        async def ops_logs() -> str:
            return "large logs page"

        async def _run() -> None:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                assert (await client.get("/health")).status_code == 200
                assert (await client.get("/health/full")).status_code == 200
                assert (await client.get("/ops/logs?token=secret")).status_code == 200

        asyncio.run(_run())

        logging.shutdown()
        log_text = log_path.read_text(encoding="utf-8")
        assert "INFO app.http" not in log_text
