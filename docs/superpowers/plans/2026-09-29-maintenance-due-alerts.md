# Maintenance Due Alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `next_service_date` field to assets and surface overdue status on the dashboard as a KPI card, table column, and one-click filter.

**Architecture:** A nullable `next_service_date TEXT` column is added to the `assets` SQLite table and surfaced through the existing FastAPI schemas and routes. The dashboard (a single static HTML file) computes overdue status in JS by comparing each asset's date to today's local calendar date, then renders a 5th KPI card, an overdue row highlight, and a filter toggle — all within the existing JS filter pipeline.

**Tech Stack:** Python 3.11+, FastAPI, aiosqlite, Pydantic v2, pytest + httpx (async), vanilla JS + HTML/CSS (no build step).

## Global Constraints

- Python ≥ 3.11, FastAPI `>=0.115.0,<0.120.0`, aiosqlite `>=0.20.0,<0.21.0`, Pydantic `>=2.0,<3.0`
- Asset tag pattern: `^[A-Z]{2,4}-\d{4,6}$`
- Status values: `active`, `maintenance`, `retired`
- Categories: `plc`, `sensor`, `drive`, `hmi`, `robot`
- Tests use in-memory SQLite (`:memory:`) via the `client` fixture in `tests/conftest.py`
- Run tests with: `pytest` from the repo root
- `next_service_date` stores ISO date strings in `YYYY-MM-DD` format (same as `installed_date`)
- "Overdue" means `next_service_date < today` (strictly before today; today itself is not overdue)

---

## File Map

| File | Change |
|---|---|
| `src/database.py` | Add `ALTER TABLE assets ADD COLUMN next_service_date TEXT` migration |
| `src/schemas.py` | Add `next_service_date: Optional[str] = None` to `AssetCreate`, `AssetUpdate`, `AssetOut` |
| `src/main.py` | Add `next_service_date` to `POST /assets` INSERT |
| `tests/test_assets.py` | Add 5 new test cases for the new field |
| `src/static/index.html` | KPI card, table column, overdue filter, date fields in forms |

---

### Task 1: Backend — `next_service_date` field

**Files:**
- Modify: `tests/test_assets.py`
- Modify: `src/database.py`
- Modify: `src/schemas.py`
- Modify: `src/main.py`

**Interfaces:**
- Produces: `AssetOut.next_service_date: Optional[str]` — used by Task 2 and Task 3 frontend code

---

- [ ] **Step 1: Write 5 failing tests**

Append to `tests/test_assets.py`:

```python
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
```

- [ ] **Step 2: Run tests — confirm 5 failures**

```
pytest tests/test_assets.py -v -k "next_service_date"
```

Expected: 5 FAILs. `test_create_asset_with_next_service_date` will likely pass the POST (201) but fail on `next_service_date` missing from the response.

- [ ] **Step 3: Add migration to `src/database.py`**

In `create_schema`, after the `CREATE TABLE IF NOT EXISTS maintenance_events` block and before the seed-locations check, add:

```python
    # Migrate: add next_service_date column to existing databases
    try:
        await db.execute("ALTER TABLE assets ADD COLUMN next_service_date TEXT")
    except Exception:
        pass  # column already exists
```

The full updated `create_schema` function body should look like:

```python
async def create_schema(db):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            plant_code TEXT NOT NULL,
            building TEXT
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            asset_tag TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            location_id INTEGER REFERENCES locations(id),
            installed_date TEXT,
            notes TEXT
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL REFERENCES assets(id),
            due_at TEXT NOT NULL,
            task TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0
        )
    """)
    # Migrate: add next_service_date column to existing databases
    try:
        await db.execute("ALTER TABLE assets ADD COLUMN next_service_date TEXT")
    except Exception:
        pass  # column already exists
    # Seed default locations if empty
    cursor = await db.execute("SELECT COUNT(*) FROM locations")
    count = (await cursor.fetchone())[0]
    if count == 0:
        await db.executemany(
            "INSERT INTO locations (name, plant_code, building) VALUES (?, ?, ?)",
            [
                ("Milwaukee HQ - Line A", "MKE-01", "Building 4"),
                ("Milwaukee HQ - Line B", "MKE-01", "Building 4"),
                ("Twinsburg Assembly", "TWN-02", "Main"),
                ("Mequon Controls Lab", "MEQ-03", "Lab 1"),
            ],
        )
    await db.commit()
```

- [ ] **Step 4: Update `src/schemas.py`**

Add `next_service_date: Optional[str] = None` to all three models. The full updated file:

