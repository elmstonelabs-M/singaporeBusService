from app.models.bus_stop import BusStop


async def test_favorite_group_update_and_reorder(api_client, db_session) -> None:
    db_session.add(
        BusStop(
            bus_stop_code="83139",
            road_name="Marine Parade Rd",
            description="Opp Example Stop",
            latitude=1.3001,
            longitude=103.9001,
            search_text="83139 marine parade rd opp example stop",
        )
    )
    await db_session.commit()

    create_group_response = await api_client.post(
        "/v1/favorite-groups",
        json={
            "user_device_id": "device-1",
            "name": "Home",
            "emoji": "H",
            "display_order": 0,
        },
    )
    group_id = create_group_response.json()["data"]["id"]

    update_group_response = await api_client.patch(
        f"/v1/favorite-groups/{group_id}",
        json={"user_device_id": "device-1", "name": "Work", "display_order": 2},
    )
    assert update_group_response.status_code == 200
    assert update_group_response.json()["data"]["name"] == "Work"

    favorite_one = await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-1",
            "group_id": group_id,
            "bus_stop_code": "83139",
            "service_no": "36",
            "display_order": 0,
        },
    )
    favorite_two = await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-1",
            "group_id": group_id,
            "bus_stop_code": "83139",
            "service_no": "97",
            "display_order": 1,
        },
    )

    reorder_response = await api_client.patch(
        "/v1/favorites/reorder",
        json={
            "user_device_id": "device-1",
            "items": [
                {
                    "favorite_id": favorite_one.json()["data"]["id"],
                    "display_order": 5,
                },
                {
                    "favorite_id": favorite_two.json()["data"]["id"],
                    "display_order": 3,
                },
            ]
        },
    )
    assert reorder_response.status_code == 200
    assert len(reorder_response.json()["data"]["items"]) == 2


async def test_favorite_group_listing(api_client) -> None:
    await api_client.post(
        "/v1/favorite-groups",
        json={
            "user_device_id": "device-2",
            "name": "Home",
            "emoji": "H",
            "display_order": 1,
        },
    )
    response = await api_client.get("/v1/favorite-groups?user_device_id=device-2")
    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["name"] == "Home"


async def test_home_favorite_item_includes_display_name(api_client, db_session) -> None:
    db_session.add(
        BusStop(
            bus_stop_code="83139",
            road_name="Marine Parade Rd",
            description="Opp Example Stop",
            latitude=1.3001,
            longitude=103.9001,
            search_text="83139 marine parade rd opp example stop",
        )
    )
    await db_session.commit()

    group_response = await api_client.post(
        "/v1/favorite-groups",
        json={
            "user_device_id": "device-alias-home",
            "name": "Home",
            "emoji": "H",
            "display_order": 0,
        },
    )
    group_id = group_response.json()["data"]["id"]

    await api_client.put(
        "/v1/bus-stop-aliases",
        json={
            "user_device_id": "device-alias-home",
            "bus_stop_code": "83139",
            "alias": "Office Stop",
        },
    )
    await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-alias-home",
            "group_id": group_id,
            "bus_stop_code": "83139",
            "service_no": "36",
            "display_order": 0,
        },
    )

    response = await api_client.get("/v1/home?user_device_id=device-alias-home")
    assert response.status_code == 200
    group = response.json()["data"]["favorite_groups"][0]
    item = group["items"][0]
    assert group["bus_stop_code"] == "83139"
    assert group["latitude"] == 1.3001
    assert group["longitude"] == 103.9001
    assert item["description"] == "Opp Example Stop"
    assert item["display_name"] == "Office Stop"
    assert item["road_name"] == "Marine Parade Rd"
    assert item["group_name"] == "Home"
    assert item["favorite_id"] == item["id"]


async def test_create_favorite_returns_not_found_for_missing_group(api_client, db_session) -> None:
    db_session.add(
        BusStop(
            bus_stop_code="83139",
            road_name="Marine Parade Rd",
            description="Opp Example Stop",
            latitude=1.3001,
            longitude=103.9001,
            search_text="83139 marine parade rd opp example stop",
        )
    )
    await db_session.commit()

    response = await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-missing-group",
            "group_id": "00000000-0000-0000-0000-000000000001",
            "bus_stop_code": "83139",
            "service_no": "36",
            "display_order": 0,
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "FAVORITE_GROUP_NOT_FOUND"


