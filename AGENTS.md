# Rockwell Asset Tracker

## What this is
REST API for tracking manufacturing assets (PLCs, sensors, drives, HMIs, robots) across Rockwell plant locations. Built with FastAPI + SQLite.

## Architecture
- `src/main.py` - FastAPI app, all route handlers
- `src/database.py` - SQLite connection, schema init, seed data
- `src/schemas.py` - Pydantic models for request/response validation
- `tests/` - pytest + httpx async tests

## Conventions
- Asset tags follow pattern: `XX-NNNN` (2-4 uppercase letters, dash, 4-6 digits)
- Status values: `active`, `maintenance`, `retired`
- Categories: `plc`, `sensor`, `drive`, `hmi`, `robot`
- All endpoints return JSON
- Tests use in-memory SQLite (`:memory:`)

## How to run
```bash
pip install -e ".[dev]"
uvicorn src.main:app --reload
pytest
```

## Backlog (GitHub Issues)
1. Add maintenance schedule endpoint (GET/POST `/assets/{id}/maintenance`)
2. Add equipment status enum validation
3. Add CSV export for asset inventory
4. Bug: 500 error when asset location_id references non-existent location
