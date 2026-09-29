# Rockwell Asset Tracker

A REST API plus a single-page dashboard for tracking manufacturing assets (PLCs,
sensors, drives, HMIs, robots) across plant locations. FastAPI + SQLite backend,
static HTML/CSS/JS frontend served from the same app.

## Quick start

```bash
py -3.11 -m venv .venv            # cmd.exe / git bash
.venv\Scripts\activate.bat        # cmd.exe
source .venv/Scripts/activate     # git bash
pip install -e ".[dev]"
uvicorn src.main:app --reload --port 8080
```

- Dashboard UI: `http://localhost:8080/`
- API docs (Swagger): `http://localhost:8080/docs`
- Health check: `http://localhost:8080/health`

> **Port note:** examples use `8080`. Port `8000` is fine on most machines, but
> if you get `[WinError 10013] ... socket ... forbidden` on Windows, that port is
> in a reserved/excluded range. Pick another port (`8080`, `8888`, `5001`). Check
> reserved ranges with:
> `netsh interface ipv4 show excludedportrange protocol=tcp`

On first run the app creates `assets.db` and seeds 4 locations and 10 demo assets.
Delete `assets.db` to reset to seed data.

## Run the MCP server too

An MCP server that wraps this API lives in [`asset-tracker-mcp/`](asset-tracker-mcp/README.md).
To run both, use two terminals:

```bash
# Terminal 1 - the API (must start first)
uvicorn src.main:app --reload --port 8080

# Terminal 2 - the MCP server, pointed at the API's port
cd asset-tracker-mcp
set API_BASE_URL=http://127.0.0.1:8080      # cmd.exe
export API_BASE_URL=http://127.0.0.1:8080   # git bash
python server.py
```

See [asset-tracker-mcp/README.md](asset-tracker-mcp/README.md) for registering it
with Claude Code.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/assets` | List assets (optional `?status=` and `?category=` filters) |
| GET | `/assets/{id}` | Get single asset |
| POST | `/assets` | Create asset |
| PUT | `/assets/{id}` | Update asset |
| DELETE | `/assets/{id}` | Delete asset |
| GET | `/assets/{id}/maintenance` | List maintenance events for an asset (sorted by due date) |
| POST | `/assets/{id}/maintenance` | Create a maintenance event for an asset |
| GET | `/locations` | List locations |
| GET | `/health` | Health check |

## Project structure

```
src/
  main.py            - FastAPI app, route handlers, static UI mount
  database.py        - SQLite connection, schema, seed data (aiosqlite)
  schemas.py         - Pydantic request/response schemas
  static/index.html  - Single-page dashboard UI (calls the JSON API)
tests/
  conftest.py        - Shared fixtures (in-memory SQLite)
  test_assets.py     - Asset CRUD + maintenance endpoint tests
```

## Tests

```bash
pytest
```

## Tech stack

- Python 3.11+
- FastAPI
- SQLite (aiosqlite)
- Pydantic v2