async def test_create_favorite_returns_conflict_for_duplicate(api_client, db_session) -> None:
    db_session.add(
        BusStop(
            bus_stop_code="83139",
            road_name="Marine Parade Rd",
            description="Opp Example Stop",
            latitude=1.3001,
            longitude=103.9001,
            search_text="83139 marine parade rd opp example stop",
        )
    )
    await db_session.commit()

    group_response = await api_client.post(
        "/v1/favorite-groups",
        json={
            "user_device_id": "device-duplicate-favorite",
            "name": "Home",
            "emoji": "H",
            "display_order": 0,
        },
    )
    group_id = group_response.json()["data"]["id"]

    payload = {
        "user_device_id": "device-duplicate-favorite",
        "group_id": group_id,
        "bus_stop_code": "83139",
        "service_no": "36",
        "display_order": 0,
    }
    first = await api_client.post("/v1/favorites", json=payload)
    second = await api_client.post("/v1/favorites", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "FAVORITE_ALREADY_EXISTS"


async def test_create_favorite_auto_creates_group_when_group_id_missing(
    api_client,
    db_session,
) -> None:
    db_session.add(
        BusStop(
            bus_stop_code="83139",
            road_name="Marine Parade Rd",
            description="Opp Example Stop",
            latitude=1.3001,
            longitude=103.9001,
            search_text="83139 marine parade rd opp example stop",
        )
    )
    await db_session.commit()

    response = await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-auto-group",
            "bus_stop_code": "83139",
            "service_no": "36",
        },
    )

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["group_name"] == "Opp Example Stop"
    assert body["created_group"] is True
    assert body["already_exists"] is False

    groups = await api_client.get("/v1/favorite-groups?user_device_id=device-auto-group")
    assert groups.status_code == 200
    assert groups.json()["data"]["items"][0]["name"] == "Opp Example Stop"


async def test_create_favorite_auto_reuses_group_for_same_bus_stop(
    api_client,
    db_session,
) -> None:
    db_session.add(
        BusStop(
            bus_stop_code="83139",
            road_name="Marine Parade Rd",
            description="Opp Example Stop",
            latitude=1.3001,
            longitude=103.9001,
            search_text="83139 marine parade rd opp example stop",
        )
    )
    await db_session.commit()

    first = await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-auto-reuse",
            "bus_stop_code": "83139",
            "service_no": "36",
        },
    )
    second = await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-auto-reuse",
            "bus_stop_code": "83139",
            "service_no": "97",
        },
    )

    assert first.status_code == 201
    assert second.status_code == 201
    first_body = first.json()["data"]
    second_body = second.json()["data"]
    assert second_body["group_id"] == first_body["group_id"]
    assert second_body["created_group"] is False
    assert second_body["already_exists"] is False


async def test_create_favorite_auto_creates_separate_group_for_different_bus_stop(
    api_client,
    db_session,
) -> None:
    db_session.add_all(
        [
            BusStop(
                bus_stop_code="83139",
                road_name="Marine Parade Rd",
                description="Opp Example Stop",
                latitude=1.3001,
                longitude=103.9001,
                search_text="83139 marine parade rd opp example stop",
            ),
            BusStop(
                bus_stop_code="65009",
                road_name="Somerset Rd",
                description="Opp Somerset Stn",
                latitude=1.3000,
                longitude=103.8390,
                search_text="65009 somerset rd opp somerset stn",
            ),
        ]
    )
    await db_session.commit()

    first = await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-auto-separate",
            "bus_stop_code": "83139",
            "service_no": "36",
        },
    )
    second = await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-auto-separate",
            "bus_stop_code": "65009",
            "service_no": "36",
        },
    )

    assert first.status_code == 201
    assert second.status_code == 201
    first_body = first.json()["data"]
    second_body = second.json()["data"]
    assert second_body["group_id"] != first_body["group_id"]
    assert second_body["group_name"] == "Opp Somerset Stn"
    assert second_body["created_group"] is True


