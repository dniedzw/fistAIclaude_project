from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from typing import Optional
import aiosqlite

from .database import get_db, init_db
from .bulk_import import router as bulk_import_router
from .schemas import (
    AssetCreate,
    AssetUpdate,
    AssetOut,
    LocationOut,
    MaintenanceEventCreate,
    MaintenanceEventOut,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(
    title="Rockwell Asset Tracker",
    version="0.1.0",
    lifespan=lifespan,
)


app.include_router(bulk_import_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/locations", response_model=list[LocationOut])
async def list_locations(db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute("SELECT id, name, plant_code, building FROM locations")
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@app.get("/assets", response_model=list[AssetOut])
async def list_assets(
    status: Optional[str] = None,
    category: Optional[str] = None,
    db: aiosqlite.Connection = Depends(get_db),
):
    query = "SELECT * FROM assets WHERE 1=1"
    params = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if category:
        query += " AND category = ?"
        params.append(category)
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@app.get("/assets/{asset_id}", response_model=AssetOut)
async def get_asset(asset_id: int, db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")
    return dict(row)


@app.post("/assets", response_model=AssetOut, status_code=201)
async def create_asset(body: AssetCreate, db: aiosqlite.Connection = Depends(get_db)):
    try:
        cursor = await db.execute(
            """INSERT INTO assets (name, asset_tag, category, status, location_id, installed_date, next_service_date, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (body.name, body.asset_tag, body.category, body.status,
             body.location_id, body.installed_date, body.next_service_date, body.notes),
        )
        await db.commit()
    except Exception:
        raise HTTPException(status_code=409, detail="Duplicate asset_tag")
    return {**body.model_dump(), "id": cursor.lastrowid}


@app.put("/assets/{asset_id}", response_model=AssetOut)
async def update_asset(
    asset_id: int,
    body: AssetUpdate,
    db: aiosqlite.Connection = Depends(get_db),
):
    existing = await db.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
    row = await existing.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return dict(row)

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [asset_id]
    await db.execute(f"UPDATE assets SET {set_clause} WHERE id = ?", values)
    await db.commit()

    cursor = await db.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
    return dict(await cursor.fetchone())


@app.delete("/assets/{asset_id}", status_code=204)
async def delete_asset(asset_id: int, db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
    await db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Asset not found")


async def _require_asset(asset_id: int, db: aiosqlite.Connection):
    cursor = await db.execute("SELECT id FROM assets WHERE id = ?", (asset_id,))
    if await cursor.fetchone() is None:
        raise HTTPException(status_code=404, detail="Asset not found")


@app.post(
    "/assets/{asset_id}/maintenance",
    response_model=MaintenanceEventOut,
    status_code=201,
)
async def create_maintenance_event(
    asset_id: int,
    body: MaintenanceEventCreate,
    db: aiosqlite.Connection = Depends(get_db),
):
    await _require_asset(asset_id, db)
    cursor = await db.execute(
        "INSERT INTO maintenance_events (asset_id, due_at, task, completed) "
        "VALUES (?, ?, ?, ?)",
        (asset_id, body.due_at, body.task, int(body.completed)),
    )
    await db.commit()
    return {
        "id": cursor.lastrowid,
        "asset_id": asset_id,
        "due_at": body.due_at,
        "task": body.task,
        "completed": body.completed,
    }


@app.get(
    "/assets/{asset_id}/maintenance",
    response_model=list[MaintenanceEventOut],
)
async def list_maintenance_events(
    asset_id: int,
    db: aiosqlite.Connection = Depends(get_db),
):
    await _require_asset(asset_id, db)
    cursor = await db.execute(
        "SELECT id, asset_id, due_at, task, completed FROM maintenance_events "
        "WHERE asset_id = ? ORDER BY due_at ASC",
        (asset_id,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# Serve the static dashboard UI at "/". Mounted last so API routes take precedence.
_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="ui")
