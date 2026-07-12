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
             "desc": "Linear scratch detected on surface (12mm length, 0.3mm depth est.)",
             "bbox": {"x": 120, "y": 85, "width": 180, "height": 25}},
            {"class": "scratch", "approach": "anomaly", "confidence": 0.88, "severity": "major",
             "desc": "Anomaly region correlating with surface discontinuity",
             "bbox": {"x": 115, "y": 80, "width": 190, "height": 35}},
        ],
    },
    "scenario-03": {
        "decision": "FAIL",
        "fusion_rule": "F-04",
        "findings": [
            {"class": "dent", "approach": "anomaly", "confidence": 0.87, "severity": "major",
             "desc": "Surface depression detected by anomaly model (impact dent)",
             "bbox": {"x": 200, "y": 150, "width": 60, "height": 55}},
            {"class": "dent", "approach": "golden", "confidence": 0.91, "severity": "major",
             "desc": "Golden comparison deviation exceeds tolerance in zone B3",
             "bbox": {"x": 195, "y": 145, "width": 70, "height": 65}},
        ],
    },
    "scenario-04": {
        "decision": "FAIL",
        "fusion_rule": "F-01",
        "findings": [
            {"class": "missing_component", "approach": "rule", "confidence": 1.0, "severity": "critical",
             "desc": "Rule FAIL: Expected 8 fasteners, detected 7. Position #5 (NW) missing.",
             "bbox": {"x": 80, "y": 60, "width": 40, "height": 40}},
            {"class": "missing_component", "approach": "model", "confidence": 0.95, "severity": "critical",
             "desc": "Object detection confirms absent fastener at grid position NW-5",
             "bbox": {"x": 75, "y": 55, "width": 50, "height": 50}},
        ],
    },
    "scenario-05": {
        "decision": "FAIL",
        "fusion_rule": "F-02",
        "findings": [
            {"class": "contamination", "approach": "model", "confidence": 0.89, "severity": "major",
             "desc": "Particulate contamination detected on electropolished surface (area: 8.2 mm²)",
             "bbox": {"x": 150, "y": 200, "width": 90, "height": 70}},
            {"class": "contamination", "approach": "anomaly", "confidence": 0.84, "severity": "major",
             "desc": "Anomaly detection confirms foreign material presence",
             "bbox": {"x": 145, "y": 195, "width": 100, "height": 80}},
        ],
    },
    "scenario-06": {
        "decision": "REVIEW",
        "fusion_rule": "F-03",
        "findings": [
            {"class": "surface_anomaly", "approach": "anomaly", "confidence": 0.62, "severity": "minor",
             "desc": "Unknown surface irregularity detected — no matching supervised class. Requires human review.",
             "bbox": {"x": 180, "y": 120, "width": 45, "height": 30}},
        ],
    },
    "scenario-07": {
        "decision": "REVIEW",
        "fusion_rule": "F-03",
        "findings": [
            {"class": "surface_anomaly", "approach": "golden", "confidence": 0.58, "severity": "minor",
             "desc": "Golden comparison shows subtle finish variation in zone C2 — within marginal tolerance band.",
             "bbox": {"x": 100, "y": 180, "width": 120, "height": 80}},
        ],
    },
    "scenario-08": {
        "decision": "FAIL",
        "fusion_rule": "F-02",
        "findings": [
            {"class": "missing_component", "approach": "model", "confidence": 0.96, "severity": "critical",
             "desc": "Missing capacitor C14 (0805 package, position U3-adjacent)",
             "bbox": {"x": 230, "y": 140, "width": 20, "height": 15}},
            {"class": "crack", "approach": "model", "confidence": 0.88, "severity": "major",
             "desc": "Solder bridge detected between pins 3-4 on U7 (QFP-48)",
             "bbox": {"x": 310, "y": 90, "width": 15, "height": 20}},
            {"class": "contamination", "approach": "anomaly", "confidence": 0.79, "severity": "minor",
             "desc": "Board contamination / flux residue near J2 connector area",
             "bbox": {"x": 50, "y": 250, "width": 60, "height": 40}},
        ],
    },
    "scenario-09": {
        "decision": "REVIEW",
        "fusion_rule": "F-06",
        "findings": [
            {"class": "contamination", "approach": "model", "confidence": 0.57, "severity": "minor",
             "desc": "Possible heat tint / discoloration near weld zone (confidence at decision boundary)",
             "bbox": {"x": 160, "y": 130, "width": 80, "height": 50}},
        ],
    },
    "scenario-10": {
        "decision": "FAIL",
        "fusion_rule": "F-02",
        "findings": [
            {"class": "scratch", "approach": "model", "confidence": 0.86, "severity": "major",
             "desc": "Apparent linear mark detected — likely ring-light reflection artifact on chamfer edge",
             "bbox": {"x": 90, "y": 170, "width": 150, "height": 10}},
        ],
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

        # Non-scenario: run real inference pipeline
        return await self._run_real_pipeline(inspection_id, family_name, thresholds)

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

        findings = []
        for f in scenario_data["findings"]:
            finding = Finding(
                id=str(uuid.uuid4()),
                defect_class=f["class"],
                approach=Approach(f["approach"]),
                confidence=f["confidence"],
                severity=Severity(f["severity"]),
                bbox=BoundingBox(**f["bbox"]) if f.get("bbox") else None,
                heatmap_url=None,  # Generated during real inference
                mask_url=None,
                description=f["desc"],
                image_id=None,
            )
            findings.append(finding)

        max_conf = max((f.confidence for f in findings), default=0.0)
        approaches_triggered = len(set(f.approach.value for f in findings))

        decision = Decision(
            result=DecisionResult(scenario_data["decision"]),
            fusion_rule=scenario_data["fusion_rule"],
            findings_count=len(findings),
            confidence_summary={
                "overall": max_conf,
                "max_finding": max_conf,
                "approaches_triggered": float(approaches_triggered),
            },
        )

        return InspectionResult(findings=findings, decision=decision)
