import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { RotateCcw } from "lucide-react";
import { getScenarios, runScenario, resetDemo } from "../../api/demo";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
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
    <div className="p-6 space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground tracking-tight">Demo — Presenter Panel</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Run pre-built scenarios to demonstrate platform capabilities</p>
        </div>
        <Button
          variant="outline"
          onClick={() => resetMutation.mutate()}
          disabled={resetMutation.isPending}
        >
          <RotateCcw className="mr-1.5" />
          {resetMutation.isPending ? "Resetting..." : "Reset All Data"}
        </Button>
      </div>

      {/* Last result banner */}
      {lastResult && (
        <Card className={
          lastResult.decision === "PASS" ? "border-avip-pass/30 bg-emerald-50/50" :
          lastResult.decision === "FAIL" ? "border-avip-fail/30 bg-red-50/50" :
          "border-avip-review/30 bg-amber-50/50"
        }>
          <CardContent className="pt-4 pb-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-sm text-foreground font-medium">Last: {lastResult.scenario}</span>
              <Badge
                variant={lastResult.decision === "PASS" ? "secondary" : lastResult.decision === "FAIL" ? "destructive" : "outline"}
                className={lastResult.decision === "PASS" ? "bg-emerald-100 text-emerald-700" : ""}
              >
                {lastResult.decision}
              </Badge>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="xs" render={<Link to={`/kiosk/result/${lastResult.inspectionId}`} />}>
                View Result
              </Button>
              {lastResult.decision !== "PASS" && (
                <Button variant="outline" size="xs" render={<Link to={`/review/${lastResult.inspectionId}`} />}>
                  Open in Review
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
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
      <div className="border-t pt-6">
        <h3 className="text-sm font-medium text-muted-foreground mb-3">Demo Navigation</h3>
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
  const borderColor = {
    PASS: "border-avip-pass/30",
    FAIL: "border-avip-fail/30",
    REVIEW: "border-avip-review/30",
  }[scenario.expected_decision] || "border-border";

  return (
    <Card className={`${borderColor} hover:shadow-md transition-shadow`}>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-sm">{scenario.name}</CardTitle>
            <CardDescription className="text-xs mt-0.5">{scenario.family}</CardDescription>
          </div>
          <Badge
            variant={scenario.expected_decision === "FAIL" ? "destructive" : scenario.expected_decision === "PASS" ? "secondary" : "outline"}
            className={scenario.expected_decision === "PASS" ? "bg-emerald-50 text-emerald-700" : ""}
          >
            {scenario.expected_decision}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground line-clamp-2">{scenario.description}</p>
        <p className="text-xs text-muted-foreground/70 italic">Demonstrates: {scenario.demonstrates}</p>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            className="flex-1"
            onClick={onRun}
            disabled={isRunning}
          >
            {isRunning ? "Running..." : "Run (background)"}
          </Button>
          <Button
            size="sm"
            className="flex-1"
            onClick={onRunAndShow}
            disabled={isRunning}
          >
            Run & Show Result
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function QuickLink({ to, label, desc }: { to: string; label: string; desc: string }) {
  return (
    <Card className="hover:border-lam-navy/30 hover:shadow-sm transition-colors" size="sm">
      <CardContent className="pt-3 pb-3">
        <Link to={to} className="block">
          <p className="text-sm font-medium text-foreground">{label}</p>
          <p className="text-xs text-muted-foreground mt-1">{desc}</p>
        </Link>
      </CardContent>
    </Card>
  );
}
