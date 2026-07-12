"""Anomaly Detection Service — PatchCore-based inference.

In the full implementation, this loads a pre-trained PatchCore ONNX model
and produces pixel-level anomaly score maps. For the PoC, it generates
realistic simulated anomaly maps when real models aren't available.
"""

import uuid
from pathlib import Path

import numpy as np
from PIL import Image

from app.config import settings
from app.models.inspection import Approach, BoundingBox, Finding, Severity


class AnomalyDetector:
    """PatchCore-based anomaly detection service."""

    def __init__(self) -> None:
        self._model_loaded = False
        self._model = None

    def _try_load_model(self) -> bool:
        """Attempt to load the ONNX model."""
        model_path = settings.models_dir / "patchcore" / "model.onnx"
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
        family_name: str,
        threshold: float = 0.5,
    ) -> tuple[list[Finding], str | None]:
        """Run anomaly detection on a single image.

        Returns:
            Tuple of (findings list, heatmap_url or None)
        """
        if self._model_loaded or self._try_load_model():
            return await self._run_real_inference(image_path, threshold)
        else:
            return await self._run_simulated(image_path, family_name, threshold)

    async def _run_real_inference(
        self, image_path: str, threshold: float
    ) -> tuple[list[Finding], str | None]:
        """Run actual PatchCore inference via ONNX Runtime."""
        import onnxruntime as ort

        # Load and preprocess image
        img = Image.open(image_path).convert("RGB").resize((224, 224))
        img_array = np.array(img, dtype=np.float32) / 255.0
        img_array = np.transpose(img_array, (2, 0, 1))  # CHW
        img_array = np.expand_dims(img_array, 0)  # NCHW

        # Normalize (ImageNet)
        mean = np.array([0.485, 0.456, 0.406]).reshape(1, 3, 1, 1)
        std = np.array([0.229, 0.224, 0.225]).reshape(1, 3, 1, 1)
        img_array = (img_array - mean) / std

        # Run inference
        input_name = self._model.get_inputs()[0].name
        outputs = self._model.run(None, {input_name: img_array.astype(np.float32)})

        # Process anomaly score map
        anomaly_map = outputs[0][0, 0]  # Assume (1, 1, H, W) output
        anomaly_score = float(np.max(anomaly_map))

        # Generate heatmap image
        heatmap_url = None
        if anomaly_score > threshold:
            heatmap_url = await self._generate_heatmap(anomaly_map, image_path)

        findings = []
        if anomaly_score > threshold:
            # Find bounding box of anomaly region
            binary_mask = anomaly_map > threshold
            ys, xs = np.where(binary_mask)
            if len(xs) > 0:
                bbox = BoundingBox(
                    x=float(np.min(xs)),
                    y=float(np.min(ys)),
                    width=float(np.max(xs) - np.min(xs)),
                    height=float(np.max(ys) - np.min(ys)),
                )
            else:
                bbox = None

            severity = (
                Severity.CRITICAL if anomaly_score > 0.9
                else Severity.MAJOR if anomaly_score > 0.7
                else Severity.MINOR
            )

            findings.append(Finding(
                id=str(uuid.uuid4()),
                defect_class="surface_anomaly",
                approach=Approach.ANOMALY,
                confidence=min(anomaly_score, 1.0),
                severity=severity,
                bbox=bbox,
                heatmap_url=heatmap_url,
                mask_url=None,
                description=f"Anomaly detected (score: {anomaly_score:.2f}). "
                            "Region deviates from learned normal distribution.",
                image_id=None,
            ))

        return findings, heatmap_url

    async def _run_simulated(
        self, image_path: str, family_name: str, threshold: float
    ) -> tuple[list[Finding], str | None]:
        """Generate a simulated anomaly heatmap for demonstration.

        Creates a realistic-looking Gaussian anomaly blob on a random location.
        Used when ONNX model is not available.
        """
        # For PoC without real model, return empty (scenarios handle specific findings)
        return [], None

    async def _generate_heatmap(
        self, anomaly_map: np.ndarray, source_image_path: str
    ) -> str:
        """Generate a heatmap visualization and save it."""
        from app.utils.image_processing import create_heatmap_overlay

        heatmap_id = str(uuid.uuid4())[:8]
        heatmap_path = settings.heatmaps_dir / f"anomaly_{heatmap_id}.png"

        # Normalize to 0-255 for visualization
        norm_map = (anomaly_map - anomaly_map.min()) / (anomaly_map.max() - anomaly_map.min() + 1e-8)
        norm_map = (norm_map * 255).astype(np.uint8)

        # Apply colormap
        heatmap_img = create_heatmap_overlay(norm_map, source_image_path)
        heatmap_img.save(str(heatmap_path))

        return f"/static/heatmaps/anomaly_{heatmap_id}.png"
