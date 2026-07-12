"""Golden Sample Comparison Service — Image registration and differencing.

Compares captured images against certified golden reference images using
classical computer vision: feature-based registration + SSIM + absolute difference.
No ML model required — deterministic and explainable.
"""

import uuid

import cv2
import numpy as np
from PIL import Image

from app.config import settings
from app.models.inspection import Approach, BoundingBox, Finding, Severity


class GoldenComparator:
    """Golden sample comparison using image registration and differencing."""

    def __init__(self) -> None:
        self._orb = cv2.ORB_create(nfeatures=1000)
        self._matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    async def compare(
        self,
        test_image_path: str,
        golden_image_path: str,
        tolerance_threshold: float = 0.15,
        min_region_area: int = 100,
    ) -> tuple[list[Finding], str | None]:
        """Compare a test image against the golden reference.

        Args:
            test_image_path: Path to the captured test image.
            golden_image_path: Path to the certified golden reference image.
            tolerance_threshold: Normalized difference threshold (0-1).
            min_region_area: Minimum contour area in pixels to report as finding.

        Returns:
            Tuple of (findings list, difference_heatmap_url or None)
        """
        # Load images
        test_img = cv2.imread(test_image_path)
        golden_img = cv2.imread(golden_image_path)

        if test_img is None or golden_img is None:
            return [], None

        # Ensure same size
        h, w = golden_img.shape[:2]
        test_img = cv2.resize(test_img, (w, h))

        # Register (align) test image to golden reference
        aligned_test = self._register_images(test_img, golden_img)

        # Compute difference
        diff_map = self._compute_difference(aligned_test, golden_img)

        # Generate difference heatmap
        heatmap_url = await self._save_difference_heatmap(diff_map)

        # Find regions exceeding tolerance
        findings = self._extract_findings(diff_map, tolerance_threshold, min_region_area)

        return findings, heatmap_url

    def _register_images(
        self, test_img: np.ndarray, golden_img: np.ndarray
    ) -> np.ndarray:
        """Align test image to golden reference using ORB feature matching."""
        # Convert to grayscale for feature detection
        test_gray = cv2.cvtColor(test_img, cv2.COLOR_BGR2GRAY)
        golden_gray = cv2.cvtColor(golden_img, cv2.COLOR_BGR2GRAY)

        # Detect keypoints and descriptors
        kp1, des1 = self._orb.detectAndCompute(test_gray, None)
        kp2, des2 = self._orb.detectAndCompute(golden_gray, None)

        if des1 is None or des2 is None or len(kp1) < 4 or len(kp2) < 4:
            # Not enough features for registration — return as-is
            return test_img

        # Match features
        matches = self._matcher.match(des1, des2)
        matches = sorted(matches, key=lambda x: x.distance)

        # Use top matches for homography
        good_matches = matches[: min(50, len(matches))]
        if len(good_matches) < 4:
            return test_img

        src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

        # Find homography
        H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        if H is None:
            return test_img

        # Warp test image to align with golden
        h, w = golden_img.shape[:2]
        aligned = cv2.warpPerspective(test_img, H, (w, h))

        return aligned

    def _compute_difference(
        self, test_img: np.ndarray, golden_img: np.ndarray
    ) -> np.ndarray:
        """Compute normalized difference map combining SSIM and absolute difference."""
        # Convert to grayscale
        test_gray = cv2.cvtColor(test_img, cv2.COLOR_BGR2GRAY).astype(np.float64)
        golden_gray = cv2.cvtColor(golden_img, cv2.COLOR_BGR2GRAY).astype(np.float64)

        # Absolute difference (normalized 0-1)
        abs_diff = np.abs(test_gray - golden_gray) / 255.0

        # SSIM-based difference (local structural dissimilarity)
        # Simplified SSIM using local statistics
        kernel_size = 11
        C1 = (0.01 * 255) ** 2
        C2 = (0.03 * 255) ** 2

        mu_test = cv2.GaussianBlur(test_gray, (kernel_size, kernel_size), 1.5)
        mu_golden = cv2.GaussianBlur(golden_gray, (kernel_size, kernel_size), 1.5)

        sigma_test = cv2.GaussianBlur(test_gray ** 2, (kernel_size, kernel_size), 1.5) - mu_test ** 2
        sigma_golden = cv2.GaussianBlur(golden_gray ** 2, (kernel_size, kernel_size), 1.5) - mu_golden ** 2
        sigma_cross = (
            cv2.GaussianBlur(test_gray * golden_gray, (kernel_size, kernel_size), 1.5)
            - mu_test * mu_golden
        )

        ssim_map = ((2 * mu_test * mu_golden + C1) * (2 * sigma_cross + C2)) / (
            (mu_test ** 2 + mu_golden ** 2 + C1) * (sigma_test + sigma_golden + C2)
        )

        # Convert SSIM to dissimilarity (1 - SSIM)
        dissim_map = np.clip(1.0 - ssim_map, 0, 1)

        # Combine: weighted average of absolute diff and structural dissimilarity
        combined = 0.4 * abs_diff + 0.6 * dissim_map

        # Apply Gaussian smoothing to reduce noise
        combined = cv2.GaussianBlur(combined, (5, 5), 1.0)

        return combined.astype(np.float32)

    def _extract_findings(
        self,
        diff_map: np.ndarray,
        tolerance_threshold: float,
        min_region_area: int,
    ) -> list[Finding]:
        """Extract findings from regions exceeding the tolerance threshold."""
        # Threshold the difference map
        binary = (diff_map > tolerance_threshold).astype(np.uint8) * 255

        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        findings = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_region_area:
                continue

            # Bounding box
            x, y, w, h = cv2.boundingRect(contour)

            # Average deviation in this region
            region_diff = diff_map[y : y + h, x : x + w]
            avg_deviation = float(np.mean(region_diff))
            max_deviation = float(np.max(region_diff))

            # Severity based on deviation magnitude
            severity = (
                Severity.CRITICAL if max_deviation > 0.6
                else Severity.MAJOR if max_deviation > 0.35
                else Severity.MINOR
            )

            # Confidence based on how much the deviation exceeds threshold
            confidence = min(1.0, avg_deviation / tolerance_threshold)

            findings.append(Finding(
                id=str(uuid.uuid4()),
                defect_class="surface_anomaly",
                approach=Approach.GOLDEN,
                confidence=confidence,
                severity=severity,
                bbox=BoundingBox(x=float(x), y=float(y), width=float(w), height=float(h)),
                heatmap_url=None,  # Set after heatmap generation
                mask_url=None,
                description=(
                    f"Golden comparison deviation (avg: {avg_deviation:.2%}, "
                    f"max: {max_deviation:.2%}) exceeds tolerance ({tolerance_threshold:.2%})"
                ),
                image_id=None,
            ))

        return findings

    async def _save_difference_heatmap(self, diff_map: np.ndarray) -> str:
        """Save the difference map as a colored heatmap image."""
        heatmap_id = str(uuid.uuid4())[:8]
        heatmap_path = settings.heatmaps_dir / f"golden_diff_{heatmap_id}.png"

        # Normalize to 0-255
        norm_map = (np.clip(diff_map, 0, 1) * 255).astype(np.uint8)

        # Apply colormap (COLORMAP_JET: blue=low, red=high)
        colored = cv2.applyColorMap(norm_map, cv2.COLORMAP_JET)

        cv2.imwrite(str(heatmap_path), colored)

        return f"/static/heatmaps/golden_diff_{heatmap_id}.png"
