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
const SOURCE_ORDER: SCSource[] = ["LAIR", "FAIR", "SHQ"];

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

function isMissing(value: string | number | null | undefined): boolean {
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
function referenceSource(
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
function computeOutliers(
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
type CellState = "missing" | "reference" | "outlier" | "neutral";

function cellState(
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
