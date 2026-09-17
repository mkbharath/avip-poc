import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2, AlertTriangle } from "lucide-react";
import { getDiscrepancy, decideDiscrepancy } from "../../api/source-comparison";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { SCProvenance } from "../../types";
import { cleanContextField, revisionLabel } from "./table-parts";

export function SourceComparisonWorkbench() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [reviewer, setReviewer] = useState("IQA Inspector");
  const [note, setNote] = useState("");

  const { data: discrepancy, isLoading, isError } = useQuery({
    queryKey: ["sc", "discrepancy", id],
    queryFn: () => getDiscrepancy(id!),
    enabled: !!id,
  });

  const decideMutation = useMutation({
    mutationFn: (decision: "confirmed" | "dismissed") =>
      decideDiscrepancy(id!, {
        decision,
        reviewer,
        note: note.trim() || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sc"] });
      navigate("/source-comparison/review");
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-3rem)]">
        <Loader2 className="w-8 h-8 text-lam-navy animate-spin" />
      </div>
    );
  }

  if (isError || !discrepancy) {
    return (
      <div className="p-6">
        <Button variant="ghost" size="sm" render={<Link to="/source-comparison/review" />}>
          <ArrowLeft className="mr-1" />
          Back to Review
        </Button>
        <div className="text-center py-20">
          <AlertTriangle className="w-16 h-16 text-muted-foreground/30 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-muted-foreground">Discrepancy not found</h3>
          <p className="text-sm text-muted-foreground/70 mt-1">
            The discrepancy you are looking for does not exist or has been removed.
          </p>
        </div>
      </div>
    );
  }

  // Human-readable part context (present when the part number is in the parts
  // table); falls back to just the identifiers when absent.
  const partDescription = cleanContextField(discrepancy.part_context?.description);
  const partRev = revisionLabel(discrepancy.part_context);

  const alreadyDecided = discrepancy.review_state !== "pending";
  const needsManualComparison =
    discrepancy.provenance === "llm-unavailable" || discrepancy.provenance === "llm";
  const canSubmit = reviewer.trim().length > 0 && !alreadyDecided;

  return (
    <div className="flex flex-col min-h-[calc(100vh-3rem)]">
      {/* Subheader */}
      <div className="flex items-center justify-between px-6 py-3 bg-background border-b">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" render={<Link to="/source-comparison/review" />}>
            <ArrowLeft className="mr-1" />
            Review
          </Button>
          <div className="w-px h-5 bg-border" />
          <div>
            {partDescription ? (
              <p className="text-xs font-medium text-slate-700">
                {partDescription}
                {partRev ? (
                  <span className="ml-1.5 font-normal text-slate-500">· {partRev}</span>
                ) : null}
              </p>
            ) : null}
            <h1 className="text-base font-bold text-foreground">
              {discrepancy.part_number} &bull; Lot {discrepancy.lot_number}
            </h1>
            <p className="text-xs text-slate-600 capitalize">
              {discrepancy.field_name.replace(/_/g, " ")} ({discrepancy.field_type.replace(/_/g, " ")})
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ProvenanceBadge provenance={discrepancy.provenance} />
          <Badge
            variant={
              discrepancy.review_state === "confirmed"
                ? "destructive"
                : discrepancy.review_state === "dismissed"
                  ? "outline"
                  : "secondary"
            }
            className="text-xs capitalize"
          >
            {discrepancy.review_state}
          </Badge>
        </div>
      </div>

      <div className="flex-1 p-6 space-y-6 max-w-3xl w-full">
        {/* Manual-comparison notice for LLM provenance */}
        {needsManualComparison && (
          <div className="flex items-start gap-3 rounded-lg border border-avip-review/40 bg-avip-review/5 px-4 py-3">
            <AlertTriangle className="w-5 h-5 text-avip-review flex-shrink-0 mt-0.5" />
            <div className="text-sm text-slate-700">
              {discrepancy.provenance === "llm-unavailable" ? (
                <>
                  <span className="font-semibold">Automated comparison unavailable.</span> The LLM
                  provider could not evaluate this free-text field, so it requires manual comparison.
                  Review the source values below and decide.
                </>
              ) : (
                <>
                  <span className="font-semibold">LLM-assisted flag.</span> This free-text field was
                  flagged by the LLM check. Confirm the values genuinely differ before deciding.
                </>
              )}
            </div>
          </div>
        )}

        {/* Source values side by side */}
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-600 mb-3">
            Source Values
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {Object.entries(discrepancy.values).map(([source, value]) => (
              <Card key={source} className="p-4 bg-slate-100 border-slate-200">
                <div className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
                  {source}
                </div>
                <div className="mt-1 text-lg font-mono font-semibold text-slate-900 break-words">
                  {value === null ? "—" : String(value)}
                </div>
              </Card>
            ))}
          </div>
        </div>

        {/* Decision panel */}
        <Card className="p-5 space-y-4">
          <h3 className="text-sm font-semibold text-foreground">Review Decision</h3>

          {alreadyDecided ? (
            <p className="text-sm text-slate-700">
              This discrepancy has already been {discrepancy.review_state}
              {discrepancy.reviewer ? ` by ${discrepancy.reviewer}` : ""}
              {discrepancy.reviewer_note ? ` — "${discrepancy.reviewer_note}"` : ""}.
            </p>
          ) : (
            <>
              <div className="space-y-2">
                <Label>Reviewer</Label>
                <Input value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
              </div>

              <div className="space-y-2">
                <Label>
                  Note <span className="text-muted-foreground font-normal">(optional)</span>
                </Label>
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={3}
                  placeholder="Add an optional note about this decision..."
                  className="flex w-full rounded-lg border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 outline-none resize-none"
                />
              </div>

              <div className="flex gap-2 pt-1">
                <Button
                  className="flex-1 bg-avip-pass hover:bg-avip-pass/90 text-white"
                  size="sm"
                  onClick={() => decideMutation.mutate("confirmed")}
                  disabled={!canSubmit || decideMutation.isPending}
                >
                  {decideMutation.isPending ? "Submitting..." : "Confirm"}
                </Button>
                <Button
                  variant="outline"
                  className="flex-1"
                  size="sm"
                  onClick={() => decideMutation.mutate("dismissed")}
                  disabled={!canSubmit || decideMutation.isPending}
                >
                  Dismiss
                </Button>
              </div>
            </>
          )}
        </Card>
      </div>
    </div>
  );
}

function ProvenanceBadge({ provenance }: { provenance: SCProvenance }) {
  const variant =
    provenance === "llm-unavailable"
      ? "destructive"
      : provenance === "llm"
        ? "secondary"
        : "outline";
  const label =
    provenance === "exact-match"
      ? "Exact Match"
      : provenance === "numeric-threshold"
        ? "Numeric Threshold"
        : provenance === "llm"
          ? "LLM"
          : "LLM Unavailable";
  return (
    <Badge
      variant={variant}
      className={variant === "outline" ? "text-xs text-slate-700 border-slate-300" : "text-xs"}
    >
      {label}
    </Badge>
  );
}
