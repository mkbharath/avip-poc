import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getInspection } from "../../api/inspections";
import { LamResearchLogo } from "../common/Logo";
import type { DecisionResult } from "../../types";

export function ResultScreen() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [countdown, setCountdown] = useState(5);

  const { data: inspection } = useQuery({
    queryKey: ["inspection", id],
    queryFn: () => getInspection(id!),
    enabled: !!id,
    // Refetch until we have a decision (handles race condition when navigating before data is ready)
    refetchInterval: (query) => {
      const data = query.state.data as unknown as Record<string, unknown> | undefined;
      const dec = data?.decision as Record<string, unknown> | null | undefined;
      return dec?.result ? false : 1000;
    },
  });

  // Safely extract decision and findings from the response
  const inspectionData = inspection as unknown as Record<string, unknown> | undefined;
  const decision = inspectionData?.decision as { result: string } | null | undefined;
  const decisionResult = (decision?.result || null) as DecisionResult | null;
  const part = inspectionData?.part as Record<string, unknown> | undefined;
  const partNumber = (inspectionData?.part_number ?? part?.part_number ?? "") as string;
  const revision = (inspectionData?.revision ?? part?.revision ?? "") as string;
  const findings = (Array.isArray(inspectionData?.findings) ? inspectionData.findings : []) as Array<Record<string, unknown>>;

  // Auto-dismiss PASS after countdown
  useEffect(() => {
    if (decisionResult !== "PASS") return;

    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          navigate("/kiosk");
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [decisionResult, navigate]);

  // Play audio cue
  useEffect(() => {
    if (!decisionResult) return;
    // Audio cues would play here in production
    // For now we rely on the visual impact
  }, [decisionResult]);

  if (!inspection || !decisionResult) {
    return (
      <div className="min-h-screen bg-gray-900 flex flex-col items-center justify-center">
        <div className="animate-spin w-8 h-8 border-4 border-avip-info border-t-transparent rounded-full" />
        <p className="text-gray-400 mt-4 text-sm">Loading inspection result...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-gray-900">
      {/* Branded header */}
      <div className="flex items-center justify-between px-6 py-3 bg-lam-navy">
        <div className="flex items-center gap-4">
          <LamResearchLogo variant="light" className="h-8" />
          <div className="w-px h-5 bg-white/20" />
          <span className="text-white/60 text-xs font-medium">AI Vision Inspection Platform</span>
        </div>
        <span className="text-white/50 text-xs">STN-LIV-01 • Inspection Complete</span>
      </div>

      {/* Decision content */}
      <div className="flex-1 flex flex-col items-center justify-center px-6">
        {/* Decision badge */}
        <div className={`w-20 h-20 rounded-full flex items-center justify-center mb-6 ${
          decisionResult === "PASS" ? "bg-avip-pass" :
          decisionResult === "FAIL" ? "bg-avip-fail" : "bg-avip-review"
        }`}>
          {decisionResult === "PASS" && (
            <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
            </svg>
          )}
          {decisionResult === "FAIL" && (
            <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
            </svg>
          )}
          {decisionResult === "REVIEW" && (
            <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M12 9v2m0 4h.01" />
            </svg>
          )}
        </div>

        {/* Decision text */}
        <h1 className={`text-6xl font-extrabold tracking-tight ${
          decisionResult === "PASS" ? "text-avip-pass" :
          decisionResult === "FAIL" ? "text-avip-fail" : "text-avip-review"
        }`}>{decisionResult}</h1>

        {/* Part info */}
        <p className="text-xl text-white/80 mt-4 font-medium font-mono">
          {partNumber} Rev {revision}
        </p>
        <p className="text-white/50 mt-2">
          {decisionResult === "PASS" ? "Route to Staging → Bay 4A" :
           decisionResult === "FAIL" ? "Route to IQA → Quarantine Bin Q3" :
           "Routed to IQA Review Queue"}
        </p>

        {/* Findings card (FAIL/REVIEW only) */}
        {decisionResult !== "PASS" && findings.length > 0 && (
          <div className="mt-8 bg-gray-800 rounded-xl px-6 py-4 border border-gray-700 max-w-md w-full">
            <p className="text-white/50 text-xs uppercase tracking-wide mb-3">
              Findings ({findings.length})
            </p>
            <div className="flex gap-2 flex-wrap">
              {findings.map((f, i) => (
                <span key={i} className={`badge text-xs ${
                  (f.severity as string) === "critical" ? "bg-avip-fail/20 text-avip-fail" :
                  (f.severity as string) === "major" ? "bg-avip-review/20 text-avip-review" :
                  "bg-gray-700 text-gray-300"
                }`}>
                  {f.defect_class as string}
                  <span className="ml-1 opacity-60">{Math.round((f.confidence as number) * 100)}%</span>
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Certificate (PASS only) */}
        {decisionResult === "PASS" && (
          <div className="mt-8 bg-gray-800 rounded-xl px-6 py-4 border border-avip-pass/30">
            <p className="text-white/50 text-xs uppercase tracking-wide mb-1">Certificate ID</p>
            <p className="text-avip-pass font-mono text-lg font-bold">{(id || "").slice(0, 8).toUpperCase()}</p>
          </div>
        )}

        {/* Actions */}
        <div className="mt-10 flex gap-4">
          {decisionResult !== "PASS" && (
            <Link
              to={`/review/${id}`}
              className={`px-6 py-3 min-h-[48px] font-semibold rounded-lg transition-colors ${
                decisionResult === "FAIL"
                  ? "bg-avip-fail text-white hover:bg-avip-fail/80"
                  : "bg-avip-review text-white hover:bg-avip-review/80"
              }`}
            >
              View Findings
            </Link>
          )}
          <button
            onClick={() => navigate("/kiosk")}
            className="px-6 py-3 min-h-[48px] bg-gray-700 text-white font-semibold rounded-lg hover:bg-gray-600 transition-colors"
          >
            Next Part
          </button>
        </div>

        {/* Auto-dismiss countdown (PASS only) */}
        {decisionResult === "PASS" && (
          <p className="mt-6 text-white/30 text-sm">Auto-dismiss in {countdown}s</p>
        )}
      </div>
    </div>
  );
}