```python
from pydantic import BaseModel, Field
from typing import Optional

class LocationOut(BaseModel):
    id: int
    name: str
    plant_code: str
    building: Optional[str] = None

class AssetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    asset_tag: str = Field(..., pattern=r"^[A-Z]{2,4}-\d{4,6}$")
    category: str = Field(..., description="plc | sensor | drive | hmi | robot")
    status: str = Field(default="active", pattern=r"^(active|maintenance|retired)$")
    location_id: Optional[int] = None
    installed_date: Optional[str] = None
    next_service_date: Optional[str] = None
    notes: Optional[str] = None

class AssetUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = Field(default=None, pattern=r"^(active|maintenance|retired)$")
    location_id: Optional[int] = None
    next_service_date: Optional[str] = None
    notes: Optional[str] = None

class AssetOut(BaseModel):
    id: int
    name: str
    asset_tag: str
    category: str
    status: str
    location_id: Optional[int] = None
    installed_date: Optional[str] = None
    next_service_date: Optional[str] = None
    notes: Optional[str] = None

class MaintenanceEventCreate(BaseModel):
    due_at: str = Field(..., min_length=1)
    task: str = Field(..., min_length=1, max_length=500)
    completed: bool = False

class MaintenanceEventOut(BaseModel):
    id: int
    asset_id: int
    due_at: str
    task: str
    completed: bool

class BulkImportRequest(BaseModel):
    assets: list[AssetCreate]

class BulkImportResult(BaseModel):
    imported: int
```

- [ ] **Step 5: Update `POST /assets` in `src/main.py`**

Replace the INSERT in `create_asset` to include `next_service_date`. Find this block:

```python
        cursor = await db.execute(
            """INSERT INTO assets (name, asset_tag, category, status, location_id, installed_date, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (body.name, body.asset_tag, body.category, body.status,
             body.location_id, body.installed_date, body.notes),
        )
```

Replace with:

```python
        cursor = await db.execute(
            """INSERT INTO assets (name, asset_tag, category, status, location_id, installed_date, next_service_date, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (body.name, body.asset_tag, body.category, body.status,
             body.location_id, body.installed_date, body.next_service_date, body.notes),
        )
```

No other route changes needed — `GET /assets` uses `SELECT *` (picks up new column automatically) and `PUT /assets/{id}` uses `model_dump(exclude_unset=True)` (includes the field when provided).

- [ ] **Step 6: Run all tests — confirm they pass**

```
pytest tests/test_assets.py -v -k "next_service_date"
```

Expected: 5 PASSes. Then run the full suite to confirm nothing regressed:

```
pytest
```

Expected: all tests pass. If `test_clear_next_service_date` fails with a 422, verify that `AssetUpdate.next_service_date` has no `Field(...)` constraint preventing `None`. If `test_create_asset_with_next_service_date` fails with a 500, check the INSERT column list in `main.py` for a typo.

- [ ] **Step 7: Commit**

```
git add src/database.py src/schemas.py src/main.py tests/test_assets.py
git commit -m "feat: add next_service_date field to assets"
```

---

### Task 2: Dashboard — KPI card, table column, overdue filter

All changes are in `src/static/index.html`. There is no build step — edit the file directly and refresh the browser to test.

**Files:**
- Modify: `src/static/index.html`

**Interfaces:**
- Consumes: `asset.next_service_date: string | null` from `GET /assets` response (produced by Task 1)
- Produces: `overdueOnly: boolean` state + `localToday(): string` helper — used by Task 3

---

- [ ] **Step 1: Add `overdueOnly` state variable and `localToday()` helper**

In the `<script>` block, find this line:

```js
let currentId = null;   // drawer target
```

Add two lines immediately after:

```js
let overdueOnly = false;

function localToday() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}
```

- [ ] **Step 2: Update KPI grid CSS to 5 columns and add the 5th KPI card**

In `<style>`, find:

```css
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; padding: 20px 24px 4px; }
```

Replace with:

```css
.kpis { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; padding: 20px 24px 4px; }
```

In the HTML, find the `<section class="kpis">` block. It currently has 4 `.kpi` divs. Add a 5th after the last one (the "Retired" card):

```html
<div class="kpi" id="k-overdue-card" style="cursor:pointer;border-color:var(--red)">
  <div class="num" id="k-overdue" style="color:var(--red)">0</div>
  <div class="cap">Overdue for Service</div>
</div>
```

- [ ] **Step 3: Add "Overdue only" toggle button to the filter bar and "Next Service" column header**

In the filter bar HTML, find:

```html
<span class="count" id="count">0 assets</span>
```

Add the button immediately before that span:

```html
<button class="btn-ghost" id="f-overdue">Overdue only</button>
<span class="count" id="count">0 assets</span>
```

In the table `<thead>`, find:

```html
<th>Asset Tag</th><th>Name</th><th>Category</th><th>Status</th><th>Location</th><th>Installed</th>
```

Replace with:

```html
<th>Asset Tag</th><th>Name</th><th>Category</th><th>Status</th><th>Location</th><th>Installed</th><th>Next Service</th>
```

