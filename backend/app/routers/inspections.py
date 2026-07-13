"""Inspections router — inspection lifecycle."""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.db.database import get_db
from app.models.inspection import (
    CreateInspectionRequest,
    Decision,
    DecisionResult,
    Finding,
    ImageQualityResult,
    Inspection,
    InspectionImage,
    InspectionStatus,
)
from app.services.ai_pipeline import AIPipeline

router = APIRouter()
ai_pipeline = AIPipeline()


@router.post("/inspections")
async def create_inspection(request: CreateInspectionRequest):
    """Create a new inspection session after part identification."""
    db = await get_db()

    # Look up part
    cursor = await db.execute(
        "SELECT * FROM parts WHERE part_number = ?", (request.part_number,)
    )
    part_row = await cursor.fetchone()
    if not part_row:
        raise HTTPException(status_code=404, detail=f"Part {request.part_number} not found")

    inspection_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    await db.execute(
        """INSERT INTO inspections (id, part_id, status, started_at)
           VALUES (?, ?, ?, ?)""",
        (inspection_id, part_row["id"], InspectionStatus.IDENTIFIED.value, now),
    )
    await db.commit()

    return {
        "id": inspection_id,
        "status": "identified",
        "part_number": part_row["part_number"],
        "revision": part_row["revision"],
        "family_id": part_row["family_id"],
        "started_at": now,
    }


