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
    {
        "id": "scenario-11",
        "name": "Solder Bridge — RF Driver Board",
        "family": "pcb-sub-assembly",
        "part_number": "444-027654-003",
        "expected_decision": "FAIL",
        "description": "RF Driver Board with excess solder bridging IC U7 pins 3 and 4 — confirmed short circuit detected by AI.",
        "demonstrates": "PCB solder bridge detection, FAIL routing for rework",
    },
    {
        "id": "scenario-12",
        "name": "Cold Solder Joint — Power Board",
        "family": "pcb-sub-assembly",
        "part_number": "444-027654-004",
        "expected_decision": "FAIL",
        "description": "Power Distribution Board with a cold (crystalline, fractured) solder joint on C1 electrolytic capacitor.",
        "demonstrates": "Cold joint detection via visual anomaly — intermittent failure risk",
    },
    {
        "id": "scenario-13",
        "name": "Material Porosity — p1 Sample 3",
        "family": "machined-aluminum-plate",
        "part_number": "839-041322-003",
        "expected_decision": "FAIL",
        "description": "Material porosity exposure after machining — dark voids/pits visible on the machined sealing surface.",
        "demonstrates": "Material Porosity detection — Lam cosmetic defect sample (PDF p1)",
    },
    {
        "id": "scenario-14",
        "name": "Machining Lines / Tool Marks — p1 Sample 9",
        "family": "machined-aluminum-plate",
        "part_number": "839-041322-004",
        "expected_decision": "FAIL",
        "description": "Machining lines and tool marks on the corner piece — parallel grooves exceeding surface finish Ra tolerance.",
        "demonstrates": "Machining Lines / Tool Marks detection — Lam cosmetic defect sample (PDF p1)",
    },
    {
        "id": "scenario-15",
        "name": "Coating Stain — p4 Sample 4",
        "family": "anodized-housing",
        "part_number": "839-055678-004",
        "expected_decision": "FAIL",
        "description": "Coating stain on anodized surface — contamination stain visible on the perforated plate surface.",
        "demonstrates": "Coating Stain detection — Lam cosmetic defect sample (PDF p4)",
    },
    {
        "id": "scenario-16",
        "name": "Label / S/N Mismatch — p2 Sample 5",
        "family": "anodized-housing",
        "part_number": "839-055678-005",
        "expected_decision": "FAIL",
        "description": "The serial number on the label does not match the part engraving.",
        "demonstrates": "Label / S/N Mismatch detection — Lam cosmetic defect sample (PDF p2)",
    },
    {
        "id": "scenario-17",
        "name": "Machining Burr — p6 Sample 3",
        "family": "precision-screw-assembly",
        "part_number": "715-098456-008",
        "expected_decision": "FAIL",
        "description": "Raised material is visible on the edge of the component, indicating a burr defect.",
        "demonstrates": "Machining Burr detection — Lam cosmetic defect sample (PDF p6)",
    },
    {
        "id": "scenario-18",
        "name": "Paint Peel-Off — p3 Sample 4",
        "family": "welded-stainless-component",
        "part_number": "839-055678-006",
        "expected_decision": "FAIL",
        "description": "Paint peel-off near mounting hole — small area of coating delamination exposing bare substrate.",
        "demonstrates": "Paint Peel-Off detection — Lam cosmetic defect sample (PDF p3)",
    },
    {
        "id": "scenario-19",
        "name": "Material Porosity — p1 Sample 2",
        "family": "machined-aluminum-plate",
        "part_number": "839-041322-019",
        "expected_decision": "FAIL",
        "description": "Material porosity exposure on machined channel — curved surface with visible voids after machining.",
        "demonstrates": "Material Porosity detection — Lam cosmetic defect sample (PDF p1)",
    },
    {
        "id": "scenario-20",
        "name": "Dent / Impact Damage — p1 Sample 4",
        "family": "machined-aluminum-plate",
        "part_number": "839-041322-020",
        "expected_decision": "FAIL",
        "description": "Impact dent and scratch marks on dark machined surface — circular depression with linear scratch damage.",
        "demonstrates": "Dent / Impact Damage detection — Lam cosmetic defect sample (PDF p1)",
    },
    {
        "id": "scenario-21",
        "name": "Machining Lines / Tool Marks — p1 Sample 5",
        "family": "machined-aluminum-plate",
        "part_number": "839-041322-021",
        "expected_decision": "FAIL",
        "description": "Machining lines on cylindrical bore surface — parallel lines from turning tool exceeding Ra specification.",
        "demonstrates": "Machining Lines / Tool Marks detection — Lam cosmetic defect sample (PDF p1)",
    },
    {
        "id": "scenario-22",
        "name": "Scratch Marks — p1 Sample 6",
        "family": "machined-aluminum-plate",
        "part_number": "839-041322-022",
        "expected_decision": "FAIL",
        "description": "Scratch marks on machined chamfer edge — diagonal linear damage crossing the precision-ground surface.",
        "demonstrates": "Scratch Marks detection — Lam cosmetic defect sample (PDF p1)",
    },
    {
        "id": "scenario-23",
        "name": "Scratch Marks — p1 Sample 7",
        "family": "machined-aluminum-plate",
        "part_number": "839-041322-023",
        "expected_decision": "FAIL",
        "description": "Scratch marks on narrow machined channel — linear damage visible along the machined groove.",
        "demonstrates": "Scratch Marks detection — Lam cosmetic defect sample (PDF p1)",
    },
    {
        "id": "scenario-24",
        "name": "Machining Burr — p1 Sample 8",
        "family": "precision-screw-assembly",
        "part_number": "715-098456-009",
        "expected_decision": "FAIL",
        "description": "Machining burr at threaded hole — raised material around the screw hole bore edge from machining.",
        "demonstrates": "Machining Burr detection — Lam cosmetic defect sample (PDF p1)",
    },
    {
        "id": "scenario-25",
        "name": "Label / S/N Mismatch — p2 Sample 3",
        "family": "anodized-housing",
        "part_number": "839-055678-013",
        "expected_decision": "FAIL",
        "description": "Serial number mismatch on label — part label shows incorrect S/N vs part engraving. Traceability failure.",
        "demonstrates": "Label / S/N Mismatch detection — Lam cosmetic defect sample (PDF p2)",
    },
    {
        "id": "scenario-26",
        "name": "Label / S/N Mismatch — p2 Sample 7",
        "family": "anodized-housing",
        "part_number": "839-055678-014",
        "expected_decision": "FAIL",
        "description": "Label serial number mismatch — packaging label S/N does not match part S/N. Traceability failure.",
        "demonstrates": "Label / S/N Mismatch detection — Lam cosmetic defect sample (PDF p2)",
    },
    {
        "id": "scenario-27",
        "name": "Scratch Marks — p3 Sample 2",
        "family": "machined-aluminum-plate",
        "part_number": "839-041322-024",
        "expected_decision": "FAIL",
        "description": "Scratch mark on anodized showerhead plate — linear defect visible on left perforated panel.",
        "demonstrates": "Scratch Marks detection — Lam cosmetic defect sample (PDF p3)",
    },
    {
        "id": "scenario-28",
        "name": "Dent / Impact Damage — p3 Sample 3",
        "family": "machined-aluminum-plate",
        "part_number": "839-041322-025",
        "expected_decision": "FAIL",
        "description": "Dent on anodized showerhead plate — circular depression visible on perforated surface.",
        "demonstrates": "Dent / Impact Damage detection — Lam cosmetic defect sample (PDF p3)",
    },
    {
        "id": "scenario-29",
        "name": "Coating Stain — p4 Sample 5",
        "family": "anodized-housing",
        "part_number": "839-055678-015",
        "expected_decision": "FAIL",
        "description": "Coating stain on anodized perforated plate — discolored region indicating uneven anodizing or contamination.",
        "demonstrates": "Coating Stain detection — Lam cosmetic defect sample (PDF p4)",
    },
    {
        "id": "scenario-30",
        "name": "Color Variation — p5 Sample 2",
        "family": "anodized-housing",
        "part_number": "839-055678-016",
        "expected_decision": "FAIL",
        "description": "Color variation on anodized housing — visible shade inconsistency from uneven coating thickness.",
        "demonstrates": "Color Variation detection — Lam cosmetic defect sample (PDF p5)",
    },
    {
        "id": "scenario-31",
        "name": "Machining Burr — p6 Sample 2",
        "family": "precision-screw-assembly",
        "part_number": "715-098456-010",
        "expected_decision": "FAIL",
        "description": "Machining burr on shaft fitting — raised metal curl visible at collar junction, particle contamination risk.",
        "demonstrates": "Machining Burr detection — Lam cosmetic defect sample (PDF p6)",
    },
    {
        "id": "scenario-32",
        "name": "Machining Burr — p6 Sample 4",
        "family": "precision-screw-assembly",
        "part_number": "715-098456-011",
        "expected_decision": "FAIL",
        "description": "Burr on fastener head — sharp raised material at right edge of screw head from machining.",
        "demonstrates": "Machining Burr detection — Lam cosmetic defect sample (PDF p6)",
    },
    {
        "id": "scenario-33",
        "name": "Coating Stain — p4 Sample 2",
        "family": "anodized-housing",
        "part_number": "839-055678-017",
        "expected_decision": "FAIL",
        "description": "Line marks and stains on anodized coated bowl interior — multiple contamination marks from coating process.",
        "demonstrates": "Coating Stain detection — Lam cosmetic defect sample (PDF p4)",
    },
    {
        "id": "scenario-34",
        "name": "Coating Stain — p4 Sample 3",
        "family": "anodized-housing",
        "part_number": "839-055678-018",
        "expected_decision": "FAIL",
        "description": "Stains on anodized coated interior surface — discoloration and streak marks from contamination.",
        "demonstrates": "Coating Stain detection — Lam cosmetic defect sample (PDF p4)",
    },
    {
        "id": "scenario-35",
        "name": "Poor Coating Finish — p5 Sample 3",
        "family": "anodized-housing",
        "part_number": "715-098456-012",
        "expected_decision": "FAIL",
        "description": "Poor anodized coating finish — comparison shows streaks and uneven surface appearance on left side vs good finish on right.",
        "demonstrates": "Poor Coating Finish detection — Lam cosmetic defect sample (PDF p5)",
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
    # Store scenario_id on the inspection BEFORE capture so it picks the right image variant
    db = await get_db()
    await db.execute(
        "UPDATE inspections SET scenario_id = ? WHERE id = ?",
        (scenario_id, inspection_id),
    )
    await db.commit()

    await simulate_capture(inspection_id)

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
