from typing import Any

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_fixed

from app.core.config import get_settings
from app.core.errors import ExternalServiceError


class LTAClient:
    def __init__(
        self,
        account_key: str,
        base_url: str,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.account_key = account_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @property
    def headers(self) -> dict[str, str]:
        return {
            "AccountKey": self.account_key,
            "accept": "application/json",
        }

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.account_key:
            raise ExternalServiceError(
                "LTA_ACCOUNT_KEY_MISSING",
                "LTA account key is not configured.",
            )

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_fixed(0.5),
            retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
            reraise=True,
        ):
            with attempt:
                async with httpx.AsyncClient(
                    base_url=self.base_url,
                    timeout=self.timeout_seconds,
                    headers=self.headers,
                ) as client:
                    response = await client.get(path, params=params)
                    response.raise_for_status()
                    return response.json()
        raise ExternalServiceError("LTA_REQUEST_FAILED")

    async def get_bus_arrival(
        self,
        bus_stop_code: str,
        service_no: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"BusStopCode": bus_stop_code}
        if service_no:
            params["ServiceNo"] = service_no
        return await self._get("/v3/BusArrival", params=params)

    async def get_bus_stops(self, skip: int = 0) -> list[dict[str, Any]]:
        payload = await self._get("/BusStops", params={"$skip": skip})
        return payload.get("value", [])

    async def get_bus_routes(self, skip: int = 0) -> list[dict[str, Any]]:
        payload = await self._get("/BusRoutes", params={"$skip": skip})
        return payload.get("value", [])

    async def get_bus_services(self, skip: int = 0) -> list[dict[str, Any]]:
        payload = await self._get("/BusServices", params={"$skip": skip})
        return payload.get("value", [])


def get_lta_client() -> LTAClient:
    settings = get_settings()
    return LTAClient(
        account_key=settings.lta_account_key,
        base_url=settings.lta_base_url,
        timeout_seconds=settings.lta_timeout_seconds,
    )
