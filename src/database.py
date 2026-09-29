import aiosqlite
import os

DB_PATH = os.environ.get("DB_PATH", "assets.db")

async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()

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

async def seed_assets(db):
    """Seed demo assets for the running server. Not used by the test harness."""
    cursor = await db.execute("SELECT COUNT(*) FROM assets")
    if (await cursor.fetchone())[0] != 0:
        return
    await db.executemany(
        "INSERT INTO assets (name, asset_tag, category, status, location_id, installed_date) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("CompactLogix 5380", "PLC-1042", "plc", "active", 1, "2023-03-15"),
            ("ControlLogix 5580", "PLC-2087", "plc", "active", 2, "2022-07-01"),
            ("PowerFlex 755", "DRV-3310", "drive", "maintenance", 1, "2021-11-20"),
            ("Kinetix 5700", "DRV-4120", "drive", "active", 3, "2024-01-10"),
            ("PanelView Plus 7", "HMI-5501", "hmi", "active", 2, "2023-06-05"),
            ("PanelView Plus 6", "HMI-5502", "hmi", "retired", 4, "2019-02-14"),
            ("Photoelectric Sensor 42EF", "SEN-6201", "sensor", "active", 3, "2024-05-22"),
            ("Proximity Sensor 871C", "SEN-6355", "sensor", "maintenance", 1, "2022-09-30"),
            ("FANUC ArcMate Robot", "ROB-7001", "robot", "active", 3, "2023-08-18"),
            ("ABB IRB 1200 Robot", "ROB-7042", "robot", "active", 2, "2024-03-01"),
        ],
    )
    await db.commit()

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await create_schema(db)
        await seed_assets(db)
