import os
from collections.abc import AsyncIterator

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

from app.api.deps import (
    get_arrival_service,
    get_bus_stop_alias_service,
    get_bus_stop_service,
    get_db,
    get_favorite_service,
    get_feedback_email_service,
    get_feedback_service,
    get_home_service,
)
from app.clients.lta_client import LTAClient
from app.core.cache import CacheService
from app.main import app
from app.models import Base
from app.services.arrival_service import ArrivalService
from app.services.bus_stop_alias_service import BusStopAliasService
from app.services.bus_stop_service import BusStopService
from app.services.favorite_service import FavoriteService
from app.services.feedback_email_service import FeedbackEmailService
from app.services.feedback_service import FeedbackService
from app.services.home_service import HomeService
from app.services.retention_service import RetentionService, get_retention_service


class FakeFeedbackEmailService(FeedbackEmailService):
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.sent_feedback_ids: list[str] = []

    async def send_feedback(self, feedback) -> None:  # type: ignore[override]
        if self.should_fail:
            raise RuntimeError("smtp unavailable")
        self.sent_feedback_ids.append(str(feedback.id))


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def cache_service() -> CacheService:
    return CacheService(fakeredis.aioredis.FakeRedis(decode_responses=True))


@pytest.fixture
def lta_client() -> LTAClient:
    return LTAClient(account_key="test-key", base_url="https://example.com")


@pytest.fixture
def feedback_email_service() -> FakeFeedbackEmailService:
    return FakeFeedbackEmailService()


@pytest.fixture
async def api_client(
    db_session: AsyncSession,
    cache_service: CacheService,
    lta_client: LTAClient,
    feedback_email_service: FakeFeedbackEmailService,
) -> AsyncIterator[AsyncClient]:
    def _arrival_service() -> ArrivalService:
        return ArrivalService(lta_client=lta_client, cache=cache_service, db=db_session)

    def _bus_stop_service() -> BusStopService:
        return BusStopService(cache=cache_service, db=db_session)

    def _favorite_service() -> FavoriteService:
        return FavoriteService(db=db_session, cache=cache_service)

    def _bus_stop_alias_service() -> BusStopAliasService:
        return BusStopAliasService(db=db_session, cache=cache_service)

    def _home_service() -> HomeService:
        return HomeService(
            favorite_service=_favorite_service(),
            arrival_service=_arrival_service(),
            bus_stop_service=_bus_stop_service(),
            cache=cache_service,
        )

    def _feedback_email_service() -> FeedbackEmailService:
        return feedback_email_service

    def _feedback_service() -> FeedbackService:
        return FeedbackService(db=db_session, email_service=feedback_email_service)

    def _retention_service() -> RetentionService:
        return RetentionService(cache=cache_service)

    async def _db_override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[get_arrival_service] = _arrival_service
    app.dependency_overrides[get_bus_stop_service] = _bus_stop_service
    app.dependency_overrides[get_bus_stop_alias_service] = _bus_stop_alias_service
    app.dependency_overrides[get_favorite_service] = _favorite_service
    app.dependency_overrides[get_home_service] = _home_service
    app.dependency_overrides[get_feedback_email_service] = _feedback_email_service
    app.dependency_overrides[get_feedback_service] = _feedback_service
    app.dependency_overrides[get_retention_service] = _retention_service
    app.state.retention_service = _retention_service()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client

    if hasattr(app.state, "retention_service"):
        delattr(app.state, "retention_service")
    app.dependency_overrides.clear()