@router.post("/inspections/{inspection_id}/capture")
async def simulate_capture(inspection_id: str):
    """Simulate multi-angle image capture."""
    db = await get_db()

    # Verify inspection exists
    cursor = await db.execute("SELECT * FROM inspections WHERE id = ?", (inspection_id,))
    insp = await cursor.fetchone()
    if not insp:
        raise HTTPException(status_code=404, detail="Inspection not found")

    # Prevent duplicate captures — if images already exist, return them
    cursor = await db.execute(
        "SELECT * FROM images WHERE inspection_id = ?", (inspection_id,)
    )
    existing_images = await cursor.fetchall()
    if existing_images:
        images = [
            InspectionImage(
                id=row["id"],
                camera_angle=row["camera_angle"],
                file_url=row["file_path"],
                thumbnail_url=row["thumbnail_path"],
                quality_result=ImageQualityResult(**json.loads(row["quality_result"])),
            )
            for row in existing_images
        ]
        return {
            "inspection_id": inspection_id,
            "status": "capturing",
            "images": [img.model_dump() for img in images],
            "all_quality_passed": all(img.quality_result.passed for img in images),
        }

    # Get part family for capture profile
    cursor = await db.execute(
        """SELECT pf.capture_profile, pf.name as family_name FROM parts p
           JOIN part_families pf ON p.family_id = pf.id
           WHERE p.id = ?""",
        (insp["part_id"],),
    )
    family_row = await cursor.fetchone()
    capture_profile = json.loads(family_row["capture_profile"])
    cameras = capture_profile.get("cameras", ["top", "north", "south", "east", "west"])

    # Map family display names to demo image folder names
    family_to_folder = {
        "machined-aluminum-plate": "metal_plate",
        "precision-screw-assembly": "screw",
        "pcb-sub-assembly": "pcb",
        "welded-stainless-component": "weldment",
        "anodized-housing": "metal_plate",  # reuse metal_plate images
        "cable-assembly": "cable",
    }
    family_name = family_row["family_name"] if family_row else ""
    # Derive the internal family name from capture_profile or family_name
    folder = "metal_plate"  # default
    for key, val in family_to_folder.items():
        if key in family_name.lower().replace(" ", "-"):
            folder = val
            break

    # Determine if this inspection is a defective scenario
    scenario_id = insp["scenario_id"] if "scenario_id" in insp.keys() else None
    # Scenarios 2-10 are defective; scenario 1 and non-scenario kiosk flow use clean
    pass_scenarios = {"scenario-01", None}
    variant = "clean" if scenario_id in pass_scenarios else "defective"

    # Generate simulated images using demo_data images
    images = []
    for angle in cameras:
        image_id = str(uuid.uuid4())
        quality = ImageQualityResult(
            passed=True, checks={"focus": True, "exposure": True, "glare": False}, failure_reason=None
        )

        file_url = f"/static/demo-images/{folder}/{variant}/{angle}.jpg"
        thumb_url = f"/static/demo-images/{folder}/{variant}/{angle}_thumb.jpg"

        await db.execute(
            """INSERT INTO images (id, inspection_id, camera_angle, file_path, thumbnail_path, quality_result)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                image_id,
                inspection_id,
                angle,
                file_url,
                thumb_url,
                quality.model_dump_json(),
            ),
        )
        images.append(
            InspectionImage(
                id=image_id,
                camera_angle=angle,
                file_url=file_url,
                thumbnail_url=thumb_url,
                quality_result=quality,
            )
        )

    # Update status
    await db.execute(
        "UPDATE inspections SET status = ? WHERE id = ?",
        (InspectionStatus.CAPTURING.value, inspection_id),
    )
    await db.commit()

    return {
        "inspection_id": inspection_id,
        "status": "capturing",
        "images": [img.model_dump() for img in images],
        "all_quality_passed": all(img.quality_result.passed for img in images),
    }


@router.post("/inspections/{inspection_id}/inspect")
async def run_inspection(inspection_id: str):
    """Run the AI pipeline on captured images."""
    db = await get_db()

    # Get inspection + part info
    cursor = await db.execute(
        """SELECT i.*, p.part_number, p.family_id, p.supplier,
                  pf.name as family_name, pf.thresholds
           FROM inspections i
           JOIN parts p ON i.part_id = p.id
           JOIN part_families pf ON p.family_id = pf.id
           WHERE i.id = ?""",
        (inspection_id,),
    )
    insp = await cursor.fetchone()
    if not insp:
        raise HTTPException(status_code=404, detail="Inspection not found")

    # Prevent duplicate inspection runs — if a decision already exists, return existing result
    if insp["decision_basis"]:
        decision_data = json.loads(insp["decision_basis"])
        cursor = await db.execute(
            "SELECT * FROM findings WHERE inspection_id = ?", (inspection_id,)
        )
        existing_findings = await cursor.fetchall()
        return {
            "inspection_id": inspection_id,
            "status": insp["status"],
            "decision": decision_data,
            "findings": [
                {
                    "id": f["id"],
                    "defect_class": f["defect_class"],
                    "approach": f["approach"],
                    "confidence": f["confidence"],
                    "severity": f["severity"],
                    "bbox": json.loads(f["bbox"]) if f["bbox"] else None,
                    "heatmap_url": f["heatmap_path"],
                    "mask_url": f["mask_path"],
                    "description": f["description"],
                    "image_id": f["image_id"],
                }
                for f in existing_findings
            ],
            "findings_count": len(existing_findings),
        }

    # Update status to inspecting
    await db.execute(
        "UPDATE inspections SET status = ? WHERE id = ?",
        (InspectionStatus.INSPECTING.value, inspection_id),
    )

    # Run AI pipeline
    thresholds = json.loads(insp["thresholds"])
    result = await ai_pipeline.inspect(
        inspection_id=inspection_id,
        family_name=insp["family_name"],
        thresholds=thresholds,
    )

    # Store findings
    for finding in result.findings:
        await db.execute(
            """INSERT INTO findings (id, inspection_id, image_id, defect_class, approach,
                                    confidence, severity, bbox, heatmap_path, mask_path, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                finding.id,
                inspection_id,
                finding.image_id,
                finding.defect_class,
                finding.approach.value,
                finding.confidence,
                finding.severity.value,
                json.dumps(finding.bbox.model_dump()) if finding.bbox else None,
                finding.heatmap_url,
                finding.mask_url,
                finding.description,
            ),
        )

    # Determine final status from decision
    now = datetime.now(timezone.utc).isoformat()
    if result.decision.result == DecisionResult.PASS:
        status = InspectionStatus.PASSED
    elif result.decision.result == DecisionResult.FAIL:
        status = InspectionStatus.IN_REVIEW
    else:
        status = InspectionStatus.IN_REVIEW

    await db.execute(
        """UPDATE inspections SET status = ?, decision_result = ?, decision_basis = ?, decided_at = ?
           WHERE id = ?""",
        (
            status.value,
            result.decision.result.value,
            result.decision.model_dump_json(),
            now,
            inspection_id,
        ),
    )
    await db.commit()

    return {
        "inspection_id": inspection_id,
        "status": status.value,
        "decision": result.decision.model_dump(),
        "findings": [f.model_dump() for f in result.findings],
        "findings_count": len(result.findings),
    }


