from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import CacheService
from app.models.bus_stop import BusStop
from app.models.bus_stop_alias import BusStopAlias
from app.models.favorite import FavoriteGroup, FavoriteItem
from app.models.user import User
from app.schemas.bus_stop import BusStopAliasUpsert


class BusStopAliasService:
    def __init__(self, db: AsyncSession, cache: CacheService | None = None) -> None:
        self.db = db
        self.cache = cache

    async def upsert_alias(self, payload: BusStopAliasUpsert) -> BusStopAlias:
        user = await self._get_or_create_user(payload.user_device_id)
        result = await self.db.execute(
            select(BusStopAlias)
            .where(BusStopAlias.user_id == user.id)
            .where(BusStopAlias.bus_stop_code == payload.bus_stop_code)
        )
        alias = result.scalar_one_or_none()
        if alias is None:
            alias = BusStopAlias(
                user_id=user.id,
                bus_stop_code=payload.bus_stop_code,
                alias=payload.alias,
            )
            self.db.add(alias)
        else:
            alias.alias = payload.alias
        await self._sync_group_names_for_bus_stop(
            user_id=user.id,
            bus_stop_code=payload.bus_stop_code,
            name=payload.alias,
        )
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(alias)
        await self._invalidate_home_cache(payload.user_device_id)
        return alias

    async def list_aliases(self, user_device_id: str) -> list[BusStopAlias]:
        user = await self._get_or_create_user(user_device_id)
        result = await self.db.execute(
            select(BusStopAlias)
            .where(BusStopAlias.user_id == user.id)
            .order_by(BusStopAlias.bus_stop_code)
        )
        return list(result.scalars().all())

    async def delete_alias(self, user_device_id: str, bus_stop_code: str) -> None:
        user = await self._get_or_create_user(user_device_id)
        await self.db.execute(
            delete(BusStopAlias)
            .where(BusStopAlias.user_id == user.id)
            .where(BusStopAlias.bus_stop_code == bus_stop_code)
        )
        bus_stop = await self._get_bus_stop(bus_stop_code)
        if bus_stop is not None:
            await self._sync_group_names_for_bus_stop(
                user_id=user.id,
                bus_stop_code=bus_stop_code,
                name=bus_stop.description,
            )
        await self.db.commit()
        await self._invalidate_home_cache(user_device_id)

    async def get_alias_map(self, user_device_id: str | None) -> dict[str, str]:
        if not user_device_id:
            return {}
        aliases = await self.list_aliases(user_device_id)
        return {item.bus_stop_code: item.alias for item in aliases}

    async def _get_or_create_user(self, device_id: str) -> User:
        result = await self.db.execute(select(User).where(User.device_id == device_id))
        user = result.scalar_one_or_none()
        if user is not None:
            return user
        user = User(device_id=device_id)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def _sync_group_names_for_bus_stop(
        self,
        user_id: object,
        bus_stop_code: str,
        name: str,
    ) -> None:
        result = await self.db.execute(
            select(FavoriteGroup.id)
            .join(FavoriteItem, FavoriteItem.group_id == FavoriteGroup.id)
            .where(
                FavoriteGroup.user_id == user_id,
                FavoriteItem.bus_stop_code == bus_stop_code,
            )
            .group_by(FavoriteGroup.id)
        )
        group_ids = list(result.scalars().all())
        if not group_ids:
            return
        await self.db.execute(
            update(FavoriteGroup)
            .where(FavoriteGroup.id.in_(group_ids))
            .values(name=name)
        )

    async def _get_bus_stop(self, bus_stop_code: str) -> BusStop | None:
        result = await self.db.execute(
            select(BusStop).where(BusStop.bus_stop_code == bus_stop_code)
        )
        return result.scalar_one_or_none()

    async def _invalidate_home_cache(self, user_device_id: str) -> None:
        if self.cache is None:
            return
        await self.cache.delete_prefix(f"home:{user_device_id}:")
