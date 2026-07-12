"""Defect Detection Service — YOLOv8-based object detection.

In the full implementation, this loads a fine-tuned YOLOv8 ONNX model
and produces bounding boxes with defect class labels. For the PoC,
it provides simulated detections when real models aren't available.
"""

import uuid
from pathlib import Path

import numpy as np
from PIL import Image

from app.config import settings
from app.models.inspection import Approach, BoundingBox, Finding, Severity

# AVIP defect classes (maps to model output indices)
DEFECT_CLASSES = [
    "scratch",
    "dent",
    "contamination",
    "missing_component",
    "crack",
    "chip",
    "rust",
    "wrong_label",
    "missing_label",
    "surface_anomaly",
]


class DefectDetector:
    """YOLOv8-based defect detection service."""

    def __init__(self) -> None:
        self._model_loaded = False
        self._model = None
        self._input_size = 640

    def _try_load_model(self) -> bool:
        """Attempt to load the ONNX model."""
        model_path = settings.models_dir / "yolov8" / "defect_detector.onnx"
        if model_path.exists():
            try:
                import onnxruntime as ort

                self._model = ort.InferenceSession(str(model_path))
                self._model_loaded = True
                return True
            except Exception:
                pass
        return False

    async def detect(
        self,
        image_path: str,
        confidence_threshold: float = 0.4,
        nms_threshold: float = 0.45,
    ) -> list[Finding]:
        """Run defect detection on a single image.

        Returns:
            List of Finding objects for detected defects.
        """
        if self._model_loaded or self._try_load_model():
            return await self._run_real_inference(
                image_path, confidence_threshold, nms_threshold
            )
        else:
            # Return empty — scenario-based results handled by ai_pipeline.py
            return []

    async def _run_real_inference(
        self,
        image_path: str,
        confidence_threshold: float,
        nms_threshold: float,
    ) -> list[Finding]:
        """Run actual YOLOv8 inference via ONNX Runtime."""
        import cv2

        # Load and preprocess image
        img = cv2.imread(image_path)
        if img is None:
            return []

        orig_h, orig_w = img.shape[:2]

        # Resize to model input size
        resized = cv2.resize(img, (self._input_size, self._input_size))
        blob = resized.astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))  # HWC → CHW
        blob = np.expand_dims(blob, 0)  # Add batch dim

        # Run inference
        input_name = self._model.get_inputs()[0].name
        outputs = self._model.run(None, {input_name: blob})

        # Process YOLO output (assuming shape [1, num_detections, 5+num_classes])
        predictions = outputs[0][0]  # Remove batch dim

        findings = []
        for det in predictions:
            # YOLOv8 output: [x_center, y_center, width, height, class_scores...]
            x_c, y_c, w, h = det[:4]
            class_scores = det[4:]
            class_id = int(np.argmax(class_scores))
            confidence = float(class_scores[class_id])

            if confidence < confidence_threshold:
                continue

            if class_id >= len(DEFECT_CLASSES):
                continue

            # Convert from normalized to pixel coordinates (original image space)
            scale_x = orig_w / self._input_size
            scale_y = orig_h / self._input_size
            bbox = BoundingBox(
                x=float((x_c - w / 2) * scale_x),
                y=float((y_c - h / 2) * scale_y),
                width=float(w * scale_x),
                height=float(h * scale_y),
            )

            defect_class = DEFECT_CLASSES[class_id]
            severity = self._classify_severity(confidence, defect_class, w * h)

            findings.append(Finding(
                id=str(uuid.uuid4()),
                defect_class=defect_class,
                approach=Approach.MODEL,
                confidence=confidence,
                severity=severity,
                bbox=bbox,
                heatmap_url=None,
                mask_url=None,
                description=self._generate_description(defect_class, confidence, bbox),
                image_id=None,
            ))

        # Apply NMS (simplified — group by class, remove overlapping)
        findings = self._apply_nms(findings, nms_threshold)

        return findings

    def _classify_severity(
        self, confidence: float, defect_class: str, area: float
    ) -> Severity:
        """Classify severity based on confidence, class, and defect area."""
        # Critical defects regardless of size
        if defect_class in ("missing_component", "crack"):
            return Severity.CRITICAL if confidence > 0.8 else Severity.MAJOR

        # Large area = more severe
        if area > 10000:  # pixels^2 in model space
            return Severity.MAJOR

        if confidence > 0.85:
            return Severity.MAJOR
        elif confidence > 0.6:
            return Severity.MINOR
        else:
            return Severity.MINOR

    def _generate_description(
        self, defect_class: str, confidence: float, bbox: BoundingBox
    ) -> str:
        """Generate a human-readable description of the detection."""
        class_descriptions = {
            "scratch": "Linear surface damage detected",
            "dent": "Surface depression / impact damage detected",
            "contamination": "Foreign material / particulate contamination detected",
            "missing_component": "Expected component not detected at expected position",
            "crack": "Surface fracture / crack detected",
            "chip": "Material chipping / edge damage detected",
            "rust": "Corrosion / oxidation detected",
            "wrong_label": "Label content does not match expected pattern",
            "missing_label": "Required label not detected in expected zone",
            "surface_anomaly": "Surface irregularity detected (unclassified)",
        }
        desc = class_descriptions.get(defect_class, f"{defect_class} detected")
        return f"{desc} (confidence: {confidence:.0%})"

    def _apply_nms(self, findings: list[Finding], threshold: float) -> list[Finding]:
        """Simple NMS: remove overlapping findings of the same class."""
        if len(findings) <= 1:
            return findings

        # Group by class
        by_class: dict[str, list[Finding]] = {}
        for f in findings:
            by_class.setdefault(f.defect_class, []).append(f)

        result = []
        for cls, class_findings in by_class.items():
            # Sort by confidence descending
            class_findings.sort(key=lambda x: x.confidence, reverse=True)
            keep = []
            for f in class_findings:
                overlap = False
                for kept in keep:
                    if f.bbox and kept.bbox and self._iou(f.bbox, kept.bbox) > threshold:
                        overlap = True
                        break
                if not overlap:
                    keep.append(f)
            result.extend(keep)

        return result

    @staticmethod
    def _iou(a: BoundingBox, b: BoundingBox) -> float:
        """Calculate Intersection over Union."""
        x1 = max(a.x, b.x)
        y1 = max(a.y, b.y)
        x2 = min(a.x + a.width, b.x + b.width)
        y2 = min(a.y + a.height, b.y + b.height)

        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        area_a = a.width * a.height
        area_b = b.width * b.height
        union = area_a + area_b - intersection

        return intersection / union if union > 0 else 0.0
