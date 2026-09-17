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

-- ─────────────────────────────────────────────────────────────────────────
-- Source Comparison (LAIR / FAIR / SHQ) — feature: avip-source-comparison
-- New sc_* tables appended additively; existing tables/seed logic untouched.
-- Conventions: TEXT uuid PKs, ISO TEXT timestamps, JSON-in-TEXT columns,
-- foreign_keys=ON (set in get_db).
-- ─────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sc_source_records (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,               -- LAIR | FAIR | SHQ
    external_record_id TEXT NOT NULL,   -- id from the source/adapter
    part_number TEXT NOT NULL,
    lot_number TEXT NOT NULL,
    serial_number TEXT,
    fields TEXT NOT NULL DEFAULT '{}',  -- JSON: field_name -> raw value
    group_id TEXT,                      -- FK sc_aligned_groups.id (null until aligned/unmatched)
    received_at TEXT NOT NULL,
    FOREIGN KEY (group_id) REFERENCES sc_aligned_groups(id)
);

CREATE TABLE IF NOT EXISTS sc_aligned_groups (
    id TEXT PRIMARY KEY,
    part_number TEXT NOT NULL,
    lot_number TEXT NOT NULL,
    present_sources TEXT NOT NULL DEFAULT '[]',  -- JSON list e.g. ["LAIR","SHQ"]
    alignment_state TEXT NOT NULL,               -- partial | complete | unmatched
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (part_number, lot_number)
);

CREATE TABLE IF NOT EXISTS sc_discrepancies (
    id TEXT PRIMARY KEY,
    group_id TEXT NOT NULL,
    part_number TEXT NOT NULL,
    lot_number TEXT NOT NULL,
    field_name TEXT NOT NULL,
    field_type TEXT NOT NULL,           -- numeric | categorical | identifier | free_text
    "values" TEXT NOT NULL DEFAULT '{}',  -- JSON: source -> value ("values" quoted: reserved word)
    provenance TEXT NOT NULL,           -- exact-match | numeric-threshold | llm | llm-unavailable
    review_state TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    FOREIGN KEY (group_id) REFERENCES sc_aligned_groups(id),
    UNIQUE (group_id, field_name)       -- one discrepancy per field per group (idempotent recompare)
);

CREATE TABLE IF NOT EXISTS sc_review_decisions (
    id TEXT PRIMARY KEY,
    discrepancy_id TEXT NOT NULL UNIQUE,
    decision TEXT NOT NULL,             -- confirmed | dismissed
    reviewer TEXT NOT NULL,
    note TEXT,
    decided_at TEXT NOT NULL,
    FOREIGN KEY (discrepancy_id) REFERENCES sc_discrepancies(id)
);

CREATE TABLE IF NOT EXISTS sc_review_audit (
    id TEXT PRIMARY KEY,
    discrepancy_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    note TEXT,
    decided_at TEXT NOT NULL,
    FOREIGN KEY (discrepancy_id) REFERENCES sc_discrepancies(id)
);

