"""Drawing-Based Rule Engine — Deterministic feature verification.

Evaluates inspection rules defined per part family against detection
results. Rules check presence/absence of features, label content,
orientation, and component counts.
"""

import uuid
from typing import Any

from app.models.inspection import Approach, BoundingBox, Finding, Severity


# Demo rule definitions per part family
FAMILY_RULES: dict[str, list[dict[str, Any]]] = {
    "machined-aluminum-plate": [
        {
            "id": "rule-al-001",
            "name": "Surface label present",
            "type": "presence",
            "feature": "label",
            "expected": True,
            "zone": "top-left",
            "severity_on_fail": "major",
            "description": "Part identification label must be present in the top-left zone",
        },
        {
            "id": "rule-al-002",
            "name": "Mounting holes visible (4)",
            "type": "count",
            "feature": "mounting_hole",
            "expected_count": 4,
            "tolerance": 0,
            "severity_on_fail": "critical",
            "description": "All 4 corner mounting holes must be visible and unobstructed",
        },
        {
            "id": "rule-al-003",
            "name": "Orientation mark present",
            "type": "presence",
            "feature": "orientation_mark",
            "expected": True,
            "zone": "north-edge",
            "severity_on_fail": "major",
            "description": "Orientation datum mark must be present on the north edge",
        },
    ],
    "precision-screw-assembly": [
        {
            "id": "rule-sc-001",
            "name": "Fastener count (8)",
            "type": "count",
            "feature": "fastener",
            "expected_count": 8,
            "tolerance": 0,
            "severity_on_fail": "critical",
            "description": "All 8 mounting fasteners must be present and seated",
        },
        {
            "id": "rule-sc-002",
            "name": "Connector present",
            "type": "presence",
            "feature": "connector",
            "expected": True,
            "zone": "south",
            "severity_on_fail": "critical",
            "description": "RF connector must be present in the south-facing position",
        },
        {
            "id": "rule-sc-003",
            "name": "Part label present",
            "type": "presence",
            "feature": "label",
            "expected": True,
            "zone": "top",
            "severity_on_fail": "major",
            "description": "Part number label must be present and readable",
        },
    ],
    "welded-stainless-component": [
        {
            "id": "rule-ws-001",
            "name": "Port fittings present (3)",
            "type": "count",
            "feature": "fitting",
            "expected_count": 3,
            "tolerance": 0,
            "severity_on_fail": "critical",
            "description": "All 3 gas port fittings must be present",
        },
        {
            "id": "rule-ws-002",
            "name": "Weld seam continuous",
            "type": "presence",
            "feature": "weld_seam",
            "expected": True,
            "zone": "perimeter",
            "severity_on_fail": "critical",
            "description": "Weld seam must be continuous with no visible gaps",
        },
    ],
    "pcb-sub-assembly": [
        {
            "id": "rule-pcb-001",
            "name": "Main IC present",
            "type": "presence",
            "feature": "ic_package",
            "expected": True,
            "zone": "center",
            "severity_on_fail": "critical",
            "description": "Primary controller IC must be present and properly seated",
        },
        {
            "id": "rule-pcb-002",
            "name": "Connector count (4)",
            "type": "count",
            "feature": "board_connector",
            "expected_count": 4,
            "tolerance": 0,
            "severity_on_fail": "critical",
            "description": "All 4 board-edge connectors must be populated",
        },
        {
            "id": "rule-pcb-003",
            "name": "Board label present",
            "type": "presence",
            "feature": "label",
            "expected": True,
            "zone": "bottom-right",
            "severity_on_fail": "major",
            "description": "Board identification label must be present",
        },
    ],
    "anodized-housing": [
        {
            "id": "rule-ah-001",
            "name": "Seal groove visible",
            "type": "presence",
            "feature": "seal_groove",
            "expected": True,
            "zone": "perimeter",
            "severity_on_fail": "critical",
            "description": "O-ring seal groove must be visible and unobstructed",
        },
        {
            "id": "rule-ah-002",
            "name": "Mounting inserts (6)",
            "type": "count",
            "feature": "insert",
            "expected_count": 6,
            "tolerance": 0,
            "severity_on_fail": "critical",
            "description": "All 6 threaded mounting inserts must be present",
        },
        {
            "id": "rule-ah-003",
            "name": "Part marking present",
            "type": "presence",
            "feature": "engraving",
            "expected": True,
            "zone": "top-surface",
            "severity_on_fail": "minor",
            "description": "Part number engraving must be present and legible",
        },
    ],
}


