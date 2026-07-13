---
inclusion: fileMatch
fileMatchPattern: "**/*.py"
---

# Backend Coding Standards (Python)

## Formatting & Linting

- **Formatter:** Black (line-length: 100)
- **Linter:** Ruff (line-length: 100, target: py312)
- **Type checker:** Prefer full type annotations on all public functions
- Run before commit: `ruff check app/` and `black --check app/`

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Modules | snake_case | `ai_pipeline.py` |
| Classes | PascalCase | `AIPipeline`, `FusionEngine` |
| Functions/methods | snake_case | `run_inspection()`, `_build_decision()` |
| Constants | UPPER_SNAKE_CASE | `SCENARIO_RESULTS`, `DEFECT_CLASSES` |
| Private methods | leading underscore | `_try_load_model()` |
| Type aliases | PascalCase | `InspectionResult` |
| Variables | snake_case | `max_conf`, `finding_rows` |

## Import Order

1. Standard library (`import os`, `import json`, `from pathlib import Path`)
2. Third-party packages (`from fastapi import ...`, `import numpy as np`)
3. Application modules (`from app.config import settings`, `from app.models.inspection import ...`)

Separate each group with a blank line. Use absolute imports from `app.` — no relative imports.

## Function & Method Standards

```python
async def run_inspection(inspection_id: str) -> InspectionResult:
    """Run the AI pipeline on captured images.

    Args:
        inspection_id: UUID of the inspection to process.

    Returns:
        InspectionResult containing findings and fused decision.

    Raises:
        HTTPException: If inspection not found (404).
    """
```

- All public functions must have docstrings (Google style)
- Use `async def` for any function that does I/O (DB, file, network)
- Return early for error/guard cases (fail fast)
- Keep functions under 50 lines; extract helpers if longer

## Pydantic Models

```python
class Decision(BaseModel):
    result: DecisionResult
    fusion_rule: str
    findings_count: int
    confidence_summary: dict[str, float]
```

- Use Pydantic `BaseModel` for all request/response schemas
- Use Python 3.12 type syntax (`str | None` not `Optional[str]`)
- Use `Enum` for fixed value sets (DecisionResult, Severity, Approach)
- Never use `dict[str, Any]` in model fields — be specific

## Database Access

- All DB operations through `app/db/database.py`
- Use parameterized queries (`?` placeholders) — never string interpolation
- Always `await db.commit()` after writes
- Use `row["column_name"]` access (sqlite3.Row)
- Check for None results before accessing row data

## Error Handling

```python
if not row:
    raise HTTPException(status_code=404, detail="Inspection not found")
```

- Use `HTTPException` for client-facing errors in routers
- Use specific status codes: 400 (bad input), 404 (not found), 422 (validation)
- Error detail can be a string or a dict with `message`, `suggestion` keys
- Never catch bare `Exception` — be specific

## Endpoint Idempotency

All state-changing endpoints (POST) must be idempotent:
- Check if the operation was already performed before executing
- Return the existing result if already done
- This guards against React StrictMode double-renders and network retries

```python
# Pattern: check before mutate
cursor = await db.execute("SELECT * FROM images WHERE inspection_id = ?", (id,))
existing = await cursor.fetchall()
if existing:
    return {"images": [...existing...]}  # Return existing, don't re-create
```

## Testing

- Tests in `backend/tests/`
- Use pytest + pytest-asyncio
- Name test files `test_<module>.py`
- Name test functions `test_<behavior>()`
- Use httpx.AsyncClient for endpoint tests
