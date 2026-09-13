"""Pluggable source adapters for the source-comparison feature (LAIR / FAIR / SHQ).

A ``SourceAdapter`` supplies inspection records for one or more named sources
(LAIR, FAIR, SHQ) continuously over time (Req 1.1). The default adapter is the
:class:`SimulatorAdapter` (Req 1.2), which generates realistic LAIR / FAIR / SHQ
records for the **real seeded parts** in the AVIP ``parts`` table and pushes each
one through the Ingestion API path a real source system would use.

Design (see design.md → "Backend — Source Adapter interface"):

  * ``SourceAdapter`` is a ``Protocol`` with a ``source`` attribute and an async
    ``stream() -> AsyncIterator[IngestRecord]`` that yields records over time.
  * ``SimulatorAdapter`` draws ``part_number`` / ``material`` / ``surface_finish``
    / ``supplier`` from the seeded ``parts`` rows, synthesizes ``lot_number`` and
    ``serial_number``, and generates the comprehensive field set from
    ``DEFAULT_FIELDS``:
      - numeric (``diameter``, ``thickness``, ``flatness``, ``hardness``) around a
        per-part deterministic baseline;
      - categorical (``material_grade`` from the part's material, ``coating_finish``
        / ``surface_visual`` from surface_finish, ``supplier``);
      - free-text (``inspector_notes``, ``comments``).
  * **SHQ is the numeric reference (assumed — pending client confirmation).** A
    single per-(part, lot) baseline is computed ONCE for each numeric field and
    SHARED by all three sources: SHQ carries the baseline exactly, and LAIR / FAIR
    agree with it (within-threshold jitter) unless a discrepancy is injected — in
    which case that field deviates only modestly beyond the per-field threshold
    (a believable bad reading). The same holds for categorical/free-text: agreeing
    sources reuse the SAME value / clean note, and only an injected mismatch
    differs. A controllable fraction (``discrepancy_rate``) of these discrepancies
    is injected so the review gate and report have meaningful content.

Config knobs (all with sensible defaults): ``rate_per_sec``, ``discrepancy_rate``,
``lots_per_part``, and ``seed`` for determinism.

Entry points:
  * ``stream()`` — an (optionally bounded) async generator of ``IngestRecord``s.
  * ``run(push_fn)`` — drive the stream, pushing each record via ``push_fn``
    (defaults to ``ingestion.ingest``); the lifespan task (task 7.3) launches this.
  * ``run_forever()`` — convenience wrapper around ``run`` with the default push.
  * ``stop()`` — request a clean stop; the running loop exits at the next record.

Structured logs are emitted for the adapter lifecycle and generated records
(Req 9.4). This module does NOT start any background task itself — wiring into
the FastAPI ``lifespan`` is task 7.3.
"""

import asyncio
import logging
import random
from typing import AsyncIterator, Awaitable, Callable, Protocol, runtime_checkable

from app.db.database import get_db
from app.models.source_comparison import FieldType, IngestRecord, SourceType
from app.services.ingestion import IngestionRejected, ingest
from app.services.sc_config import (
    DEFAULT_FIELDS,
    ComparisonConfig,
    FieldConfig,
    comparison_config,
)

logger = logging.getLogger("app.source_comparison.simulator")


# ── Source adapter interface (Req 1.1) ────────────────────────────────────────


@runtime_checkable
class SourceAdapter(Protocol):
    """Pluggable interface supplying records for named source(s).

    An adapter continuously yields ``IngestRecord`` instances over time via
    :meth:`stream`. The ``source`` attribute names the source (or a summary of
    the sources) the adapter emits, matching a ``SourceType`` value where a single
    source applies. Real enterprise-system adapters can be added later behind this
    same interface (Req 1.1).
    """

    source: str  # "LAIR" | "FAIR" | "SHQ" (or a summary for multi-source adapters)

    def stream(self) -> AsyncIterator[IngestRecord]:
        """Yield ``IngestRecord`` instances continuously over time."""
        ...


# Type of the push callback used by ``run`` — mirrors ``ingestion.ingest``.
PushFn = Callable[[IngestRecord], Awaitable[object]]