class RuleEngine:
    """Deterministic inspection rule evaluation engine."""

    async def evaluate(
        self,
        family_name: str,
        detections: list[Finding] | None = None,
    ) -> list[Finding]:
        """Evaluate all rules for a given part family.

        In production, `detections` comes from the YOLO detector providing evidence
        for presence/absence checks. In PoC scenario mode, rules evaluate
        based on pre-defined outcomes.

        Args:
            family_name: Part family name to look up rules.
            detections: Optional YOLO detection results to use as evidence.

        Returns:
            List of rule-based findings (PASS rules generate no findings;
            FAIL rules generate findings).
        """
        rules = FAMILY_RULES.get(family_name, [])
        if not rules:
            return []

        findings = []
        for rule in rules:
            finding = self._evaluate_rule(rule, detections)
            if finding:
                findings.append(finding)

        return findings

    def _evaluate_rule(
        self, rule: dict[str, Any], detections: list[Finding] | None
    ) -> Finding | None:
        """Evaluate a single rule.

        In the PoC, rules always PASS by default (scenarios inject FAILs via ai_pipeline).
        In production, this would cross-reference YOLO detections against expectations.
        """
        # Default behavior: rules pass (no finding generated)
        # Scenario-specific failures are injected by the AI pipeline
        return None

    def evaluate_with_simulated_failure(
        self, rule: dict[str, Any], detected_count: int | None = None
    ) -> Finding | None:
        """Evaluate a rule with a specific simulated detection result.

        Used by demo scenarios to produce realistic rule engine outputs.
        """
        rule_type = rule["type"]

        if rule_type == "count" and detected_count is not None:
            expected = rule["expected_count"]
            if detected_count != expected:
                return Finding(
                    id=str(uuid.uuid4()),
                    defect_class="missing_component",
                    approach=Approach.RULE,
                    confidence=1.0,  # Rules are deterministic
                    severity=Severity(rule["severity_on_fail"]),
                    bbox=None,
                    heatmap_url=None,
                    mask_url=None,
                    description=(
                        f"Rule FAIL: {rule['name']}. "
                        f"Expected {expected} {rule['feature']}(s), "
                        f"detected {detected_count}."
                    ),
                    image_id=None,
                )

        if rule_type == "presence":
            # Simulated absence detection
            return Finding(
                id=str(uuid.uuid4()),
                defect_class="missing_component" if rule["expected"] else "wrong_label",
                approach=Approach.RULE,
                confidence=1.0,
                severity=Severity(rule["severity_on_fail"]),
                bbox=None,
                heatmap_url=None,
                mask_url=None,
                description=f"Rule FAIL: {rule['name']}. {rule['description']}",
                image_id=None,
            )

        return None

    def get_rules_for_family(self, family_name: str) -> list[dict[str, Any]]:
        """Get all rules defined for a part family."""
        return FAMILY_RULES.get(family_name, [])

    def get_rules_summary(self, family_name: str) -> dict:
        """Get a summary of rules for display in the UI."""
        rules = self.get_rules_for_family(family_name)
        return {
            "family": family_name,
            "rule_count": len(rules),
            "rules": [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "type": r["type"],
                    "severity_on_fail": r["severity_on_fail"],
                    "description": r["description"],
                }
                for r in rules
            ],
        }
