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
        "name": "Material Porosity",
        "family": "machined-aluminum-plate",
        "part_number": "839-041322-003",
        "expected_decision": "FAIL",
        "description": "Chamber lid plate with subsurface porosity exposed after machining — voids visible as dark pits on the sealing surface.",
        "demonstrates": "Porosity detection on machined aluminum — critical for vacuum seal integrity",
    },
    {
        "id": "scenario-14",
        "name": "Tool Marks",
        "family": "machined-aluminum-plate",
        "part_number": "839-041322-004",
        "expected_decision": "FAIL",
        "description": "Gas inlet manifold with visible machining lines and tool marks exceeding Ra surface finish tolerance.",
        "demonstrates": "Surface finish quality check — tool path pattern detection",
    },
    {
        "id": "scenario-15",
        "name": "Coating Stain",
        "family": "anodized-housing",
        "part_number": "839-055678-004",
        "expected_decision": "FAIL",
        "description": "Anodized lower shield with visible stain marks on the coated surface — contamination during anodizing process.",
        "demonstrates": "Surface contamination on coated parts — process quality issue",
    },
    {
        "id": "scenario-16",
        "name": "Label Mismatch",
        "family": "anodized-housing",
        "part_number": "839-055678-005",
        "expected_decision": "FAIL",
        "description": "Upper chamber ring where the serial number on the part engraving does not match the attached shipping label.",
        "demonstrates": "OCR cross-validation — engraving vs label serial number comparison",
    },
    {
        "id": "scenario-17",
        "name": "Machining Burr",
        "family": "precision-screw-assembly",
        "part_number": "715-098456-008",
        "expected_decision": "FAIL",
        "description": "Showerhead retainer screw with visible machining burr on the thread edge — potential particle generation risk.",
        "demonstrates": "Edge defect detection — burr identification on fastener threads",
    },
    {
        "id": "scenario-18",
        "name": "Paint Peel-Off",
        "family": "anodized-housing",
        "part_number": "839-055678-006",
        "expected_decision": "FAIL",
        "description": "Electrode housing with paint/coating peeling off near a mounting hole — adhesion failure exposing bare substrate.",
        "demonstrates": "Coating integrity check — delamination and peel detection",
    },
    # ── Scenarios 19-31: All images from client PDF (Lam defect catalog) ─────
    {
        "id": "scenario-19",
        "name": "Material Porosity — Curved Channel",
        "family": "machined-aluminum-plate",
        "part_number": "839-041322-005",
        "expected_decision": "FAIL",
        "description": "Chamber lid ring with porosity exposure on curved machined channel — voids along sealing groove.",
        "demonstrates": "Porosity detection on curved surfaces — vacuum seal risk",
    },
    {
        "id": "scenario-20",
        "name": "Dent & Scratch Marks",
        "family": "machined-aluminum-plate",
        "part_number": "839-041322-006",
        "expected_decision": "FAIL",
        "description": "Machined plate with impact dent and linear scratch marks — surface finish and flatness compromised.",
        "demonstrates": "Combined dent + scratch detection on machined surface",
    },
    {
        "id": "scenario-21",
        "name": "Machining Lines — Cylindrical Surface",
        "family": "machined-aluminum-plate",
        "part_number": "839-041322-007",
        "expected_decision": "FAIL",
        "description": "Cylinder bore with parallel machining lines visible on surface — Ra surface finish exceeds specification.",
        "demonstrates": "Tool marks on cylindrical bore — surface finish failure",
    },
    {
        "id": "scenario-22",
        "name": "Scratch Marks — Chamfer Edge",
        "family": "machined-aluminum-plate",
        "part_number": "839-041322-008",
        "expected_decision": "FAIL",
        "description": "Machined ring with diagonal scratch marks on chamfer — linear damage crossing precision-ground surface.",
        "demonstrates": "Scratch detection on angled/chamfered edges",
    },
    {
        "id": "scenario-23",
        "name": "Machining Burr — Threaded Hole",
        "family": "machined-aluminum-plate",
        "part_number": "715-098456-009",
        "expected_decision": "FAIL",
        "description": "Machined block with burr at threaded hole entry — raised material around bore edge, particle risk.",
        "demonstrates": "Burr detection at hole entry — cleanroom contamination risk",
    },
    {
        "id": "scenario-24",
        "name": "Serial Number Engraving Mismatch",
        "family": "anodized-housing",
        "part_number": "839-055678-007",
        "expected_decision": "FAIL",
        "description": "Part engraving reads S/N 16-435080-00 REV D but label shows different revision — traceability failure.",
        "demonstrates": "Engraving vs label cross-validation — revision mismatch",
    },
    {
        "id": "scenario-25",
        "name": "Scratch Marks — Showerhead Plate",
        "family": "anodized-housing",
        "part_number": "839-055678-008",
        "expected_decision": "FAIL",
        "description": "Showerhead plate with visible scratch marks on perforated anodized surface.",
        "demonstrates": "Scratch detection on perforated anodized plates",
    },
    {
        "id": "scenario-26",
        "name": "Dent — Showerhead Plate",
        "family": "anodized-housing",
        "part_number": "839-055678-009",
        "expected_decision": "FAIL",
        "description": "Showerhead plate with impact dent on perforated surface near hole pattern.",
        "demonstrates": "Dent detection on perforated anodized surface",
    },
    {
        "id": "scenario-27",
        "name": "Line Marks & Stains — Coated Bowl",
        "family": "anodized-housing",
        "part_number": "839-055678-010",
        "expected_decision": "FAIL",
        "description": "Anodized interior bowl with multiple stain marks and line marks — process contamination during coating.",
        "demonstrates": "Multi-region stain detection on dark anodized surfaces",
    },
    {
        "id": "scenario-28",
        "name": "Stains — Perforated Plate",
        "family": "anodized-housing",
        "part_number": "839-055678-011",
        "expected_decision": "FAIL",
        "description": "Anodized perforated plate with staining — discolored region indicating contamination or uneven anodizing.",
        "demonstrates": "Coating stain on perforated plate — subtle discoloration detection",
    },
    {
        "id": "scenario-29",
        "name": "Color Variation — Coated Parts",
        "family": "anodized-housing",
        "part_number": "839-055678-012",
        "expected_decision": "FAIL",
        "description": "Anodized housing with visible color variation — uneven coating thickness causing shade inconsistency.",
        "demonstrates": "Color uniformity check — anodizing shade variation",
    },
    {
        "id": "scenario-30",
        "name": "Poor Coating Finish",
        "family": "anodized-housing",
        "part_number": "715-098456-010",
        "expected_decision": "FAIL",
        "description": "Housing with poor anodized coating finish — streaks and uneven surface appearance fail cosmetic standard.",
        "demonstrates": "Coating finish quality — streak and texture anomaly detection",
    },
    {
        "id": "scenario-31",
        "name": "Burr — Fastener Head",
        "family": "precision-screw-assembly",
        "part_number": "715-098456-011",
        "expected_decision": "FAIL",
        "description": "Fastener with visible burr on head edge — sharp raised material from machining, particle contamination risk.",
        "demonstrates": "Burr detection on fastener heads — COTS part inspection",
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
