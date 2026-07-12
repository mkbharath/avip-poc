"""Decision Fusion Engine — Combines findings from all three approaches into a final decision.

Implements fusion rules F-01 through F-07 from AVIP Spec 03 §4.4:
  F-01: Hard-fail rule finding in critical zone → FAIL
  F-02: Learned-model finding with high confidence + high severity → FAIL
  F-03: Findings in REVIEW band (between thresholds) or anomaly-only → REVIEW
  F-04: Golden-diff corroborated by another approach → escalate severity
  F-05: No findings above low threshold → PASS
  F-06: Conflicts (rule pass but high-confidence model FAIL) → REVIEW with conflict flag
  F-07: All thresholds are per-family, versioned, QE-owned
"""

from app.models.inspection import (
    Approach,
    Decision,
    DecisionResult,
    Finding,
    Severity,
)


class FusionEngine:
    """Fuses findings from multiple inspection approaches into a single decision."""

    def decide(
        self,
        findings: list[Finding],
        thresholds: dict,
    ) -> Decision:
        """Produce a fused decision from all findings.

        Args:
            findings: Combined findings from all three approaches.
            thresholds: Per-family decision thresholds containing:
                - confidence_high: Upper threshold for automatic FAIL
                - confidence_low: Lower threshold (below = ignore)
                - severity_threshold: Minimum severity for FAIL
                - max_findings_pass: Max findings allowed for PASS (usually 0)

        Returns:
            A Decision object with result, fusion rule triggered, and summary.
        """
        confidence_high = thresholds.get("confidence_high", 0.85)
        confidence_low = thresholds.get("confidence_low", 0.55)
        severity_threshold = thresholds.get("severity_threshold", "major")
        max_findings_pass = thresholds.get("max_findings_pass", 0)

        # Filter to findings above the low threshold
        relevant_findings = [f for f in findings if f.confidence >= confidence_low]

        # F-05: No findings above low threshold → PASS
        if not relevant_findings:
            return Decision(
                result=DecisionResult.PASS,
                fusion_rule="F-05",
                findings_count=0,
                confidence_summary={"overall": 0.0, "approaches_triggered": 0.0},
            )

        # F-01: Hard-fail rule finding with critical severity → FAIL
        rule_critical = [
            f for f in relevant_findings
            if f.approach == Approach.RULE and f.severity == Severity.CRITICAL
        ]
        if rule_critical:
            return self._build_decision(
                DecisionResult.FAIL, "F-01", relevant_findings
            )

        # F-04: Check for golden-diff corroboration (escalate severity)
        golden_findings = [f for f in relevant_findings if f.approach == Approach.GOLDEN]
        other_findings = [f for f in relevant_findings if f.approach != Approach.GOLDEN]
        corroborated = False
        for gf in golden_findings:
            for of in other_findings:
                if self._findings_overlap(gf, of):
                    corroborated = True
                    # Escalate severity conceptually (affects F-02 check)
                    break

        # F-02: High-confidence model/anomaly finding + sufficient severity → FAIL
        severity_order = {"minor": 0, "major": 1, "critical": 2}
        threshold_level = severity_order.get(severity_threshold, 1)

        high_confidence_severe = [
            f for f in relevant_findings
            if f.confidence >= confidence_high
            and severity_order.get(f.severity.value, 0) >= threshold_level
            and f.approach in (Approach.MODEL, Approach.ANOMALY, Approach.RULE)
        ]

        if high_confidence_severe:
            return self._build_decision(
                DecisionResult.FAIL, "F-02", relevant_findings
            )

        # If golden-diff corroborated findings exist, treat as FAIL (F-04 escalation)
        if corroborated and golden_findings:
            return self._build_decision(
                DecisionResult.FAIL, "F-04", relevant_findings
            )

        # F-06: Conflict detection — rule passes but model says FAIL at high confidence
        rule_pass = not any(f.approach == Approach.RULE for f in relevant_findings)
        model_high = any(
            f.confidence >= confidence_high
            for f in relevant_findings
            if f.approach == Approach.MODEL
        )
        if rule_pass and model_high:
            return self._build_decision(
                DecisionResult.REVIEW, "F-06", relevant_findings
            )

        # F-03: Findings in the REVIEW band (above low, below high) → REVIEW
        review_band = [
            f for f in relevant_findings
            if confidence_low <= f.confidence < confidence_high
        ]
        anomaly_only = [
            f for f in relevant_findings
            if f.approach == Approach.ANOMALY and f.confidence < confidence_high
        ]

        if review_band or anomaly_only:
            return self._build_decision(
                DecisionResult.REVIEW, "F-03", relevant_findings
            )

        # If we get here with findings above threshold, FAIL
        if len(relevant_findings) > max_findings_pass:
            return self._build_decision(
                DecisionResult.FAIL, "F-02", relevant_findings
            )

        # Default: PASS
        return self._build_decision(
            DecisionResult.PASS, "F-05", relevant_findings
        )

    def _build_decision(
        self,
        result: DecisionResult,
        fusion_rule: str,
        findings: list[Finding],
    ) -> Decision:
        """Construct a Decision object with summary statistics."""
        max_conf = max((f.confidence for f in findings), default=0.0)
        approaches_triggered = len(set(f.approach.value for f in findings))

        return Decision(
            result=result,
            fusion_rule=fusion_rule,
            findings_count=len(findings),
            confidence_summary={
                "overall": max_conf,
                "max_finding": max_conf,
                "approaches_triggered": float(approaches_triggered),
            },
        )

    @staticmethod
    def _findings_overlap(a: Finding, b: Finding) -> bool:
        """Check if two findings spatially overlap (simple bbox intersection)."""
        if not a.bbox or not b.bbox:
            return True  # If no spatial info, assume overlap (conservative)

        # Check intersection
        x1 = max(a.bbox.x, b.bbox.x)
        y1 = max(a.bbox.y, b.bbox.y)
        x2 = min(a.bbox.x + a.bbox.width, b.bbox.x + b.bbox.width)
        y2 = min(a.bbox.y + a.bbox.height, b.bbox.y + b.bbox.height)

        return x2 > x1 and y2 > y1
