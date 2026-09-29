import pytest


@pytest.mark.asyncio
async def test_bulk_import_assets(client):
    payload = {
        "assets": [
            {"name": "CompactLogix 5380", "asset_tag": "PLC-8001", "category": "plc"},
            {"name": "PowerFlex 755", "asset_tag": "DRV-8002", "category": "drive"},
        ]
    }
    r = await client.post("/assets/bulk-import", json=payload)
    assert r.status_code == 201
    assert r.json()["imported"] == 2


@pytest.mark.asyncio
async def test_bulk_import_rejects_invalid_asset_tag(client):
    payload = {
        "assets": [
            {"name": "Bad Tag", "asset_tag": "not-a-tag", "category": "plc"},
        ]
    }
    r = await client.post("/assets/bulk-import", json=payload)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_bulk_import_duplicate_asset_tag_returns_conflict(client):
    payload = {
        "assets": [
            {"name": "PanelView Plus", "asset_tag": "HMI-8003", "category": "hmi"},
            {"name": "PanelView Plus Duplicate", "asset_tag": "HMI-8003", "category": "hmi"},
        ]
    }
    r = await client.post("/assets/bulk-import", json=payload)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_search_assets_by_name(client):
    await client.post("/assets", json={
        "name": "Kinetix 5700", "asset_tag": "DRV-8010", "category": "drive",
    })
    r = await client.get("/assets/search", params={"q": "Kinetix"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["asset_tag"] == "DRV-8010"


@pytest.mark.asyncio
async def test_search_assets_by_asset_tag(client):
    await client.post("/assets", json={
        "name": "GuardLogix", "asset_tag": "PLC-8020", "category": "plc",
    })
    r = await client.get("/assets/search", params={"q": "PLC-8020"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["name"] == "GuardLogix"


@pytest.mark.asyncio
async def test_search_assets_no_match_returns_empty_list(client):
    r = await client.get("/assets/search", params={"q": "nonexistent"})
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_search_assets_sql_injection_attempt_is_safe(client):
    r = await client.get("/assets/search", params={"q": "' OR '1'='1"})
    assert r.status_code == 200
    assert r.json() == []
