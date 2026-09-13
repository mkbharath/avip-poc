import {
  AlertTriangle,
  Equal,
  Ruler,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { SCFieldType, SCProvenance, SCSource, SCValues } from "../../types";

// ---------------------------------------------------------------------------
// Shared presentational pieces for the Source Comparison feature.
//
// These are PURE presentation components: no data fetching, no query keys, no
// behavioral logic. They exist so the review list and the report render the
// same polished, readable table cells.
// ---------------------------------------------------------------------------

// The three sources, rendered in a consistent order everywhere.
export const SOURCE_ORDER: SCSource[] = ["LAIR", "FAIR", "SHQ"];

// Non-technical-reviewer-friendly labels for the field types.
const FIELD_TYPE_LABELS: Record<string, string> = {
  numeric: "Measurement",
  categorical: "Category",
  identifier: "Identifier",
  free_text: "Free text",
};

// ---------------------------------------------------------------------------
// ProvenancePill — color-coded pill with a small lucide icon per provenance.
// ---------------------------------------------------------------------------

interface ProvenanceStyle {
  icon: LucideIcon;
  label: string;
  className: string;
  iconClassName: string;
}

const PROVENANCE_STYLES: Record<SCProvenance, ProvenanceStyle> = {
  "numeric-threshold": {
    icon: Ruler,
    label: "Number tolerance",
    className: "bg-blue-50 border-blue-200 text-blue-700",
    iconClassName: "text-blue-500",
  },
  "exact-match": {
    icon: Equal,
    label: "Exact match",
    className: "bg-indigo-50 border-indigo-200 text-indigo-700",
    iconClassName: "text-indigo-500",
  },
  llm: {
    icon: Sparkles,
    label: "AI text review",
    className: "bg-amber-50 border-amber-200 text-amber-700",
    iconClassName: "text-amber-500",
  },
  "llm-unavailable": {
    icon: AlertTriangle,
    label: "Needs manual check",
    className: "bg-red-50 border-red-200 text-red-700",
    iconClassName: "text-red-500",
  },
};

export function ProvenancePill({ provenance }: { provenance: SCProvenance }) {
  const style = PROVENANCE_STYLES[provenance];
  const Icon = style.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium whitespace-nowrap",
        style.className
      )}
    >
      <Icon className={cn("size-3.5 shrink-0", style.iconClassName)} />
      {style.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// ProvenancePillCount — a compact chip that reuses the same provenance color /
// icon mapping as ProvenancePill, but shows a COUNT instead of the full label.
// Used in group summaries where several provenance types are tallied side by
// side. Guards gracefully against unknown provenance keys coming from the
// backend's provenance_counts map.
// ---------------------------------------------------------------------------

export function ProvenancePillCount({
  provenance,
  count,
}: {
  provenance: string;
  count: number;
}) {
  const style = PROVENANCE_STYLES[provenance as SCProvenance];

  // Unknown provenance key — render a neutral fallback chip so we never crash.
  if (!style) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600 whitespace-nowrap">
        {provenance}
        <span className="font-semibold tabular-nums">{count}</span>
      </span>
    );
  }

  const Icon = style.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium whitespace-nowrap",
        style.className
      )}
      title={`${style.label}: ${count}`}
    >
      <Icon className={cn("size-3 shrink-0", style.iconClassName)} />
      <span className="tabular-nums font-semibold">{count}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// PartLotCell — bold mono part number with a muted lot beneath.
// ---------------------------------------------------------------------------

