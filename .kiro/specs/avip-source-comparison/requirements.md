# Requirements Document

## Introduction

This feature adds a production-shaped **source-comparison capability** to the
existing **AVIP** (AI Vision Inspection Platform) portal. It ingests quality
inspection records from three sources — **LAIR** (Last Article Inspection
Report), **FAIR** (First Article Inspection Report), and **SHQ** — reconciles
them by a common key (part number + lot number), flags discrepancies across a
comprehensive semiconductor-inspection field set, routes every flagged
discrepancy through a **human review gate**, and produces a filterable,
exportable discrepancy report as a native AVIP screen.

This is the production-grade successor to the completed pilot documented at
`kiro-spec/lair-fair-shq-comparison/` (requirements.md, design.md). The core
pilot behaviors are inherited and preserved: alignment by common key,
rule-based/statistical/LLM-assisted comparison, a mandatory human review gate,
and a clear discrepancy report. This successor differs from the pilot in five
deliberate ways, all confirmed with stakeholders:

1. It is built **into AVIP** (new backend router + services + models + SQLite
   tables; new frontend component area + route + sidebar entry) using AVIP's
   existing conventions — FastAPI under `/api/v1`, SQLite via `aiosqlite`,
   React 18 + TypeScript (strict) + Tailwind v3 + React Query v5 + Recharts,
   the shared `AppLayout`, the shared API client, and the review-workbench UX.
2. Ingestion is **near-real-time and continuous** through a **pluggable source
   interface**, fed for now by a realistic **simulator** rather than a
   one-shot folder scan.
3. The comparison operates over a **comprehensive, configurable field set**
   spanning numeric, categorical, identifier, and free-text field types.
4. The **LLM** used for free-text comparison is **pluggable** (provider
   interface) with a **mock default**, swappable via configuration later, and
   its output always routes through the review gate.
5. The application code and architecture are **production quality** (domain
   models, service layer, input validation, structured error handling,
   background processing, observability hooks, tests) while keeping AVIP's
   **existing infrastructure** — SQLite and the current auth approach. No
   Postgres, no portal-wide auth/role changes, and **cloud deployment is out
   of scope**.

The pilot's `[CONFIRM]` discipline is retained for items that remain genuinely
open with the client. Items settled by the confirmed scope decisions above are
resolved in this document and are no longer marked `[CONFIRM]`.

## Glossary

- **AVIP**: AI Vision Inspection Platform — the existing portal into which this
  feature is integrated (FastAPI backend, React/TypeScript frontend, SQLite).
- **LAIR**: Last Article Inspection Report — one of three ingested source
  record types.
- **FAIR**: First Article Inspection Report — one of three ingested source
  record types.
- **SHQ**: The third ingested source record type, and the source whose
  measurement methodology serves as the benchmark for numeric-threshold checks
  (`[CONFIRM]` — exact benchmark methodology still to be confirmed with client).
- **IQA**: Incoming Quality Assurance — the existing AVIP review function whose
  workbench UX patterns this feature reuses.
- **Common Key**: The identifier used to align records across all three
  sources — the combination of part number and lot number.
- **Comparison Service**: The AVIP backend component that classifies each
  in-scope field and dispatches it to the appropriate comparison check.
- **Source Adapter**: An implementation of the pluggable source interface that
  supplies records for one source (LAIR, FAIR, or SHQ). The default adapter is
  a simulator; real enterprise system adapters can be added later.
- **Ingestion API**: The internal AVIP endpoint to which a real enterprise
  source system, or the simulator, pushes source records.
- **Near-real-time**: Records arrive continuously over time and are processed
  as they arrive, rather than in a single batch scan. Target end-to-end
  processing latency is defined in Requirement 8.
- **Review Gate**: The mandatory human-review step. No flagged discrepancy is
  treated as final or presented as a decision until a reviewer confirms it.
- **Provenance**: The identifier of the specific check (exact-match rule,
  numeric threshold, or LLM-assisted comparison) that produced a given flag.
- **LLM Provider**: A pluggable implementation used only for free-text field
  comparison. The default implementation is a mock; a real provider is
  swappable via configuration.
- **Discrepancy**: A per-part/lot, per-field finding that source values differ
  beyond the applicable rule or threshold.
- **[CONFIRM]**: A convention marking an open item not yet resolved with the
  client. `[CONFIRM]` items MUST be surfaced (logged and shown in the UI)
  rather than silently resolved with an assumption in the implementation.

## Requirements

### Requirement 1: Continuous Ingestion via Pluggable Source Interface

**User Story:** As a quality engineer, I want LAIR, FAIR, and SHQ records to be
ingested continuously through a pluggable source interface, so that the
platform reflects new inspection data as it arrives without a manual batch run.

#### Acceptance Criteria

1. THE AVIP_Source_Comparison_Service SHALL expose a pluggable Source_Adapter
   interface that supplies records for a named source of LAIR, FAIR, or SHQ.
2. THE AVIP_Source_Comparison_Service SHALL provide a simulator Source_Adapter
   as the default that emits LAIR, FAIR, and SHQ records continuously over
   time.
