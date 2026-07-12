import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getInspection } from "../../api/inspections";
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
    <div
      className={`min-h-screen flex flex-col items-center justify-center transition-colors duration-500 ${
        decisionResult === "PASS"
          ? "bg-avip-pass"
          : decisionResult === "FAIL"
          ? "bg-avip-fail"
          : "bg-avip-review"
      }`}
    >
      {/* Decision text */}
      <div className="text-center">
        {decisionResult === "PASS" && (
          <>
            <div className="mb-4">
              <svg className="w-24 h-24 text-white mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h1 className="kiosk-text-decision text-white">PASS</h1>
            <p className="text-2xl text-white/80 mt-4 font-medium">
              {partNumber} Rev {revision}
            </p>
            <p className="text-xl text-white/60 mt-2">Route to Staging → Bay 4A</p>
            <div className="mt-8 bg-white/20 rounded-xl px-6 py-3 inline-block">
              <p className="text-white/70 text-sm">Certificate ID</p>
              <p className="text-white font-mono text-lg">{(id || "").slice(0, 8).toUpperCase()}</p>
            </div>
            <p className="mt-8 text-white/50 text-sm">
              Auto-dismiss in {countdown}s
            </p>
          </>
        )}

        {decisionResult === "FAIL" && (
          <>
            <div className="mb-4">
              <svg className="w-24 h-24 text-white mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
                  d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h1 className="kiosk-text-decision text-white">FAIL</h1>
            <p className="text-2xl text-white/80 mt-4 font-medium">
              {partNumber} Rev {revision}
            </p>
            <p className="text-xl text-white/60 mt-2">Route to IQA → Quarantine Bin Q3</p>

            <div className="mt-6 bg-white/10 rounded-xl px-6 py-4 inline-block">
              <p className="text-white/70 text-sm mb-1">Findings</p>
              <div className="flex gap-2 flex-wrap justify-center">
                {findings.map((f, i) => (
                  <span key={i} className="badge bg-white/20 text-white">
                    {f.defect_class as string}
                  </span>
                ))}
              </div>
            </div>

            <div className="mt-8 flex gap-4 justify-center">
              <Link
                to={`/review/${id}`}
                className="px-6 py-3 min-h-[48px] bg-white text-avip-fail font-semibold rounded-lg hover:bg-white/90 transition-colors"
              >
                View Findings
              </Link>
              <button
                onClick={() => navigate("/kiosk")}
                className="px-6 py-3 min-h-[48px] bg-white/20 text-white font-semibold rounded-lg hover:bg-white/30 transition-colors"
              >
                Next Part
              </button>
            </div>
          </>
        )}

        {decisionResult === "REVIEW" && (
          <>
            <div className="mb-4">
              <svg className="w-24 h-24 text-white mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <h1 className="kiosk-text-decision text-white">REVIEW</h1>
            <p className="text-2xl text-white/80 mt-4 font-medium">
              {partNumber} Rev {revision}
            </p>
            <p className="text-xl text-white/60 mt-2">Routed to IQA Review Queue</p>
            <p className="text-lg text-white/50 mt-1">Human decision required</p>

            <div className="mt-6 bg-white/10 rounded-xl px-6 py-4 inline-block">
              <p className="text-white/70 text-sm mb-1">Findings requiring review</p>
              <div className="flex gap-2 flex-wrap justify-center">
                {findings.map((f, i) => (
                  <span key={i} className="badge bg-white/20 text-white">
                    {f.defect_class as string} ({Math.round((f.confidence as number) * 100)}%)
                  </span>
                ))}
              </div>
            </div>

            <div className="mt-8 flex gap-4 justify-center">
              <Link
                to={`/review/${id}`}
                className="px-6 py-3 min-h-[48px] bg-white text-avip-review font-semibold rounded-lg hover:bg-white/90 transition-colors"
              >
                Open in Review
              </Link>
              <button
                onClick={() => navigate("/kiosk")}
                className="px-6 py-3 min-h-[48px] bg-white/20 text-white font-semibold rounded-lg hover:bg-white/30 transition-colors"
              >
                Next Part
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
