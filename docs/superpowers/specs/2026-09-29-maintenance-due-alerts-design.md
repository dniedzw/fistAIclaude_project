# Design: Maintenance Due Alerts

**Date:** 2026-09-29
**Feature file:** `Prompts/FEATURE.md`

## Problem

The asset tracker is a passive inventory list. It has no way to surface which assets have missed their scheduled maintenance date. Missed preventive maintenance leads to unplanned equipment failure and production downtime.

## Goal

Give plant managers an at-a-glance view of which assets are overdue for service, and a one-click work list of exactly which ones need attention.

## Scope

This version adds a single `next_service_date` per asset and surfaces overdue status on the dashboard. Full maintenance logging, service history, and automated scheduling are out of scope.

## Decisions

| Question | Decision | Reason |
|---|---|---|
| Where is the date stored? | New `next_service_date TEXT` column on `assets` | Spec calls for a single date per asset, independent of maintenance events |
| Use existing `maintenance_events.due_at`? | No | Spec intentionally scopes to one date per asset; coupling the two features would complicate both |
| Where is "overdue" computed? | Frontend JS | Dashboard already filters entirely in JS; date comparison is trivial; avoids server timezone issues |

---

## Data Layer

### Schema change

Add one nullable column to the `assets` table:

```sql
ALTER TABLE assets ADD COLUMN next_service_date TEXT
```

**Migration strategy:** In `database.py::create_schema`, attempt the `ALTER TABLE` after the `CREATE TABLE IF NOT EXISTS` block. Catch the "duplicate column name" OperationalError SQLite raises if the column already exists. Tests use `:memory:` so they always run against a fresh schema.

No new tables. No migration files. No breaking change to existing data.

---

## API Layer

### Schema changes (`src/schemas.py`)

Add `next_service_date: Optional[str] = None` to:
- `AssetCreate`
- `AssetUpdate`
- `AssetOut`

### Route changes (`src/main.py`)

- `POST /assets` — add `next_service_date` to the INSERT column list and values tuple.
- `PUT /assets/{id}` — no change; already uses `model_dump(exclude_unset=True)`, so the new field is included automatically when provided.
- `GET /assets` — no change; uses `SELECT *`, picks up the new column automatically.

All changes are backwards-compatible. Existing clients receive `next_service_date: null` for assets that don't have one set.

---

## Frontend (`src/static/index.html`)

### State

Add one boolean variable: `let overdueOnly = false;`

### KPI strip

- Change CSS grid from `repeat(4, 1fr)` to `repeat(5, 1fr)`.
- Add a 5th KPI card: **"Overdue for Service"**, count in `--red`.
- Clicking the card sets `overdueOnly = true` and re-renders the table (same effect as the filter toggle).

### Asset table

- Add **"Next Service"** column header (after "Installed").
- Each row: show `next_service_date` or `—`. If overdue, append a small inline `OVERDUE` badge styled with `--red` text and `--red-light` background.
- Overdue rows get a `background: var(--red-light)` row highlight.

### Filter bar

- Add an **"Overdue only"** toggle button after the category dropdown.
- Active state: `--red` background, white text. Inactive: ghost style.
- Clicking toggles `overdueOnly`, re-renders table.

### `filtered()` function

```js
const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD local date
// existing filters ...
if (overdueOnly) {
  if (!a.next_service_date || a.next_service_date >= today) return false;
}
```

### `renderKpis()`

```js
const today = new Date().toISOString().slice(0, 10);
const overdueCount = assets.filter(a => a.next_service_date && a.next_service_date < today).length;
$("k-overdue").textContent = overdueCount;
```

### Add modal

Add a **"Next Service Date"** `<input type="date">` field (`id="a-service"`). Include `next_service_date` in the POST payload.

### Detail drawer

Add a **"Next Service Date"** `<input type="date">` field (`id="d-service"`). Pre-fill on `openDrawer`. Include `next_service_date` in the PUT payload. Show an "OVERDUE" badge below the field if the date has passed.

---

## Tests (`tests/`)

Four new test cases:

1. `POST /assets` with `next_service_date` set → response includes the value.
2. `POST /assets` without `next_service_date` → response has `next_service_date: null`.
3. `PUT /assets/{id}` with a new `next_service_date` → response reflects the update.
4. `GET /assets` → each asset object includes the `next_service_date` field.

---

## Success criteria

- A manager opens the dashboard and immediately sees how many assets are overdue in the KPI strip.
- Clicking the overdue card (or the filter toggle) narrows the table to only overdue assets.
- Overdue rows are visually distinct from the rest of the list.
- Adding or editing an asset exposes a Next Service Date field.
- All existing tests continue to pass.