async def test_create_favorite_ignores_mismatched_group_id_for_different_bus_stop(
    api_client,
    db_session,
) -> None:
    db_session.add_all(
        [
            BusStop(
                bus_stop_code="83139",
                road_name="Marine Parade Rd",
                description="Opp Example Stop",
                latitude=1.3001,
                longitude=103.9001,
                search_text="83139 marine parade rd opp example stop",
            ),
            BusStop(
                bus_stop_code="65009",
                road_name="Somerset Rd",
                description="Opp Somerset Stn",
                latitude=1.3000,
                longitude=103.8390,
                search_text="65009 somerset rd opp somerset stn",
            ),
        ]
    )
    await db_session.commit()

    first = await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-mismatch-group-id",
            "bus_stop_code": "83139",
            "service_no": "21",
        },
    )
    first_group_id = first.json()["data"]["group_id"]

    second = await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-mismatch-group-id",
            "group_id": first_group_id,
            "bus_stop_code": "65009",
            "service_no": "43",
        },
    )

    assert second.status_code == 201
    second_body = second.json()["data"]
    assert second_body["group_id"] != first_group_id
    assert second_body["group_name"] == "Opp Somerset Stn"
    assert second_body["created_group"] is True

    home = await api_client.get("/v1/home?user_device_id=device-mismatch-group-id")
    assert home.status_code == 200
    groups = home.json()["data"]["favorite_groups"]
    assert len(groups) == 2
    first_group = next(group for group in groups if group["group_id"] == first_group_id)
    second_group = next(group for group in groups if group["group_id"] == second_body["group_id"])
    assert [item["service_no"] for item in first_group["items"]] == ["21"]
    assert [item["service_no"] for item in second_group["items"]] == ["43"]


async def test_create_favorite_reuses_explicit_group_for_same_bus_stop(
    api_client,
    db_session,
) -> None:
    db_session.add(
        BusStop(
            bus_stop_code="83139",
            road_name="Marine Parade Rd",
            description="Opp Example Stop",
            latitude=1.3001,
            longitude=103.9001,
            search_text="83139 marine parade rd opp example stop",
        )
    )
    await db_session.commit()

    first = await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-explicit-same-stop",
            "bus_stop_code": "83139",
            "service_no": "21",
        },
    )
    group_id = first.json()["data"]["group_id"]

    second = await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-explicit-same-stop",
            "group_id": group_id,
            "bus_stop_code": "83139",
            "service_no": "43",
        },
    )

    assert second.status_code == 201
    second_body = second.json()["data"]
    assert second_body["group_id"] == group_id
    assert second_body["created_group"] is False
    assert second_body["already_exists"] is False


async def test_create_favorite_auto_returns_existing_for_same_stop_and_service(
    api_client,
    db_session,
) -> None:
    db_session.add(
        BusStop(
            bus_stop_code="83139",
            road_name="Marine Parade Rd",
            description="Opp Example Stop",
            latitude=1.3001,
            longitude=103.9001,
            search_text="83139 marine parade rd opp example stop",
        )
    )
    await db_session.commit()

    first = await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-auto-existing",
            "bus_stop_code": "83139",
            "service_no": "36",
        },
    )
    second = await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-auto-existing",
            "bus_stop_code": "83139",
            "service_no": "36",
        },
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["data"]["favorite_id"] == first.json()["data"]["favorite_id"]
    assert second.json()["data"]["already_exists"] is True


async def test_create_favorite_accepts_empty_group_id_as_auto_mode(
    api_client,
    db_session,
) -> None:
    db_session.add(
        BusStop(
            bus_stop_code="83139",
            road_name="Marine Parade Rd",
            description="Opp Example Stop",
            latitude=1.3001,
            longitude=103.9001,
            search_text="83139 marine parade rd opp example stop",
        )
    )
    await db_session.commit()

    response = await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-empty-group-id",
            "group_id": "",
            "bus_stop_code": "83139",
            "service_no": "36",
        },
    )

    assert response.status_code == 201
    assert response.json()["data"]["created_group"] is True


async def test_delete_favorite_removes_empty_bus_stop_card(api_client, db_session) -> None:
    db_session.add(
        BusStop(
            bus_stop_code="83139",
            road_name="Marine Parade Rd",
            description="Opp Example Stop",
            latitude=1.3001,
            longitude=103.9001,
            search_text="83139 marine parade rd opp example stop",
        )
    )
    await db_session.commit()

    created = await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-delete-empty",
            "bus_stop_code": "83139",
            "service_no": "36",
        },
    )
    favorite_id = created.json()["data"]["favorite_id"]

    deleted = await api_client.delete(
        f"/v1/favorites/{favorite_id}?user_device_id=device-delete-empty"
    )
    assert deleted.status_code == 204

    groups = await api_client.get("/v1/favorite-groups?user_device_id=device-delete-empty")
    assert groups.status_code == 200
    assert groups.json()["data"]["items"] == []