export function PartLotCell({
  partNumber,
  lotNumber,
}: {
  partNumber: string;
  lotNumber: string;
}) {
  return (
    <div className="flex flex-col leading-tight">
      <span className="font-mono text-sm font-bold text-slate-900">
        {partNumber}
      </span>
      <span className="font-mono text-xs text-slate-500">Lot {lotNumber}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// FieldLabel — humanized field name (strong) with the friendly type below.
// ---------------------------------------------------------------------------

export function FieldLabel({ name, type }: { name: string; type: SCFieldType }) {
  return (
    <div className="flex flex-col leading-tight">
      <span className="text-sm font-medium text-slate-900">
        {name.replace(/_/g, " ")}
      </span>
      <span className="text-xs text-slate-500">
        {FIELD_TYPE_LABELS[type] ?? type}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SourceValueCompare — the key piece. Renders LAIR / FAIR / SHQ as a compact
// 3-up grid, highlighting the value(s) that differ from the others.
// ---------------------------------------------------------------------------

export function isMissing(value: string | number | null | undefined): boolean {
  return value === null || value === undefined || value === "";
}

function normalize(value: string | number | null | undefined): string | null {
  if (isMissing(value)) return null;
  return String(value).trim().toLowerCase();
}

/**
 * Which source, if any, is the neutral "reference" for this field.
 *
 * For numeric fields SHQ is the authoritative reference: it is rendered in a
 * calm neutral style (never amber) and only the OTHER sources that deviate
 * from it are emphasized.
 */
export function referenceSource(
  values: SCValues,
  fieldType: SCFieldType
): SCSource | null {
  if (fieldType === "numeric" && !isMissing(values.SHQ)) return "SHQ";
  return null;
}

/**
 * Determine which sources should be highlighted as outliers, keeping the
 * highlight MEANINGFUL rather than painting everything amber.
 *
 * - Numeric fields: SHQ is the reference. Any present source whose value
 *   differs from SHQ is highlighted; SHQ itself stays neutral. (If SHQ is
 *   missing, fall back to the majority rule below.)
 * - Categorical / identifier / free_text: highlight only the minority
 *   value(s) — the ones that differ from a clear MAJORITY. If there is no
 *   majority (every present value is distinct, or a 1-vs-1 tie), nothing is
 *   highlighted — the amber ProvenancePill remains the "this is flagged"
 *   signal, so we avoid lighting up every cell.
 *
 * Works with either 2 or 3 present sources. If every present source agrees,
 * nothing is highlighted.
 */
export function computeOutliers(
  values: SCValues,
  fieldType: SCFieldType
): Set<SCSource> {
  const present = SOURCE_ORDER.filter((s) => !isMissing(values[s]));
  const outliers = new Set<SCSource>();

  // Fewer than two values to compare — nothing to flag.
  if (present.length < 2) return outliers;

  if (referenceSource(values, fieldType) === "SHQ") {
    const reference = normalize(values.SHQ);
    for (const source of present) {
      if (source === "SHQ") continue;
      if (normalize(values[source]) !== reference) {
        outliers.add(source);
      }
    }
    return outliers;
  }

  // Majority rule: tally how many present sources share each normalized value.
  const counts = new Map<string, number>();
  for (const source of present) {
    const key = normalize(values[source]) ?? "";
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }

  // All present sources agree — no outliers.
  if (counts.size <= 1) return outliers;

  const maxCount = Math.max(...counts.values());

  // No clear majority: every value is a minority (all distinct, or an even
  // tie). Highlighting all of them would just be noise, so highlight nothing
  // and let the ProvenancePill carry the "flagged" meaning.
  const majorityGroups = [...counts.values()].filter((c) => c === maxCount).length;
  const hasClearMajority = maxCount > 1 && majorityGroups === 1;
  if (!hasClearMajority) return outliers;

  // Highlight the values that are NOT part of the single majority group.
  for (const source of present) {
    const key = normalize(values[source]) ?? "";
    if ((counts.get(key) ?? 0) < maxCount) {
      outliers.add(source);
    }
  }

  return outliers;
}

// The visual state a single source cell can take.
export type CellState = "missing" | "reference" | "outlier" | "neutral";

export function cellState(
  source: SCSource,
  values: SCValues,
  reference: SCSource | null,
  outliers: Set<SCSource>
): CellState {
  if (isMissing(values[source])) return "missing";
  if (source === reference) return "reference";
  if (outliers.has(source)) return "outlier";
  return "neutral";
}

export function SourceValueCompare({
  values,
  fieldType,
}: {
  values: SCValues;
  fieldType: SCFieldType;
}) {
  const reference = referenceSource(values, fieldType);
  const outliers = computeOutliers(values, fieldType);

  // Free text (full-sentence values) gets a vertical stacked layout so long
  // values have room and stay on a single truncated line per source. Short
  // value types keep the compact 3-up grid.
  if (fieldType === "free_text") {
    return (
      <div className="flex w-full min-w-0 flex-col gap-1.5">
        {SOURCE_ORDER.map((source) => {
          const raw = values[source];
          const state = cellState(source, values, reference, outliers);
          return (
            <SourceValueRow key={source} source={source} value={raw} state={state} />
          );
        })}
      </div>
    );
  }

  return (
    <div className="grid w-full min-w-0 grid-cols-3 gap-2">
      {SOURCE_ORDER.map((source) => {
        const raw = values[source];
        const state = cellState(source, values, reference, outliers);
        return (
          <SourceValueTile key={source} source={source} value={raw} state={state} />
        );
      })}
    </div>
  );
}

// Shared per-state styling. Highlighting is deliberately restrained: outliers
// get amber text plus a subtle amber-50 background (no heavy ring), the numeric
// reference gets a calm slate/blue treatment, everything else stays neutral.
const TILE_STYLES: Record<CellState, string> = {
  missing: "border-slate-200 bg-slate-50/60",
  reference: "border-blue-200 bg-blue-50/60",
  outlier: "border-amber-200 bg-amber-50",
  neutral: "border-slate-200 bg-slate-50",
};

const VALUE_TEXT_STYLES: Record<CellState, string> = {
  missing: "text-slate-300",
  reference: "text-slate-900",
  outlier: "text-amber-900",
  neutral: "text-slate-900",
};

function SourceValueTile({
  source,
  value,
  state,
}: {
  source: SCSource;
  value: string | number | null | undefined;
  state: CellState;
}) {
  const missing = state === "missing";
  return (
    <div
      className={cn(
        "flex min-w-0 flex-col items-start gap-0.5 overflow-hidden rounded-md border px-2.5 py-2",
        TILE_STYLES[state]
      )}
    >
      <span className="flex w-full items-center gap-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
        {source}
        {state === "reference" ? (
          <span className="rounded-sm bg-blue-100 px-1 text-[9px] font-semibold text-blue-700">
            ref
          </span>
        ) : null}
      </span>
      <span
        className={cn(
          "block w-full min-w-0 truncate text-left font-mono text-sm font-medium tabular-nums",
          VALUE_TEXT_STYLES[state]
        )}
        title={missing ? undefined : String(value)}
      >
        {missing ? "—" : String(value)}
      </span>
    </div>
  );
}

function SourceValueRow({
  source,
  value,
  state,
}: {
  source: SCSource;
  value: string | number | null | undefined;
  state: CellState;
}) {
  const missing = state === "missing";
  return (
    <div
      className={cn(
        "flex w-full min-w-0 items-center gap-2 overflow-hidden rounded-md border px-2 py-1.5",
        TILE_STYLES[state],
        // A subtle amber left accent gives outliers a "differs" affordance
        // without a heavy full-cell treatment.
        state === "outlier" && "border-l-2 border-l-amber-400"
      )}
    >
      <span className="w-12 shrink-0 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
        {source}
      </span>
      <span
        className={cn(
          "min-w-0 flex-1 truncate text-sm",
          missing ? "font-mono text-slate-300" : VALUE_TEXT_STYLES[state]
        )}
        title={missing ? undefined : String(value)}
      >
        {missing ? "—" : String(value)}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SourceValueCompareCard — a card-friendly variant of SourceValueCompare.
//
// Cards have more room than table cells, so this variant leans into that:
//   - numeric / categorical / identifier: a clean 3-up row of taller value
//     chips (equal width) with the source label small-uppercase ABOVE the
//     value, and the numeric SHQ reference shown as a neutral "REF".
//   - free_text: the three sources stacked vertically with the full value
//     readable across up to three lines (line-clamp-3) instead of a single
//     truncated line, plus a title tooltip for the complete text.
//
// It reuses the exact same referenceSource / computeOutliers / cellState
// logic as SourceValueCompare — no comparison logic is duplicated or changed.
// ---------------------------------------------------------------------------

export function SourceValueCompareCard({
  values,
  fieldType,
}: {
  values: SCValues;
  fieldType: SCFieldType;
}) {
  const reference = referenceSource(values, fieldType);
  const outliers = computeOutliers(values, fieldType);

  if (fieldType === "free_text") {
    return (
      <div className="flex w-full min-w-0 flex-col gap-2">
        {SOURCE_ORDER.map((source) => {
          const state = cellState(source, values, reference, outliers);
          return (
            <SourceValueCardRow
              key={source}
              source={source}
              value={values[source]}
              state={state}
            />
          );
        })}
      </div>
    );
  }

  return (
    <div className="grid w-full min-w-0 grid-cols-3 gap-2">
      {SOURCE_ORDER.map((source) => {
        const state = cellState(source, values, reference, outliers);
        return (
          <SourceValueCardTile
            key={source}
            source={source}
            value={values[source]}
            state={state}
          />
        );
      })}
    </div>
  );
}

function SourceValueCardTile({
  source,
  value,
  state,
}: {
  source: SCSource;
  value: string | number | null | undefined;
  state: CellState;
}) {
  const missing = state === "missing";
  return (
    <div
      className={cn(
        "flex min-w-0 flex-col items-start gap-1 rounded-lg border px-3 py-2.5",
        TILE_STYLES[state]
      )}
    >
      <span className="flex w-full items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        {source}
        {state === "reference" ? (
          <span className="rounded-sm bg-blue-100 px-1 text-[9px] font-semibold text-blue-700">
            REF
          </span>
        ) : null}
      </span>
      <span
        className={cn(
          "block w-full min-w-0 break-words [overflow-wrap:anywhere] text-left font-mono text-sm font-medium tabular-nums",
          VALUE_TEXT_STYLES[state]
        )}
        title={missing ? undefined : String(value)}
      >
        {missing ? "—" : String(value)}
      </span>
    </div>
  );
}

function SourceValueCardRow({
  source,
  value,
  state,
}: {
  source: SCSource;
  value: string | number | null | undefined;
  state: CellState;
}) {
  const missing = state === "missing";
  return (
    <div
      className={cn(
        "flex w-full min-w-0 flex-col gap-1 rounded-lg border px-3 py-2",
        TILE_STYLES[state],
        state === "outlier" && "border-l-2 border-l-amber-400"
      )}
    >
      <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        {source}
      </span>
      <span
        className={cn(
          "block w-full min-w-0 text-sm leading-snug break-words [overflow-wrap:anywhere] line-clamp-3",
          missing ? "font-mono text-slate-300" : VALUE_TEXT_STYLES[state]
        )}
        title={missing ? undefined : String(value)}
      >
        {missing ? "—" : String(value)}
      </span>
    </div>
  );
}

// ===========================================================================
// CARD-FEED HELPERS
//
// The pieces below power the "Source Comparison Review" CARD FEED. They are
// pure presentation + tiny pure functions that REUSE the exact same
// referenceSource / computeOutliers / cellState comparison logic above — no
// comparison rule is duplicated or changed here.
// ===========================================================================

// ---------------------------------------------------------------------------
// Accent color per detection type — drives the card's colored accent bar and
// the quiet "how detected" tag so the reviewer can scan by color:
//   numeric-threshold -> blue, exact-match -> indigo,
//   llm (AI text)     -> amber, llm-unavailable -> red.
// ---------------------------------------------------------------------------

export interface CardAccent {
  /** Tailwind bg-* for the thin top accent bar. */
  bar: string;
  /** Muted text color for the tiny "how detected" tag. */
  tagText: string;
  /** Plain-words description of how the difference was detected. */
  detectLabel: string;
}

const CARD_ACCENTS: Record<SCProvenance, CardAccent> = {
  "numeric-threshold": {
    bar: "bg-blue-500",
    tagText: "text-blue-600",
    detectLabel: "Measurement check",
  },
  "exact-match": {
    bar: "bg-indigo-500",
    tagText: "text-indigo-600",
    detectLabel: "Exact match",
  },
  llm: {
    bar: "bg-amber-500",
    tagText: "text-amber-600",
    detectLabel: "AI text review",
  },
  "llm-unavailable": {
    bar: "bg-red-500",
    tagText: "text-red-600",
    detectLabel: "Needs manual check",
  },
};

export function cardAccent(provenance: SCProvenance): CardAccent {
  return (
    CARD_ACCENTS[provenance] ?? {
      bar: "bg-slate-300",
      tagText: "text-slate-500",
      detectLabel: "Flagged",
    }
  );
}

// ---------------------------------------------------------------------------
// humanizeField — "coating_finish" -> "Coating Finish".
// ---------------------------------------------------------------------------

export function humanizeField(name: string): string {
  return name
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .split(" ")
    .map((w) => (w ? w.charAt(0).toUpperCase() + w.slice(1) : w))
    .join(" ");
}

// ---------------------------------------------------------------------------
// numericDelta — for numeric fields, the signed difference between an outlier
// source and the SHQ reference, formatted compactly. Returns null when it
// cannot be computed safely (missing values, non-numeric, no reference).
// ---------------------------------------------------------------------------

function toNumber(value: string | number | null | undefined): number | null {
  if (isMissing(value)) return null;
  const n = typeof value === "number" ? value : Number(String(value).trim());
  return Number.isFinite(n) ? n : null;
}

function formatDelta(delta: number): string {
  // Trim trailing zeros while keeping small deltas readable.
  const abs = Math.abs(delta);
  const str =
    abs >= 1
      ? abs.toFixed(2).replace(/\.?0+$/, "")
      : abs.toPrecision(2).replace(/\.?0+$/, "");
  return str;
}

// ---------------------------------------------------------------------------
// computeHeadline — the plain-language, human-terms headline for a card.
//
//   numeric      : "Diameter is off by 0.03" (delta vs SHQ) or
//                  "Diameter reading disagrees" fallback.
//   categorical  : "Coating Finish disagrees"
//   identifier   : "Serial Number doesn't match"
//   free_text    : "Inspector notes differ"
//
// It never throws and always returns a safe, readable sentence.
// ---------------------------------------------------------------------------

export function computeHeadline(item: {
  field_name: string;
  field_type: SCFieldType;
  values: SCValues;
}): string {
  const field = humanizeField(item.field_name);

  if (item.field_type === "free_text") {
    return "Inspector notes differ";
  }

  if (item.field_type === "numeric") {
    const reference = referenceSource(item.values, "numeric");
    const outliers = computeOutliers(item.values, "numeric");
    const ref = toNumber(item.values.SHQ);
    if (reference === "SHQ" && ref !== null && outliers.size > 0) {
      // Use the largest deviation from SHQ across highlighted sources.
      let biggest: number | null = null;
      for (const source of outliers) {
        const v = toNumber(item.values[source]);
        if (v === null) continue;
        const d = v - ref;
        if (biggest === null || Math.abs(d) > Math.abs(biggest)) biggest = d;
      }
      if (biggest !== null && biggest !== 0) {
        return `${field} is off by ${formatDelta(biggest)}`;
      }
    }
    return `${field} reading disagrees`;
  }

  // categorical / identifier
  if (item.field_type === "identifier") {
    return `${field} doesn't match`;
  }
  return `${field} disagrees`;
}

// ---------------------------------------------------------------------------
// SpotlightValues — the value presentation for a card. It SPOTLIGHTS the odd
// source(s) and DE-EMPHASIZES the agreeing ones so the reviewer instantly sees
// which source is out of line.
//
//   - Highlighted (outlier) sources render as a larger colored chip carrying
//     the source label + value (+ signed delta vs SHQ for numeric fields).
//   - The neutral / reference / agreeing sources render small and muted.
//   - free_text: the differing note is shown prominently; agreeing notes stay
//     quiet and clamped.
//   - If nothing computes as an outlier, all values render cleanly in the calm
//     muted style (no forced amber).
//
// Reuses referenceSource / computeOutliers / cellState verbatim.
// ---------------------------------------------------------------------------

export function SpotlightValues({
  values,
  fieldType,
}: {
  values: SCValues;
  fieldType: SCFieldType;
}) {
  const reference = referenceSource(values, fieldType);
  const outliers = computeOutliers(values, fieldType);
  const refNum = fieldType === "numeric" ? toNumber(values.SHQ) : null;

  const present = SOURCE_ORDER.filter((s) => !isMissing(values[s]));
  const spotlighted = present.filter((s) => outliers.has(s));
  const quiet = present.filter((s) => !outliers.has(s));

  if (fieldType === "free_text") {
    return (
      <div className="flex flex-col gap-2">
        {spotlighted.map((source) => (
          <FreeTextSpotlight
            key={source}
            source={source}
            value={values[source]}
            emphasized
          />
        ))}
        {quiet.map((source) => (
          <FreeTextSpotlight
            key={source}
            source={source}
            value={values[source]}
            emphasized={false}
          />
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2.5">
      {/* Spotlighted odd-one-out value(s) — larger colored chips. */}
      {spotlighted.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {spotlighted.map((source) => {
            const delta =
              refNum !== null ? computeSignedDelta(values[source], refNum) : null;
            return (
              <ValueSpotlightChip
                key={source}
                source={source}
                value={values[source]}
                delta={delta}
              />
            );
          })}
        </div>
      )}

      {/* Quiet, agreeing / reference values — small muted row. */}
      {quiet.length > 0 && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          {quiet.map((source) => {
            const state = cellState(source, values, reference, outliers);
            return (
              <QuietValue
                key={source}
                source={source}
                value={values[source]}
                isReference={state === "reference"}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

function computeSignedDelta(
  value: string | number | null | undefined,
  ref: number
): string | null {
  const v = toNumber(value);
  if (v === null) return null;
  const d = v - ref;
  if (d === 0) return null;
  return `${d > 0 ? "+" : "−"}${formatDelta(d)}`;
}

// A bold, colored chip for the differing value — the visual focal point.
function ValueSpotlightChip({
  source,
  value,
  delta,
}: {
  source: SCSource;
  value: string | number | null | undefined;
  delta: string | null;
}) {
  return (
    <div className="inline-flex items-baseline gap-2 rounded-xl border border-amber-300 bg-amber-50 px-3.5 py-2">
      <span className="text-[10px] font-bold uppercase tracking-wide text-amber-700">
        {source}
      </span>
      <span className="font-mono text-lg font-semibold tabular-nums text-amber-900 [overflow-wrap:anywhere]">
        {isMissing(value) ? "—" : String(value)}
      </span>
      {delta ? (
        <span className="font-mono text-xs font-semibold tabular-nums text-amber-600">
          {delta}
        </span>
      ) : null}
    </div>
  );
}

// A small muted inline value for the sources that agree / the reference.
function QuietValue({
  source,
  value,
  isReference,
}: {
  source: SCSource;
  value: string | number | null | undefined;
  isReference: boolean;
}) {
  return (
    <span className="inline-flex items-baseline gap-1.5 text-xs text-slate-500">
      <span className="font-semibold uppercase tracking-wide text-slate-400">
        {source}
      </span>
      <span className="font-mono tabular-nums text-slate-600 [overflow-wrap:anywhere]">
        {isMissing(value) ? "—" : String(value)}
      </span>
      {isReference ? (
        <span className="rounded-sm bg-blue-100 px-1 text-[9px] font-semibold text-blue-700">
          REF
        </span>
      ) : null}
    </span>
  );
}

// Free-text: the differing note prominent, agreeing notes quiet + clamped.
function FreeTextSpotlight({
  source,
  value,
  emphasized,
}: {
  source: SCSource;
  value: string | number | null | undefined;
  emphasized: boolean;
}) {
  const missing = isMissing(value);
  if (emphasized) {
    return (
      <div className="rounded-xl border border-amber-300 bg-amber-50 px-3.5 py-2.5">
        <span className="text-[10px] font-bold uppercase tracking-wide text-amber-700">
          {source}
        </span>
        <p className="mt-0.5 text-sm leading-snug text-amber-900 [overflow-wrap:anywhere]">
          {missing ? "—" : String(value)}
        </p>
      </div>
    );
  }
  return (
    <div className="rounded-lg px-1">
      <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
        {source}
      </span>
      <p
        className="mt-0.5 text-xs leading-snug text-slate-500 line-clamp-2 [overflow-wrap:anywhere]"
        title={missing ? undefined : String(value)}
      >
        {missing ? "—" : String(value)}
      </p>
    </div>
  );
}
