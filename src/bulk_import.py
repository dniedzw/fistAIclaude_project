"""Bulk import and search endpoints for assets."""
from fastapi import APIRouter, Depends, HTTPException
import aiosqlite

from .database import get_db
from .schemas import AssetOut, BulkImportRequest, BulkImportResult

router = APIRouter()


@router.post("/assets/bulk-import", response_model=BulkImportResult, status_code=201)
async def bulk_import_assets(payload: BulkImportRequest, db: aiosqlite.Connection = Depends(get_db)):
    imported = 0
    try:
        for asset in payload.assets:
            await db.execute(
                "INSERT INTO assets (name, asset_tag, category, status) VALUES (?, ?, ?, ?)",
                (asset.name, asset.asset_tag, asset.category, asset.status),
            )
            imported += 1
        await db.commit()
    except aiosqlite.IntegrityError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return BulkImportResult(imported=imported)


@router.get("/assets/search", response_model=list[AssetOut])
async def search_assets(q: str = "", db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute(
        "SELECT * FROM assets WHERE name LIKE ? OR asset_tag LIKE ?",
        (f"%{q}%", f"%{q}%"),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]
