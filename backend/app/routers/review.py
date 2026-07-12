"""Review router — IQA review queue and overrides."""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.db.database import get_db
from app.models.inspection import InspectionStatus, OverrideRequest

router = APIRouter()


@router.get("/review/queue")
async def get_review_queue():
    """Get prioritized IQA review queue."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT i.id, i.started_at, i.decision_result, p.part_number, p.supplier,
                  pf.display_name as family_name
           FROM inspections i
           JOIN parts p ON i.part_id = p.id
           JOIN part_families pf ON p.family_id = pf.id
           WHERE i.status IN ('in_review', 'failed')
           ORDER BY i.started_at ASC"""
    )
    rows = await cursor.fetchall()

    queue = []
    for row in rows:
        # Get defect classes for this inspection
        fc = await db.execute(
            "SELECT DISTINCT defect_class FROM findings WHERE inspection_id = ?",
            (row["id"],),
        )
        defect_rows = await fc.fetchall()
        defect_classes = [d["defect_class"] for d in defect_rows]

        # Get max confidence
        cc = await db.execute(
            "SELECT MAX(confidence) as max_conf FROM findings WHERE inspection_id = ?",
            (row["id"],),
        )
        conf_row = await cc.fetchone()
        max_conf = conf_row["max_conf"] if conf_row and conf_row["max_conf"] else 0

        # Calculate age
        started = datetime.fromisoformat(row["started_at"])
        age_seconds = int((datetime.now(timezone.utc) - started).total_seconds())

        # Simple priority: older items + higher confidence = higher priority
        priority = min(100, age_seconds // 60 + int(max_conf * 50))

        confidence_band = "high" if max_conf >= 0.8 else "medium" if max_conf >= 0.5 else "low"

        queue.append({
            "id": row["id"],
            "part_number": row["part_number"],
            "family_name": row["family_name"],
            "supplier": row["supplier"],
            "decision": row["decision_result"],
            "defect_classes": defect_classes,
            "confidence_band": confidence_band,
            "age_seconds": age_seconds,
            "priority": priority,
            "started_at": row["started_at"],
        })

    # Sort by priority descending
    queue.sort(key=lambda x: x["priority"], reverse=True)

    return {"data": queue, "total_count": len(queue)}


@router.post("/review/{inspection_id}/override")
async def override_decision(inspection_id: str, request: OverrideRequest):
    """Override an AI decision."""
    db = await get_db()

    # Get current inspection
    cursor = await db.execute(
        "SELECT * FROM inspections WHERE id = ?", (inspection_id,)
    )
    insp = await cursor.fetchone()
    if not insp:
        raise HTTPException(status_code=404, detail="Inspection not found")

    if insp["status"] not in ("in_review", "failed"):
        raise HTTPException(status_code=409, detail="Inspection is not in review state")

    # Create override record
    override_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    await db.execute(
        """INSERT INTO overrides (id, inspection_id, old_decision, new_decision,
                                  reason_code, comment, reviewer, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            override_id,
            inspection_id,
            insp["decision_result"],
            request.new_decision,
            request.reason_code,
            request.comment,
            request.reviewer,
            now,
        ),
    )

    # Update inspection status
    new_status = (
        InspectionStatus.OVERRIDDEN.value
        if request.new_decision == "PASS"
        else InspectionStatus.FAILED.value
    )
    await db.execute(
        "UPDATE inspections SET status = ?, decision_result = ? WHERE id = ?",
        (new_status, request.new_decision, inspection_id),
    )
    await db.commit()

    return {
        "id": override_id,
        "inspection_id": inspection_id,
        "old_decision": insp["decision_result"],
        "new_decision": request.new_decision,
        "reason_code": request.reason_code,
        "reviewer": request.reviewer,
        "new_status": new_status,
    }


@router.post("/review/{inspection_id}/confirm")
async def confirm_decision(inspection_id: str):
    """Confirm AI FAIL decision."""
    db = await get_db()

    cursor = await db.execute(
        "SELECT * FROM inspections WHERE id = ?", (inspection_id,)
    )
    insp = await cursor.fetchone()
    if not insp:
        raise HTTPException(status_code=404, detail="Inspection not found")

    await db.execute(
        "UPDATE inspections SET status = ? WHERE id = ?",
        (InspectionStatus.FAILED.value, inspection_id),
    )
    await db.commit()

    return {"inspection_id": inspection_id, "status": "failed", "confirmed": True}