- [ ] **Step 4: Update `renderKpis()`, `filtered()`, and `renderTable()`**

Replace the entire `renderKpis` function:

```js
function renderKpis() {
  $("k-total").textContent = assets.length;
  $("k-active").textContent = assets.filter(a => a.status === "active").length;
  $("k-maint").textContent = assets.filter(a => a.status === "maintenance").length;
  $("k-retired").textContent = assets.filter(a => a.status === "retired").length;
  const today = localToday();
  $("k-overdue").textContent = assets.filter(a => a.next_service_date && a.next_service_date < today).length;
}
```

Replace the entire `filtered` function:

```js
function filtered() {
  const q = $("search").value.trim().toLowerCase();
  const st = $("f-status").value;
  const cat = $("f-category").value;
  const today = localToday();
  return assets.filter(a => {
    if (selectedLoc && String(a.location_id) !== selectedLoc) return false;
    if (st && a.status !== st) return false;
    if (cat && a.category !== cat) return false;
    if (q && !(a.asset_tag.toLowerCase().includes(q) || a.name.toLowerCase().includes(q))) return false;
    if (overdueOnly && (!a.next_service_date || a.next_service_date >= today)) return false;
    return true;
  });
}
```

Replace the entire `renderTable` function:

```js
function renderTable() {
  const rows = filtered();
  const tb = $("rows");
  const today = localToday();
  tb.innerHTML = "";
  $("count").textContent = rows.length + (rows.length === 1 ? " asset" : " assets");
  $("empty").style.display = rows.length ? "none" : "block";
  for (const a of rows) {
    const tr = document.createElement("tr");
    const loc = locById[a.location_id];
    const isOverdue = a.next_service_date && a.next_service_date < today;
    if (isOverdue) tr.style.background = "var(--red-light)";
    const svcCell = a.next_service_date
      ? `${a.next_service_date}${isOverdue ? ' <span style="color:var(--red);font-weight:700;font-size:11px;text-transform:uppercase;margin-left:6px">OVERDUE</span>' : ''}`
      : "—";
    tr.innerHTML =
      `<td><span class="tag">${a.asset_tag}</span></td>` +
      `<td style="color:var(--navy);font-weight:600">${escapeHtml(a.name)}</td>` +
      `<td><span class="cat">${a.category}</span></td>` +
      `<td><span class="pill"><span class="dot" style="background:${STATUS_COLOR[a.status] || "var(--caption)"}"></span>${a.status}</span></td>` +
      `<td>${loc ? escapeHtml(loc.name) : "—"}</td>` +
      `<td>${a.installed_date || "—"}</td>` +
      `<td>${svcCell}</td>`;
    tr.onclick = () => openDrawer(a.id);
    tb.appendChild(tr);
  }
}
```

- [ ] **Step 5: Wire click handlers for the overdue toggle and KPI card**

In the `/* Wire events */` section, after the existing event wires, add:

```js
function setOverdueFilter(on) {
  overdueOnly = on;
  $("f-overdue").style.background = on ? "var(--red)" : "";
  $("f-overdue").style.color = on ? "var(--white)" : "";
  $("f-overdue").style.borderColor = on ? "var(--red)" : "";
  renderTable();
}
$("f-overdue").onclick = () => setOverdueFilter(!overdueOnly);
$("k-overdue-card").onclick = () => setOverdueFilter(true);
```

- [ ] **Step 6: Manual smoke test**

Start the server: `uvicorn src.main:app --reload`

Open `http://localhost:8000` in a browser and verify:
- 5 KPI cards visible, "Overdue for Service" in red
- "Next Service" column present in the table (shows "—" for all seeded assets since they have no `next_service_date` yet)
- "Overdue only" button in filter bar — click it, overdue KPI count is 0, table shows "No assets match"
- KPI card click also activates the filter

To see overdue behavior, use the API directly to set a past date on one asset:
```
curl -X PUT http://localhost:8000/assets/1 -H "Content-Type: application/json" -d "{\"next_service_date\": \"2026-01-01\"}"
```
Refresh the page. Asset 1 should show the red OVERDUE badge, the KPI card should show "1", and the overdue filter should include it.

- [ ] **Step 7: Commit**

```
git add src/static/index.html
git commit -m "feat: add overdue KPI card, table column, and filter toggle"
```

---

### Task 3: Dashboard — Next Service Date in add modal and detail drawer

All changes are in `src/static/index.html`. Continue from where Task 2 left off.

**Files:**
- Modify: `src/static/index.html`

**Interfaces:**
- Consumes: `asset.next_service_date: string | null` from `GET /assets` (Task 1), `localToday(): string` (Task 2)

---

- [ ] **Step 1: Add Next Service Date field to the Add modal**

