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
 * Determine which sources should be highlighted as outliers.
 *
 * - Numeric fields: SHQ is the reference. Any present source whose value
 *   differs from SHQ is highlighted. (If SHQ is missing, fall back to the
 *   minority rule below.)
 * - Categorical / text / identifier: highlight the minority value(s) — the
 *   values shared by the fewest present sources.
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

  const useShqReference = fieldType === "numeric" && !isMissing(values.SHQ);

  if (useShqReference) {
    const reference = normalize(values.SHQ);
    for (const source of present) {
      if (source === "SHQ") continue;
      if (normalize(values[source]) !== reference) {
        outliers.add(source);
      }
    }
    return outliers;
  }

  // Minority rule: tally how many present sources share each normalized value.
  const counts = new Map<string, number>();
  for (const source of present) {
    const key = normalize(values[source]) ?? "";
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }

  // All present sources agree — no outliers.
  if (counts.size <= 1) return outliers;

  const maxCount = Math.max(...counts.values());
  for (const source of present) {
    const key = normalize(values[source]) ?? "";
    // A value is an outlier if it is NOT part of the majority group. When there
    // is a tie (e.g. two sources with different values), every distinct value
    // is a minority, so both get highlighted.
    if ((counts.get(key) ?? 0) < maxCount || maxCount === 1) {
      outliers.add(source);
    }
  }

  return outliers;
}

export function SourceValueCompare({
  values,
  fieldType,
}: {
  values: SCValues;
  fieldType: SCFieldType;
}) {
  const outliers = computeOutliers(values, fieldType);

  return (
    <div className="grid grid-cols-3 gap-1.5">
      {SOURCE_ORDER.map((source) => {
        const raw = values[source];
        const missing = isMissing(raw);
        const isOutlier = outliers.has(source);

        return (
          <div
            key={source}
            className={cn(
              "flex flex-col items-start rounded-md border px-2 py-1.5",
              missing
                ? "border-slate-200 bg-slate-50/60"
                : isOutlier
                  ? "border-amber-300 bg-amber-50 ring-1 ring-amber-300/60"
                  : "border-slate-200 bg-slate-50"
            )}
          >
            <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              {source}
            </span>
            <span
              className={cn(
                "font-mono text-sm font-medium",
                missing
                  ? "text-slate-300"
                  : isOutlier
                    ? "text-amber-900"
                    : "text-slate-900"
              )}
            >
              {missing ? "—" : String(raw)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
