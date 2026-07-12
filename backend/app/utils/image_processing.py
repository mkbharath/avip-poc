"""Image processing utilities — heatmap generation, overlays, thumbnails."""

import cv2
import numpy as np
from PIL import Image


def create_heatmap_overlay(
    anomaly_map: np.ndarray,
    source_image_path: str,
    alpha: float = 0.5,
) -> Image.Image:
    """Create a colored heatmap overlaid on the source image.

    Args:
        anomaly_map: 2D array (H, W) with values 0-255 representing anomaly intensity.
        source_image_path: Path to the original image for overlay.
        alpha: Blending alpha for the heatmap overlay.

    Returns:
        PIL Image with the heatmap overlay.
    """
    # Load source image
    source = cv2.imread(source_image_path)
    if source is None:
        # Create blank background if source unavailable
        h, w = anomaly_map.shape[:2]
        source = np.zeros((h, w, 3), dtype=np.uint8)

    # Resize anomaly map to match source
    h, w = source.shape[:2]
    resized_map = cv2.resize(anomaly_map, (w, h))

    # Apply colormap (JET: blue=low, red=high)
    heatmap = cv2.applyColorMap(resized_map, cv2.COLORMAP_JET)

    # Blend with source
    overlay = cv2.addWeighted(source, 1 - alpha, heatmap, alpha, 0)

    # Convert BGR → RGB for PIL
    overlay_rgb = cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)
    return Image.fromarray(overlay_rgb)


def create_difference_visualization(
    test_image_path: str,
    golden_image_path: str,
    diff_map: np.ndarray,
) -> Image.Image:
    """Create a side-by-side-with-diff visualization.

    Shows: [Golden | Difference Heatmap | Test]
    """
    golden = cv2.imread(golden_image_path)
    test = cv2.imread(test_image_path)

    if golden is None or test is None:
        # Fallback
        h, w = diff_map.shape[:2]
        golden = np.zeros((h, w, 3), dtype=np.uint8)
        test = np.zeros((h, w, 3), dtype=np.uint8)

    # Ensure same size
    h, w = golden.shape[:2]
    test = cv2.resize(test, (w, h))

    # Create heatmap from diff_map
    norm_map = (np.clip(diff_map, 0, 1) * 255).astype(np.uint8)
    heatmap = cv2.applyColorMap(norm_map, cv2.COLORMAP_JET)

    # Stack horizontally
    vis = np.hstack([golden, heatmap, test])
    vis_rgb = cv2.cvtColor(vis, cv2.COLOR_BGR2RGB)
    return Image.fromarray(vis_rgb)


def generate_thumbnail(
    image_path: str,
    output_path: str,
    max_size: tuple[int, int] = (256, 256),
) -> None:
    """Generate a thumbnail of an image."""
    img = Image.open(image_path)
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    img.save(output_path, "JPEG", quality=80)


def draw_bounding_boxes(
    image_path: str,
    bboxes: list[dict],
    output_path: str,
) -> None:
    """Draw bounding boxes on an image and save.

    Args:
        image_path: Source image path.
        bboxes: List of dicts with x, y, width, height, label, color.
        output_path: Where to save the annotated image.
    """
    img = cv2.imread(image_path)
    if img is None:
        return

    for bbox in bboxes:
        x, y, w, h = int(bbox["x"]), int(bbox["y"]), int(bbox["width"]), int(bbox["height"])
        color = bbox.get("color", (0, 0, 255))  # Default red (BGR)
        label = bbox.get("label", "")

        cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
        if label:
            cv2.putText(
                img, label, (x, y - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA
            )

    cv2.imwrite(output_path, img)