In the Add modal HTML, find:

```html
<div class="field"><label>Notes</label><textarea id="a-notes" rows="2"></textarea></div>
```

Insert a new field immediately before it:

```html
<div class="field"><label>Next Service Date</label><input id="a-service" type="date"></div>
<div class="field"><label>Notes</label><textarea id="a-notes" rows="2"></textarea></div>
```

- [ ] **Step 2: Add Next Service Date field to the Detail drawer**

In the Detail drawer HTML, find:

```html
<div class="field"><label>Notes</label><textarea id="d-notes" rows="2"></textarea></div>
```

Insert a new field immediately before it:

```html
<div class="field">
  <label>Next Service Date</label>
  <input id="d-service" type="date">
  <div id="d-overdue-badge" style="display:none;color:var(--red);font-size:13px;font-weight:700;margin-top:4px">OVERDUE</div>
</div>
<div class="field"><label>Notes</label><textarea id="d-notes" rows="2"></textarea></div>
```

- [ ] **Step 3: Update `openAdd()` to reset the new field**

Replace the entire `openAdd` function:

```js
function openAdd() {
  $("a-name").value = ""; $("a-tag").value = ""; $("a-category").value = "plc";
  $("a-status").value = "active"; $("a-installed").value = "";
  $("a-service").value = ""; $("a-notes").value = "";
  $("a-err").textContent = "";
  fillLocationSelect($("a-location"), null);
  $("addOverlay").classList.add("open");
}
```

- [ ] **Step 4: Update `saveAdd()` to include `next_service_date` in the POST payload**

In `saveAdd`, replace the `payload` object. Find:

```js
  const payload = {
    name: $("a-name").value.trim(),
    asset_tag: tag,
    category: $("a-category").value,
    status: $("a-status").value,
    location_id: $("a-location").value ? Number($("a-location").value) : null,
    installed_date: $("a-installed").value || null,
    notes: $("a-notes").value.trim() || null,
  };
```

Replace with:

```js
  const payload = {
    name: $("a-name").value.trim(),
    asset_tag: tag,
    category: $("a-category").value,
    status: $("a-status").value,
    location_id: $("a-location").value ? Number($("a-location").value) : null,
    installed_date: $("a-installed").value || null,
    next_service_date: $("a-service").value || null,
    notes: $("a-notes").value.trim() || null,
  };
```

- [ ] **Step 5: Update `openDrawer()` to pre-fill the field and show the overdue badge**

Replace the entire `openDrawer` function:

```js
function openDrawer(id) {
  const a = assets.find(x => x.id === id);
  if (!a) return;
  currentId = id;
  $("d-title").textContent = a.name;
  $("d-tag").value = a.asset_tag;
  $("d-name").value = a.name;
  $("d-category").value = a.category;
  $("d-status").value = a.status;
  $("d-installed").value = a.installed_date || "—";
  $("d-service").value = a.next_service_date || "";
  const isOverdue = a.next_service_date && a.next_service_date < localToday();
  $("d-overdue-badge").style.display = isOverdue ? "block" : "none";
  $("d-notes").value = a.notes || "";
  $("d-err").textContent = "";
  fillLocationSelect($("d-location"), a.location_id);
  $("drawerOverlay").classList.add("open");
}
```

- [ ] **Step 6: Update `saveDrawer()` to include `next_service_date` in the PUT payload**

In `saveDrawer`, replace the `payload` object. Find:

```js
  const payload = {
    name: $("d-name").value.trim(),
    category: $("d-category").value,
    status: $("d-status").value,
    location_id: $("d-location").value ? Number($("d-location").value) : null,
    notes: $("d-notes").value.trim() || null,
  };
```

Replace with:

```js
  const payload = {
    name: $("d-name").value.trim(),
    category: $("d-category").value,
    status: $("d-status").value,
    location_id: $("d-location").value ? Number($("d-location").value) : null,
    next_service_date: $("d-service").value || null,
    notes: $("d-notes").value.trim() || null,
  };
```

- [ ] **Step 7: Manual smoke test**

With the server running (`uvicorn src.main:app --reload`), open `http://localhost:8000` and verify:

1. Click **+ Add Asset** — "Next Service Date" date picker is present. Fill in a past date (e.g. `2026-01-01`) and save. The new asset should appear in the table with the red OVERDUE badge, and the overdue KPI count should increment.
2. Click any asset row — drawer opens. "Next Service Date" field is present and pre-filled if a date was saved.
3. For an asset with a past service date, the "OVERDUE" badge appears below the date field in the drawer.
4. Clear the date in the drawer and save — the asset should no longer show OVERDUE.

- [ ] **Step 8: Run the full test suite one final time**

```
pytest
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```
git add src/static/index.html
git commit -m "feat: add next service date field to add modal and detail drawer"
```
