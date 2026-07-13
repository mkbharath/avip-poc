import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { getScenarios, runScenario, resetDemo } from "../../api/demo";
import { LamResearchLogo, IdeyaLabsLogo } from "../common/Logo";
import type { DemoScenario } from "../../types";

export function PresenterPanel() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [lastResult, setLastResult] = useState<{
    scenario: string;
    inspectionId: string;
    decision: string;
  } | null>(null);

  const { data } = useQuery({
    queryKey: ["demo", "scenarios"],
    queryFn: getScenarios,
  });

  const runMutation = useMutation({
    mutationFn: (scenarioId: string) => runScenario(scenarioId),
    onSuccess: (result) => {
      setLastResult({
        scenario: result.scenario.name,
        inspectionId: result.inspection_id,
        decision: result.result.decision.result,
      });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["reviewQueue"] });
    },
  });

  const resetMutation = useMutation({
    mutationFn: resetDemo,
    onSuccess: () => {
      setLastResult(null);
      queryClient.invalidateQueries();
    },
  });

  const scenarios = data?.data || [];

  const handleRunAndNavigate = async (scenario: DemoScenario) => {
    const result = await runMutation.mutateAsync(scenario.id);
    // Navigate to the result screen to show the demo flow
    navigate(`/kiosk/result/${result.inspection_id}`);
  };

  return (
    <div className="min-h-screen bg-gray-900 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <LamResearchLogo variant="light" />
          <div className="w-px h-6 bg-white/20" />
          <div>
            <h1 className="text-lg font-bold text-white">AVIP Demo — Presenter Panel</h1>
            <p className="text-xs text-gray-400">
              Run pre-built scenarios to demonstrate platform capabilities
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Link to="/kiosk" className="text-sm text-gray-400 hover:text-white">Station</Link>
          <Link to="/review" className="text-sm text-gray-400 hover:text-white">Review</Link>
          <Link to="/dashboard/inspection" className="text-sm text-gray-400 hover:text-white">Dashboard</Link>
          <button
            onClick={() => resetMutation.mutate()}
            disabled={resetMutation.isPending}
            className="px-4 py-2 bg-gray-700 text-gray-300 text-sm rounded-lg hover:bg-gray-600 transition-colors disabled:opacity-50"
          >
            {resetMutation.isPending ? "Resetting..." : "Reset All Data"}
          </button>
          <div className="w-px h-4 bg-white/10" />
          <div className="flex items-center gap-1.5">
            <span className="text-white/30 text-[10px]">Powered by</span>
            <IdeyaLabsLogo variant="light" className="h-4" />
          </div>
        </div>
      </div>

      {/* Last result banner */}
      {lastResult && (
        <div className={`mb-6 rounded-xl p-4 flex items-center justify-between ${
          lastResult.decision === "PASS" ? "bg-avip-pass/20 border border-avip-pass/40" :
          lastResult.decision === "FAIL" ? "bg-avip-fail/20 border border-avip-fail/40" :
          "bg-avip-review/20 border border-avip-review/40"
        }`}>
          <div>
            <span className="text-sm text-white font-medium">Last: {lastResult.scenario}</span>
            <span className={`ml-3 badge ${
              lastResult.decision === "PASS" ? "badge-pass" : lastResult.decision === "FAIL" ? "badge-fail" : "badge-review"
            }`}>
              {lastResult.decision}
            </span>
          </div>
          <div className="flex gap-2">
            <Link
              to={`/kiosk/result/${lastResult.inspectionId}`}
              className="text-xs text-white bg-white/20 px-3 py-1.5 rounded hover:bg-white/30"
            >
              View Result
            </Link>
            {lastResult.decision !== "PASS" && (
              <Link
                to={`/review/${lastResult.inspectionId}`}
                className="text-xs text-white bg-white/20 px-3 py-1.5 rounded hover:bg-white/30"
              >
                Open in Review
              </Link>
            )}
          </div>
        </div>
      )}

      {/* Scenario grid */}
      <div className="grid grid-cols-2 gap-4">
        {scenarios.map((scenario) => (
          <ScenarioCard
            key={scenario.id}
            scenario={scenario}
            onRun={() => runMutation.mutate(scenario.id)}
            onRunAndShow={() => handleRunAndNavigate(scenario)}
            isRunning={runMutation.isPending && runMutation.variables === scenario.id}
          />
        ))}
      </div>

      {/* Quick links */}
      <div className="mt-8 border-t border-gray-700 pt-6">
        <h3 className="text-sm font-medium text-gray-400 mb-3">Demo Navigation</h3>
        <div className="grid grid-cols-4 gap-3">
          <QuickLink to="/kiosk" label="Operator Kiosk" desc="Scan → Capture → Result flow" />
          <QuickLink to="/review" label="IQA Review Queue" desc="Pending inspections for review" />
          <QuickLink to="/dashboard/inspection" label="Inspection Dashboard" desc="Real-time operations view" />
          <QuickLink to="/dashboard/defects" label="Defect Dashboard" desc="Pareto, trends, heatmap" />
        </div>
      </div>
    </div>
  );
}

function ScenarioCard({
  scenario,
  onRun,
  onRunAndShow,
  isRunning,
}: {
  scenario: DemoScenario;
  onRun: () => void;
  onRunAndShow: () => void;
  isRunning: boolean;
}) {
  const decisionColor = {
    PASS: "border-avip-pass/50 bg-avip-pass/5",
    FAIL: "border-avip-fail/50 bg-avip-fail/5",
    REVIEW: "border-avip-review/50 bg-avip-review/5",
  }[scenario.expected_decision] || "border-gray-600 bg-gray-800";

  const decisionBadge = {
    PASS: "badge-pass",
    FAIL: "badge-fail",
    REVIEW: "badge-review",
  }[scenario.expected_decision] || "bg-gray-100 text-gray-600";

  return (
    <div className={`rounded-xl border p-4 ${decisionColor} transition-all hover:shadow-lg`}>
      <div className="flex items-start justify-between mb-2">
        <div>
          <h4 className="text-sm font-bold text-white">{scenario.name}</h4>
          <p className="text-xs text-gray-400 mt-0.5">{scenario.family}</p>
        </div>
        <span className={`badge ${decisionBadge}`}>{scenario.expected_decision}</span>
      </div>
      <p className="text-xs text-gray-300 mb-3 line-clamp-2">{scenario.description}</p>
      <p className="text-xs text-gray-500 italic mb-3">Demonstrates: {scenario.demonstrates}</p>
      <div className="flex gap-2">
        <button
          onClick={onRun}
          disabled={isRunning}
          className="flex-1 px-3 py-2 min-h-[40px] text-xs font-medium bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition-colors disabled:opacity-50"
        >
          {isRunning ? "Running..." : "Run (background)"}
        </button>
        <button
          onClick={onRunAndShow}
          disabled={isRunning}
          className="flex-1 px-3 py-2 min-h-[40px] text-xs font-medium bg-avip-info text-white rounded-lg hover:bg-avip-info/80 transition-colors disabled:opacity-50"
        >
          Run & Show Result
        </button>
      </div>
    </div>
  );
}

function QuickLink({ to, label, desc }: { to: string; label: string; desc: string }) {
  return (
    <Link
      to={to}
      className="p-4 rounded-lg bg-gray-800 border border-gray-700 hover:border-avip-info/50 hover:bg-gray-750 transition-colors"
    >
      <p className="text-sm font-medium text-white">{label}</p>
      <p className="text-xs text-gray-400 mt-1">{desc}</p>
    </Link>
  );
}