# ── Simulator adapter (Req 1.2, 3.1-3.5) ──────────────────────────────────────


class SimulatorAdapter:
    """Default source adapter: a realistic LAIR / FAIR / SHQ simulator.

    Emits records for the REAL seeded parts across the comprehensive configured
    field set, designating SHQ as the numeric reference (assumed) and injecting a
    controllable rate of discrepancies so the review gate and report have
    meaningful content.

    Parameters
    ----------
    rate_per_sec:
        Approximate records emitted per second (throttles ``run``; ``<= 0`` means
        emit as fast as possible, useful for tests).
    discrepancy_rate:
        Fraction in ``[0, 1]`` controlling how often LAIR / FAIR values deviate
        from the SHQ baseline beyond the per-field threshold (numeric), differ
        categorically, or carry differing free-text notes.
    lots_per_part:
        Number of distinct synthesized lots generated per seeded part.
    seed:
        RNG seed for deterministic generation.
    config:
        The comparison configuration (in-scope fields + per-field thresholds);
        defaults to the module-level ``comparison_config``.
    """

    #: This adapter emits all three sources; ``source`` summarizes that.
    source: str = "SIMULATOR(LAIR,FAIR,SHQ)"

    # An injected numeric deviation lands at ``threshold * factor`` beyond the
    # SHQ baseline, with ``factor`` drawn from this range — modestly out of
    # tolerance (a believable bad reading), never orders of magnitude off. E.g.
    # a 25.40mm diameter (threshold 0.10mm) becomes ~25.52-25.60mm, not 194mm.
    _DEVIATION_FACTOR_RANGE: tuple[float, float] = (1.2, 2.0)
    # Fraction of the threshold used for in-tolerance (non-flagged) jitter, so
    # agreeing values stay safely inside the boundary and read as ≈ SHQ.
    _AGREEMENT_MARGIN: float = 0.25

    def __init__(
        self,
        rate_per_sec: float = 3.0,
        discrepancy_rate: float = 0.25,
        lots_per_part: int = 2,
        seed: int = 1337,
        config: ComparisonConfig | None = None,
    ) -> None:
        self.rate_per_sec = rate_per_sec
        self.discrepancy_rate = max(0.0, min(1.0, discrepancy_rate))
        self.lots_per_part = max(1, lots_per_part)
        self.seed = seed
        self.config = config or comparison_config
        self._rng = random.Random(seed)
        self._stop = asyncio.Event()

    # ── Lifecycle control ─────────────────────────────────────────────────────

    def stop(self) -> None:
        """Request a clean stop; a running :meth:`run` loop exits promptly."""
        self._stop.set()

    def _stopped(self) -> bool:
        return self._stop.is_set()

    # ── Seeded-part access ────────────────────────────────────────────────────

    async def _load_seeded_parts(self) -> list[dict[str, str | None]]:
        """Read the REAL seeded parts from the DB (the parts the sim generates for).

        Selects exactly the columns the design calls out: ``part_number``,
        ``material``, ``surface_finish``, ``supplier``.
        """
        db = await get_db()
        cursor = await db.execute(
            "SELECT part_number, material, surface_finish, supplier FROM parts "
            "ORDER BY part_number"
        )
        rows = await cursor.fetchall()
        parts = [
            {
                "part_number": row["part_number"],
                "material": row["material"],
                "surface_finish": row["surface_finish"],
                "supplier": row["supplier"],
            }
            for row in rows
        ]
        logger.info("Simulator loaded %d seeded part(s) from the parts table", len(parts))
        return parts

    # ── Deterministic per-part baselines ──────────────────────────────────────

    def _part_rng(self, part_number: str, lot_number: str) -> random.Random:
        """A deterministic RNG keyed by seed + part + lot for stable baselines."""
        return random.Random(f"{self.seed}:{part_number}:{lot_number}")

    def _numeric_baseline(self, field_name: str, part_rng: random.Random) -> float:
        """A plausible per-part/lot numeric baseline for a field (the SHQ value).

        Ranges are chosen to be realistic for semiconductor machined parts and are
        well above the per-field thresholds so both agreeing and flagged
        perturbations are representable.
        """
        base_ranges: dict[str, tuple[float, float]] = {
            "diameter": (10.0, 150.0),   # mm — real machined-part dimensions
            "thickness": (1.0, 20.0),    # mm
            "flatness": (0.0, 0.20),     # mm
            "hardness": (35.0, 60.0),    # HRC
        }
        low, high = base_ranges.get(field_name, (0.0, 100.0))
        return round(part_rng.uniform(low, high), 4)

    def _group_baselines(self, part_rng: random.Random) -> dict[str, float]:
        """Precompute the per-(part, lot) numeric baseline for EVERY in-scope
        numeric field ONCE, so all three sources (SHQ, LAIR, FAIR) start from the
        SAME baseline number.

        This is the crux of the shared-baseline fix: the baselines are drawn from
        ``part_rng`` here a single time per group, rather than being re-drawn on
        each per-source ``_build_fields`` call (which advanced the RNG differently
        per source and produced wildly different numbers for the same part).
        """
        return {
            name: self._numeric_baseline(name, part_rng)
            for name, fc in self._in_scope_fields().items()
            if fc.type == FieldType.NUMERIC
        }

    def _numeric_thresholds(self) -> dict[str, float]:
        """Per-field numeric thresholds from config (Req 8.2)."""
        thresholds: dict[str, float] = dict(self.config.numeric_thresholds)
        # Fall back to any threshold declared on the FieldConfig itself.
        for name, fc in self._in_scope_fields().items():
            if fc.type == FieldType.NUMERIC and name not in thresholds and fc.threshold is not None:
                thresholds[name] = fc.threshold
        return thresholds

    def _in_scope_fields(self) -> dict[str, FieldConfig]:
        """In-scope configured fields (Req 3.7), defaulting to DEFAULT_FIELDS."""
        fields = self.config.fields or DEFAULT_FIELDS
        return {name: fc for name, fc in fields.items() if fc.in_scope}

    # ── Categorical / free-text derivation ────────────────────────────────────

    _COATING_ALT = {
        "Matte anodized": "Gloss anodized",
        "Type III hard anodized": "Type II anodized",
        "Machined bright": "Passivated",
        "Electropolished": "Bead blasted",
        "As-machined": "Deburred",
        "HASL": "ENIG",
        "ENIG": "HASL",
    }
    _VISUAL_STATES = ["clean", "minor scuff", "light staining", "tool marks", "discoloration"]
    _NOTES_CLEAN = [
        "All measured dimensions within nominal tolerance.",
        "Surface inspection passed; no anomalies noted.",
        "Part conforms to drawing; ready for release.",
    ]
    _NOTES_ISSUE = [
        "Observed localized surface staining near edge; recommend re-check.",
        "Slight tool witness marks on machined face; borderline acceptance.",
        "Coating thickness appears uneven along one quadrant.",
    ]

    def _material_grade(self, material: str | None) -> str:
        return material or "unspecified"

    def _coating_alt(self, finish: str | None) -> str:
        """A plausible alternate finish, for injecting categorical mismatches."""
        if finish and finish in self._COATING_ALT:
            return self._COATING_ALT[finish]
        return f"{finish or 'unspecified'} (alt)"

    # ── Record generation ─────────────────────────────────────────────────────

    def _should_discrepate(self) -> bool:
        return self._rng.random() < self.discrepancy_rate

    def _group_agreeing_text(self, part_rng: random.Random) -> dict[str, str]:
        """Pick ONE clean free-text note per free-text field for the whole group.

        Chosen deterministically from ``part_rng`` (per group), so every source
        that agrees carries the EXACT same note. Previously each source picked its
        own "clean" sentence independently, so two genuinely-fine notes ("Surface
        inspection passed" vs "Part conforms to drawing") were flagged as different.
        Only a source with an injected discrepancy carries a different (issue) note.
        """
        return {
            name: part_rng.choice(self._NOTES_CLEAN)
            for name, fc in self._in_scope_fields().items()
            if fc.type == FieldType.FREE_TEXT
        }

    def _build_fields(
        self,
        source: SourceType,
        part: dict[str, str | None],
        lot_number: str,
        serial_number: str,
        baselines: dict[str, float],
        agreeing_text: dict[str, str],
    ) -> dict[str, object]:
        """Build the comprehensive field set for one source's record.

        ``baselines`` and ``agreeing_text`` are precomputed ONCE per (part, lot)
        group and SHARED by all three sources, so SHQ / LAIR / FAIR start from the
        identical baseline number and the identical clean note.

        SHQ carries the baseline (numeric reference) / agreeing values exactly.
        LAIR / FAIR carry those same agreeing values, unless a discrepancy is
        injected — in which case that field deviates modestly beyond the per-field
        threshold (numeric), differs categorically, or carries a differing (issue)
        free-text note.
        """
        is_reference = source == SourceType.SHQ
        thresholds = self._numeric_thresholds()
        fields: dict[str, object] = {}

        for name, fc in self._in_scope_fields().items():
            if fc.type == FieldType.NUMERIC:
                baseline = baselines[name]
                threshold = thresholds.get(name, 0.0)
                if is_reference:
                    value = baseline
                elif self._should_discrepate():
                    # Deviate modestly beyond the threshold (flagged vs SHQ): a
                    # believable out-of-tolerance reading, not a wild number.
                    direction = 1 if self._rng.random() < 0.5 else -1
                    factor = self._rng.uniform(*self._DEVIATION_FACTOR_RANGE)
                    value = baseline + direction * threshold * factor
                else:
                    # Jitter within tolerance (agrees with SHQ ≈ baseline).
                    jitter = self._rng.uniform(-1, 1) * threshold * self._AGREEMENT_MARGIN
                    value = baseline + jitter
                fields[name] = round(value, 4)

            elif fc.type == FieldType.CATEGORICAL:
                base = self._categorical_base(name, part)
                if not is_reference and self._should_discrepate():
                    fields[name] = self._categorical_alt(name, part, base)
                else:
                    # Agreeing sources share the exact same category value.
                    fields[name] = base

            elif fc.type == FieldType.FREE_TEXT:
                if not is_reference and self._should_discrepate():
                    fields[name] = self._rng.choice(self._NOTES_ISSUE)
                else:
                    # Agreeing sources reuse the single clean note for the group.
                    fields[name] = agreeing_text[name]

            elif fc.type == FieldType.IDENTIFIER:
                # Identifier fields carried in the fields map echo the record's
                # identity so the identifier exact-match check has data to compare.
                if name == "part_number":
                    fields[name] = part["part_number"]
                elif name == "lot_number":
                    fields[name] = lot_number
                elif name == "serial_number":
                    fields[name] = serial_number

        return fields

    def _categorical_base(self, name: str, part: dict[str, str | None]) -> str:
        if name == "material_grade":
            return self._material_grade(part["material"])
        if name in ("coating_finish", "surface_visual"):
            return part["surface_finish"] or "unspecified"
        if name == "supplier":
            return part["supplier"] or "unspecified"
        return "unspecified"

    def _categorical_alt(self, name: str, part: dict[str, str | None], base: str) -> str:
        if name in ("coating_finish", "surface_visual"):
            return self._coating_alt(part["surface_finish"])
        if name == "material_grade":
            return f"{base} (regrade)"
        if name == "supplier":
            return f"{base} — alt site"
        return f"{base} (alt)"

    # ── Streaming ─────────────────────────────────────────────────────────────

    async def stream(self, limit: int | None = None) -> AsyncIterator[IngestRecord]:
        """Yield ``IngestRecord``s for the seeded parts, all three sources per lot.

        Iterates parts × lots and, per group, yields SHQ (the numeric reference)
        first followed by LAIR and FAIR. Emission continues until ``limit`` records
        (if given) have been yielded or :meth:`stop` is called; with no ``limit``
        the generator loops indefinitely (cycling lots) for continuous operation.

        The optional ``limit`` makes this a BOUNDED generator for tests and for
        callers that want a finite batch.
        """
        parts = await self._load_seeded_parts()
        if not parts:
            logger.warning("Simulator has no seeded parts to generate records for")
            return

        emitted = 0
        cycle = 0
        # SHQ first so the numeric reference exists before LAIR/FAIR are compared.
        source_order = [SourceType.SHQ, SourceType.LAIR, SourceType.FAIR]

        while not self._stopped():
            for part in parts:
                for lot_idx in range(self.lots_per_part):
                    lot_number = f"LOT-{part['part_number']}-{cycle:02d}{lot_idx:02d}"
                    part_rng = self._part_rng(str(part["part_number"]), lot_number)
                    # Precompute the SHARED per-group baselines and the single
                    # clean free-text note ONCE, so all three sources start from
                    # the same numbers/notes (fixes the 194/38/48 divergence).
                    baselines = self._group_baselines(part_rng)
                    agreeing_text = self._group_agreeing_text(part_rng)
                    for source in source_order:
                        if self._stopped():
                            return
                        if limit is not None and emitted >= limit:
                            return
                        serial_number = (
                            f"SN-{part['part_number']}-{cycle:02d}{lot_idx:02d}-{source.value}"
                        )
                        record = IngestRecord(
                            source=source,
                            external_record_id=(
                                f"{source.value}-{part['part_number']}-{lot_number}"
                            ),
                            part_number=str(part["part_number"]),
                            lot_number=lot_number,
                            serial_number=serial_number,
                            fields=self._build_fields(
                                source,
                                part,
                                lot_number,
                                serial_number,
                                baselines,
                                agreeing_text,
                            ),
                        )
                        emitted += 1
                        logger.debug(
                            "Simulator generated record: source=%s part=%s lot=%s (#%d)",
                            source.value,
                            record.part_number,
                            record.lot_number,
                            emitted,
                        )
                        yield record
            cycle += 1
            if limit is None:
                # Continuous mode: yield control so the loop is cooperative.
                await asyncio.sleep(0)

    # ── Drive the stream through the ingestion path ───────────────────────────

    async def run(
        self,
        push_fn: PushFn | None = None,
        *,
        limit: int | None = None,
    ) -> int:
        """Drive :meth:`stream`, pushing each record via ``push_fn``.

        ``push_fn`` defaults to :func:`app.services.ingestion.ingest` — the same
        Ingestion API path a real source system uses (design.md). Rejections
        (``IngestionRejected``) are logged and skipped so a single bad record can't
        halt the feed. Throttles to roughly ``rate_per_sec`` when positive.

        Returns the number of records successfully pushed. The FastAPI ``lifespan``
        task (task 7.3) launches this; call :meth:`stop` for a clean shutdown.
        """
        push = push_fn or ingest
        delay = (1.0 / self.rate_per_sec) if self.rate_per_sec and self.rate_per_sec > 0 else 0.0
        pushed = 0

        logger.info(
            "Simulator run starting: rate_per_sec=%s discrepancy_rate=%s "
            "lots_per_part=%s seed=%s limit=%s",
            self.rate_per_sec,
            self.discrepancy_rate,
            self.lots_per_part,
            self.seed,
            limit,
        )
        async for record in self.stream(limit=limit):
            if self._stopped():
                break
            try:
                await push(record)
                pushed += 1
            except IngestionRejected as exc:
                logger.warning(
                    "Simulator record rejected by ingestion: source=%s record_id=%s reason=%s",
                    exc.source,
                    exc.record_id,
                    exc.reason,
                )
            except Exception:  # noqa: BLE001 — never let one bad push stop the feed
                logger.exception(
                    "Simulator failed to push record source=%s part=%s lot=%s",
                    record.source.value,
                    record.part_number,
                    record.lot_number,
                )
            if delay:
                await asyncio.sleep(delay)

        logger.info("Simulator run finished: pushed=%d records", pushed)
        return pushed

    async def run_forever(self, push_fn: PushFn | None = None) -> None:
        """Continuous entry point for the lifespan task — runs until :meth:`stop`."""
        await self.run(push_fn, limit=None)
