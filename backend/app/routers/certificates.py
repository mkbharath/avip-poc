"""Certificates router — PDF generation and verification."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings
from app.db.database import get_db
from app.services.certificate_gen import generate_certificate_pdf

router = APIRouter()


@router.get("/certificates/{certificate_id}")
async def get_certificate(certificate_id: str):
    """Get certificate metadata."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM certificates WHERE id = ?", (certificate_id,)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Certificate not found")

    return {
        "id": row["id"],
        "inspection_id": row["inspection_id"],
        "token": row["token"],
        "pdf_url": f"/api/v1/certificates/{row['id']}/pdf",
        "created_at": row["created_at"],
    }


@router.get("/certificates/{certificate_id}/pdf")
async def get_certificate_pdf(certificate_id: str):
    """Download certificate PDF."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM certificates WHERE id = ?", (certificate_id,)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Certificate not found")

    pdf_path = settings.certificates_dir / f"{certificate_id}.pdf"
    if not pdf_path.exists():
        # Generate on-demand if not yet created
        await _generate_cert(db, certificate_id, row["inspection_id"])

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"AVIP-Certificate-{certificate_id[:8]}.pdf",
    )


@router.get("/certificates/verify/{token}")
async def verify_certificate(token: str):
    """Public certificate verification endpoint (QR code target)."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT c.*, i.decision_result, i.decided_at, p.part_number
           FROM certificates c
           JOIN inspections i ON c.inspection_id = i.id
           JOIN parts p ON i.part_id = p.id
           WHERE c.token = ?""",
        (token,),
    )
    row = await cursor.fetchone()
    if not row:
        return {"valid": False, "part_number": None, "decision": None, "decided_at": None}

    return {
        "valid": True,
        "part_number": row["part_number"],
        "decision": row["decision_result"],
        "decided_at": row["decided_at"],
    }


async def create_certificate_for_inspection(inspection_id: str) -> str:
    """Create a certificate for a passed/overridden inspection."""
    db = await get_db()

    # Check if certificate already exists
    cursor = await db.execute(
        "SELECT id FROM certificates WHERE inspection_id = ?", (inspection_id,)
    )
    existing = await cursor.fetchone()
    if existing:
        return existing["id"]

    cert_id = str(uuid.uuid4())
    token = uuid.uuid4().hex[:16]
    now = datetime.now(timezone.utc).isoformat()

    await db.execute(
        """INSERT INTO certificates (id, inspection_id, token, pdf_path, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (cert_id, inspection_id, token, f"certificates/{cert_id}.pdf", now),
    )
    await db.commit()

    # Generate PDF
    await _generate_cert(db, cert_id, inspection_id)

    return cert_id


async def _generate_cert(db, cert_id: str, inspection_id: str):
    """Generate the actual PDF file."""
    import json

    cursor = await db.execute(
        """SELECT i.*, p.part_number, p.revision, p.description, p.supplier,
                  pf.display_name as family_name, c.token
           FROM inspections i
           JOIN parts p ON i.part_id = p.id
           JOIN part_families pf ON p.family_id = pf.id
           JOIN certificates c ON c.inspection_id = i.id
           WHERE i.id = ?""",
        (inspection_id,),
    )
    insp = await cursor.fetchone()
    if not insp:
        return

    # Get findings
    cursor = await db.execute(
        "SELECT * FROM findings WHERE inspection_id = ?", (inspection_id,)
    )
    findings = await cursor.fetchall()

    pdf_path = settings.certificates_dir / f"{cert_id}.pdf"
    generate_certificate_pdf(
        output_path=str(pdf_path),
        cert_id=cert_id,
        token=insp["token"],
        part_number=insp["part_number"],
        revision=insp["revision"],
        description=insp["description"],
        family=insp["family_name"],
        supplier=insp["supplier"],
        decision=insp["decision_result"],
        decided_at=insp["decided_at"],
        findings_count=len(findings),
    )