3. THE AVIP_Source_Comparison_Service SHALL expose an internal Ingestion_API
   endpoint under `/api/v1` that accepts source records pushed by a
   Source_Adapter or an external source system.
4. WHEN a source record is received through the Ingestion_API or a
   Source_Adapter, THE AVIP_Source_Comparison_Service SHALL persist the record
   in a new SQLite table using the existing AVIP database layer.
5. THE AVIP_Source_Comparison_Service SHALL process records through a
   background worker as records arrive rather than requiring a manual batch
   trigger.
6. WHEN a received record does not conform to the required ingestion schema,
   THE AVIP_Source_Comparison_Service SHALL reject the record with an error
   response that names the source and the record identifier and SHALL record
   the rejection.
7. IF ingestion of a record fails, THEN THE AVIP_Source_Comparison_Service
   SHALL retain the offending record and its error in a rejected-records store
   rather than discarding the record.

### Requirement 2: Alignment of Streamed Records by Common Key

**User Story:** As a quality reviewer, I want incoming records aligned by the
common key as they arrive, so that partial groups are visible and no record is
lost while later data is still arriving.

#### Acceptance Criteria

1. WHEN a record is ingested, THE AVIP_Source_Comparison_Service SHALL align it
   with existing records that share the same Common_Key of part number and lot
   number.
2. WHERE a Common_Key has records from only one or two of the three sources at
   a given time, THE AVIP_Source_Comparison_Service SHALL represent the group
   as a partial group and SHALL retain it for later completion.
3. WHEN a later record arrives for an existing partial group, THE
   AVIP_Source_Comparison_Service SHALL attach the record to that group and
   SHALL re-evaluate the group's alignment state.
4. THE AVIP_Source_Comparison_Service SHALL record, for each aligned group,
   which of the three sources are present and which are absent.
5. IF a record cannot be assigned to any Common_Key, THEN THE
   AVIP_Source_Comparison_Service SHALL flag the record as unmatched and SHALL
   retain it rather than discarding the record.

### Requirement 3: Comprehensive Configurable Field Set

**User Story:** As a quality engineer, I want the comparison to cover a broad,
configurable set of semiconductor-inspection fields, so that all relevant
inspection attributes are reconciled and the field set can evolve without code
changes.

#### Acceptance Criteria

1. THE AVIP_Source_Comparison_Service SHALL support a configurable field set
   that includes numeric fields, categorical fields, identifier fields, and
   free-text fields.
2. THE AVIP_Source_Comparison_Service SHALL support numeric fields including
   diameter, thickness, flatness, and hardness.
3. THE AVIP_Source_Comparison_Service SHALL support categorical fields
   including material grade, coating or finish, surface or visual attributes,
   and supplier.
4. THE AVIP_Source_Comparison_Service SHALL support identifier fields including
   part number, lot number, and serial number.
5. THE AVIP_Source_Comparison_Service SHALL support free-text fields including
   inspector notes and comments.
6. THE AVIP_Source_Comparison_Service SHALL determine which comparison check
   applies to a field from that field's configured type rather than from a
   hardcoded field list.
7. WHERE a field is not marked in scope for comparison in the configuration,
   THE AVIP_Source_Comparison_Service SHALL exclude that field from comparison.

### Requirement 4: Automated Discrepancy Detection with Provenance

**User Story:** As a quality reviewer, I want discrepancies flagged
automatically with a record of which check produced each flag, so that I only
review genuine mismatches and can trust their origin.

#### Acceptance Criteria

1. WHEN an aligned group contains a categorical or identifier field present in
   more than one source, THE Comparison_Service SHALL apply an exact-match
   check and SHALL flag the field if and only if the source values differ.
2. WHEN an aligned group contains a numeric field present in more than one
   source, THE Comparison_Service SHALL apply a statistical-threshold check
   using the per-field threshold from configuration and SHALL flag the field
   if and only if the deviation exceeds that threshold.
3. WHERE a field is classified as free-text and is in scope, THE
   Comparison_Service SHALL use the LLM-assisted check for that field only and
   SHALL NOT use the LLM-assisted check for numeric, categorical, or identifier
   fields.
4. WHEN the Comparison_Service produces a discrepancy, THE Comparison_Service
   SHALL attach Provenance identifying the check that produced the flag.
5. WHEN records for a field agree within the applicable rule or threshold, THE
   Comparison_Service SHALL NOT flag that field.

### Requirement 5: Pluggable LLM Provider for Free-Text Comparison

**User Story:** As a platform maintainer, I want the free-text comparison to
use a pluggable LLM provider that defaults to a mock, so that the feature runs
without external dependencies and a real provider can be enabled later without
code changes.

#### Acceptance Criteria

1. THE AVIP_Source_Comparison_Service SHALL define an LLM_Provider interface
   used only for free-text field comparison.
2. THE AVIP_Source_Comparison_Service SHALL use a mock LLM_Provider
   implementation as the default.
