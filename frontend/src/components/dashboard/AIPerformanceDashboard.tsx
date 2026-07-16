import { useQuery } from "@tanstack/react-query";
import { getAIPerformanceDashboard } from "../../api/dashboard";
import {
  LineChart, Line, BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const toTitleCase = (str: string) =>
  str.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export function AIPerformanceDashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard", "ai"],
    queryFn: getAIPerformanceDashboard,
    refetchInterval: 60_000,
  });

  if (isLoading || !data) {
    return (
      <div className="p-6 lg:p-8">
        <Card><CardContent className="pt-5"><Skeleton className="h-64 w-full rounded-lg" /></CardContent></Card>
      </div>
    );
  }

  // Format dates for FPR/FNR trend
  const ratesTrend = data.fpr_trend.map((fp, i) => {
    const d = new Date(fp.date + "T00:00:00");
    const formatted = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    return { date: formatted, FPR: fp.value, FNR: data.fnr_trend[i]?.value || 0 };
  });

  return (
    <div className="p-6 lg:p-8 space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-xl font-semibold text-foreground tracking-tight">AI Performance</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Model accuracy, error rates, and override analysis</p>
      </div>

      {/* KPI Strip */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="text-center relative overflow-hidden">
          <CardContent className="pt-5 pb-5 relative z-10">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Overall Accuracy</p>
            <p className="text-3xl font-bold text-avip-pass mt-2">{data.accuracy}%</p>
            <p className="text-xs text-muted-foreground mt-1">Target: ≥97%</p>
          </CardContent>
          <div className="absolute inset-0 bg-avip-pass opacity-[0.04]" />
        </Card>
        <Card className="text-center relative overflow-hidden">
          <CardContent className="pt-5 pb-5 relative z-10">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">False Positive Rate</p>
            <p className={`text-3xl font-bold mt-2 ${data.fpr <= 5 ? "text-avip-pass" : "text-avip-review"}`}>
              {data.fpr}%
            </p>
            <p className="text-xs text-muted-foreground mt-1">Target: ≤5%</p>
          </CardContent>
        </Card>
        <Card className="text-center relative overflow-hidden">
          <CardContent className="pt-5 pb-5 relative z-10">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">False Negative Rate</p>
            <p className={`text-3xl font-bold mt-2 ${data.fnr <= 1 ? "text-avip-pass" : "text-avip-fail"}`}>
              {data.fnr}%
            </p>
            <p className="text-xs text-muted-foreground mt-1">Target: ≤1%</p>
          </CardContent>
        </Card>
        <Card className="text-center">
          <CardContent className="pt-5 pb-5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Model Version</p>
            <p className="text-xl font-bold text-foreground mt-2">{data.model_info.version}</p>
            <p className="text-xs text-muted-foreground mt-1">Updated: {data.model_info.last_updated}</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* FPR / FNR Trend */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle>FPR / FNR Trend (7 Days)</CardTitle>
            <CardDescription>False positive and negative rates over time</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={ratesTrend} margin={{ top: 10, right: 20, bottom: 20, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 13, fill: "#374151" }} axisLine={false} tickLine={false} dy={8} />
                <YAxis tick={{ fontSize: 13, fill: "#374151" }} axisLine={false} tickLine={false} domain={[0, "auto"]} unit="%" dx={-5} />
                <Tooltip
                  content={({ active, payload, label }) => {
                    if (!active || !payload?.length) return null;
                    return (
                      <div className="bg-card border border-border rounded-lg shadow-elevated px-4 py-3 text-sm">
                        <p className="font-semibold mb-1">{label}</p>
                        {payload.map((entry, i) => (
                          <div key={i} className="flex items-center gap-2 py-0.5">
                            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: entry.color }} />
                            <span className="text-muted-foreground">{entry.name}</span>
                            <span className="ml-auto font-bold">{(entry.value as number).toFixed(2)}%</span>
                          </div>
                        ))}
                      </div>
                    );
                  }}
                />
                <Legend verticalAlign="top" height={36} formatter={(value: string) => <span className="text-sm text-foreground">{value}</span>} />
                <ReferenceLine y={5} stroke="#f59e0b" strokeDasharray="5 5" />
                <ReferenceLine y={1} stroke="#ef4444" strokeDasharray="5 5" />
                <Line type="monotone" dataKey="FPR" stroke="#f59e0b" strokeWidth={2} dot={{ r: 4, fill: "#f59e0b", strokeWidth: 0 }} activeDot={{ r: 6, stroke: "#fff", strokeWidth: 2 }} />
                <Line type="monotone" dataKey="FNR" stroke="#ef4444" strokeWidth={2} dot={{ r: 4, fill: "#ef4444", strokeWidth: 0 }} activeDot={{ r: 6, stroke: "#fff", strokeWidth: 2 }} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Confidence Distribution */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle>Confidence Score Distribution</CardTitle>
            <CardDescription>AI decision confidence histogram</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={data.confidence_histogram} margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                <XAxis dataKey="range" tick={{ fontSize: 11, fill: "#374151" }} axisLine={false} tickLine={false} dy={5} />
                <YAxis tick={{ fontSize: 13, fill: "#374151" }} axisLine={false} tickLine={false} dx={-5} />
                <Tooltip
                  content={({ active, payload, label }) => {
                    if (!active || !payload?.length) return null;
                    return (
                      <div className="bg-card border border-border rounded-lg shadow-elevated px-4 py-2.5 text-sm">
                        <p className="font-semibold">Range: {label}</p>
                        <p className="text-muted-foreground">{payload[0].value} inspections</p>
                      </div>
                    );
                  }}
                  cursor={{ fill: "rgba(0,0,0,0.03)" }}
                />
                <Bar dataKey="count" fill="#1B2A4A" radius={[4, 4, 0, 0]} barSize={28} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Override Rate by Class */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle>Override Rate by Defect Class</CardTitle>
          <CardDescription>% of AI decisions overridden by IQA — high rates indicate retraining candidates</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.override_by_class} layout="vertical" margin={{ left: 20, right: 20, top: 10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 13, fill: "#374151" }} unit="%" domain={[0, 25]} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="defect_class" tick={{ fontSize: 13, fill: "#1f2937" }} width={140} axisLine={false} tickLine={false} tickFormatter={toTitleCase} />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload;
                  return (
                    <div className="bg-card border border-border rounded-lg shadow-elevated px-4 py-2.5 text-sm">
                      <p className="font-semibold">{toTitleCase(d.defect_class)}</p>
                      <p className="text-muted-foreground">Override rate: <span className="font-bold">{d.override_rate}%</span></p>
                    </div>
                  );
                }}
                cursor={{ fill: "rgba(0,0,0,0.03)" }}
              />
              <ReferenceLine x={10} stroke="#f59e0b" strokeDasharray="5 5" />
              <Bar dataKey="override_rate" radius={[0, 6, 6, 0]} barSize={22}>
                {data.override_by_class.map((entry) => {
                  const fill = entry.override_rate > 15 ? "#ef4444" : entry.override_rate > 8 ? "#f59e0b" : "#3b82f6";
                  return <Cell key={entry.defect_class} fill={fill} />;
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Model Info Card */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle>Active Models</CardTitle>
          <CardDescription>Currently deployed inference models</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div className="p-5 bg-muted/40 rounded-xl">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Anomaly Detection</p>
              <p className="text-base font-bold text-foreground mt-2">{data.model_info.anomaly_model}</p>
              <p className="text-sm text-muted-foreground mt-1">PatchCore • ONNX Runtime • Edge inference</p>
            </div>
            <div className="p-5 bg-muted/40 rounded-xl">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Defect Detection</p>
              <p className="text-base font-bold text-foreground mt-2">{data.model_info.detection_model}</p>
              <p className="text-sm text-muted-foreground mt-1">YOLOv8n • ONNX Runtime • 10 classes</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

