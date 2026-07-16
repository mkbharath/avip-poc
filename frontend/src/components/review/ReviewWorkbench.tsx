import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import { getInspection, overrideDecision, confirmDecision } from "../../api/inspections";
import { OVERRIDE_REASONS } from "../../types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type OverlayType = "bbox" | "heatmap" | "golden";

export function ReviewWorkbench() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeImage, setActiveImage] = useState(0);
  const [overlays, setOverlays] = useState<Set<OverlayType>>(new Set(["bbox"]));
  const [showOverrideModal, setShowOverrideModal] = useState(false);
  const [selectedFinding, setSelectedFinding] = useState<number | null>(null);

  const { data: inspection, isLoading } = useQuery({
    queryKey: ["inspection", id],
    queryFn: () => getInspection(id!),
    enabled: !!id,
  });

  const confirmMutation = useMutation({
    mutationFn: () => confirmDecision(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inspection", id] });
      navigate("/review");
    },
  });

  if (isLoading || !inspection) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-3rem)]">
        <Loader2 className="w-8 h-8 text-lam-navy animate-spin" />
      </div>
    );
  }

  const data = inspection as unknown as Record<string, unknown>;
  const images = (data.images as Array<Record<string, unknown>>) || [];
  const findings = (data.findings as Array<Record<string, unknown>>) || [];
  const decision = data.decision as Record<string, unknown> | null;
  const status = data.status as string;

  const toggleOverlay = (type: OverlayType) => {
    setOverlays((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  const isReviewable = status === "in_review" || status === "failed";

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)]">
      {/* Subheader with part info */}
      <div className="flex items-center justify-between px-6 py-3 bg-background border-b">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" render={<Link to="/review" />}>
            <ArrowLeft className="mr-1" />
            Queue
          </Button>
          <div className="w-px h-5 bg-border" />
          <div>
            <h1 className="text-sm font-bold text-foreground">
              Review: {data.part_number as string} Rev {data.revision as string}
            </h1>
            <p className="text-xs text-muted-foreground">
              {data.family_name as string} &bull; {data.supplier as string}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {decision && (
            <Badge variant={(decision.result as string) === "FAIL" ? "destructive" : "secondary"}>
              AI Decision: {decision.result as string}
            </Badge>
          )}
          {decision && (
            <Badge variant="outline">
              Rule: {decision.fusion_rule as string}
            </Badge>
          )}
        </div>
      </div>

      {/* Three-pane layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Image viewer (dark canvas) */}
        <div className="flex-1 flex flex-col p-4 bg-muted/30 min-w-0">
          {/* Filmstrip */}
          <div className="flex gap-2 mb-3 overflow-x-auto pb-2">
            {images.map((img, idx) => (
              <button
                key={idx}
                onClick={() => setActiveImage(idx)}
                className={`flex-shrink-0 w-20 h-16 rounded-lg border-2 overflow-hidden transition-all relative ${
                  idx === activeImage
                    ? "border-lam-navy ring-2 ring-lam-navy/20"
                    : "border-border hover:border-muted-foreground/40"
                }`}
              >
                {(img.thumbnail_url || img.file_url) ? (
                  <img
                    src={(img.thumbnail_url || img.file_url) as string}
                    alt={(img.camera_angle as string).toUpperCase()}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full bg-muted" />
                )}
                <span className="absolute bottom-0 left-0 right-0 text-[10px] font-medium text-white bg-black/60 text-center py-0.5">
                  {(img.camera_angle as string).toUpperCase()}
                </span>
              </button>
            ))}
          </div>

          {/* Main canvas */}
          <div className="flex-1 bg-gray-900 rounded-xl relative overflow-hidden flex items-center justify-center min-h-[400px]">
            {/* Image wrapper with bbox overlays */}
            <div className="relative inline-block max-w-full max-h-full">
              {images[activeImage] && (images[activeImage].file_url as string) ? (
                <img
                  src={images[activeImage].file_url as string}
                  alt={`Camera: ${(images[activeImage].camera_angle as string).toUpperCase()}`}
                  className="max-w-full max-h-[500px] object-contain block"
                />
              ) : (
                <div className="w-[640px] h-[480px] flex items-center justify-center">
                  <span className="text-gray-500 text-sm">
                    {images[activeImage] ? `Camera: ${(images[activeImage].camera_angle as string).toUpperCase()}` : "No image"}
                  </span>
                </div>
              )}

              {/* Overlay: XAI Heatmap */}
              {overlays.has("heatmap") && images[activeImage] && (() => {
                const fileUrl = images[activeImage].file_url as string;
                const baseDir = fileUrl.substring(0, fileUrl.lastIndexOf("/"));
                return (
                  <img
                    src={`${baseDir}/heatmap.png?v=${Date.now()}`}
                    alt="XAI Heatmap"
                    className="absolute inset-0 w-full h-full object-contain pointer-events-none"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                  />
                );
              })()}

              {/* Overlay: Golden Diff */}
              {overlays.has("golden") && images[activeImage] && (() => {
                const fileUrl = images[activeImage].file_url as string;
                const baseDir = fileUrl.substring(0, fileUrl.lastIndexOf("/"));
                return (
                  <img
                    src={`${baseDir}/golden_diff.png?v=${Date.now()}`}
                    alt="Golden Comparison Diff"
                    className="absolute inset-0 w-full h-full object-contain pointer-events-none"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                  />
                );
              })()}

              {/* Overlay: Bounding boxes — percentages relative to displayed image */}
              {overlays.has("bbox") && findings.map((f, i) => {
                const bbox = f.bbox as { x: number; y: number; width: number; height: number } | null;
                if (!bbox) return null;
                const severity = f.severity as string;
                const borderColor = severity === "critical" ? "border-red-500" : severity === "major" ? "border-orange-400" : "border-yellow-400";
                return (
                  <div
                    key={i}
                    className={`absolute border-2 ${borderColor} rounded ${selectedFinding === i ? "ring-2 ring-white" : ""}`}
                    style={{
                      left: `${(bbox.x / 640) * 100}%`,
                      top: `${(bbox.y / 480) * 100}%`,
                      width: `${(bbox.width / 640) * 100}%`,
                      height: `${(bbox.height / 480) * 100}%`,
                    }}
                    onClick={() => setSelectedFinding(i)}
                  >
                    <span className={`absolute -top-5 left-0 text-xs px-1 rounded ${
                      severity === "critical" ? "bg-red-500" : severity === "major" ? "bg-orange-400" : "bg-yellow-400"
                    } text-white`}>
                      {f.defect_class as string}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Overlay controls */}
          <div className="flex items-center gap-3 mt-3">
            <span className="text-xs font-medium text-muted-foreground uppercase">Overlays:</span>
            <OverlayToggle label="Bounding Boxes" active={overlays.has("bbox")} onClick={() => toggleOverlay("bbox")} />
            <OverlayToggle label="XAI Heatmap" active={overlays.has("heatmap")} onClick={() => toggleOverlay("heatmap")} />
            <OverlayToggle label="Golden Diff" active={overlays.has("golden")} onClick={() => toggleOverlay("golden")} />
            <div className="ml-auto flex gap-2">
              <Button variant="outline" size="xs">Fit</Button>
              <Button variant="outline" size="xs">1:1</Button>
            </div>
          </div>
        </div>

        {/* Right: Findings panel */}
        <div className="w-[340px] border-l border-border/50 bg-card flex flex-col">
          <div className="px-5 py-4 border-b border-border/50">
            <h3 className="text-sm font-semibold text-foreground">
              Findings
              <span className="ml-1.5 text-xs font-normal text-muted-foreground">({findings.length})</span>
            </h3>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-border/30">
            {findings.map((f, i) => {
              const severity = f.severity as string;
              const isSelected = selectedFinding === i;
              const confidence = Math.round((f.confidence as number) * 100);

              return (
                <button
                  key={i}
                  onClick={() => setSelectedFinding(i)}
                  className={`w-full text-left px-5 py-4 transition-colors ${
                    isSelected
                      ? "bg-avip-info/5 border-l-[3px] border-l-avip-info"
                      : "hover:bg-muted/40 border-l-[3px] border-l-transparent"
                  }`}
                >
                  {/* Row 1: Defect name + severity */}
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[13px] font-semibold text-foreground capitalize">
                      {(f.defect_class as string).replace(/_/g, " ")}
                    </span>
                    <SeverityBadge severity={severity} />
                  </div>

                  {/* Row 2: Confidence bar + approach */}
                  <div className="flex items-center gap-3 mb-2">
                    <div className="flex-1">
                      <div className="h-1.5 w-full bg-border/50 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            confidence >= 90 ? "bg-avip-fail" : confidence >= 70 ? "bg-avip-review" : "bg-muted-foreground/40"
                          }`}
                          style={{ width: `${confidence}%` }}
                        />
                      </div>
                    </div>
                    <span className="text-[11px] font-mono text-muted-foreground w-8 text-right">{confidence}%</span>
                    <ApproachBadge approach={f.approach as string} />
                  </div>

                  {/* Row 3: Description (truncated) */}
                  <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
                    {f.description as string}
                  </p>
                </button>
              );
            })}
          </div>

          {/* Part Context */}
          <div className="border-t border-border/50 p-5 bg-muted/20">
            <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">Part Context</h4>
            <div className="space-y-2">
              {[
                ["Material", data.material as string],
                ["Family", data.family_name as string],
                ["Supplier", data.supplier as string],
              ].map(([label, value]) => (
                <div key={label} className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">{label}</span>
                  <span className="text-xs font-medium text-foreground">{value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Action bar */}
          {isReviewable && (
            <div className="border-t border-border/50 p-4 flex gap-2 bg-card">
              <Button
                variant="destructive"
                className="flex-1 bg-avip-fail hover:bg-avip-fail/90 text-white"
                size="sm"
                onClick={() => confirmMutation.mutate()}
                disabled={confirmMutation.isPending}
              >
                Confirm FAIL
              </Button>
              <Button
                className="flex-1 bg-avip-pass hover:bg-avip-pass/90 text-white"
                size="sm"
                onClick={() => setShowOverrideModal(true)}
              >
                Override → PASS
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Override Dialog */}
      <OverrideDialog
        open={showOverrideModal}
        inspectionId={id!}
        onClose={() => setShowOverrideModal(false)}
        onSuccess={() => {
          setShowOverrideModal(false);
          queryClient.invalidateQueries({ queryKey: ["inspection", id] });
          navigate("/review");
        }}
      />
    </div>
  );
}

function OverrideDialog({
  open,
  inspectionId,
  onClose,
  onSuccess,
}: {
  open: boolean;
  inspectionId: string;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [reasonCode, setReasonCode] = useState("");
  const [comment, setComment] = useState("");
  const [reviewer, setReviewer] = useState("IQA Inspector");

  const mutation = useMutation({
    mutationFn: () =>
      overrideDecision(inspectionId, {
        new_decision: "PASS",
        reason_code: reasonCode,
        comment,
        reviewer,
      }),
    onSuccess,
  });

  const canSubmit = reasonCode && comment.length >= 10 && reviewer;

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Override Decision → PASS</DialogTitle>
          <DialogDescription>
            Provide a reason and comment to override the AI FAIL decision.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label>
              Reason Code <span className="text-destructive">*</span>
            </Label>
            <Select value={reasonCode} onValueChange={(v) => setReasonCode(v ?? "")}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select reason..." />
              </SelectTrigger>
              <SelectContent>
                {OVERRIDE_REASONS.map((r) => (
                  <SelectItem key={r.code} value={r.code}>
                    {r.code}: {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>
              Comment <span className="text-destructive">*</span>
              <span className="text-muted-foreground font-normal"> (min 10 characters)</span>
            </Label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={3}
              placeholder="Explain why this override is appropriate..."
              className="flex w-full rounded-lg border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 outline-none resize-none"
            />
          </div>

          <div className="space-y-2">
            <Label>Reviewer</Label>
            <Input
              value={reviewer}
              onChange={(e) => setReviewer(e.target.value)}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            className="bg-avip-pass hover:bg-avip-pass/90 text-white"
            onClick={() => mutation.mutate()}
            disabled={!canSubmit || mutation.isPending}
          >
            {mutation.isPending ? "Submitting..." : "Confirm Override → PASS"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function OverlayToggle({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <Button
      variant={active ? "default" : "outline"}
      size="xs"
      onClick={onClick}
      className={active ? "bg-lam-navy hover:bg-lam-navy-light" : ""}
    >
      {label}
    </Button>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const styles: Record<string, string> = {
    critical: "bg-red-100 text-red-700 border-red-200",
    major: "bg-orange-100 text-orange-700 border-orange-200",
    minor: "bg-slate-100 text-slate-600 border-slate-200",
  };
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide border ${styles[severity] || styles.minor}`}>
      {severity}
    </span>
  );
}

function ApproachBadge({ approach }: { approach: string }) {
  const labels: Record<string, string> = {
    rule: "RULE",
    golden: "GOLD",
    model: "MODEL",
    anomaly: "ANOM",
  };
  return (
    <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-muted text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">
      {labels[approach] || approach}
    </span>
  );
}
