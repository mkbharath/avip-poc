"""Background worker for the source-comparison feature (Req 1.5, 9.1, 9.4, 9.5).

A source adapter (the simulator by default) or a real source system pushes
records through the Ingestion API; :func:`app.services.ingestion.ingest`
persists each accepted record and enqueues the persisted ``SourceRecord`` on the
shared in-process ``asyncio.Queue`` (``get_ingest_queue()``). This module is the
**consumer** of that queue: an ``asyncio`` task started in the FastAPI lifespan
(task 7.3) drains the queue and drives each record through the pipeline as it
arrives, rather than requiring a manual batch trigger (Req 1.5).

Per record the worker:

  1. calls :func:`app.services.alignment.align_record` to attach the record to
     its aligned group (find-or-create by common key; late arrivals re-evaluate
     an existing partial group; unmatched records are retained). Alignment is
     idempotent and order-independent, so a duplicate re-delivery does not change
     the group;
  2. decides whether the alignment **warranted comparison** and, if so, calls
     :func:`app.services.comparison.compare_group` to (re)compute and persist the
     group's discrepancies as ``pending``. Recompare is idempotent
     (``UNIQUE(group_id, field_name)`` upsert preserving reviewer decisions), so
     re-running comparison for a group that grew from a late arrival is safe and
     surfaces newly-comparable fields (Req 4.3, Property 9/10).

**Chosen "when to compare" rule** (documented per the design's "alignment
completing/re-completing a group triggers comparison"):

    Run ``compare_group`` for a group iff, after aligning this record, the group
    has **>= 2 present sources** — i.e. there is something to compare — AND the
    group's *present-sources set changed as a result of this record* (a new
    source became present, or the group crossed from 1 -> 2 sources, or a late
    arrival re-completed it). Idempotent duplicate deliveries do not change the
    present-sources set and therefore do not trigger a redundant recompare.

This rule is deliberately broader than "only when complete": a two-source
partial group already surfaces real discrepancies for review, and a later third
record re-runs comparison (recompare is idempotent) so the completed group's
extra fields are picked up without dropping earlier findings. ``unmatched``
groups (no derivable common key, single synthetic record) never reach >= 2
present sources and so are never compared — they are retained for the groups
view instead.

**Resilience (Req 9.5).** Every per-record step runs inside a try/except so a
single poisoned record (e.g. one whose comparison raises) is caught, logged with
structured context (record id, source, part/lot), its error retained in the
worker's ``errors`` list, and the loop keeps draining subsequent records — one
bad record can never halt the stream. ``queue.task_done()`` is always called in
a ``finally`` so producers awaiting ``queue.join()`` are not blocked by a failed
record. Because ``compare_group`` already routes LLM-provider failures to the
``llm-unavailable`` provenance internally, the worker does not special-case the
LLM: non-free-text processing keeps working even when the provider errors
(Req 9.5).

**Structured logs (Req 9.4).** The worker emits structured log lines for
ingestion-processed, comparison, and error events, complementing the logs the
ingestion / alignment / comparison services already emit.

**Clean shutdown (task 7.3).** The worker supports a clean stop so the lifespan
can shut it down: enqueue the module ``STOP`` sentinel (``request_stop``) to make
the loop finish after draining, or cancel the task. Either way the loop exits
without leaving work in an inconsistent state.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from app.models.source_comparison import AlignedGroup, AlignmentState, SourceRecord
from app.services.alignment import align_record
from app.services.comparison import compare_group
from app.services.ingestion import get_ingest_queue
from app.services.sc_config import ComparisonConfig, comparison_config

logger = logging.getLogger("app.source_comparison.worker")

# Sentinel enqueued to request a clean stop after the queue drains (task 7.3).
STOP = object()

# Minimum number of distinct present sources for a group to be worth comparing.
MIN_SOURCES_TO_COMPARE = 2


@dataclass
class RecordError:
    """A retained per-record processing failure (Req 9.5).

    The offending record stays persisted (ingestion already stored it); this
    captures the failure so the worker keeps running while the error is not lost.
    """

    record_id: str
    source: str
    part_number: str
    lot_number: str
    error: str


@dataclass
class WorkerStats:
    """Lightweight in-memory counters for observability / the status endpoint."""

    processed: int = 0
    compared: int = 0
    skipped_no_compare: int = 0
    failed: int = 0
    errors: list[RecordError] = field(default_factory=list)


def _should_compare(before_present: set[str], after: AlignedGroup) -> bool:
    """Decide whether aligning this record warrants (re)comparison.

    Returns ``True`` iff the group now has ``>= MIN_SOURCES_TO_COMPARE`` distinct
    present sources AND this record actually changed the present-sources set
    (grew it), per the module's documented "when to compare" rule. An
    ``unmatched`` group is never compared. Idempotent duplicate deliveries leave
    the present-sources set unchanged and so return ``False``.
    """
    if after.alignment_state == AlignmentState.UNMATCHED:
        return False
    after_present = {s.value for s in after.present_sources}
    if len(after_present) < MIN_SOURCES_TO_COMPARE:
        return False
    # Compare only when this record grew the present-sources set (new source
    # added, or crossed the 1 -> 2 threshold, or re-completed the group).
    return after_present != before_present


async def _process_record(
    record: SourceRecord,
    stats: WorkerStats,
    config: ComparisonConfig,
) -> None:
    """Align one record and, if warranted, (re)compare its group.

    Raises on any failure so the caller can catch, log, retain the error, and
    keep draining (Req 9.5). Kept separate from the loop so the resilience
    boundary is a single well-defined try/except.
    """
    # Snapshot the group's present sources BEFORE this record so we can tell
    # whether the record meaningfully changed the group (vs an idempotent
    # duplicate that changes nothing).
    before_present = await _present_sources_for_key(
        record.part_number, record.lot_number, config
    )

    group = await align_record(record, config=config)

    logger.info(
        "worker: record aligned record_id=%s source=%s part_number=%s "
        "lot_number=%s group_id=%s state=%s present_sources=%s",
        record.id,
        record.source.value,
        record.part_number,
        record.lot_number,
        group.id,
        group.alignment_state.value,
        [s.value for s in group.present_sources],
    )

    if _should_compare(before_present, group):
        discrepancies = await compare_group(group, config=config)
        stats.compared += 1
        logger.info(
            "worker: comparison run group_id=%s part_number=%s lot_number=%s "
            "present_sources=%s discrepancies=%d",
            group.id,
            group.part_number,
            group.lot_number,
            [s.value for s in group.present_sources],
            len(discrepancies),
        )
    else:
        stats.skipped_no_compare += 1
        logger.debug(
            "worker: comparison skipped group_id=%s state=%s present_sources=%s "
            "(rule: >=%d present sources and set changed this record)",
            group.id,
            group.alignment_state.value,
            [s.value for s in group.present_sources],
            MIN_SOURCES_TO_COMPARE,
        )


async def _present_sources_for_key(
    part_number: str, lot_number: str, config: ComparisonConfig
) -> set[str]:
    """Return the distinct present sources of the group for a common key, if any.

    Read-only helper used to detect whether the incoming record meaningfully
    changes the group. Returns an empty set when no group exists yet (the record
    will create it). Never raises for a missing group.
    """
    # Only meaningful when the common key is derivable; unmatched records get a
    # fresh synthetic group each time, so an empty "before" set is correct.
    from app.db.database import get_db

    db = await get_db()
    cursor = await db.execute(
        "SELECT present_sources FROM sc_aligned_groups "
        "WHERE part_number = ? AND lot_number = ?",
        (part_number, lot_number),
    )
    row = await cursor.fetchone()
    if row is None:
        return set()
    import json

    try:
        return set(json.loads(row["present_sources"]))
    except (TypeError, ValueError):
        return set()


async def run_worker(
    queue: "asyncio.Queue[Any] | None" = None,
    *,
    config: ComparisonConfig | None = None,
    stats: WorkerStats | None = None,
) -> WorkerStats:
    """Drain the ingest queue, driving each record through align -> compare.

    Runs until it either (a) receives the :data:`STOP` sentinel (a clean stop
    requested via :func:`request_stop`, after which it returns) or (b) the task
    is cancelled (the lifespan cancels it on shutdown, task 7.3). For every
    ``SourceRecord`` it aligns the record and, per the documented rule,
    (re)compares the group; per-record failures are caught, logged with
    structured context, retained in ``stats.errors``, and never halt the loop
    (Req 9.5). ``queue.task_done()`` is always called so ``queue.join()`` works.

    Returns the :class:`WorkerStats` accumulated during the run. ``queue``,
    ``config``, and ``stats`` are injectable for testing; they default to the
    shared ingest queue, the module-level ``comparison_config``, and a fresh
    stats object respectively.
    """
    q = queue if queue is not None else get_ingest_queue()
    cfg = config if config is not None else comparison_config
    st = stats if stats is not None else WorkerStats()

    logger.info("worker: started; draining ingest queue")
    try:
        while True:
            item = await q.get()
            try:
                if item is STOP:
                    logger.info("worker: STOP sentinel received; stopping cleanly")
                    return st
                if not isinstance(item, SourceRecord):
                    logger.warning(
                        "worker: ignoring unexpected queue item of type %s",
                        type(item).__name__,
                    )
                    continue
                await _process_record(item, st, cfg)
                st.processed += 1
            except asyncio.CancelledError:
                # Propagate cancellation so the task can be shut down cleanly.
                raise
            except Exception as exc:  # noqa: BLE001 — resilience boundary (Req 9.5)
                st.failed += 1
                rec_id = getattr(item, "id", "<unknown>")
                source = getattr(getattr(item, "source", None), "value", "<unknown>")
                part = getattr(item, "part_number", "<unknown>")
                lot = getattr(item, "lot_number", "<unknown>")
                st.errors.append(
                    RecordError(
                        record_id=rec_id,
                        source=source,
                        part_number=part,
                        lot_number=lot,
                        error=repr(exc),
                    )
                )
                logger.exception(
                    "worker: per-record processing FAILED (retained, worker "
                    "continues) record_id=%s source=%s part_number=%s "
                    "lot_number=%s error=%r",
                    rec_id,
                    source,
                    part,
                    lot,
                    exc,
                )
            finally:
                q.task_done()
    except asyncio.CancelledError:
        logger.info("worker: cancelled; shutting down")
        raise
    finally:
        logger.info(
            "worker: stopped; processed=%d compared=%d skipped=%d failed=%d",
            st.processed,
            st.compared,
            st.skipped_no_compare,
            st.failed,
        )


async def request_stop(queue: "asyncio.Queue[Any] | None" = None) -> None:
    """Request a clean stop by enqueuing the :data:`STOP` sentinel.

    The worker finishes draining items already queued ahead of the sentinel and
    then returns from :func:`run_worker`. An alternative for the lifespan is to
    cancel the worker task directly; both paths exit cleanly (task 7.3).
    """
    q = queue if queue is not None else get_ingest_queue()
    await q.put(STOP)


class Worker:
    """Thin start/stop wrapper around :func:`run_worker` for the lifespan (7.3).

    ``start`` launches the drain loop as an ``asyncio`` task; ``stop`` requests a
    clean stop (STOP sentinel), waits briefly, then cancels if still running.
    Kept minimal — the lifespan wiring itself is task 7.3 and is not done here.
    """

    def __init__(
        self,
        queue: "asyncio.Queue[Any] | None" = None,
        *,
        config: ComparisonConfig | None = None,
    ) -> None:
        self._queue = queue if queue is not None else get_ingest_queue()
        self._config = config if config is not None else comparison_config
        self.stats = WorkerStats()
        self._task: asyncio.Task[Any] | None = None

    def start(self) -> asyncio.Task[Any]:
        """Start the worker as a background task (idempotent)."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(
                run_worker(self._queue, config=self._config, stats=self.stats),
                name="sc-background-worker",
            )
            logger.info("worker: background task created")
        return self._task

    async def stop(self, *, timeout: float = 5.0) -> None:
        """Request a clean stop, then cancel if the task does not finish in time."""
        if self._task is None:
            return
        await request_stop(self._queue)
        try:
            await asyncio.wait_for(asyncio.shield(self._task), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("worker: clean stop timed out; cancelling task")
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
