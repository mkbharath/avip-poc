"""Vision LLM Service — GPT-4 Vision few-shot defect classification.

Uses OpenAI's GPT-4 Vision (or GPT-4o) to classify defects in inspection images
with few-shot reference examples from the client's defect catalog.

This runs ADDITIVELY alongside the existing demo pipeline — it does not replace
the hardcoded scenario results. When enabled, it adds a 'vision_llm' approach
finding to the inspection results.
"""

import base64
import json
import logging
import uuid
from pathlib import Path

from app.config import settings
from app.models.inspection import Approach, BoundingBox, Finding, Severity

logger = logging.getLogger(__name__)

# Lam defect classes with descriptions for the prompt
DEFECT_CATALOG = {
    "porosity": {
        "description": "Subsurface voids/pits exposed after machining, visible as dark spots on metal surface",
        "severity_default": "critical",
        "reference_image": "porosity_ref.jpg",
    },
    "tool_marks": {
        "description": "Visible machining marks, parallel lines/grooves from cutting tools that exceed surface finish spec",
        "severity_default": "major",
        "reference_image": "tool_marks_ref.jpg",
    },
    "coating_stain": {
        "description": "Discoloration, staining, or uneven coating on anodized or painted surfaces",
        "severity_default": "major",
        "reference_image": "coating_stain_ref.jpg",
    },
    "label_mismatch": {
        "description": "Part label does not match expected content — wrong serial number, missing info, or damaged label",
        "severity_default": "critical",
        "reference_image": "label_mismatch_ref.jpg",
    },
    "burr": {
        "description": "Raised material on edges or holes from machining — sharp protrusions that exceed tolerance",
        "severity_default": "major",
        "reference_image": "burr_ref.jpg",
    },
    "paint_peel": {
        "description": "Paint or coating delamination — peeling, flaking, or bubbling revealing bare substrate",
        "severity_default": "critical",
        "reference_image": "paint_peel_ref.jpg",
    },
    "scratch": {
        "description": "Linear surface damage — scratches, gouges, or drag marks on machined or coated surfaces",
        "severity_default": "major",
        "reference_image": None,
    },
    "dent": {
        "description": "Impact damage — circular or irregular depression on the surface",
        "severity_default": "major",
        "reference_image": None,
    },
    "contamination": {
        "description": "Foreign material or particles on a clean surface",
        "severity_default": "major",
        "reference_image": None,
    },
    "no_defect": {
        "description": "Part appears normal with no visible defects",
        "severity_default": "minor",
        "reference_image": None,
    },
}

SYSTEM_PROMPT = """You are an AI vision inspection system for semiconductor manufacturing equipment parts at Lam Research.

Your job is to analyze images of machined metal parts, anodized housings, and coated components to detect cosmetic defects.

You will be shown an inspection image. Classify any visible defects using ONLY these defect classes:
- porosity: dark pits/voids on machined metal surface
- tool_marks: parallel grooves/lines from machining tools
- coating_stain: discoloration or uneven coating
- label_mismatch: incorrect or damaged part label
- burr: raised sharp material on edges/holes
- paint_peel: coating delamination, peeling, flaking
- scratch: linear surface damage
- dent: impact depression on surface
- contamination: foreign particles on surface
- no_defect: part looks good, no visible issues

Respond ONLY with valid JSON in this exact format:
{
  "defect_class": "<class_name>",
  "confidence": <0.0-1.0>,
  "severity": "<minor|major|critical>",
  "description": "<one sentence describing what you see>",
  "bbox_estimate": {"x_pct": <0-100>, "y_pct": <0-100>, "w_pct": <0-100>, "h_pct": <0-100>}
}

bbox_estimate should be approximate percentage coordinates of where the defect is in the image.
If no defect is found, use defect_class "no_defect" with confidence 0.95 and null bbox_estimate.
Be precise and conservative — only flag real defects, not normal machining textures or lighting artifacts."""


