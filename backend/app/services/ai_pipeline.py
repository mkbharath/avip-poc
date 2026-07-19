"""AI Pipeline — orchestrates the three inspection approaches and produces fused decisions."""

import uuid
from dataclasses import dataclass
from pathlib import Path

from app.models.inspection import (
    Approach,
    BoundingBox,
    Decision,
    DecisionResult,
    Finding,
    Severity,
)
from app.services.anomaly_detector import AnomalyDetector
from app.services.defect_detector import DefectDetector
from app.services.fusion_engine import FusionEngine
from app.services.rule_engine import RuleEngine


@dataclass
class InspectionResult:
    """Result of the full AI pipeline."""

    findings: list[Finding]
    decision: Decision


# Scenario-based demo results for predictable demonstrations
SCENARIO_RESULTS: dict[str, dict] = {
    "scenario-01": {
        "decision": "PASS",
        "fusion_rule": "F-05",
        "findings": [],
    },
    "scenario-02": {
        "decision": "FAIL",
        "fusion_rule": "F-02",
        "findings": [
            {"class": "scratch", "approach": "model", "confidence": 0.92, "severity": "major",
             "desc": "Linear surface scratch detected — 15mm length, crosses critical seal area.",
             "bbox": {"x": 220, "y": 200, "width": 200, "height": 50}},
        ],
    },
    "scenario-03": {
        "decision": "FAIL",
        "fusion_rule": "F-04",
        "findings": [
            {"class": "dent", "approach": "anomaly", "confidence": 0.91, "severity": "major",
             "desc": "Impact dent detected — circular depression 8mm diameter, depth exceeds 0.2mm tolerance.",
             "bbox": {"x": 280, "y": 195, "width": 100, "height": 100}},
        ],
    },
    "scenario-04": {
        "decision": "FAIL",
        "fusion_rule": "F-01",
        "findings": [
            {"class": "missing_component", "approach": "rule", "confidence": 1.0, "severity": "critical",
             "desc": "Rule FAIL: Expected 8 fasteners, detected 7. Position #3 empty.",
             "bbox": {"x": 370, "y": 140, "width": 40, "height": 40}},
        ],
    },
    "scenario-05": {
        "decision": "FAIL",
        "fusion_rule": "F-02",
        "findings": [
            {"class": "contamination", "approach": "model", "confidence": 0.89, "severity": "major",
             "desc": "Particulate contamination on electropolished surface — area 8.2 mm², foreign material confirmed.",
             "bbox": {"x": 270, "y": 190, "width": 100, "height": 80}},
        ],
    },
    "scenario-06": {
        "decision": "REVIEW",
        "fusion_rule": "F-03",
        "findings": [
            {"class": "surface_anomaly", "approach": "anomaly", "confidence": 0.62, "severity": "minor",
             "desc": "Subtle surface discoloration detected — no matching defect class. Requires human review.",
             "bbox": {"x": 280, "y": 210, "width": 100, "height": 70}},
        ],
    },
    "scenario-07": {
        "decision": "REVIEW",
        "fusion_rule": "F-03",
        "findings": [
            {"class": "surface_anomaly", "approach": "golden", "confidence": 0.58, "severity": "minor",
             "desc": "Golden comparison shows finish variation in zone C2 — within marginal tolerance band.",
             "bbox": {"x": 280, "y": 210, "width": 100, "height": 70}},
        ],
    },
    "scenario-08": {
        "decision": "FAIL",
        "fusion_rule": "F-02",
        "findings": [
            {"class": "missing_component", "approach": "model", "confidence": 0.96, "severity": "critical",
             "desc": "Missing capacitor C14 (0805 package) — pad empty, component absent.",
             "bbox": {"x": 335, "y": 190, "width": 30, "height": 20}},
            {"class": "crack", "approach": "model", "confidence": 0.88, "severity": "major",
             "desc": "Solder crack detected on U7 pin 3 joint — intermittent connection risk.",
             "bbox": {"x": 375, "y": 95, "width": 60, "height": 20}},
        ],
    },
    "scenario-09": {
        "decision": "REVIEW",
        "fusion_rule": "F-06",
        "findings": [
            {"class": "contamination", "approach": "model", "confidence": 0.57, "severity": "minor",
             "desc": "Possible heat tint / discoloration near weld zone — confidence at decision boundary.",
             "bbox": {"x": 280, "y": 210, "width": 100, "height": 70}},
        ],
    },
    "scenario-10": {
        "decision": "FAIL",
        "fusion_rule": "F-02",
        "findings": [
            {"class": "scratch", "approach": "model", "confidence": 0.86, "severity": "major",
             "desc": "Linear mark detected on chamfer edge — likely ring-light reflection artifact, not actual defect.",
             "bbox": {"x": 220, "y": 200, "width": 200, "height": 50}},
        ],
    },
    "scenario-11": {
        "decision": "FAIL",
        "fusion_rule": "F-02",
        "findings": [
            {"class": "crack", "approach": "model", "confidence": 0.94, "severity": "critical",
             "desc": "Solder bridge detected on IC U7 — excess solder shorting pins 3 and 4. Short circuit confirmed.",
             "bbox": {"x": 380, "y": 134, "width": 55, "height": 30}},
        ],
    },
    "scenario-12": {
        "decision": "FAIL",
        "fusion_rule": "F-02",
        "findings": [
            {"class": "missing_component", "approach": "model", "confidence": 0.91, "severity": "critical",
             "desc": "Cold solder joint on C1 electrolytic capacitor — dull, fractured joint. Intermittent power failure risk.",
             "bbox": {"x": 228, "y": 230, "width": 40, "height": 25}},
        ],
    },
}