3. WHERE configuration selects a different LLM_Provider, THE
   AVIP_Source_Comparison_Service SHALL use the configured provider without
   requiring code changes.
4. WHEN the LLM_Provider produces a free-text discrepancy, THE
   AVIP_Source_Comparison_Service SHALL enter that discrepancy into the
   Review_Gate as pending and SHALL NOT mark it confirmed automatically.
5. IF the configured LLM_Provider is unavailable or returns an error, THEN THE
   AVIP_Source_Comparison_Service SHALL route the affected free-text field to
   manual review with Provenance indicating provider unavailability and SHALL
   NOT treat the field as agreeing.

### Requirement 6: Human Review Gate Integrated into AVIP Review UX

**User Story:** As an IQA reviewer, I want to review flagged discrepancies in a
workbench consistent with AVIP's existing review experience, so that I can
confirm or dismiss each flag before it becomes final.

#### Acceptance Criteria

1. WHEN a discrepancy is flagged, THE AVIP_Source_Comparison_Service SHALL
   present the discrepancy in a review interface before the discrepancy is
   included in any final report.
2. THE Review_Gate SHALL present flagged discrepancies using AVIP's existing
   review-workbench UX patterns within the shared AppLayout.
3. WHEN a reviewer confirms or dismisses a flagged discrepancy, THE
   AVIP_Source_Comparison_Service SHALL record the decision, the reviewer
   identity, and an optional reviewer note against the discrepancy.
4. WHILE a flagged discrepancy has not been confirmed by a reviewer, THE
   AVIP_Source_Comparison_Service SHALL exclude that discrepancy from the final
   report.
5. THE AVIP_Source_Comparison_Service SHALL exclude any dismissed discrepancy
   from the final report.

### Requirement 7: Discrepancy Report and Dashboard Screen

**User Story:** As a quality reviewer, I want a clear, filterable, exportable
discrepancy report as an AVIP screen, so that I can present confirmed findings
without additional explanation.

#### Acceptance Criteria

1. WHEN confirmed discrepancies exist, THE AVIP_Source_Comparison_Service SHALL
   render a discrepancy report as an AVIP screen accessible from a sidebar
   entry.
2. WHEN the report is rendered, THE AVIP_Source_Comparison_Service SHALL show,
   for each confirmed discrepancy, the part and lot identifier, the field name,
   the value from each present source, and the Provenance that produced the
   flag.
3. THE AVIP_Source_Comparison_Service SHALL allow the report to be filtered by
   part, lot, source, field, and Provenance.
4. THE AVIP_Source_Comparison_Service SHALL allow the report to be exported to
   a downloadable file.
5. THE AVIP_Source_Comparison_Service SHALL render the report so that a
   non-technical reviewer can interpret the findings without additional
   explanation from the delivery team.

### Requirement 8: Configuration of Comparison Behavior

**User Story:** As a quality engineer, I want in-scope fields, thresholds, the
common-key definition, and the AI provider to be configurable rather than
hardcoded, so that I can tune the comparison without engineering changes.

#### Acceptance Criteria

1. THE AVIP_Source_Comparison_Service SHALL read the set of in-scope fields
   from configuration.
2. THE AVIP_Source_Comparison_Service SHALL read the per-field numeric
   threshold for each numeric field from configuration.
3. THE AVIP_Source_Comparison_Service SHALL read the Common_Key definition from
   configuration.
4. THE AVIP_Source_Comparison_Service SHALL read the selected LLM_Provider from
   configuration.
5. IF a `[CONFIRM]` configuration item remains set to its placeholder value,
   THEN THE AVIP_Source_Comparison_Service SHALL emit a logged warning naming
   the unresolved item and SHALL surface the unresolved item in the report
   header rather than substituting a default silently.

### Requirement 9: Production-Quality Non-Functional Behavior

**User Story:** As a platform maintainer, I want the feature to behave
predictably under continuous load with no data loss and full auditability, so
that it is trustworthy in a production-shaped setting.

#### Acceptance Criteria

1. WHEN a record is ingested during continuous operation, THE
   AVIP_Source_Comparison_Service SHALL complete alignment and comparison for
   that record within 5 seconds under expected simulator load (`[CONFIRM]`
   target latency and load profile with client).
2. THE AVIP_Source_Comparison_Service SHALL persist every ingested record,
   every aligned group, every discrepancy, and every review decision so that no
   ingested record is lost.
3. WHEN a review decision is recorded, THE AVIP_Source_Comparison_Service SHALL
   store an audit entry capturing the reviewer identity, the decision, the
   reviewer note, and the decision timestamp.
4. THE AVIP_Source_Comparison_Service SHALL emit structured logs for ingestion,
   comparison, and review events for observability.
5. WHEN the LLM_Provider is unavailable, THE AVIP_Source_Comparison_Service
   SHALL continue ingesting, aligning, and comparing non-free-text fields
   without interruption.
6. THE AVIP_Source_Comparison_Service SHALL store its data in new SQLite tables
   through the existing AVIP database layer and SHALL NOT introduce a different
   database system or portal-wide authentication changes.
