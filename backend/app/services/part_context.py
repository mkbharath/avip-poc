"""Human-readable part context for source-comparison rows.

Discrepancies, review-queue rows, and report rows all carry a bare
``part_number`` — which tells a reviewer *which* part a finding is on, but not
*what that part is*. This service joins those part numbers back to the existing
``parts`` table so each row can surface a concise, human-readable context
(description + revision, plus material/supplier when available) without the
reviewer having to look the part up separately.

Design intent:

  * **Batch, never N+1.** :func:`get_part_context_map` resolves a whole page of
    part numbers in a SINGLE ``SELECT ... WHERE part_number IN (...)`` query and
    returns a map keyed by ``part_number``. Callers collect the distinct part
    numbers on a page, fetch once, then attach ``part_context`` to each row from
    the map.
  * **Null-safe / absent-safe.** The comparison feed includes external and
    simulated parts that may not exist in the ``parts`` table. A part number with
    no matching row simply has no entry in the map, so the caller attaches
    ``part_context = None`` — never an error.

The attached ``part_context`` object shape is::

    {
      "description": str | None,
      "revision":    str | None,
      "material":    str | None,
      "supplier":    str | None,
    }
"""

import logging

from app.db.database import get_db

logger = logging.getLogger("app.source_comparison.part_context")


async def get_part_context_map(part_numbers: list[str]) -> dict[str, dict]:
    """Batch-fetch human-readable part context for a list of part numbers.

    Runs ONE query — ``SELECT part_number, description, revision, material,
    supplier FROM parts WHERE part_number IN (...)`` — over the distinct part
    numbers and returns a map ``{part_number: {description, revision, material,
    supplier}}``. Part numbers with no matching ``parts`` row are simply absent
    from the map (never an error), so a caller treats a miss as
    ``part_context = None`` (external/simulated parts may not be in the table).

    Args:
        part_numbers: the part numbers to resolve (duplicates are de-duped;
            an empty list short-circuits to an empty map with no query).

    Returns:
        A dict keyed by ``part_number`` whose values are the context dict
        described above. Only part numbers that matched a row are present.
    """
    # Empty input → empty map, no query.
    distinct = list({pn for pn in part_numbers if pn is not None})
    if not distinct:
        return {}

    placeholders = ",".join("?" * len(distinct))
    db = await get_db()
    cursor = await db.execute(
        f"""SELECT part_number, description, revision, material, supplier
              FROM parts
             WHERE part_number IN ({placeholders})""",
        tuple(distinct),
    )
    rows = await cursor.fetchall()

    context_map: dict[str, dict] = {}
    for row in rows:
        context_map[row["part_number"]] = {
            "description": row["description"],
            "revision": row["revision"],
            "material": row["material"],
            "supplier": row["supplier"],
        }

    logger.info(
        "Part context resolved: requested=%d matched=%d",
        len(distinct),
        len(context_map),
    )
    return context_map
