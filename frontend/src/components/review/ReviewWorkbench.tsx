import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getInspection, overrideDecision, confirmDecision } from "../../api/inspections";
import { OVERRIDE_REASONS } from "../../types";

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
      <div className="page-content flex items-center justify-center min-h-[calc(100vh-56px)]">
        <div className="animate-spin w-8 h-8 border-4 border-lam-navy border-t-transparent rounded-full" />
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
    <div className="flex flex-col h-[calc(100vh-56px)]">
      {/* Subheader with part info */}
      <div className="flex items-center justify-between px-6 py-3 bg-white border-b border-gray-200">
        <div className="flex items-center gap-4">
          <Link to="/review" className="text-lam-navy hover:underline text-sm">
            &larr; Queue
          </Link>
          <div className="w-px h-5 bg-gray-200" />
          <div>
            <h1 className="text-sm font-bold text-gray-900">
              Review: {data.part_number as string} Rev {data.revision as string}
            </h1>
            <p className="text-xs text-gray-500">
              {data.family_name as string} &bull; {data.supplier as string}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {decision && (
            <span className={`badge text-sm ${
              (decision.result as string) === "FAIL" ? "badge-fail" : "badge-review"
            }`}>
              AI Decision: {decision.result as string}
            </span>
          )}
          {decision && (
            <span className="badge bg-gray-100 text-gray-600 border border-gray-200 text-sm">
              Rule: {decision.fusion_rule as string}
            </span>
          )}
        </div>
      </div>

      {/* Three-pane layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Image viewer (dark canvas) */}
        <div className="flex-1 flex flex-col p-4 bg-gray-100 min-w-0">
          {/* Filmstrip */}
          <div className="flex gap-2 mb-3 overflow-x-auto pb-2">
            {images.map((img, idx) => (
              <button
                key={idx}
                onClick={() => setActiveImage(idx)}
                className={`flex-shrink-0 w-20 h-16 rounded-lg border-2 overflow-hidden transition-all relative ${
                  idx === activeImage
                    ? "border-lam-navy ring-2 ring-lam-navy/20"
                    : "border-gray-300 hover:border-gray-400"
                }`}
              >
                {(img.thumbnail_url || img.file_url) ? (
                  <img
                    src={(img.thumbnail_url || img.file_url) as string}
                    alt={(img.camera_angle as string).toUpperCase()}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full bg-gray-200" />
                )}
                <span className="absolute bottom-0 left-0 right-0 text-[10px] font-medium text-white bg-black/60 text-center py-0.5">
                  {(img.camera_angle as string).toUpperCase()}
                </span>
              </button>
            ))}
          </div>

          {/* Main canvas (stays dark for image viewing) */}
          <div className="flex-1 bg-gray-900 rounded-xl relative overflow-hidden flex items-center justify-center min-h-[400px]">
            <div className="w-full h-full relative flex items-center justify-center">
              {images[activeImage] && (images[activeImage].file_url as string) ? (
                <img
                  src={images[activeImage].file_url as string}
                  alt={`Camera: ${(images[activeImage].camera_angle as string).toUpperCase()}`}
                  className="max-w-full max-h-full object-contain"
                />
              ) : (
                <span className="text-gray-500 text-sm">
                  {images[activeImage] ? `Camera: ${(images[activeImage].camera_angle as string).toUpperCase()}` : "No image"}
                </span>
              )}

              {/* Overlay: Bounding boxes */}
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
                      left: `${(bbox.x / 400) * 100}%`,
                      top: `${(bbox.y / 300) * 100}%`,
                      width: `${(bbox.width / 400) * 100}%`,
                      height: `${(bbox.height / 300) * 100}%`,
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
          <div className="flex items-center gap-4 mt-3">
            <span className="text-xs font-medium text-gray-500 uppercase">Overlays:</span>
            <OverlayToggle label="Bounding Boxes" active={overlays.has("bbox")} onClick={() => toggleOverlay("bbox")} />
            <OverlayToggle label="XAI Heatmap" active={overlays.has("heatmap")} onClick={() => toggleOverlay("heatmap")} />
            <OverlayToggle label="Golden Diff" active={overlays.has("golden")} onClick={() => toggleOverlay("golden")} />
            <div className="ml-auto flex gap-2">
              <button className="text-xs px-2 py-1 bg-white border border-gray-200 text-gray-600 rounded hover:bg-gray-50">Fit</button>
              <button className="text-xs px-2 py-1 bg-white border border-gray-200 text-gray-600 rounded hover:bg-gray-50">1:1</button>
            </div>
          </div>
        </div>

        {/* Right: Findings panel (white) */}
        <div className="w-80 border-l border-gray-200 bg-white flex flex-col">
          <div className="px-4 py-3 border-b border-gray-200">
            <h3 className="text-sm font-semibold text-gray-900">
              Findings ({findings.length})
            </h3>
          </div>
          <div className="flex-1 overflow-y-auto">
            {findings.map((f, i) => (
              <button
                key={i}
                onClick={() => setSelectedFinding(i)}
                className={`w-full text-left px-4 py-3 border-b border-gray-100 hover:bg-gray-50 transition-colors ${
                  selectedFinding === i ? "bg-gray-50 border-l-4 border-l-lam-navy" : ""
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <DefectIcon defectClass={f.defect_class as string} />
                  <span className="text-sm font-medium text-gray-900">{f.defect_class as string}</span>
                  <SeverityBadge severity={f.severity as string} />
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">
                    {Math.round((f.confidence as number) * 100)}% confidence
                  </span>
                  <ApproachBadge approach={f.approach as string} />
                </div>
                <p className="text-xs text-gray-400 mt-1 line-clamp-2">{f.description as string}</p>
              </button>
            ))}
          </div>

          {/* Context panel */}
          <div className="border-t border-gray-200 p-4 bg-gray-50">
            <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Part Context</h4>
            <div className="space-y-1 text-xs">
              <div className="flex justify-between">
                <span className="text-gray-500">Material</span>
                <span className="text-gray-900">{data.material as string}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Family</span>
                <span className="text-gray-900">{data.family_name as string}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Supplier</span>
                <span className="text-gray-900">{data.supplier as string}</span>
              </div>
            </div>
          </div>

          {/* Action bar */}
          {isReviewable && (
            <div className="border-t border-gray-200 p-4 flex gap-2">
              <button
                onClick={() => confirmMutation.mutate()}
                className="btn-fail flex-1 text-sm py-2"
                disabled={confirmMutation.isPending}
              >
                Confirm FAIL
              </button>
              <button
                onClick={() => setShowOverrideModal(true)}
                className="btn-pass flex-1 text-sm py-2"
              >
                Override &rarr; PASS
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Override Modal */}
      {showOverrideModal && (
        <OverrideModal
          inspectionId={id!}
          onClose={() => setShowOverrideModal(false)}
          onSuccess={() => {
            setShowOverrideModal(false);
            queryClient.invalidateQueries({ queryKey: ["inspection", id] });
            navigate("/review");
          }}
        />
      )}
    </div>
  );
}

function OverrideModal({
  inspectionId,
  onClose,
  onSuccess,
}: {
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
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-1">Override Decision &rarr; PASS</h2>
        <p className="text-sm text-gray-500 mb-6">
          Provide a reason and comment to override the AI FAIL decision.
        </p>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Reason Code <span className="text-avip-fail">*</span>
            </label>
            <select
              value={reasonCode}
              onChange={(e) => setReasonCode(e.target.value)}
              className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:border-lam-navy focus:ring-2 focus:ring-lam-navy/10 focus:outline-none"
            >
              <option value="">Select reason...</option>
              {OVERRIDE_REASONS.map((r) => (
                <option key={r.code} value={r.code}>
                  {r.code}: {r.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Comment <span className="text-avip-fail">*</span>
              <span className="text-gray-400 font-normal"> (min 10 characters)</span>
            </label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={3}
              placeholder="Explain why this override is appropriate..."
              className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-lam-navy focus:ring-2 focus:ring-lam-navy/10 focus:outline-none resize-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Reviewer</label>
            <input
              type="text"
              value={reviewer}
              onChange={(e) => setReviewer(e.target.value)}
              className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:border-lam-navy focus:ring-2 focus:ring-lam-navy/10 focus:outline-none"
            />
          </div>
        </div>

        <div className="flex gap-3 mt-6">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2.5 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium text-sm"
          >
            Cancel
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!canSubmit || mutation.isPending}
            className="flex-1 btn-pass text-sm py-2.5 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {mutation.isPending ? "Submitting..." : "Confirm Override \u2192 PASS"}
          </button>
        </div>
      </div>
    </div>
  );
}

function OverlayToggle({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-md transition-colors ${
        active ? "bg-lam-navy text-white" : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
      }`}
    >
      <div className={`w-3 h-3 rounded border ${active ? "bg-white border-white" : "border-gray-400"}`}>
        {active && (
          <svg className="w-3 h-3 text-lam-navy" fill="currentColor" viewBox="0 0 12 12">
            <path d="M10 3L4.5 8.5 2 6" stroke="currentColor" fill="none" strokeWidth="2" />
          </svg>
        )}
      </div>
      {label}
    </button>
  );
}

function DefectIcon({ defectClass }: { defectClass: string }) {
  const icons: Record<string, string> = {
    scratch: "\u2E3B",
    dent: "\u25EF",
    contamination: "\u25C6",
    missing_component: "\u2298",
    crack: "\u26A1",
    surface_anomaly: "\u25C7",
  };
  return <span className="text-sm">{icons[defectClass] || "\u25CF"}</span>;
}

function SeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    critical: "bg-red-100 text-red-700",
    major: "bg-orange-100 text-orange-700",
    minor: "bg-yellow-100 text-yellow-700",
  };
  return <span className={`badge text-xs ${colors[severity] || "bg-gray-100 text-gray-600"}`}>{severity}</span>;
}

function ApproachBadge({ approach }: { approach: string }) {
  const colors: Record<string, string> = {
    rule: "bg-blue-100 text-blue-700",
    golden: "bg-purple-100 text-purple-700",
    model: "bg-green-100 text-green-700",
    anomaly: "bg-orange-100 text-orange-700",
  };
  const labels: Record<string, string> = {
    rule: "RULE",
    golden: "GOLD",
    model: "MODEL",
    anomaly: "ANOM",
  };
  return <span className={`badge text-xs ${colors[approach] || "bg-gray-100 text-gray-600"}`}>{labels[approach] || approach}</span>;
}