async def test_delete_favorite_keeps_bus_stop_card_when_other_services_remain(
    api_client,
    db_session,
) -> None:
    db_session.add(
        BusStop(
            bus_stop_code="83139",
            road_name="Marine Parade Rd",
            description="Opp Example Stop",
            latitude=1.3001,
            longitude=103.9001,
            search_text="83139 marine parade rd opp example stop",
        )
    )
    await db_session.commit()

    first = await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-delete-keep",
            "bus_stop_code": "83139",
            "service_no": "36",
        },
    )
    await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-delete-keep",
            "bus_stop_code": "83139",
            "service_no": "97",
        },
    )

    deleted = await api_client.delete(
        f"/v1/favorites/{first.json()['data']['favorite_id']}?user_device_id=device-delete-keep"
    )
    assert deleted.status_code == 204

    groups = await api_client.get("/v1/favorite-groups?user_device_id=device-delete-keep")
    assert groups.status_code == 200
    assert len(groups.json()["data"]["items"]) == 1

    home = await api_client.get("/v1/home?user_device_id=device-delete-keep")
    assert home.status_code == 200
    items = home.json()["data"]["favorite_groups"][0]["items"]
    assert len(items) == 1
    assert items[0]["service_no"] == "97"


async def test_update_favorite_group_name_syncs_bus_stop_alias(api_client, db_session) -> None:
    db_session.add(
        BusStop(
            bus_stop_code="83139",
            road_name="Marine Parade Rd",
            description="Opp Example Stop",
            latitude=1.3001,
            longitude=103.9001,
            search_text="83139 marine parade rd opp example stop",
        )
    )
    await db_session.commit()

    created = await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-rename-group",
            "bus_stop_code": "83139",
            "service_no": "36",
        },
    )
    group_id = created.json()["data"]["group_id"]

    renamed = await api_client.patch(
        f"/v1/favorite-groups/{group_id}",
        json={
            "user_device_id": "device-rename-group",
            "name": "Office Stop",
        },
    )
    assert renamed.status_code == 200
    assert renamed.json()["data"]["name"] == "Office Stop"

    aliases = await api_client.get("/v1/bus-stop-aliases?user_device_id=device-rename-group")
    assert aliases.status_code == 200
    assert aliases.json()["data"]["items"][0]["alias"] == "Office Stop"

    search = await api_client.get(
        "/v1/bus-stops/search?q=83139&user_device_id=device-rename-group"
    )
    assert search.status_code == 200
    assert search.json()["data"]["items"][0]["display_name"] == "Office Stop"


async def test_update_bus_stop_alias_syncs_favorite_group_name(api_client, db_session) -> None:
    db_session.add(
        BusStop(
            bus_stop_code="83139",
            road_name="Marine Parade Rd",
            description="Opp Example Stop",
            latitude=1.3001,
            longitude=103.9001,
            search_text="83139 marine parade rd opp example stop",
        )
    )
    await db_session.commit()

    await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-rename-alias",
            "bus_stop_code": "83139",
            "service_no": "36",
        },
    )

    aliased = await api_client.put(
        "/v1/bus-stop-aliases",
        json={
            "user_device_id": "device-rename-alias",
            "bus_stop_code": "83139",
            "alias": "Office Stop",
        },
    )
    assert aliased.status_code == 201

    groups = await api_client.get("/v1/favorite-groups?user_device_id=device-rename-alias")
    assert groups.status_code == 200
    assert groups.json()["data"]["items"][0]["name"] == "Office Stop"


async def test_home_cache_invalidates_after_favorite_create(api_client, db_session) -> None:
    db_session.add(
        BusStop(
            bus_stop_code="83139",
            road_name="Marine Parade Rd",
            description="Opp Example Stop",
            latitude=1.3001,
            longitude=103.9001,
            search_text="83139 marine parade rd opp example stop",
        )
    )
    await db_session.commit()

    first_home = await api_client.get("/v1/home?user_device_id=device-home-cache")
    assert first_home.status_code == 200
    assert first_home.json()["data"]["favorite_groups"] == []

    created = await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-home-cache",
            "bus_stop_code": "83139",
            "service_no": "36",
        },
    )
    assert created.status_code == 201

    second_home = await api_client.get("/v1/home?user_device_id=device-home-cache")
    assert second_home.status_code == 200
    groups = second_home.json()["data"]["favorite_groups"]
    assert len(groups) == 1
    assert groups[0]["bus_stop_code"] == "83139"
