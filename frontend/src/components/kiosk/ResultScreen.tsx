import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle, AlertCircle, Loader2 } from "lucide-react";
import { getInspection } from "../../api/inspections";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { DecisionResult } from "../../types";

export function ResultScreen() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [countdown, setCountdown] = useState(5);

  const { data: inspection } = useQuery({
    queryKey: ["inspection", id],
    queryFn: () => getInspection(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data as unknown as Record<string, unknown> | undefined;
      const dec = data?.decision as Record<string, unknown> | null | undefined;
      return dec?.result ? false : 1000;
    },
  });

  const inspectionData = inspection as unknown as Record<string, unknown> | undefined;
  const decision = inspectionData?.decision as { result: string } | null | undefined;
  const decisionResult = (decision?.result || null) as DecisionResult | null;
  const part = inspectionData?.part as Record<string, unknown> | undefined;
  const partNumber = (inspectionData?.part_number ?? part?.part_number ?? "") as string;
  const revision = (inspectionData?.revision ?? part?.revision ?? "") as string;
  const findings = (Array.isArray(inspectionData?.findings) ? inspectionData.findings : []) as Array<Record<string, unknown>>;

  useEffect(() => {
    if (decisionResult !== "PASS") return;
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) { clearInterval(timer); navigate("/kiosk"); return 0; }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [decisionResult, navigate]);

  if (!inspection || !decisionResult) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-3rem)] p-6">
        <Loader2 className="w-8 h-8 text-lam-navy animate-spin" />
        <p className="text-muted-foreground mt-4 text-sm">Loading inspection result...</p>
      </div>
    );
  }

  const resultConfig = {
    PASS: { icon: CheckCircle2, color: "bg-avip-pass", textColor: "text-avip-pass" },
    FAIL: { icon: XCircle, color: "bg-avip-fail", textColor: "text-avip-fail" },
    REVIEW: { icon: AlertCircle, color: "bg-avip-review", textColor: "text-avip-review" },
  }[decisionResult] || { icon: AlertCircle, color: "bg-muted", textColor: "text-muted-foreground" };

  const ResultIcon = resultConfig.icon;

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-3rem)] p-6">
      <div className={`w-20 h-20 rounded-full flex items-center justify-center mb-6 ${resultConfig.color}`}>
        <ResultIcon className="w-10 h-10 text-white" />
      </div>

      <h1 className={`text-6xl font-extrabold tracking-tight ${resultConfig.textColor}`}>
        {decisionResult}
      </h1>

      <p className="text-xl text-foreground mt-4 font-medium font-mono">{partNumber} Rev {revision}</p>
      <p className="text-muted-foreground mt-2">
        {decisionResult === "PASS" ? "Route to Staging \u2192 Bay 4A" :
         decisionResult === "FAIL" ? "Route to IQA \u2192 Quarantine Bin Q3" :
         "Routed to IQA Review Queue"}
      </p>

      {decisionResult !== "PASS" && findings.length > 0 && (
        <Card className="mt-8 max-w-md w-full">
          <CardContent className="pt-4">
            <p className="text-muted-foreground text-xs uppercase tracking-wide mb-3">
              Findings ({findings.length})
            </p>
            <div className="flex gap-2 flex-wrap">
              {findings.map((f, i) => (
                <Badge
                  key={i}
                  variant={(f.severity as string) === "critical" ? "destructive" : "secondary"}
                  className="text-xs"
                >
                  {f.defect_class as string}
                  <span className="ml-1 opacity-60">{Math.round((f.confidence as number) * 100)}%</span>
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {decisionResult === "PASS" && (
        <Card className="mt-8 border-avip-pass/30">
          <CardContent className="pt-4 text-center">
            <p className="text-muted-foreground text-xs uppercase tracking-wide mb-1">Certificate ID</p>
            <p className="text-avip-pass font-mono text-lg font-bold">{(id || "").slice(0, 8).toUpperCase()}</p>
          </CardContent>
        </Card>
      )}

      <div className="mt-10 flex gap-3">
        {decisionResult !== "PASS" && (
          <Button
            size="lg"
            className={`${
              decisionResult === "FAIL" ? "bg-avip-fail hover:bg-avip-fail/90" : "bg-avip-review hover:bg-avip-review/90"
            } text-white`}
            render={<Link to={`/review/${id}`} />}
          >
            View Findings
          </Button>
        )}
        <Button variant="outline" size="lg" onClick={() => navigate("/kiosk")}>
          Next Part
        </Button>
      </div>

      {decisionResult === "PASS" && (
        <p className="mt-6 text-muted-foreground text-sm">Auto-dismiss in {countdown}s</p>
      )}
    </div>
  );
}
