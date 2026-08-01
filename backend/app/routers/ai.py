"""AI endpoints — test and explore the Vision LLM classification."""

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, UploadFile

from app.config import settings

router = APIRouter()


@router.get("/ai/vision-llm/status")
async def vision_llm_status():
    """Check whether the Vision LLM service is enabled and ready."""
    from app.services.vision_llm import vision_llm_service

    ready = False
    reference_count = 0
    if settings.vision_llm_enabled:
        ready = vision_llm_service._ensure_initialized()
        reference_count = len(vision_llm_service._reference_images)

    return {
        "enabled": settings.vision_llm_enabled,
        "ready": ready,
        "model": settings.openai_model,
        "reference_images_loaded": reference_count,
        "api_key_configured": bool(settings.openai_api_key),
    }


@router.post("/ai/vision-llm/classify/scenario/{scenario_id}")
async def classify_scenario(scenario_id: str):
    """Run Vision LLM classification on a demo scenario image.

    This does NOT modify the scenario result — it just returns what the
    Vision LLM thinks about the image independently.
    """
    if not settings.vision_llm_enabled:
        return {"error": "Vision LLM is not enabled. Set AVIP_VISION_LLM=true"}

    from app.services.vision_llm import vision_llm_service

    image_path = settings.demo_data_dir / "images" / "scenarios" / scenario_id / "top.jpg"
    if not image_path.exists():
        return {"error": f"No image found for {scenario_id}"}

    finding = await vision_llm_service.classify(str(image_path))

    if finding:
        return {
            "scenario_id": scenario_id,
            "classification": {
                "defect_class": finding.defect_class,
                "confidence": finding.confidence,
                "severity": finding.severity.value,
                "description": finding.description,
                "bbox": finding.bbox.model_dump() if finding.bbox else None,
            },
        }
    else:
        return {
            "scenario_id": scenario_id,
            "classification": {
                "defect_class": "no_defect",
                "confidence": 0.95,
                "severity": "minor",
                "description": "No defect detected by Vision LLM",
                "bbox": None,
            },
            "error": vision_llm_service._last_error,
            "raw_response": vision_llm_service._last_raw_response,
        }


@router.post("/ai/vision-llm/classify/upload")
async def classify_upload(file: UploadFile = File(...)):
    """Upload an image and get Vision LLM classification.

    Useful for testing with arbitrary images outside the demo set.
    """
    if not settings.vision_llm_enabled:
        return {"error": "Vision LLM is not enabled. Set AVIP_VISION_LLM=true"}

    from app.services.vision_llm import vision_llm_service

    # Save uploaded file temporarily
    suffix = Path(file.filename).suffix if file.filename else ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        finding = await vision_llm_service.classify(tmp_path)

        if finding:
            return {
                "filename": file.filename,
                "classification": {
                    "defect_class": finding.defect_class,
                    "confidence": finding.confidence,
                    "severity": finding.severity.value,
                    "description": finding.description,
                    "bbox": finding.bbox.model_dump() if finding.bbox else None,
                },
            }
        else:
            return {
                "filename": file.filename,
                "classification": {
                    "defect_class": "no_defect",
                    "confidence": 0.95,
                    "severity": "minor",
                    "description": "No defect detected by Vision LLM",
                    "bbox": None,
                },
            }
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@router.post("/ai/vision-llm/classify/all-scenarios")
async def classify_all_scenarios():
    """Run Vision LLM on all 18 scenarios and return comparative results.

    Useful for demonstrating the LLM's accuracy vs the hardcoded ground truth.
    """
    if not settings.vision_llm_enabled:
        return {"error": "Vision LLM is not enabled. Set AVIP_VISION_LLM=true"}

    from app.services.vision_llm import vision_llm_service

    results = []
    scenarios_dir = settings.demo_data_dir / "images" / "scenarios"

    for i in range(1, 19):
        scenario_id = f"scenario-{i:02d}"
        image_path = scenarios_dir / scenario_id / "top.jpg"

        if not image_path.exists():
            results.append({"scenario_id": scenario_id, "error": "no image"})
            continue

        finding = await vision_llm_service.classify(str(image_path))
        if finding:
            results.append({
                "scenario_id": scenario_id,
                "defect_class": finding.defect_class,
                "confidence": finding.confidence,
                "severity": finding.severity.value,
                "description": finding.description,
            })
        else:
            results.append({
                "scenario_id": scenario_id,
                "defect_class": "no_defect",
                "confidence": 0.95,
            })

    return {"results": results, "total": len(results)}
