# PCBA TPI Generation — Demonstration Walkthrough

**Feature:** pcba-tpi-generation · **Requirement:** 10.2 (end-to-end demonstration
over the sample PCBAs, observable through the UI)

This is a presenter's script for showing the full path —
**ingestion → extraction → generation → review → final TPI** — for the sample
PCBA set entirely inside the AVIP portal. It is meant to be followed live.
Everything runs on the **mock** multimodal LLM by default, so no API key or
network access is required.

> The sample inputs under `backend/sample_data/tpi/<PCBA-ID>/` are
> **clearly-marked fixtures pending real client samples** (see the fixtures
> `README.md` in this directory). They exist to exercise the pipeline, not to
> represent real Lam Research documents.

---

## 1. Prerequisites — start the portal

Two processes: the FastAPI backend and the React frontend.

### Backend (port 8000)

```bash
cd backend
AVIP_SC_SIMULATOR=false PYTHONPATH=. .venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- `AVIP_SC_SIMULATOR=false` keeps the source-comparison simulator's unbounded
  feed off so the demo stays quiet and focused on TPI.
- The TPI API is served under `/api/v1/tpi/*`.

### Frontend (port 3000)

```bash
cd frontend
npm run dev
```

Open **http://localhost:3000** and sign in as any operator. In the left sidebar
you'll see the **TPI Generation** group with three pipeline-ordered items:
**TPI Monitor → Review → Final TPIs**.

### LLM provider — mock by default, OpenAI by configuration

- **Default is the mock provider.** The multimodal LLM used for visual
  extraction and section drafting defaults to a deterministic mock
  (`MockMultimodalProvider`) — **no `OPENAI_API_KEY` needed, no network call.**
  The active provider is shown live on TPI Monitor ("LLM provider: mock").
- **Switching to a real provider is configuration-only, no code change.** The
  provider is selected by `get_multimodal_provider(...)`, which reads a
  `llm_provider` config value: `"mock"` (default) or `"openai"`. The OpenAI path
  mirrors the portal's existing vision-LLM env pattern:

  ```bash
  # backend/.env — the established AVIP vision-LLM pattern
  AVIP_VISION_LLM=true
  OPENAI_API_KEY=sk-...
  OPENAI_MODEL=gpt-4o
  ```

  The OpenAI client is constructed lazily (no network at import/construction),
  so selecting it never blocks startup.

  > **[CONFIRM] / known gap to state honestly in the demo:** the OpenAI
  > multimodal provider class and the wiring of an env flag into the TPI
  > `llm_provider` setting are not fully landed yet — the selector defaults to
  > mock and the mock is what the demo runs on. Presenting on mock is the
  > intended demo posture; the switch point is designed and in place, the real
  > provider is a configuration swap once confirmed.

---

## 2. The demo story — step by step

### Step 1 — Ingest the sample PCBAs (TPI Monitor)

1. Go to **TPI Monitor** (`/tpi/monitor`).
2. Click **"Ingest sample PCBAs"** (top-right, tagged **demo**). This seeds the
   four bundled sample PCBAs from the fixtures:
   - `PCBA-444-027654-002`
   - `PCBA-444-027654-003`
   - `PCBA-444-027654-004`
   - `PCBA-622-073891-010`
3. A toast confirms *"Ingested N sample PCBAs."* and **4 PCBA rows appear**, each
   with a **status badge** (Ingesting / Drafted / In review / Finalized — text +
   icon, not color alone).
4. **Expand one row** (chevron on the left) to show its **four inputs** with a
   **per-input status** (Ingested / Needs manual annotation) and a
   **detected-format** badge per input.
   - *Point out:* the two **visual inputs** (circuit diagram, drawing) report
     their **detected format honestly** — the format is a **[CONFIRM]** item, so
     the system detects and *reports* what it found rather than assuming.

### Step 2 — Process a PCBA (extraction → mapping → generation)

1. On a PCBA row, click **"Process"** (the button reads **"Re-process"** once a
   draft already exists).
2. The control shows **"Processing…"** and is disabled while it runs (no
   duplicate submissions). Behind it: extraction → mapping → draft generation,
   all on the **mock** provider.
3. On success a toast confirms *"Draft TPI generated for {PCBA}."* and the
   PCBA's **status badge moves to "Drafted."** A **"Review"** action appears on
   the row.

### Step 3 — Review the draft (Review → Workbench)

1. Go to **Review** (`/tpi/review`). The drafted TPI appears as a card showing
   its section count and how many sections are still incomplete.
2. Click **"Open"** to enter the deep-linkable workbench
   (`/tpi/review/{pcba_id}` — a stable, shareable URL).
3. Walk the **section-by-section workbench**:
   - **Provenance** — each section shows *"Derived from N source input(s)"* with
     the source-input id badges (traceability back to the inputs, Req 3.3).
   - **[INCOMPLETE] markers** — sections derived from a flagged input carry an
     **"Incomplete — pending manual annotation"** badge and a summary notice at
     the top; they're surfaced, never silently omitted.
   - **Inline edit** — edit a section's content, then **Save** (commits the edit
     locally) or **Discard** (reverts to the generated draft). An
     **unsaved-changes guard** warns before navigating away.
4. In the **Finalize TPI** panel, enter a **Reviewer** name (required — Finalize
   stays disabled and explains why until it's filled), optionally add a note,
   then click **Finalize**. A confirmation follows and you're taken to Final
   TPIs. Finalizing records the corrected sections as the final TPI and writes
   one audit entry (who / when / what changed).

### Step 4 — Final TPI (preview + export)

1. Go to **Final TPIs** (`/tpi/final`). The finalized TPI appears with a
   template-kind badge (**Placeholder template** by default — called out so it's
   never mistaken for a confirmed client format) and any remaining
   *N incomplete* count.
2. **Expand** the row to preview the finalized sections inline (numbered, with
   any **Incomplete** tags still visible).
3. Click **"Download PDF"** to export a **recognizable TPI document** via the
   portal's existing document-generation capability.

### Step 5 — Point out the honest open items

- On **TPI Monitor**, the amber **"Open items awaiting client confirmation"**
  banner lists the unresolved **[CONFIRM]** items (surfaced, never assumed): the
  pipeline runs on the documented placeholder until each is confirmed.
- On **Final TPIs**, the **"Side-by-side vs. human-authored TPI"** panel is
  shown as **CONFIRM / Pending** with a disabled **Compare** button — the
  comparison depends on the client providing a reference TPI, so it's honestly
  parked rather than faked.

---

## 3. What to emphasize for the stakeholder

- **Human-review gate.** No unreviewed AI output is ever treated as final. A
  draft only enters the final set after a named reviewer finalizes it, and every
  finalize writes an audit entry.
- **Provenance / traceability.** Every generated section links back to the
  source input(s) it was derived from, so a reviewer can judge each section in
  context.
- **Incomplete-section honesty.** Sections built from inputs that couldn't be
  parsed are marked **[INCOMPLETE]** and carried through to the preview — never
  dropped and never presented as complete.
- **Pluggable mock → real LLM.** Runs out of the box on a deterministic mock
  (no key, no network); a real multimodal provider is a **configuration swap**,
  no code change, mirroring the portal's `AVIP_VISION_LLM` / `OPENAI_API_KEY` /
  `OPENAI_MODEL` pattern.
- **Portal integration.** This is not a standalone script — it lives inside the
  AVIP portal, reusing the shared sidebar, component library, React Query
  patterns, the shared SQLite database (additive `tpi_*` tables), and the
  existing document-export capability.
- **Sample scope, clearly flagged.** The demo runs on 3–5 sample fixtures
  pending real client samples; visual-input format, the client TPI template, a
  human-authored reference TPI, and full-catalog size are all open **[CONFIRM]**
  items surfaced in the UI.

---

## 4. Talking points / FAQ — tying to the client questionnaire

Open items below map to the questionnaire's outstanding decisions. Each is
**surfaced in the UI** rather than silently resolved.

- **"What format are the circuit diagrams and drawings?"**
  Unconfirmed (CAD export / PDF / image). The fixtures are `.txt` stand-ins; the
  ingestion service **detects and reports** `detected_format` per input rather
  than assuming one. Real-format samples slot straight in.
- **"Can it match our TPI template?"**
  The client template isn't provided yet, so generation uses a **documented
  placeholder structure** (test steps, expected results, referenced equipment).
  The template is swappable without touching extraction; once the real template
  is confirmed, exports match it.
- **"How does it compare to a TPI our engineers wrote?"**
  A side-by-side comparison is built as a **conditional** affordance — it needs
  at least one human-authored reference TPI from the client. Until that's
  provided, the panel is shown as **Pending** rather than faked.
- **"Does it use a purpose-trained model?"**
  No — out of scope for this release. It runs on a pluggable multimodal LLM
  (mock by default; a general provider like OpenAI by configuration).
- **"Will this scale to the full catalog?"**
  Full-catalog coverage is out of scope for this release; catalog size is an
  open scaling item tracked in the questionnaire. The demo proves the capability
  on the sample set first.
- **"What about production infrastructure (managed DB, SSO, cloud deploy)?"**
  Deferred and tracked in the questionnaire, not in this feature. The feature is
  built to the production-grade code bar, but production infra decisions are
  separate.

---

*Fixtures and this walkthrough are development artifacts pending real client
samples. See `README.md` in this directory for the fixture layout and the full
list of open [CONFIRM] items.*
