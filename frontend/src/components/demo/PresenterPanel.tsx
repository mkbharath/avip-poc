import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { getScenarios, runScenario, resetDemo } from "../../api/demo";
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
    navigate(`/kiosk/result/${result.inspection_id}`);
  };

  return (
    <div className="page-content">
      {/* Page header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">Demo &mdash; Presenter Panel</h1>
          <p className="page-subtitle">Run pre-built scenarios to demonstrate platform capabilities</p>
        </div>
        <button
          onClick={() => resetMutation.mutate()}
          disabled={resetMutation.isPending}
          className="px-4 py-2 bg-white border border-gray-200 text-gray-700 text-sm rounded-lg hover:bg-gray-50 transition-colors shadow-sm disabled:opacity-50"
        >
          {resetMutation.isPending ? "Resetting..." : "Reset All Data"}
        </button>
      </div>

      {/* Last result banner */}
      {lastResult && (
        <div className={`mb-6 rounded-xl p-4 flex items-center justify-between ${
          lastResult.decision === "PASS" ? "bg-emerald-50 border border-emerald-200" :
          lastResult.decision === "FAIL" ? "bg-red-50 border border-red-200" :
          "bg-amber-50 border border-amber-200"
        }`}>
          <div>
            <span className="text-sm text-gray-900 font-medium">Last: {lastResult.scenario}</span>
            <span className={`ml-3 badge ${
              lastResult.decision === "PASS" ? "badge-pass" : lastResult.decision === "FAIL" ? "badge-fail" : "badge-review"
            }`}>
              {lastResult.decision}
            </span>
          </div>
          <div className="flex gap-2">
            <Link
              to={`/kiosk/result/${lastResult.inspectionId}`}
              className="text-xs text-lam-navy bg-white border border-gray-200 px-3 py-1.5 rounded hover:bg-gray-50 shadow-sm"
            >
              View Result
            </Link>
            {lastResult.decision !== "PASS" && (
              <Link
                to={`/review/${lastResult.inspectionId}`}
                className="text-xs text-lam-navy bg-white border border-gray-200 px-3 py-1.5 rounded hover:bg-gray-50 shadow-sm"
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
      <div className="mt-8 border-t border-gray-200 pt-6">
        <h3 className="text-sm font-medium text-gray-500 mb-3">Demo Navigation</h3>
        <div className="grid grid-cols-4 gap-3">
          <QuickLink to="/kiosk" label="Operator Kiosk" desc="Scan \u2192 Capture \u2192 Result flow" />
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
    PASS: "border-emerald-200 bg-emerald-50/50",
    FAIL: "border-red-200 bg-red-50/50",
    REVIEW: "border-amber-200 bg-amber-50/50",
  }[scenario.expected_decision] || "border-gray-200 bg-white";

  const decisionBadge = {
    PASS: "badge-pass",
    FAIL: "badge-fail",
    REVIEW: "badge-review",
  }[scenario.expected_decision] || "bg-gray-100 text-gray-600";

  return (
    <div className={`rounded-xl border p-4 ${decisionColor} transition-all hover:shadow-md`}>
      <div className="flex items-start justify-between mb-2">
        <div>
          <h4 className="text-sm font-bold text-gray-900">{scenario.name}</h4>
          <p className="text-xs text-gray-500 mt-0.5">{scenario.family}</p>
        </div>
        <span className={`badge ${decisionBadge}`}>{scenario.expected_decision}</span>
      </div>
      <p className="text-xs text-gray-600 mb-3 line-clamp-2">{scenario.description}</p>
      <p className="text-xs text-gray-400 italic mb-3">Demonstrates: {scenario.demonstrates}</p>
      <div className="flex gap-2">
        <button
          onClick={onRun}
          disabled={isRunning}
          className="flex-1 px-3 py-2 min-h-[40px] text-xs font-medium bg-white border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50 shadow-sm"
        >
          {isRunning ? "Running..." : "Run (background)"}
        </button>
        <button
          onClick={onRunAndShow}
          disabled={isRunning}
          className="flex-1 px-3 py-2 min-h-[40px] text-xs font-medium btn-primary disabled:opacity-50"
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
      className="p-4 rounded-xl bg-white border border-gray-200 hover:border-lam-navy/30 hover:shadow-sm transition-colors"
    >
      <p className="text-sm font-medium text-gray-900">{label}</p>
      <p className="text-xs text-gray-500 mt-1">{desc}</p>
    </Link>
  );
}
