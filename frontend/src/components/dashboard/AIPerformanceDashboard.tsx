import { useQuery } from "@tanstack/react-query";
import { getAIPerformanceDashboard } from "../../api/dashboard";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function AIPerformanceDashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard", "ai"],
    queryFn: getAIPerformanceDashboard,
    refetchInterval: 60_000,
  });

  if (isLoading || !data) {
    return (
      <div className="p-6">
        <Card><CardContent className="pt-4"><Skeleton className="h-64 w-full" /></CardContent></Card>
      </div>
    );
  }

  // Combine FPR/FNR trends for dual-line chart
  const ratesTrend = data.fpr_trend.map((fp, i) => ({
    date: fp.date.slice(5),
    FPR: fp.value,
    FNR: data.fnr_trend[i]?.value || 0,
  }));

  return (
    <div className="p-6 space-y-6">
      {/* KPI Strip */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="text-center">
          <CardContent className="pt-4 pb-4">
            <p className="text-xs font-medium text-muted-foreground uppercase">Overall Accuracy</p>
            <p className="text-3xl font-bold text-avip-pass mt-1">{data.accuracy}%</p>
            <p className="text-xs text-muted-foreground mt-1">Target: ≥97%</p>
          </CardContent>
        </Card>
        <Card className="text-center">
          <CardContent className="pt-4 pb-4">
            <p className="text-xs font-medium text-muted-foreground uppercase">False Positive Rate</p>
            <p className={`text-3xl font-bold mt-1 ${data.fpr <= 5 ? "text-avip-pass" : "text-avip-review"}`}>
              {data.fpr}%
            </p>
            <p className="text-xs text-muted-foreground mt-1">Target: ≤5%</p>
          </CardContent>
        </Card>
        <Card className="text-center">
          <CardContent className="pt-4 pb-4">
            <p className="text-xs font-medium text-muted-foreground uppercase">False Negative Rate</p>
            <p className={`text-3xl font-bold mt-1 ${data.fnr <= 1 ? "text-avip-pass" : "text-avip-fail"}`}>
              {data.fnr}%
            </p>
            <p className="text-xs text-muted-foreground mt-1">Target: ≤1%</p>
          </CardContent>
        </Card>
        <Card className="text-center">
          <CardContent className="pt-4 pb-4">
            <p className="text-xs font-medium text-muted-foreground uppercase">Model Version</p>
            <p className="text-lg font-bold text-foreground mt-2">{data.model_info.version}</p>
            <p className="text-xs text-muted-foreground mt-1">Updated: {data.model_info.last_updated}</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* FPR / FNR Trend */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">FPR / FNR Trend (7 days)</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={ratesTrend}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} domain={[0, "auto"]} unit="%" />
                <Tooltip formatter={(value: number) => `${value.toFixed(2)}%`} />
                <ReferenceLine y={5} stroke="#E67E22" strokeDasharray="5 5" label={{ value: "FPR target", position: "right", fontSize: 10 }} />
                <ReferenceLine y={1} stroke="#C0392B" strokeDasharray="5 5" label={{ value: "FNR target", position: "right", fontSize: 10 }} />
                <Line type="monotone" dataKey="FPR" stroke="#E67E22" strokeWidth={2} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="FNR" stroke="#C0392B" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Confidence Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Confidence Score Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={data.confidence_histogram}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="range" tick={{ fontSize: 10 }} angle={-30} textAnchor="end" height={50} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#156082" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Override Rate by Class */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Override Rate by Defect Class</CardTitle>
          <CardDescription>% of AI decisions overridden by IQA</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data.override_by_class} layout="vertical" margin={{ left: 30 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis type="number" tick={{ fontSize: 11 }} unit="%" domain={[0, 25]} />
              <YAxis type="category" dataKey="defect_class" tick={{ fontSize: 11 }} width={130} />
              <Tooltip formatter={(value: number) => `${value}%`} />
              <ReferenceLine x={10} stroke="#E67E22" strokeDasharray="5 5" />
              <Bar dataKey="override_rate" radius={[0, 4, 4, 0]}>
                {data.override_by_class.map((entry) => (
                  <BarCell key={entry.defect_class} overrideRate={entry.override_rate} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="text-xs text-muted-foreground mt-2">
            High override rates indicate model disagreement with human reviewers — candidates for retraining focus.
          </p>
        </CardContent>
      </Card>

      {/* Model Info Card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Active Models</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 bg-muted/50 rounded-lg">
              <p className="text-xs font-medium text-muted-foreground uppercase">Anomaly Detection</p>
              <p className="text-sm font-bold text-foreground mt-1">{data.model_info.anomaly_model}</p>
              <p className="text-xs text-muted-foreground mt-0.5">PatchCore • ONNX Runtime • Edge inference</p>
            </div>
            <div className="p-4 bg-muted/50 rounded-lg">
              <p className="text-xs font-medium text-muted-foreground uppercase">Defect Detection</p>
              <p className="text-sm font-bold text-foreground mt-1">{data.model_info.detection_model}</p>
              <p className="text-xs text-muted-foreground mt-0.5">YOLOv8n • ONNX Runtime • 10 classes</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// Helper component for conditional bar coloring
function BarCell({ overrideRate }: { overrideRate: number }) {
  const fill = overrideRate > 15 ? "#C0392B" : overrideRate > 8 ? "#E67E22" : "#1E8E3E";
  return <rect fill={fill} />;
}
