import pytest


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_list_locations(client):
    r = await client.get("/locations")
    assert r.status_code == 200
    assert len(r.json()) >= 4


@pytest.mark.asyncio
async def test_create_asset(client):
    payload = {
        "name": "CompactLogix 5380",
        "asset_tag": "PLC-0001",
        "category": "plc",
        "location_id": 1,
        "installed_date": "2025-03-15",
    }
    r = await client.post("/assets", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["asset_tag"] == "PLC-0001"
    assert data["id"] >= 1


@pytest.mark.asyncio
async def test_get_asset_not_found(client):
    r = await client.get("/assets/9999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_asset(client):
    # create first
    await client.post("/assets", json={
        "name": "Kinetix 5700",
        "asset_tag": "DRV-0010",
        "category": "drive",
    })
    r = await client.put("/assets/1", json={"status": "maintenance"})
    assert r.status_code == 200
    assert r.json()["status"] == "maintenance"


@pytest.mark.asyncio
async def test_create_maintenance_event(client):
    await client.post("/assets", json={
        "name": "PanelView Plus",
        "asset_tag": "HMI-1001",
        "category": "hmi",
    })

    payload = {
        "due_at": "2026-08-01T09:00:00Z",
        "task": "Replace cooling fan and inspect wiring",
        "completed": False,
    }
    r = await client.post("/assets/1/maintenance", json=payload)

    assert r.status_code == 201
    data = r.json()
    assert data["asset_id"] == 1
    assert data["due_at"] == payload["due_at"]
    assert data["task"] == payload["task"]
    assert data["completed"] is False
    assert isinstance(data["id"], int)


@pytest.mark.asyncio
async def test_list_maintenance_events_filters_by_asset_and_sorts_due_at(client):
    await client.post("/assets", json={
        "name": "GuardLogix",
        "asset_tag": "PLC-2001",
        "category": "plc",
    })
    await client.post("/assets", json={
        "name": "PowerFlex 755",
        "asset_tag": "DRV-2002",
        "category": "drive",
    })

    await client.post("/assets/1/maintenance", json={
        "due_at": "2026-09-10T10:00:00Z",
        "task": "Quarterly firmware validation",
        "completed": False,
    })
    await client.post("/assets/1/maintenance", json={
        "due_at": "2026-07-15T08:30:00Z",
        "task": "Safety IO inspection",
        "completed": True,
    })
    await client.post("/assets/2/maintenance", json={
        "due_at": "2026-07-01T07:00:00Z",
        "task": "Drive alignment calibration",
        "completed": False,
    })

    r = await client.get("/assets/1/maintenance")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert [event["due_at"] for event in data] == [
        "2026-07-15T08:30:00Z",
        "2026-09-10T10:00:00Z",
    ]


@pytest.mark.asyncio
async def test_create_maintenance_event_asset_not_found(client):
    r = await client.post("/assets/9999/maintenance", json={
        "due_at": "2026-08-01T09:00:00Z",
        "task": "Inspect actuator",
        "completed": False,
    })
    assert r.status_code == 404
    assert r.json()["detail"] == "Asset not found"


@pytest.mark.asyncio
async def test_create_maintenance_event_rejects_blank_task(client):
    await client.post("/assets", json={
        "name": "FactoryTalk Server",
        "asset_tag": "SEN-3001",
        "category": "sensor",
    })

    r = await client.post("/assets/1/maintenance", json={
        "due_at": "2026-08-01T09:00:00Z",
        "task": "",
        "completed": False,
    })

    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_asset_with_next_service_date(client):
    r = await client.post("/assets", json={
        "name": "PowerFlex 755",
        "asset_tag": "DRV-0020",
        "category": "drive",
        "next_service_date": "2026-10-15",
    })
    assert r.status_code == 201
    assert r.json()["next_service_date"] == "2026-10-15"


@pytest.mark.asyncio
async def test_create_asset_without_next_service_date_defaults_to_null(client):
    r = await client.post("/assets", json={
        "name": "Kinetix 5700",
        "asset_tag": "DRV-0021",
        "category": "drive",
    })
    assert r.status_code == 201
    assert r.json()["next_service_date"] is None


@pytest.mark.asyncio
async def test_update_next_service_date(client):
    await client.post("/assets", json={
        "name": "CompactLogix 5380",
        "asset_tag": "PLC-0030",
        "category": "plc",
    })
    r = await client.put("/assets/1", json={"next_service_date": "2026-12-01"})
    assert r.status_code == 200
    assert r.json()["next_service_date"] == "2026-12-01"


@pytest.mark.asyncio
async def test_list_assets_includes_next_service_date(client):
    await client.post("/assets", json={
        "name": "PanelView Plus 7",
        "asset_tag": "HMI-0040",
        "category": "hmi",
        "next_service_date": "2026-11-01",
    })
    r = await client.get("/assets")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["next_service_date"] == "2026-11-01"


@pytest.mark.asyncio
async def test_clear_next_service_date(client):
    await client.post("/assets", json={
        "name": "GuardLogix 5580",
        "asset_tag": "PLC-0050",
        "category": "plc",
        "next_service_date": "2026-10-01",
    })
    r = await client.put("/assets/1", json={"next_service_date": None})
    assert r.status_code == 200
    assert r.json()["next_service_date"] is None