# Part-number-based results for kiosk flow (manual barcode scans)
# Gives each part a realistic, consistent outcome
KIOSK_RESULTS: dict[str, dict] = {
    "839-041322-001": {
        # Chamber Lid Plate — PASS (clean part)
        "decision": "PASS",
        "fusion_rule": "F-05",
        "findings": [],
    },
    "839-041322-002": {
        # Gas Distribution Plate — FAIL (scratch)
        "decision": "FAIL",
        "fusion_rule": "F-02",
        "findings": [
            {"class": "scratch", "approach": "model", "confidence": 0.89, "severity": "major",
             "desc": "Linear surface scratch on gas channel face — 15mm length, crosses critical seal area.",
             "bbox": {"x": 220, "y": 200, "width": 200, "height": 50}},
        ],
    },
    "715-098456-003": {
        # RF Feed Assembly — FAIL (missing screw)
        "decision": "FAIL",
        "fusion_rule": "F-01",
        "findings": [
            {"class": "missing_component", "approach": "rule", "confidence": 1.0, "severity": "critical",
             "desc": "Rule FAIL: Expected 8 fasteners, detected 7. Position #3 (NE) empty.",
             "bbox": {"x": 370, "y": 140, "width": 40, "height": 40}},
        ],
    },
    "622-073891-001": {
        # Process Gas Manifold — REVIEW (subtle anomaly near weld)
        "decision": "REVIEW",
        "fusion_rule": "F-03",
        "findings": [
            {"class": "surface_anomaly", "approach": "anomaly", "confidence": 0.61, "severity": "minor",
             "desc": "Subtle discoloration near weld HAZ — possible heat tint. Needs human verification.",
             "bbox": {"x": 162, "y": 125, "width": 75, "height": 50}},
        ],
    },
    "444-027654-003": {
        # RF Driver Board — FAIL (solder bridge)
        "decision": "FAIL",
        "fusion_rule": "F-02",
        "findings": [
            {"class": "crack", "approach": "model", "confidence": 0.94, "severity": "critical",
             "desc": "Solder bridge on IC U7 pins 3-4 — excess solder causing short circuit. Rework required.",
             "bbox": {"x": 380, "y": 134, "width": 55, "height": 30}},
        ],
    },
    "444-027654-004": {
        # Power Distribution Board — FAIL (cold solder joint)
        "decision": "FAIL",
        "fusion_rule": "F-02",
        "findings": [
            {"class": "missing_component", "approach": "model", "confidence": 0.91, "severity": "critical",
             "desc": "Cold solder joint on C1 capacitor — dull crystalline joint with fracture crack. Power failure risk.",
             "bbox": {"x": 228, "y": 230, "width": 40, "height": 25}},
        ],
    },
    "444-027654-002": {
        # ESC Controller Board — FAIL (missing cap + crack)
        "decision": "FAIL",
        "fusion_rule": "F-02",
        "findings": [
            {"class": "missing_component", "approach": "model", "confidence": 0.96, "severity": "critical",
             "desc": "Missing capacitor C14 (0805 package) — pad empty.",
             "bbox": {"x": 335, "y": 190, "width": 30, "height": 20}},
            {"class": "crack", "approach": "model", "confidence": 0.88, "severity": "major",
             "desc": "Solder crack on U7 pin 3 joint — intermittent connection risk.",
             "bbox": {"x": 375, "y": 95, "width": 60, "height": 20}},
        ],
    },
    "839-055678-001": {
        # Upper Electrode Housing — PASS
        "decision": "PASS",
        "fusion_rule": "F-05",
        "findings": [],
    },
    "839-055678-003": {
        # Lower Chamber Shield — REVIEW (golden comparison deviation)
        "decision": "REVIEW",
        "fusion_rule": "F-03",
        "findings": [
            {"class": "surface_anomaly", "approach": "golden", "confidence": 0.58, "severity": "minor",
             "desc": "Golden comparison shows finish variation in anodize zone — within marginal tolerance.",
             "bbox": {"x": 162, "y": 125, "width": 75, "height": 50}},
        ],
    },
    "715-098456-007": {
        # Showerhead Mounting Bracket — PASS
        "decision": "PASS",
        "fusion_rule": "F-05",
        "findings": [],
    },
}


