from uuid import UUID

from sqlalchemy import case, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import CacheService
from app.core.errors import AppError
from app.models.bus_stop import BusStop
from app.models.bus_stop_alias import BusStopAlias
from app.models.favorite import FavoriteGroup, FavoriteItem
from app.models.user import User
from app.schemas.favorite import (
    FavoriteCreate,
    FavoriteCreatedResult,
    FavoriteGroupCreate,
    FavoriteGroupUpdate,
    FavoriteReorderRequest,
)


class FavoriteService:
    def __init__(self, db: AsyncSession, cache: CacheService | None = None) -> None:
        self.db = db
        self.cache = cache

    async def create_group(self, payload: FavoriteGroupCreate) -> FavoriteGroup:
        user = await self._get_or_create_user(payload.user_device_id)
        group = FavoriteGroup(
            user_id=user.id,
            name=payload.name,
            emoji=payload.emoji,
            display_order=payload.display_order,
        )
        self.db.add(group)
        await self.db.commit()
        await self.db.refresh(group)
        await self._invalidate_home_cache_by_user_id(user.id)
        return group

    async def update_group(
        self,
        group_id: UUID,
        payload: FavoriteGroupUpdate,
    ) -> FavoriteGroup:
        user = await self._get_or_create_user(payload.user_device_id)
        group = await self._require_group_for_user(group_id, user.id)
        values = payload.model_dump(exclude={"user_device_id"}, exclude_none=True)
        if "name" in values:
            await self._sync_group_name_to_alias(
                user_id=user.id,
                group_id=group_id,
                name=str(values["name"]),
            )
        if values:
            await self.db.execute(
                update(FavoriteGroup).where(FavoriteGroup.id == group_id).values(**values)
            )
            await self.db.commit()
            result = await self.db.execute(
                select(FavoriteGroup).where(FavoriteGroup.id == group_id)
            )
            refreshed = result.scalar_one_or_none()
            if refreshed is not None:
                await self._invalidate_home_cache_by_user_id(user.id)
                return refreshed
        return group

    async def create_favorite(self, payload: FavoriteCreate) -> FavoriteCreatedResult:
        user = await self._get_or_create_user(payload.user_device_id)
        bus_stop = await self._require_bus_stop(payload.bus_stop_code)

        target_group = await self._resolve_explicit_group_for_bus_stop(
            user_id=user.id,
            group_id=payload.group_id,
            bus_stop_code=payload.bus_stop_code,
        )

        existing = await self._find_favorite_for_user(
            user.id,
            payload.bus_stop_code,
            payload.service_no,
        )
        if existing is not None:
            if target_group is not None and existing.group_id == target_group.id:
                await self._ensure_favorite_not_exists(
                    target_group.id,
                    payload.bus_stop_code,
                    payload.service_no,
                )
            return FavoriteCreatedResult(
                favorite=existing,
                created_group=False,
                already_exists=True,
            )

        created_group = False
        if target_group is None:
            target_group = await self._find_group_for_bus_stop(user.id, payload.bus_stop_code)
        if target_group is None:
            target_group = await self._create_auto_group(user.id, bus_stop)
            created_group = True
            display_order = 0
        else:
            await self._ensure_favorite_not_exists(
                target_group.id,
                payload.bus_stop_code,
                payload.service_no,
            )
            display_order = await self._next_favorite_display_order(target_group.id)

        favorite = FavoriteItem(
            group_id=target_group.id,
            bus_stop_code=payload.bus_stop_code,
            service_no=payload.service_no,
            display_order=display_order,
        )
        self.db.add(favorite)
        await self.db.commit()
        await self.db.refresh(favorite)
        await self._invalidate_home_cache_by_user_id(user.id)
        return FavoriteCreatedResult(
            favorite=favorite,
            created_group=created_group,
            already_exists=False,
        )

    async def reorder_favorites(self, payload: FavoriteReorderRequest) -> list[FavoriteItem]:
        if not payload.items:
            return []
        user = await self._get_or_create_user(payload.user_device_id)
        order_map = {item.favorite_id: item.display_order for item in payload.items}
        result = await self.db.execute(
            select(FavoriteItem)
            .join(FavoriteGroup, FavoriteGroup.id == FavoriteItem.group_id)
            .where(
                FavoriteItem.id.in_(list(order_map)),
                FavoriteGroup.user_id == user.id,
            )
        )
        favorites = list(result.scalars().all())
        existing_ids = {favorite.id for favorite in favorites}
        if len(existing_ids) != len(order_map):
            raise AppError(
                "FAVORITE_NOT_FOUND",
                "One or more favorites do not exist.",
                404,
            )
        await self.db.execute(
            update(FavoriteItem)
            .where(FavoriteItem.id.in_(list(order_map)))
            .values(display_order=case(order_map, value=FavoriteItem.id))
        )
        await self.db.commit()
        await self._invalidate_home_cache_by_user_id(user.id)
        refreshed = await self.db.execute(
            select(FavoriteItem)
            .where(FavoriteItem.id.in_(list(order_map)))
            .order_by(FavoriteItem.display_order)
        )
        return list(refreshed.scalars().all())

    async def list_groups(self, user_device_id: str) -> list[FavoriteGroup]:
        user = await self._get_or_create_user(user_device_id)
        result = await self.db.execute(
            select(FavoriteGroup)
            .where(FavoriteGroup.user_id == user.id)
            .order_by(FavoriteGroup.display_order)
        )
        return list(result.scalars().all())

    async def list_items(self, group_id: UUID) -> list[FavoriteItem]:
        result = await self.db.execute(
            select(FavoriteItem)
            .where(FavoriteItem.group_id == group_id)
            .order_by(FavoriteItem.display_order)
        )
        return list(result.scalars().all())

    async def delete_group(self, group_id: UUID, user_device_id: str) -> None:
        user = await self._get_or_create_user(user_device_id)
        await self._require_group_for_user(group_id, user.id)
        await self.db.execute(delete(FavoriteGroup).where(FavoriteGroup.id == group_id))
        await self.db.commit()
        await self._invalidate_home_cache_by_user_id(user.id)

    async def delete_favorite(self, favorite_id: UUID, user_device_id: str) -> None:
        user = await self._get_or_create_user(user_device_id)
        favorite = await self._require_favorite_for_user(favorite_id, user.id)
        await self.db.execute(delete(FavoriteItem).where(FavoriteItem.id == favorite_id))
        remaining = await self.db.execute(
            select(func.count())
            .select_from(FavoriteItem)
            .where(FavoriteItem.group_id == favorite.group_id)
        )
        if remaining.scalar_one() == 0:
            await self.db.execute(
                delete(FavoriteGroup).where(FavoriteGroup.id == favorite.group_id)
            )
        await self.db.commit()
        await self._invalidate_home_cache_by_user_id(user.id)

    async def get_favorite_metadata_map(
        self,
        user_device_id: str,
        bus_stop_code: str,
    ) -> dict[str, dict[str, str | int | bool | None]]:
        user = await self._get_or_create_user(user_device_id)
        result = await self.db.execute(
            select(
                FavoriteItem.id,
                FavoriteItem.service_no,
                FavoriteItem.display_order,
                FavoriteGroup.id,
                FavoriteGroup.name,
                FavoriteGroup.display_order,
            )
            .join(FavoriteGroup, FavoriteGroup.id == FavoriteItem.group_id)
            .where(
                FavoriteGroup.user_id == user.id,
                FavoriteItem.bus_stop_code == bus_stop_code,
            )
            .order_by(FavoriteGroup.display_order, FavoriteItem.display_order)
        )
        metadata: dict[str, dict[str, str | int | bool | None]] = {}
        for (
            favorite_id,
            service_no,
            display_order,
            group_id,
            group_name,
            _group_display_order,
        ) in result.all():
            metadata[service_no] = {
                "is_favorite": True,
                "favorite_id": str(favorite_id),
                "group_id": str(group_id),
                "group_name": group_name,
                "display_order": display_order,
            }
        return metadata

    async def get_group(self, group_id: UUID) -> FavoriteGroup | None:
        result = await self.db.execute(select(FavoriteGroup).where(FavoriteGroup.id == group_id))
        return result.scalar_one_or_none()

    async def get_group_for_bus_stop(
        self,
        user_device_id: str,
        bus_stop_code: str,
    ) -> FavoriteGroup | None:
        user = await self._get_or_create_user(user_device_id)
        return await self._find_group_for_bus_stop(user.id, bus_stop_code)

    async def get_favorite_for_user(
        self,
        user_device_id: str,
        bus_stop_code: str,
        service_no: str,
    ) -> FavoriteItem | None:
        user = await self._get_or_create_user(user_device_id)
        return await self._find_favorite_for_user(user.id, bus_stop_code, service_no)

    async def sync_group_names_for_bus_stop(
        self,
        user_id: UUID,
        bus_stop_code: str,
        name: str,
    ) -> None:
        group_ids = await self._group_ids_for_bus_stop(user_id, bus_stop_code)
        if not group_ids:
            return
        await self.db.execute(
            update(FavoriteGroup)
            .where(FavoriteGroup.id.in_(group_ids))
            .values(name=name)
        )
        await self.db.commit()
        await self._invalidate_home_cache_by_user_id(user_id)

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

    async def _require_group(self, group_id: UUID) -> FavoriteGroup:
        result = await self.db.execute(select(FavoriteGroup).where(FavoriteGroup.id == group_id))
        group = result.scalar_one_or_none()
        if group is None:
            raise AppError(
                "FAVORITE_GROUP_NOT_FOUND",
                "Favorite group does not exist.",
                404,
            )
        return group

    async def _require_group_for_user(self, group_id: UUID, user_id: UUID) -> FavoriteGroup:
        result = await self.db.execute(
            select(FavoriteGroup).where(
                FavoriteGroup.id == group_id,
                FavoriteGroup.user_id == user_id,
            )
        )
        group = result.scalar_one_or_none()
        if group is None:
            raise AppError(
                "FAVORITE_GROUP_NOT_FOUND",
                "Favorite group does not exist for this user.",
                404,
            )
        return group

    async def _find_group_for_bus_stop(
        self,
        user_id: UUID,
        bus_stop_code: str,
    ) -> FavoriteGroup | None:
        result = await self.db.execute(
            select(FavoriteGroup)
            .join(FavoriteItem, FavoriteItem.group_id == FavoriteGroup.id)
            .where(
                FavoriteGroup.user_id == user_id,
                FavoriteItem.bus_stop_code == bus_stop_code,
            )
            .order_by(FavoriteGroup.display_order, FavoriteItem.display_order)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _resolve_explicit_group_for_bus_stop(
        self,
        user_id: UUID,
        group_id: UUID | None,
        bus_stop_code: str,
    ) -> FavoriteGroup | None:
        if group_id is None:
            return None
        group = await self._require_group_for_user(group_id, user_id)
        existing_bus_stop_code = await self._first_group_bus_stop_code(group.id)
        if existing_bus_stop_code is None or existing_bus_stop_code == bus_stop_code:
            return group
        return None

    async def _group_ids_for_bus_stop(self, user_id: UUID, bus_stop_code: str) -> list[UUID]:
        result = await self.db.execute(
            select(FavoriteGroup.id)
            .join(FavoriteItem, FavoriteItem.group_id == FavoriteGroup.id)
            .where(
                FavoriteGroup.user_id == user_id,
                FavoriteItem.bus_stop_code == bus_stop_code,
            )
            .group_by(FavoriteGroup.id)
            .order_by(FavoriteGroup.display_order)
        )
        return list(result.scalars().all())

    async def _first_group_bus_stop_code(self, group_id: UUID) -> str | None:
        result = await self.db.execute(
            select(FavoriteItem.bus_stop_code)
            .where(FavoriteItem.group_id == group_id)
            .order_by(FavoriteItem.display_order, FavoriteItem.created_at, FavoriteItem.id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _require_bus_stop(self, bus_stop_code: str) -> BusStop:
        result = await self.db.execute(
            select(BusStop).where(BusStop.bus_stop_code == bus_stop_code)
        )
        bus_stop = result.scalar_one_or_none()
        if bus_stop is None:
            raise AppError(
                "BUS_STOP_NOT_FOUND",
                "Bus stop does not exist.",
                404,
            )
        return bus_stop

    async def _find_favorite_for_user(
        self,
        user_id: UUID,
        bus_stop_code: str,
        service_no: str,
    ) -> FavoriteItem | None:
        result = await self.db.execute(
            select(FavoriteItem)
            .join(FavoriteGroup, FavoriteGroup.id == FavoriteItem.group_id)
            .where(
                FavoriteGroup.user_id == user_id,
                FavoriteItem.bus_stop_code == bus_stop_code,
                FavoriteItem.service_no == service_no,
            )
        )
        return result.scalar_one_or_none()

    async def _create_auto_group(self, user_id: UUID, bus_stop: BusStop) -> FavoriteGroup:
        display_order = await self._next_group_display_order(user_id)
        name = await self._resolve_auto_group_name(user_id, bus_stop)
        group = FavoriteGroup(
            user_id=user_id,
            name=name,
            emoji=None,
            display_order=display_order,
        )
        self.db.add(group)
        await self.db.flush()
        return group

    async def _resolve_auto_group_name(self, user_id: UUID, bus_stop: BusStop) -> str:
        result = await self.db.execute(
            select(BusStopAlias.alias).where(
                BusStopAlias.user_id == user_id,
                BusStopAlias.bus_stop_code == bus_stop.bus_stop_code,
            )
        )
        alias = result.scalar_one_or_none()
        return alias or bus_stop.description

    async def _sync_group_name_to_alias(
        self,
        user_id: UUID,
        group_id: UUID,
        name: str,
    ) -> None:
        result = await self.db.execute(
            select(FavoriteItem.bus_stop_code)
            .where(FavoriteItem.group_id == group_id)
            .limit(1)
        )
        bus_stop_code = result.scalar_one_or_none()
        if bus_stop_code is None:
            return
        alias_result = await self.db.execute(
            select(BusStopAlias)
            .where(BusStopAlias.user_id == user_id)
            .where(BusStopAlias.bus_stop_code == bus_stop_code)
        )
        alias = alias_result.scalar_one_or_none()
        if alias is None:
            self.db.add(
                BusStopAlias(
                    user_id=user_id,
                    bus_stop_code=bus_stop_code,
                    alias=name,
                )
            )
        else:
            alias.alias = name

    async def _next_group_display_order(self, user_id: UUID) -> int:
        result = await self.db.execute(
            select(func.max(FavoriteGroup.display_order)).where(FavoriteGroup.user_id == user_id)
        )
        current = result.scalar_one_or_none()
        return (current or -1) + 1

    async def _next_favorite_display_order(self, group_id: UUID) -> int:
        result = await self.db.execute(
            select(func.max(FavoriteItem.display_order)).where(FavoriteItem.group_id == group_id)
        )
        current = result.scalar_one_or_none()
        return (current or -1) + 1

    async def _ensure_favorite_not_exists(
        self,
        group_id: UUID,
        bus_stop_code: str,
        service_no: str,
    ) -> None:
        result = await self.db.execute(
            select(FavoriteItem).where(
                FavoriteItem.group_id == group_id,
                FavoriteItem.bus_stop_code == bus_stop_code,
                FavoriteItem.service_no == service_no,
            )
        )
        favorite = result.scalar_one_or_none()
        if favorite is not None:
            raise AppError(
                "FAVORITE_ALREADY_EXISTS",
                "This service is already in the selected favorite group.",
                409,
            )

    async def _require_favorite(self, favorite_id: UUID) -> FavoriteItem:
        result = await self.db.execute(select(FavoriteItem).where(FavoriteItem.id == favorite_id))
        favorite = result.scalar_one_or_none()
        if favorite is None:
            raise AppError(
                "FAVORITE_NOT_FOUND",
                "Favorite does not exist.",
                404,
            )
        return favorite

    async def _require_favorite_for_user(self, favorite_id: UUID, user_id: UUID) -> FavoriteItem:
        result = await self.db.execute(
            select(FavoriteItem)
            .join(FavoriteGroup, FavoriteGroup.id == FavoriteItem.group_id)
            .where(
                FavoriteItem.id == favorite_id,
                FavoriteGroup.user_id == user_id,
            )
        )
        favorite = result.scalar_one_or_none()
        if favorite is None:
            raise AppError(
                "FAVORITE_NOT_FOUND",
                "Favorite does not exist for this user.",
                404,
            )
        return favorite

    async def _invalidate_home_cache_by_user_id(self, user_id: UUID) -> None:
        if self.cache is None:
            return
        result = await self.db.execute(select(User.device_id).where(User.id == user_id))
        device_id = result.scalar_one_or_none()
        if device_id is None:
            return
        await self.cache.delete_prefix(f"home:{device_id}:")