CREATE TABLE IF NOT EXISTS sc_rejected_records (
    id TEXT PRIMARY KEY,
    source TEXT,
    external_record_id TEXT,
    raw_payload TEXT NOT NULL,          -- JSON of the offending record
    reason TEXT NOT NULL,
    rejected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sc_comparison_config (
    id TEXT PRIMARY KEY DEFAULT 'default',
    common_key TEXT NOT NULL DEFAULT '["part_number","lot_number"]',
    fields TEXT NOT NULL DEFAULT '{}',          -- JSON: field -> {type, in_scope, threshold?}
    llm_provider TEXT NOT NULL DEFAULT 'mock',
    assumptions TEXT NOT NULL DEFAULT '[]',     -- JSON list of AssumptionItem
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sc_source_group ON sc_source_records(group_id);
CREATE INDEX IF NOT EXISTS idx_sc_source_key ON sc_source_records(part_number, lot_number);
CREATE INDEX IF NOT EXISTS idx_sc_disc_group ON sc_discrepancies(group_id);
CREATE INDEX IF NOT EXISTS idx_sc_disc_state ON sc_discrepancies(review_state);
CREATE INDEX IF NOT EXISTS idx_sc_disc_key ON sc_discrepancies(part_number, lot_number);
CREATE INDEX IF NOT EXISTS idx_sc_audit_disc ON sc_review_audit(discrepancy_id);

-- ─────────────────────────────────────────────────────────────────────────
-- Configurable numeric thresholds — feature: avip-source-comparison
-- Runtime-editable thresholds persisted across restart, with a global
-- per-FIELD default (in sc_comparison_config.fields JSON) PLUS an optional
-- per-PART override here, and a fully append-only audit of every change.
-- Conventions match the sc_* tables above: TEXT uuid PKs, ISO TEXT
-- timestamps, JSON-in-TEXT columns, foreign_keys=ON.
-- ─────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sc_threshold_overrides (
    id TEXT PRIMARY KEY,
    part_number TEXT NOT NULL,
    field_name TEXT NOT NULL,
    threshold REAL NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (part_number, field_name)    -- one override per (part, field): idempotent upsert
);

CREATE TABLE IF NOT EXISTS sc_config_audit (
    id TEXT PRIMARY KEY,
    change_type TEXT NOT NULL,          -- field_default | part_override_set | part_override_delete | field_scope
    field_name TEXT,
    part_number TEXT,                   -- nullable: field_default / field_scope changes are part-agnostic
    old_value TEXT,
    new_value TEXT,
    changed_by TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    note TEXT
);

CREATE INDEX IF NOT EXISTS idx_sc_threshold_overrides_part ON sc_threshold_overrides(part_number);
CREATE INDEX IF NOT EXISTS idx_sc_config_audit_changed_at ON sc_config_audit(changed_at);

-- ─────────────────────────────────────────────────────────────────────────
-- PCBA TPI Generation — feature: pcba-tpi-generation
-- New tpi_* tables appended additively; existing tables/seed logic untouched
-- (Req 9.2). Conventions match the sc_* tables above: TEXT uuid PKs, ISO TEXT
-- timestamps, JSON-in-TEXT columns, foreign_keys=ON (set in get_db).
-- Pipeline: ingestion -> extraction -> mapping/generation -> review -> final.
-- ─────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tpi_pcbas (
    id TEXT PRIMARY KEY,
    pcba_id TEXT NOT NULL UNIQUE,       -- external/business id for the sample PCBA
    status TEXT NOT NULL DEFAULT 'ingesting',  -- ingesting | drafted | in_review | finalized
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tpi_inputs (
    id TEXT PRIMARY KEY,
    pcba_id TEXT NOT NULL,              -- FK tpi_pcbas.pcba_id (business id)
    input_type TEXT NOT NULL,           -- testing_procedure | operating_procedure | circuit_diagram | drawing
    filename TEXT NOT NULL,
    detected_format TEXT,               -- e.g. pdf | png | cad [CONFIRM]; null until detected
    status TEXT NOT NULL,               -- ingested | flagged_for_manual_annotation (Req 1.4)
    raw_ref TEXT NOT NULL,              -- stored file/blob reference
    FOREIGN KEY (pcba_id) REFERENCES tpi_pcbas(pcba_id)
);

CREATE TABLE IF NOT EXISTS tpi_extractions (
    id TEXT PRIMARY KEY,
    input_id TEXT NOT NULL,             -- FK tpi_inputs.id
    content_json TEXT NOT NULL DEFAULT '{}',  -- JSON: structured extracted content
    status TEXT NOT NULL,               -- ingested | flagged_for_manual_annotation
    provider TEXT NOT NULL DEFAULT 'mock',    -- mock | openai | ...
    FOREIGN KEY (input_id) REFERENCES tpi_inputs(id)
);

CREATE TABLE IF NOT EXISTS tpi_sections (
    id TEXT PRIMARY KEY,
    pcba_id TEXT NOT NULL,              -- FK tpi_pcbas.pcba_id (business id)
    key TEXT NOT NULL,                  -- e.g. test_steps | expected_results | equipment
    title TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    source_input_ids TEXT NOT NULL DEFAULT '[]',  -- JSON list of tpi_inputs.id (provenance, Req 3.3)
    incomplete INTEGER NOT NULL DEFAULT 0,        -- 0/1: true if a source input was flagged (Req 3.4)
    FOREIGN KEY (pcba_id) REFERENCES tpi_pcbas(pcba_id)
);

CREATE TABLE IF NOT EXISTS tpi_drafts (
    pcba_id TEXT PRIMARY KEY,           -- FK tpi_pcbas.pcba_id (one draft per PCBA)
    template_kind TEXT NOT NULL DEFAULT 'placeholder',  -- client | placeholder [CONFIRM]
    provider TEXT NOT NULL DEFAULT 'mock',
    review_state TEXT NOT NULL DEFAULT 'drafted',        -- drafted | in_review | finalized
    FOREIGN KEY (pcba_id) REFERENCES tpi_pcbas(pcba_id)
);

CREATE TABLE IF NOT EXISTS tpi_review_audit (
    id TEXT PRIMARY KEY,
    pcba_id TEXT NOT NULL,              -- FK tpi_pcbas.pcba_id
    reviewer TEXT NOT NULL,
    action TEXT NOT NULL,               -- e.g. finalize | correct
    changes_json TEXT NOT NULL DEFAULT '{}',  -- JSON: what changed (who/when captured by reviewer/decided_at)
    decided_at TEXT NOT NULL,
    FOREIGN KEY (pcba_id) REFERENCES tpi_pcbas(pcba_id)
);

CREATE INDEX IF NOT EXISTS idx_tpi_inputs_pcba ON tpi_inputs(pcba_id);
CREATE INDEX IF NOT EXISTS idx_tpi_extractions_input ON tpi_extractions(input_id);
CREATE INDEX IF NOT EXISTS idx_tpi_sections_pcba ON tpi_sections(pcba_id);
CREATE INDEX IF NOT EXISTS idx_tpi_drafts_state ON tpi_drafts(review_state);
CREATE INDEX IF NOT EXISTS idx_tpi_review_audit_pcba ON tpi_review_audit(pcba_id);
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
        # ── Scenarios 19-31: All images from client PDF ──────────────────────
        {"id": "part-020", "part_number": "839-041322-005", "revision": "A",
         "family_id": "fam-machined-al", "description": "Chamber Lid Ring — Porosity (Curved)",
         "material": "Aluminum 6061-T6", "surface_finish": "As-machined", "supplier": "Precision Machining Corp"},
        {"id": "part-021", "part_number": "839-041322-006", "revision": "B",
         "family_id": "fam-machined-al", "description": "Machined Plate — Dent & Scratch",
         "material": "Aluminum 6061-T6", "surface_finish": "Matte anodized", "supplier": "Precision Machining Corp"},
        {"id": "part-022", "part_number": "839-041322-007", "revision": "A",
         "family_id": "fam-machined-al", "description": "Cylinder Bore — Machining Lines",
         "material": "Aluminum 6061-T6", "surface_finish": "As-machined", "supplier": "Precision Machining Corp"},
        {"id": "part-023", "part_number": "839-041322-008", "revision": "C",
         "family_id": "fam-machined-al", "description": "Machined Ring — Scratch Marks",
         "material": "Aluminum 6061-T6", "surface_finish": "Matte anodized", "supplier": "Precision Machining Corp"},
        {"id": "part-024", "part_number": "715-098456-009", "revision": "A",
         "family_id": "fam-machined-al", "description": "Machined Block — Burr at Threaded Hole",
         "material": "Aluminum 6061-T6", "surface_finish": "As-machined", "supplier": "Precision Machining Corp"},
        {"id": "part-025", "part_number": "839-055678-007", "revision": "D",
         "family_id": "fam-anodized", "description": "Chamber Ring — Engraving Mismatch",
         "material": "Aluminum 7075-T6", "surface_finish": "Type III hard anodized", "supplier": "AnodizeTech LLC"},
        {"id": "part-026", "part_number": "839-055678-008", "revision": "B",
         "family_id": "fam-anodized", "description": "Showerhead Plate — Scratch",
         "material": "Aluminum 7075-T6", "surface_finish": "Type III hard anodized", "supplier": "AnodizeTech LLC"},
        {"id": "part-027", "part_number": "839-055678-009", "revision": "A",
         "family_id": "fam-anodized", "description": "Showerhead Plate — Dent",
         "material": "Aluminum 7075-T6", "surface_finish": "Type III hard anodized", "supplier": "AnodizeTech LLC"},
        {"id": "part-028", "part_number": "839-055678-010", "revision": "C",
         "family_id": "fam-anodized", "description": "Chamber Bowl — Line Marks & Stains",
         "material": "Aluminum 7075-T6", "surface_finish": "Type III hard anodized", "supplier": "AnodizeTech LLC"},
        {"id": "part-029", "part_number": "839-055678-011", "revision": "A",
         "family_id": "fam-anodized", "description": "Perforated Plate — Coating Stain",
         "material": "Aluminum 7075-T6", "surface_finish": "Type III hard anodized", "supplier": "AnodizeTech LLC"},
        {"id": "part-030", "part_number": "839-055678-012", "revision": "B",
         "family_id": "fam-anodized", "description": "Coated Housing — Color Variation",
         "material": "Aluminum 7075-T6", "surface_finish": "Type III hard anodized", "supplier": "AnodizeTech LLC"},
        {"id": "part-031", "part_number": "715-098456-010", "revision": "A",
         "family_id": "fam-screw-assy", "description": "Shaft Fitting — Machining Burr at Collar Junction",
         "material": "Stainless Steel 304", "surface_finish": "Machined bright", "supplier": "Fastener Solutions Inc"},
        {"id": "part-032", "part_number": "715-098456-011", "revision": "A",
         "family_id": "fam-screw-assy", "description": "Fastener — Burr on Head",
         "material": "Stainless Steel 304", "surface_finish": "Machined bright", "supplier": "Fastener Solutions Inc"},
        {"id": "part-322019", "part_number": "839-041322-019", "revision": "A",
         "family_id": "fam-machined-al", "description": "Material Porosity Sample",
         "material": "Aluminum 6061-T6", "surface_finish": "As-machined", "supplier": "Precision Machining Corp"},
        {"id": "part-322020", "part_number": "839-041322-020", "revision": "A",
         "family_id": "fam-machined-al", "description": "Dent / Impact Damage Sample",
         "material": "Aluminum 6061-T6", "surface_finish": "Matte anodized", "supplier": "Precision Machining Corp"},
        {"id": "part-322021", "part_number": "839-041322-021", "revision": "A",
         "family_id": "fam-machined-al", "description": "Machining Lines / Tool Marks Sample",
         "material": "Aluminum 6061-T6", "surface_finish": "As-machined", "supplier": "Precision Machining Corp"},
        {"id": "part-322022", "part_number": "839-041322-022", "revision": "A",
         "family_id": "fam-machined-al", "description": "Scratch Marks Sample",
         "material": "Aluminum 6061-T6", "surface_finish": "Matte anodized", "supplier": "Precision Machining Corp"},
        {"id": "part-322023", "part_number": "839-041322-023", "revision": "A",
         "family_id": "fam-machined-al", "description": "Scratch Marks Sample",
         "material": "Aluminum 6061-T6", "surface_finish": "Matte anodized", "supplier": "Precision Machining Corp"},
        {"id": "part-678013", "part_number": "839-055678-013", "revision": "A",
         "family_id": "fam-anodized", "description": "Label / S/N Mismatch Sample",
         "material": "Aluminum 7075-T6", "surface_finish": "Type III hard anodized", "supplier": "AnodizeTech LLC"},
        {"id": "part-678014", "part_number": "839-055678-014", "revision": "A",
         "family_id": "fam-anodized", "description": "Label / S/N Mismatch Sample",
         "material": "Aluminum 7075-T6", "surface_finish": "Type III hard anodized", "supplier": "AnodizeTech LLC"},
        {"id": "part-322024", "part_number": "839-041322-024", "revision": "A",
         "family_id": "fam-machined-al", "description": "Scratch Marks Sample",
         "material": "Aluminum 6061-T6", "surface_finish": "Matte anodized", "supplier": "Precision Machining Corp"},
        {"id": "part-322025", "part_number": "839-041322-025", "revision": "A",
         "family_id": "fam-machined-al", "description": "Dent / Impact Damage Sample",
         "material": "Aluminum 6061-T6", "surface_finish": "Matte anodized", "supplier": "Precision Machining Corp"},
        {"id": "part-678015", "part_number": "839-055678-015", "revision": "A",
         "family_id": "fam-anodized", "description": "Coating Stain Sample",
         "material": "Aluminum 7075-T6", "surface_finish": "Type III hard anodized", "supplier": "AnodizeTech LLC"},
        {"id": "part-678016", "part_number": "839-055678-016", "revision": "A",
         "family_id": "fam-anodized", "description": "Color Variation Sample",
         "material": "Aluminum 7075-T6", "surface_finish": "Type III hard anodized", "supplier": "AnodizeTech LLC"},
        {"id": "part-678017", "part_number": "839-055678-017", "revision": "A",
         "family_id": "fam-anodized", "description": "Coating Stain Sample",
         "material": "Aluminum 7075-T6", "surface_finish": "Type III hard anodized", "supplier": "AnodizeTech LLC"},
        {"id": "part-678018", "part_number": "839-055678-018", "revision": "A",
         "family_id": "fam-anodized", "description": "Coating Stain Sample",
         "material": "Aluminum 7075-T6", "surface_finish": "Type III hard anodized", "supplier": "AnodizeTech LLC"},
        {"id": "part-456012", "part_number": "715-098456-012", "revision": "A",
         "family_id": "fam-anodized", "description": "Poor Coating Finish Sample",
         "material": "Aluminum 7075-T6", "surface_finish": "Type II anodized", "supplier": "AnodizeTech LLC"},
    ]

    for p in parts:
        await db.execute(
            """INSERT INTO parts (id, part_number, revision, family_id, description, material, surface_finish, supplier)
               VALUES (:id, :part_number, :revision, :family_id, :description, :material, :surface_finish, :supplier)""",
            p,
        )

    await db.commit()