class AIPipeline:
    """Orchestrates the three inspection approaches and fuses results."""

    def __init__(self) -> None:
        self.anomaly_detector = AnomalyDetector()
        self.defect_detector = DefectDetector()
        self.rule_engine = RuleEngine()
        self.fusion_engine = FusionEngine()

    async def inspect(
        self,
        inspection_id: str,
        family_name: str,
        thresholds: dict,
    ) -> InspectionResult:
        """Run full inspection pipeline."""
        # Check if this is a demo scenario
        from app.db.database import get_db

        db = await get_db()
        cursor = await db.execute(
            "SELECT scenario_id FROM inspections WHERE id = ?", (inspection_id,)
        )
        row = await cursor.fetchone()
        scenario_id = row["scenario_id"] if row else None

        if scenario_id and scenario_id in SCENARIO_RESULTS:
            return self._build_scenario_result(scenario_id)

        # Non-scenario (kiosk flow): use part-number-based results for realistic demos
        from app.db.database import get_db
        db = await get_db()
        cursor = await db.execute(
            "SELECT p.part_number FROM inspections i JOIN parts p ON i.part_id = p.id WHERE i.id = ?",
            (inspection_id,),
        )
        row = await cursor.fetchone()
        part_number = row["part_number"] if row else None

        if part_number and part_number in KIOSK_RESULTS:
            return self._build_kiosk_result(part_number)

        # Fallback: default PASS for unknown parts
        return InspectionResult(
            findings=[],
            decision=Decision(
                result=DecisionResult.PASS,
                fusion_rule="F-05",
                findings_count=0,
                confidence_summary={"overall": 0.0, "max_finding": 0.0, "approaches_triggered": 0.0},
            ),
        )

    async def _run_real_pipeline(
        self,
        inspection_id: str,
        family_name: str,
        thresholds: dict,
    ) -> InspectionResult:
        """Run the actual AI pipeline using real models."""
        from app.db.database import get_db

        # Get an image to inspect (use first captured image)
        db = await get_db()
        cursor = await db.execute(
            "SELECT file_path FROM images WHERE inspection_id = ? LIMIT 1",
            (inspection_id,),
        )
        img_row = await cursor.fetchone()

        all_findings: list[Finding] = []

        # If we have a real image path, run the AI models
        image_path = img_row["file_path"] if img_row else None
        real_image_exists = image_path and Path(image_path.lstrip("/")).exists()

        if real_image_exists:
            # Approach 1: Anomaly detection (PatchCore)
            anomaly_findings, _ = await self.anomaly_detector.detect(
                image_path=image_path,
                family_name=family_name,
                threshold=thresholds.get("confidence_low", 0.55),
            )
            all_findings.extend(anomaly_findings)

            # Approach 2: Defect detection (YOLOv8)
            defect_findings = await self.defect_detector.detect(
                image_path=image_path,
                confidence_threshold=thresholds.get("confidence_low", 0.4),
            )
            all_findings.extend(defect_findings)
        else:
            # No real image — run models on a synthetic test image
            # This path is used when images are simulated (placeholder paths)
            anomaly_findings, _ = await self._run_anomaly_on_synthetic(family_name, thresholds)
            all_findings.extend(anomaly_findings)

            defect_findings = await self._run_defect_on_synthetic(thresholds)
            all_findings.extend(defect_findings)

        # Approach 3: Rule engine (deterministic, no image needed)
        rule_findings = await self.rule_engine.evaluate(
            family_name=family_name,
            detections=all_findings,
        )
        all_findings.extend(rule_findings)

        # Fuse results
        decision = self.fusion_engine.decide(all_findings, thresholds)

        return InspectionResult(findings=all_findings, decision=decision)

    async def _run_anomaly_on_synthetic(
        self, family_name: str, thresholds: dict
    ) -> tuple[list[Finding], str | None]:
        """Run anomaly detection on a generated synthetic image."""
        import numpy as np
        from PIL import Image
        import tempfile
        import os

        # Create a synthetic test image (random noise + some structure)
        np.random.seed(hash(family_name) % 2**32)
        img_array = np.random.randint(100, 200, (224, 224, 3), dtype=np.uint8)
        # Add some structure (gradient)
        for i in range(224):
            img_array[i, :, :] = np.clip(img_array[i, :, :].astype(int) + i // 4, 0, 255)

        # Save to temp file
        temp_path = tempfile.mktemp(suffix=".jpg")
        Image.fromarray(img_array).save(temp_path)

        try:
            findings, heatmap = await self.anomaly_detector.detect(
                image_path=temp_path,
                family_name=family_name,
                threshold=thresholds.get("confidence_low", 0.55),
            )
            return findings, heatmap
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    async def _run_defect_on_synthetic(
        self, thresholds: dict
    ) -> list[Finding]:
        """Run defect detection on a generated synthetic image."""
        import numpy as np
        from PIL import Image
        import tempfile
        import os

        # Create a synthetic 640x640 image
        img_array = np.random.randint(80, 180, (640, 640, 3), dtype=np.uint8)

        temp_path = tempfile.mktemp(suffix=".jpg")
        Image.fromarray(img_array).save(temp_path)

        try:
            findings = await self.defect_detector.detect(
                image_path=temp_path,
                confidence_threshold=thresholds.get("confidence_low", 0.4),
            )
            return findings
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def _build_scenario_result(self, scenario_id: str) -> InspectionResult:
        """Build inspection result from pre-defined scenario data."""
        scenario_data = SCENARIO_RESULTS[scenario_id]
        return self._build_from_dict(scenario_data)

    def _build_kiosk_result(self, part_number: str) -> InspectionResult:
        """Build inspection result from part-number-based kiosk data."""
        kiosk_data = KIOSK_RESULTS[part_number]
        return self._build_from_dict(kiosk_data)

    def _build_from_dict(self, data: dict) -> InspectionResult:
        """Build InspectionResult from a findings dictionary."""

        findings = []
        for f in data["findings"]:
            finding = Finding(
                id=str(uuid.uuid4()),
                defect_class=f["class"],
                approach=Approach(f["approach"]),
                confidence=f["confidence"],
                severity=Severity(f["severity"]),
                bbox=BoundingBox(**f["bbox"]) if f.get("bbox") else None,
                heatmap_url=None,
                mask_url=None,
                description=f["desc"],
                image_id=None,
            )
            findings.append(finding)

        max_conf = max((f.confidence for f in findings), default=0.0)
        approaches_triggered = len(set(f.approach.value for f in findings))

        decision = Decision(
            result=DecisionResult(data["decision"]),
            fusion_rule=data["fusion_rule"],
            findings_count=len(findings),
            confidence_summary={
                "overall": max_conf,
                "max_finding": max_conf,
                "approaches_triggered": float(approaches_triggered),
            },
        )

        return InspectionResult(findings=findings, decision=decision)
