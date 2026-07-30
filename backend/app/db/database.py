"""SQLite database setup and connection management."""

import aiosqlite

from app.config import settings

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    """Get the database connection (singleton)."""
    global _db
    if _db is None:
        _db = await aiosqlite.connect(str(settings.db_path))
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
    return _db


async def close_db() -> None:
    """Close the database connection."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None


async def init_db() -> None:
    """Initialize database schema and seed data."""
    db = await get_db()
    await db.executescript(SCHEMA_SQL)
    await db.commit()

    # Check if seed data exists
    cursor = await db.execute("SELECT COUNT(*) FROM parts")
    row = await cursor.fetchone()
    if row[0] == 0:
        await _seed_demo_data(db)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS parts (
    id TEXT PRIMARY KEY,
    part_number TEXT UNIQUE NOT NULL,
    revision TEXT NOT NULL,
    family_id TEXT NOT NULL,
    description TEXT,
    material TEXT,
    surface_finish TEXT,
    supplier TEXT,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS part_families (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    material TEXT NOT NULL,
    surface_finish TEXT NOT NULL,
    thresholds TEXT NOT NULL DEFAULT '{}',
    capture_profile TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS inspections (
    id TEXT PRIMARY KEY,
    part_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'identified',
    decision_result TEXT,
    decision_basis TEXT,
    started_at TEXT NOT NULL,
    decided_at TEXT,
    scenario_id TEXT,
    FOREIGN KEY (part_id) REFERENCES parts(id)
);

CREATE TABLE IF NOT EXISTS images (
    id TEXT PRIMARY KEY,
    inspection_id TEXT NOT NULL,
    camera_angle TEXT NOT NULL,
    file_path TEXT NOT NULL,
    thumbnail_path TEXT,
    quality_result TEXT DEFAULT '{}',
    FOREIGN KEY (inspection_id) REFERENCES inspections(id)
);

CREATE TABLE IF NOT EXISTS findings (
    id TEXT PRIMARY KEY,
    inspection_id TEXT NOT NULL,
    image_id TEXT,
    defect_class TEXT NOT NULL,
    approach TEXT NOT NULL,
    confidence REAL,
    severity TEXT,
    bbox TEXT,
    heatmap_path TEXT,
    mask_path TEXT,
    description TEXT,
    FOREIGN KEY (inspection_id) REFERENCES inspections(id)
);

CREATE TABLE IF NOT EXISTS overrides (
    id TEXT PRIMARY KEY,
    inspection_id TEXT NOT NULL UNIQUE,
    old_decision TEXT NOT NULL,
    new_decision TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    comment TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (inspection_id) REFERENCES inspections(id)
);

CREATE TABLE IF NOT EXISTS certificates (
    id TEXT PRIMARY KEY,
    inspection_id TEXT NOT NULL UNIQUE,
    token TEXT UNIQUE NOT NULL,
    pdf_path TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (inspection_id) REFERENCES inspections(id)
);

CREATE INDEX IF NOT EXISTS idx_inspections_status ON inspections(status);
CREATE INDEX IF NOT EXISTS idx_inspections_part_id ON inspections(part_id);
CREATE INDEX IF NOT EXISTS idx_findings_inspection_id ON findings(inspection_id);
CREATE INDEX IF NOT EXISTS idx_images_inspection_id ON images(inspection_id);
"""