@router.get("/inspections/{inspection_id}")
async def get_inspection(inspection_id: str):
    """Get full inspection record."""
    db = await get_db()

    cursor = await db.execute(
        """SELECT i.*, p.part_number, p.revision, p.supplier, p.material, p.description as part_desc,
                  pf.display_name as family_name
           FROM inspections i
           JOIN parts p ON i.part_id = p.id
           JOIN part_families pf ON p.family_id = pf.id
           WHERE i.id = ?""",
        (inspection_id,),
    )
    insp = await cursor.fetchone()
    if not insp:
        raise HTTPException(status_code=404, detail="Inspection not found")

    # Get images
    cursor = await db.execute(
        "SELECT * FROM images WHERE inspection_id = ?", (inspection_id,)
    )
    image_rows = await cursor.fetchall()

    # Get findings
    cursor = await db.execute(
        "SELECT * FROM findings WHERE inspection_id = ?", (inspection_id,)
    )
    finding_rows = await cursor.fetchall()

    # Get override
    cursor = await db.execute(
        "SELECT * FROM overrides WHERE inspection_id = ?", (inspection_id,)
    )
    override_row = await cursor.fetchone()

    # Get certificate
    cursor = await db.execute(
        "SELECT * FROM certificates WHERE inspection_id = ?", (inspection_id,)
    )
    cert_row = await cursor.fetchone()

    decision = json.loads(insp["decision_basis"]) if insp["decision_basis"] else None

    return {
        "id": insp["id"],
        "part_number": insp["part_number"],
        "revision": insp["revision"],
        "part_description": insp["part_desc"],
        "family_name": insp["family_name"],
        "supplier": insp["supplier"],
        "material": insp["material"],
        "status": insp["status"],
        "decision": decision,
        "images": [
            {
                "id": img["id"],
                "camera_angle": img["camera_angle"],
                "file_url": img["file_path"],
                "thumbnail_url": img["thumbnail_path"],
                "quality_result": json.loads(img["quality_result"]),
            }
            for img in image_rows
        ],
        "findings": [
            {
                "id": f["id"],
                "defect_class": f["defect_class"],
                "approach": f["approach"],
                "confidence": f["confidence"],
                "severity": f["severity"],
                "bbox": json.loads(f["bbox"]) if f["bbox"] else None,
                "heatmap_url": f["heatmap_path"],
                "mask_url": f["mask_path"],
                "description": f["description"],
                "image_id": f["image_id"],
            }
            for f in finding_rows
        ],
        "override": (
            {
                "id": override_row["id"],
                "old_decision": override_row["old_decision"],
                "new_decision": override_row["new_decision"],
                "reason_code": override_row["reason_code"],
                "comment": override_row["comment"],
                "reviewer": override_row["reviewer"],
                "created_at": override_row["created_at"],
            }
            if override_row
            else None
        ),
        "certificate_id": cert_row["id"] if cert_row else None,
        "started_at": insp["started_at"],
        "decided_at": insp["decided_at"],
    }


@router.get("/inspections")
async def list_inspections(
    status: str | None = None,
    family: str | None = None,
    decision: str | None = None,
    limit: int = 50,
):
    """List inspections with optional filters."""
    db = await get_db()
    query = """SELECT i.*, p.part_number, p.supplier, pf.display_name as family_name
               FROM inspections i
               JOIN parts p ON i.part_id = p.id
               JOIN part_families pf ON p.family_id = pf.id
               WHERE 1=1"""
    params: list = []

    if status:
        query += " AND i.status = ?"
        params.append(status)
    if decision:
        query += " AND i.decision_result = ?"
        params.append(decision)

    query += " ORDER BY i.started_at DESC LIMIT ?"
    params.append(limit)

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()

    return {
        "data": [
            {
                "id": row["id"],
                "part_number": row["part_number"],
                "family_name": row["family_name"],
                "supplier": row["supplier"],
                "status": row["status"],
                "decision": row["decision_result"],
                "started_at": row["started_at"],
                "decided_at": row["decided_at"],
            }
            for row in rows
        ],
        "total_count": len(rows),
    }