class VisionLLMService:
    """GPT-4 Vision few-shot defect classifier."""

    def __init__(self) -> None:
        self._client = None
        self._reference_images: dict[str, str] = {}  # class -> base64
        self._initialized = False
        self._last_error: str | None = None
        self._last_raw_response: str | None = None

    def _ensure_initialized(self) -> bool:
        """Lazy-initialize the OpenAI client and load reference images."""
        if self._initialized:
            return self._client is not None

        self._initialized = True

        if not settings.openai_api_key:
            logger.warning("Vision LLM: No OPENAI_API_KEY configured")
            return False

        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=settings.openai_api_key)
        except ImportError:
            logger.error("Vision LLM: openai package not installed")
            return False
        except Exception as e:
            logger.error(f"Vision LLM: Failed to init client: {e}")
            return False

        # Load reference images for few-shot prompting
        self._load_reference_images()
        return True

    def _load_reference_images(self) -> None:
        """Load reference defect images as base64 for few-shot context."""
        ref_dir = settings.demo_data_dir / "reference_images"
        if not ref_dir.exists():
            logger.info("Vision LLM: No reference_images dir, running zero-shot")
            return

        for defect_class, info in DEFECT_CATALOG.items():
            ref_file = info.get("reference_image")
            if ref_file and (ref_dir / ref_file).exists():
                img_data = (ref_dir / ref_file).read_bytes()
                self._reference_images[defect_class] = base64.b64encode(img_data).decode()

        logger.info(f"Vision LLM: Loaded {len(self._reference_images)} reference images")

    def _encode_image(self, image_path: str) -> str | None:
        """Encode an image file to base64."""
        path = Path(image_path)
        if not path.exists():
            return None
        img_data = path.read_bytes()
        return base64.b64encode(img_data).decode()

    async def classify(self, image_path: str) -> Finding | None:
        """Classify a single inspection image using GPT-4 Vision.

        Args:
            image_path: Path to the image file to classify.

        Returns:
            A Finding object if a defect is detected, None otherwise.
        """
        if not self._ensure_initialized():
            self._last_error = "Service not initialized (missing API key or openai package)"
            return None

        img_b64 = self._encode_image(image_path)
        if not img_b64:
            self._last_error = f"Cannot read image at {image_path}"
            logger.warning(f"Vision LLM: {self._last_error}")
            return None

        # Build the messages with few-shot reference images
        messages = self._build_messages(img_b64)

        try:
            response = self._client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                max_tokens=500,
                temperature=0.1,  # Low temp for consistent classification
            )

            result_text = response.choices[0].message.content.strip()
            self._last_error = None
            self._last_raw_response = result_text
            return self._parse_response(result_text)

        except Exception as e:
            self._last_error = str(e)
            logger.error(f"Vision LLM: API call failed: {e}")
            return None

    def _build_messages(self, inspection_image_b64: str) -> list[dict]:
        """Build the message array with system prompt, reference images, and target."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Add few-shot reference examples if available
        if self._reference_images:
            ref_content = [
                {"type": "text", "text": "Here are reference examples of known defect types:"}
            ]
            for defect_class, img_b64 in self._reference_images.items():
                ref_content.append({
                    "type": "text",
                    "text": f"\n[{defect_class}]: {DEFECT_CATALOG[defect_class]['description']}"
                })
                ref_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img_b64}",
                        "detail": "low",  # Low detail for references to save tokens
                    }
                })
            messages.append({"role": "user", "content": ref_content})
            messages.append({
                "role": "assistant",
                "content": "I understand the defect reference catalog. Please show me the inspection image to classify."
            })

        # Add the actual inspection image
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": "Classify this inspection image. What defect (if any) do you see?"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{inspection_image_b64}",
                        "detail": "high",  # High detail for the actual inspection
                    }
                },
            ],
        })

        return messages

    def _parse_response(self, response_text: str) -> Finding | None:
        """Parse the LLM JSON response into a Finding object."""
        # Strip markdown code fences if present
        text = response_text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        if text.startswith("json"):
            text = text[4:].strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.error(f"Vision LLM: Failed to parse response: {response_text[:200]}")
            return None

        defect_class = data.get("defect_class", "no_defect")
        if defect_class == "no_defect":
            return None

        confidence = float(data.get("confidence", 0.5))
        severity_str = data.get("severity", "minor")
        description = data.get("description", f"{defect_class} detected by Vision LLM")

        # Parse bbox estimate (percentage-based -> pixel coords at 640x480)
        bbox = None
        bbox_data = data.get("bbox_estimate")
        if bbox_data and bbox_data.get("x_pct") is not None:
            bbox = BoundingBox(
                x=float(bbox_data["x_pct"]) / 100.0 * 640,
                y=float(bbox_data["y_pct"]) / 100.0 * 480,
                width=float(bbox_data.get("w_pct", 20)) / 100.0 * 640,
                height=float(bbox_data.get("h_pct", 20)) / 100.0 * 480,
            )

        severity_map = {"minor": Severity.MINOR, "major": Severity.MAJOR, "critical": Severity.CRITICAL}
        severity = severity_map.get(severity_str, Severity.MINOR)

        return Finding(
            id=str(uuid.uuid4()),
            defect_class=defect_class,
            approach=Approach.MODEL,  # Reported as 'model' approach
            confidence=confidence,
            severity=severity,
            bbox=bbox,
            heatmap_url=None,
            mask_url=None,
            description=f"[Vision AI] {description}",
            image_id=None,
        )


# Singleton instance
vision_llm_service = VisionLLMService()