async def _seed_demo_data(db: aiosqlite.Connection) -> None:
    """Seed the database with demo part families and parts."""
    import json

    families = [
        {
            "id": "fam-machined-al",
            "name": "machined-aluminum-plate",
            "display_name": "Machined Aluminum Plate",
            "material": "Aluminum 6061-T6",
            "surface_finish": "Matte anodized",
            "thresholds": json.dumps({
                "confidence_high": 0.85,
                "confidence_low": 0.55,
                "severity_threshold": "major",
                "max_findings_pass": 0,
            }),
            "capture_profile": json.dumps({
                "cameras": ["top", "north", "south", "east", "west"],
                "lighting": "diffuse-standard",
                "exposure_mode": "auto",
                "polarization": False,
            }),
        },
        {
            "id": "fam-screw-assy",
            "name": "precision-screw-assembly",
            "display_name": "Precision Screw Assembly",
            "material": "Stainless Steel 304",
            "surface_finish": "Machined bright",
            "thresholds": json.dumps({
                "confidence_high": 0.80,
                "confidence_low": 0.50,
                "severity_threshold": "major",
                "max_findings_pass": 0,
            }),
            "capture_profile": json.dumps({
                "cameras": ["top", "north", "south", "east", "west"],
                "lighting": "ring-highlight",
                "exposure_mode": "hdr",
                "polarization": True,
            }),
        },
        {
            "id": "fam-weldment",
            "name": "welded-stainless-component",
            "display_name": "Welded Stainless Component",
            "material": "Stainless Steel 316L",
            "surface_finish": "Electropolished",
            "thresholds": json.dumps({
                "confidence_high": 0.82,
                "confidence_low": 0.52,
                "severity_threshold": "minor",
                "max_findings_pass": 0,
            }),
            "capture_profile": json.dumps({
                "cameras": ["top", "north", "south", "east", "west"],
                "lighting": "diffuse-hdr",
                "exposure_mode": "hdr",
                "polarization": True,
            }),
        },
        {
            "id": "fam-pcb",
            "name": "pcb-sub-assembly",
            "display_name": "PCB Sub-Assembly",
            "material": "FR-4 / Mixed",
            "surface_finish": "HASL / OSP",
            "thresholds": json.dumps({
                "confidence_high": 0.88,
                "confidence_low": 0.60,
                "severity_threshold": "major",
                "max_findings_pass": 0,
            }),
            "capture_profile": json.dumps({
                "cameras": ["top", "north", "south", "east", "west"],
                "lighting": "diffuse-standard",
                "exposure_mode": "auto",
                "polarization": False,
            }),
        },
        {
            "id": "fam-anodized",
            "name": "anodized-housing",
            "display_name": "Anodized Housing",
            "material": "Aluminum 7075-T6",
            "surface_finish": "Type III hard anodized",
            "thresholds": json.dumps({
                "confidence_high": 0.83,
                "confidence_low": 0.53,
                "severity_threshold": "major",
                "max_findings_pass": 0,
            }),
            "capture_profile": json.dumps({
                "cameras": ["top", "north", "south", "east", "west"],
                "lighting": "diffuse-polarized",
                "exposure_mode": "hdr",
                "polarization": True,
            }),
        },
    ]

    for f in families:
        await db.execute(
            """INSERT INTO part_families (id, name, display_name, material, surface_finish, thresholds, capture_profile)
               VALUES (:id, :name, :display_name, :material, :surface_finish, :thresholds, :capture_profile)""",
            f,
        )

    parts = [
        {
            "id": "part-001",
            "part_number": "839-041322-001",
            "revision": "C",
            "family_id": "fam-machined-al",
            "description": "Chamber Lid Plate - Machined Aluminum",
            "material": "Aluminum 6061-T6",
            "surface_finish": "Matte anodized",
            "supplier": "Precision Machining Corp",
        },
        {
            "id": "part-002",
            "part_number": "839-041322-002",
            "revision": "B",
            "family_id": "fam-machined-al",
            "description": "Gas Distribution Plate",
            "material": "Aluminum 6061-T6",
            "surface_finish": "Matte anodized",
            "supplier": "Precision Machining Corp",
        },
        {
            "id": "part-003",
            "part_number": "715-098456-003",
            "revision": "A",
            "family_id": "fam-screw-assy",
            "description": "RF Feed Assembly - 8-Screw Mount",
            "material": "Stainless Steel 304",
            "surface_finish": "Machined bright",
            "supplier": "Fastener Solutions Inc",
        },
        {
            "id": "part-004",
            "part_number": "622-073891-001",
            "revision": "D",
            "family_id": "fam-weldment",
            "description": "Process Gas Manifold - Welded",
            "material": "Stainless Steel 316L",
            "surface_finish": "Electropolished",
            "supplier": "TechWeld Industries",
        },
        {
            "id": "part-005",
            "part_number": "444-027654-002",
            "revision": "E",
            "family_id": "fam-pcb",
            "description": "ESC Controller Board",
            "material": "FR-4 / Mixed",
            "surface_finish": "HASL",
            "supplier": "CircuitPro Electronics",
        },
        {
            "id": "part-009",
            "part_number": "444-027654-003",
            "revision": "B",
            "family_id": "fam-pcb",
            "description": "RF Driver Board",
            "material": "FR-4 / Mixed",
            "surface_finish": "ENIG",
            "supplier": "CircuitPro Electronics",
        },
        {
            "id": "part-010",
            "part_number": "444-027654-004",
            "revision": "A",
            "family_id": "fam-pcb",
            "description": "Power Distribution Board",
            "material": "FR-4 / Mixed",
            "surface_finish": "HASL",
            "supplier": "CircuitPro Electronics",
        },
        {
            "id": "part-011",
            "part_number": "839-041322-003",
            "revision": "A",
            "family_id": "fam-machined-al",
            "description": "Chamber Lid Plate — Porosity Sample",
            "material": "Aluminum 6061-T6",
            "surface_finish": "As-machined",
            "supplier": "Precision Machining Corp",
        },
        {
            "id": "part-012",
            "part_number": "839-041322-004",
            "revision": "B",
            "family_id": "fam-machined-al",
            "description": "Gas Inlet Manifold — Tool Marks",
            "material": "Aluminum 6061-T6",
            "surface_finish": "Matte anodized",
            "supplier": "Precision Machining Corp",
        },
        {
            "id": "part-013",
            "part_number": "839-055678-004",
            "revision": "C",
            "family_id": "fam-anodized",
            "description": "Lower Shield — Coated (Stain)",
            "material": "Aluminum 7075-T6",
            "surface_finish": "Type III hard anodized",
            "supplier": "AnodizeTech LLC",
        },
        {
            "id": "part-014",
            "part_number": "839-055678-005",
            "revision": "A",
            "family_id": "fam-anodized",
            "description": "Upper Chamber Ring — Label Issue",
            "material": "Aluminum 7075-T6",
            "surface_finish": "Type III hard anodized",
            "supplier": "SurfaceTek Global",
        },
        {
            "id": "part-015",
            "part_number": "715-098456-008",
            "revision": "B",
            "family_id": "fam-screw-assy",
            "description": "Showerhead Retainer Screw — Burr",
            "material": "Stainless Steel 304",
            "surface_finish": "Machined bright",
            "supplier": "Fastener Solutions Inc",
        },
        {
            "id": "part-016",
            "part_number": "839-055678-006",
            "revision": "D",
            "family_id": "fam-anodized",
            "description": "Electrode Housing — Paint Peel",
            "material": "Aluminum 7075-T6",
            "surface_finish": "Painted + anodized",
            "supplier": "AnodizeTech LLC",
        },
        {
            "id": "part-006",
            "part_number": "839-055678-001",
            "revision": "B",
            "family_id": "fam-anodized",
            "description": "Upper Electrode Housing",
            "material": "Aluminum 7075-T6",
            "surface_finish": "Type III hard anodized",
            "supplier": "AnodizeTech LLC",
        },
        {
            "id": "part-007",
            "part_number": "839-055678-003",
            "revision": "A",
            "family_id": "fam-anodized",
            "description": "Lower Chamber Shield",
            "material": "Aluminum 7075-T6",
            "surface_finish": "Type III hard anodized",
            "supplier": "SurfaceTek Global",
        },
        {
            "id": "part-008",
            "part_number": "715-098456-007",
            "revision": "C",
            "family_id": "fam-screw-assy",
            "description": "Showerhead Mounting Bracket",
            "material": "Stainless Steel 304",
            "surface_finish": "Passivated",
            "supplier": "Fastener Solutions Inc",
        },
    ]

    for p in parts:
        await db.execute(
            """INSERT INTO parts (id, part_number, revision, family_id, description, material, surface_finish, supplier)
               VALUES (:id, :part_number, :revision, :family_id, :description, :material, :surface_finish, :supplier)""",
            p,
        )

    await db.commit()
