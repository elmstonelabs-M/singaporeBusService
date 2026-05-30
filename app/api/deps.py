from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.lta_client import LTAClient, get_lta_client
from app.core.cache import CacheService, get_cache_service
from app.core.database import get_db_session
from app.services.arrival_service import ArrivalService
from app.services.bus_stop_alias_service import BusStopAliasService
from app.services.bus_stop_service import BusStopService
from app.services.favorite_service import FavoriteService
from app.services.feedback_email_service import FeedbackEmailService
from app.services.feedback_service import FeedbackService
from app.services.home_service import HomeService
from app.services.static_data_service import StaticDataService


async def get_db() -> AsyncIterator[AsyncSession]:
    async for session in get_db_session():
        yield session


def get_arrival_service(
    lta_client: LTAClient = Depends(get_lta_client),
    cache: CacheService = Depends(get_cache_service),
    db: AsyncSession = Depends(get_db),
) -> ArrivalService:
    return ArrivalService(lta_client=lta_client, cache=cache, db=db)


def get_bus_stop_service(
    cache: CacheService = Depends(get_cache_service),
    db: AsyncSession = Depends(get_db),
) -> BusStopService:
    return BusStopService(cache=cache, db=db)


def get_bus_stop_alias_service(
    cache: CacheService = Depends(get_cache_service),
    db: AsyncSession = Depends(get_db),
) -> BusStopAliasService:
    return BusStopAliasService(db=db, cache=cache)


def get_favorite_service(
    cache: CacheService = Depends(get_cache_service),
    db: AsyncSession = Depends(get_db),
) -> FavoriteService:
    return FavoriteService(db=db, cache=cache)


def get_home_service(
    cache: CacheService = Depends(get_cache_service),
    favorite_service: FavoriteService = Depends(get_favorite_service),
    arrival_service: ArrivalService = Depends(get_arrival_service),
    bus_stop_service: BusStopService = Depends(get_bus_stop_service),
) -> HomeService:
    return HomeService(
        favorite_service=favorite_service,
        arrival_service=arrival_service,
        bus_stop_service=bus_stop_service,
        cache=cache,
    )


def get_static_data_service(
    db: AsyncSession = Depends(get_db),
) -> StaticDataService:
    return StaticDataService(db=db)


def get_feedback_email_service() -> FeedbackEmailService:
    return FeedbackEmailService()


def get_feedback_service(
    db: AsyncSession = Depends(get_db),
    email_service: FeedbackEmailService = Depends(get_feedback_email_service),
) -> FeedbackService:
    return FeedbackService(db=db, email_service=email_service)
