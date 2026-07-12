"""Parts router — part master lookup."""

import json

from fastapi import APIRouter, HTTPException, UploadFile, File

from app.db.database import get_db
from app.models.part import CaptureProfile, FamilyThresholds, Part, PartFamily

router = APIRouter()

# Pre-staged OCR label mapping: filename -> part_number
# In production this would be real OCR inference; for the POC we use a lookup table.
# None means OCR extraction fails (damaged/unreadable label).
OCR_LABEL_MAP: dict[str, str | None] = {
    "label_839-041322-001.jpg": "839-041322-001",
    "label_839-041322-002.jpg": "839-041322-002",
    "label_444-027654-002.jpg": "444-027654-002",
    "label_622-073891-001.jpg": "622-073891-001",
    "label_715-098456-003.jpg": "715-098456-003",
    "label_damaged.jpg": None,  # Simulates unreadable/damaged label
    "label_unknown_part.jpg": "999-000001-001",  # Part not in system
}


@router.get("/parts/ocr/labels")
async def list_ocr_labels():
    """List available pre-staged OCR label images for the demo."""
    labels = []
    for filename, part_number in OCR_LABEL_MAP.items():
        if part_number is None:
            scenario_type = "error_unreadable"
        elif part_number == "999-000001-001":
            scenario_type = "error_not_found"
        else:
            scenario_type = "success"

        labels.append({
            "filename": filename,
            "part_number": part_number,
            "image_url": f"/static/labels/{filename}",
            "scenario_type": scenario_type,
        })
    return {"data": labels}


@router.post("/parts/ocr/identify")
async def identify_part_ocr(file: UploadFile = File(None), filename: str | None = None):
    """Identify a part via OCR (simulated).

    Accepts either:
    - An uploaded image file (simulates camera capture)
    - A filename query param (for pre-staged demo labels)

    In both cases, uses the pre-staged label lookup table to resolve the part number.
    """
    # Determine which label we're working with
    lookup_name = None

    if filename:
        lookup_name = filename
    elif file:
        lookup_name = file.filename
    else:
        raise HTTPException(status_code=400, detail="Provide a file upload or filename parameter")

    # Simulate OCR processing delay would go here in production
    # For the POC, just look up the filename in our map
    if lookup_name not in OCR_LABEL_MAP:
        # Try partial match (just the part number portion)
        part_number = None
        for key, pn in OCR_LABEL_MAP.items():
            if pn and pn in (lookup_name or ""):
                part_number = pn
                break
        if not part_number:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "OCR could not extract a valid part number from the image",
                    "extracted_text": f"[simulated scan of: {lookup_name}]",
                    "suggestion": "Ensure the label is clearly visible and try again",
                },
            )
    else:
        part_number = OCR_LABEL_MAP[lookup_name]

    # Handle unreadable/damaged label
    if part_number is None:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Label is damaged or unreadable — OCR extraction failed",
                "extracted_text": "P/N: ???-04??22-0?? [partial, low confidence]",
                "confidence": 0.12,
                "suggestion": "Label is too damaged for automated reading. Use manual entry or re-label the part.",
            },
        )

    # Verify part exists in the system
    db = await get_db()
    cursor = await db.execute("SELECT * FROM parts WHERE part_number = ?", (part_number,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"Part {part_number} not found in system",
                "extracted_part_number": part_number,
                "confidence": 0.95,
                "suggestion": "Part number was read correctly but does not exist in the parts database. Verify the part or contact engineering.",
            },
        )

    return {
        "method": "ocr",
        "extracted_part_number": part_number,
        "confidence": 0.97,  # Simulated OCR confidence
        "extracted_text": f"P/N: {part_number}  REV {row['revision']}",
        "part": {
            "id": row["id"],
            "part_number": row["part_number"],
            "revision": row["revision"],
            "description": row["description"],
            "material": row["material"],
            "supplier": row["supplier"],
        },
    }


@router.get("/parts/{part_number}", response_model=Part)
async def get_part(part_number: str):
    """Look up a part by part number."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT p.*, pf.name as family_name, pf.display_name as family_display_name,
                  pf.material as family_material, pf.surface_finish as family_surface_finish,
                  pf.thresholds, pf.capture_profile
           FROM parts p
           JOIN part_families pf ON p.family_id = pf.id
           WHERE p.part_number = ?""",
        (part_number,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Part {part_number} not found")

    thresholds = json.loads(row["thresholds"])
    capture_profile = json.loads(row["capture_profile"])

    family = PartFamily(
        id=row["family_id"],
        name=row["family_name"],
        display_name=row["family_display_name"],
        material=row["family_material"],
        surface_finish=row["family_surface_finish"],
        thresholds=FamilyThresholds(**thresholds),
        capture_profile=CaptureProfile(**capture_profile),
    )

    return Part(
        id=row["id"],
        part_number=row["part_number"],
        revision=row["revision"],
        family_id=row["family_id"],
        family=family,
        description=row["description"],
        material=row["material"],
        surface_finish=row["surface_finish"],
        supplier=row["supplier"],
    )


@router.get("/parts")
async def list_parts():
    """List all demo parts."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT p.*, pf.display_name as family_display_name
           FROM parts p
           JOIN part_families pf ON p.family_id = pf.id
           ORDER BY p.part_number"""
    )
    rows = await cursor.fetchall()
    return {
        "data": [
            {
                "id": row["id"],
                "part_number": row["part_number"],
                "revision": row["revision"],
                "description": row["description"],
                "family": row["family_display_name"],
                "supplier": row["supplier"],
                "material": row["material"],
            }
            for row in rows
        ],
        "total_count": len(rows),
    }
