"""Demo router — scenario orchestration for presentations."""

from fastapi import APIRouter

from app.db.database import get_db, init_db

router = APIRouter()

# Pre-defined demo scenarios
DEMO_SCENARIOS = [
    {
        "id": "scenario-01",
        "name": "Clean Machined Plate",
        "family": "machined-aluminum-plate",
        "part_number": "839-041322-001",
        "expected_decision": "PASS",
        "description": "A defect-free machined aluminum chamber lid plate passes all three inspection approaches.",
        "demonstrates": "Happy path: fast cycle, automatic PASS, certificate generation",
    },
    {
        "id": "scenario-02",
        "name": "Scratched Plate",
        "family": "machined-aluminum-plate",
        "part_number": "839-041322-002",
        "expected_decision": "FAIL",
        "description": "A machined plate with visible linear scratches on the surface detected by AI models.",
        "demonstrates": "AI scratch detection with XAI heatmap, FAIL routing to IQA",
    },
    {
        "id": "scenario-03",
        "name": "Dented Housing",
        "family": "anodized-housing",
        "part_number": "839-055678-001",
        "expected_decision": "FAIL",
        "description": "An anodized housing with an impact dent detected by anomaly detection and golden comparison.",
        "demonstrates": "Anomaly detection + golden sample difference heatmap",
    },
    {
        "id": "scenario-04",
        "name": "Missing Screw",
        "family": "precision-screw-assembly",
        "part_number": "715-098456-003",
        "expected_decision": "FAIL",
        "description": "An RF feed assembly with 7/8 screws present — one missing fastener detected by rule engine.",
        "demonstrates": "Rule engine (presence/absence check): expected 8, found 7",
    },
    {
        "id": "scenario-05",
        "name": "Surface Contamination",
        "family": "welded-stainless-component",
        "part_number": "622-073891-001",
        "expected_decision": "FAIL",
        "description": "A welded gas manifold with particulate contamination on the electropolished surface.",
        "demonstrates": "Segmentation mask showing contamination extent + severity classification",
    },
    {
        "id": "scenario-06",
        "name": "Unknown Anomaly",
        "family": "machined-aluminum-plate",
        "part_number": "839-041322-001",
        "expected_decision": "REVIEW",
        "description": "A subtle surface irregularity detected by anomaly detection but not matching any trained defect class.",
        "demonstrates": "Anomaly-only finding → REVIEW band (no supervised class match)",
    },
    {
        "id": "scenario-07",
        "name": "Golden Deviation (Subtle)",
        "family": "anodized-housing",
        "part_number": "839-055678-003",
        "expected_decision": "REVIEW",
        "description": "A lower chamber shield with subtle finish variation detected only by golden comparison.",
        "demonstrates": "Golden sample comparison with difference slider and tolerance bands",
    },
    {
        "id": "scenario-08",
        "name": "Multi-Defect Critical",
        "family": "pcb-sub-assembly",
        "part_number": "444-027654-002",
        "expected_decision": "FAIL",
        "description": "An ESC controller board with multiple issues: missing capacitor, solder bridge, and board contamination.",
        "demonstrates": "Multiple findings from different approaches; critical severity; compound FAIL",
    },
    {
        "id": "scenario-09",
        "name": "Low-Confidence Edge Case",
        "family": "welded-stainless-component",
        "part_number": "622-073891-001",
        "expected_decision": "REVIEW",
        "description": "A weldment with a suspected heat tint that falls in the confidence gray zone between thresholds.",
        "demonstrates": "REVIEW band — confidence near decision boundary; needs human judgment",
    },
    {
        "id": "scenario-10",
        "name": "Override Scenario",
        "family": "machined-aluminum-plate",
        "part_number": "839-041322-002",
        "expected_decision": "FAIL",
        "description": "A plate flagged for reflection artifact (not actual defect). Reviewer overrides to PASS with reason OR-02.",
        "demonstrates": "Full IQA review → override PASS with reason code + comment flow",
    },
]


@router.get("/demo/scenarios")
async def list_scenarios():
    """List all available demo scenarios."""
    return {"data": DEMO_SCENARIOS, "total_count": len(DEMO_SCENARIOS)}


@router.post("/demo/scenarios/{scenario_id}/run")
async def run_scenario(scenario_id: str):
    """Execute a demo scenario — creates an inspection and runs it through the pipeline."""
    scenario = next((s for s in DEMO_SCENARIOS if s["id"] == scenario_id), None)
    if not scenario:
        return {"error": f"Scenario {scenario_id} not found"}

    # Import here to avoid circular deps
    from app.routers.inspections import create_inspection, run_inspection, simulate_capture
    from app.models.inspection import CreateInspectionRequest

    # Create inspection
    request = CreateInspectionRequest(part_number=scenario["part_number"])
    result = await create_inspection(request)
    inspection_id = result["id"]

    # Simulate capture
    await simulate_capture(inspection_id)

    # Run inspection (AI pipeline will use scenario context)
    # Store scenario_id on the inspection for the AI pipeline to use
    db = await get_db()
    await db.execute(
        "UPDATE inspections SET scenario_id = ? WHERE id = ?",
        (scenario_id, inspection_id),
    )
    await db.commit()

    # Run the actual inspection
    inspect_result = await run_inspection(inspection_id)

    return {
        "scenario": scenario,
        "inspection_id": inspection_id,
        "result": inspect_result,
    }


@router.post("/demo/reset")
async def reset_demo():
    """Reset all inspection data (keeps parts/families)."""
    db = await get_db()
    await db.execute("DELETE FROM certificates")
    await db.execute("DELETE FROM overrides")
    await db.execute("DELETE FROM findings")
    await db.execute("DELETE FROM images")
    await db.execute("DELETE FROM inspections")
    await db.commit()
    return {"status": "reset", "message": "All inspection data cleared. Parts and families retained."}
