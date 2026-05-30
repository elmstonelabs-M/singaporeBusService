from app.models.bus_stop import BusStop


async def test_bus_stop_alias_overrides_display_name(api_client, db_session) -> None:
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

    upsert = await api_client.put(
        "/v1/bus-stop-aliases",
        json={
            "user_device_id": "alias-user",
            "bus_stop_code": "83139",
            "alias": "Office Stop",
        },
    )
    assert upsert.status_code == 201

    search = await api_client.get(
        "/v1/bus-stops/search?q=83139&user_device_id=alias-user",
    )
    assert search.status_code == 200
    item = search.json()["data"]["items"][0]
    assert item["display_name"] == "Office Stop"
    assert item["description"] == "Opp Example Stop"


async def test_alias_list_and_delete(api_client, db_session) -> None:
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

    await api_client.put(
        "/v1/bus-stop-aliases",
        json={
            "user_device_id": "alias-user-2",
            "bus_stop_code": "83139",
            "alias": "Home Stop",
        },
    )
    listed = await api_client.get("/v1/bus-stop-aliases?user_device_id=alias-user-2")
    assert listed.status_code == 200
    assert listed.json()["data"]["items"][0]["alias"] == "Home Stop"
    assert listed.json()["data"]["items"][0]["updated_at"] is not None

    deleted = await api_client.delete(
        "/v1/bus-stop-aliases/83139?user_device_id=alias-user-2"
    )
    assert deleted.status_code == 204

    listed_again = await api_client.get("/v1/bus-stop-aliases?user_device_id=alias-user-2")
    assert listed_again.json()["data"]["items"] == []


async def test_home_cache_invalidates_after_alias_update(api_client, db_session) -> None:
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
            "user_device_id": "alias-home-cache",
            "bus_stop_code": "83139",
            "service_no": "36",
        },
    )
    assert created.status_code == 201

    first_home = await api_client.get("/v1/home?user_device_id=alias-home-cache")
    assert first_home.status_code == 200
    assert first_home.json()["data"]["favorite_groups"][0]["items"][0]["display_name"] == (
        "Opp Example Stop"
    )

    upsert = await api_client.put(
        "/v1/bus-stop-aliases",
        json={
            "user_device_id": "alias-home-cache",
            "bus_stop_code": "83139",
            "alias": "Office Stop",
        },
    )
    assert upsert.status_code == 201

    second_home = await api_client.get("/v1/home?user_device_id=alias-home-cache")
    assert second_home.status_code == 200
    group = second_home.json()["data"]["favorite_groups"][0]
    assert group["name"] == "Office Stop"
    assert group["items"][0]["display_name"] == "Office Stop"
