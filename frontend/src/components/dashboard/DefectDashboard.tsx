import { useQuery } from "@tanstack/react-query";
import { getDefectDashboard } from "../../api/dashboard";
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  Area, AreaChart,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const DEFECT_COLORS: Record<string, string> = {
  scratch: "#ef4444",
  contamination: "#f59e0b",
  dent: "#3b82f6",
  missing_component: "#8b5cf6",
  crack: "#f97316",
  surface_anomaly: "#06b6d4",
};

const SEVERITY_COLORS: Record<string, string> = {
  minor: "#fbbf24",
  major: "#f97316",
  critical: "#ef4444",
};

const toTitleCase = (str: string) =>
  str.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

const CustomTooltip = ({ active, payload, label }: { active?: boolean; payload?: Array<{ name: string; value: number; color: string }>; label?: string }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-card border border-border rounded-lg shadow-elevated px-4 py-3 text-sm">
      <p className="font-semibold text-foreground mb-1.5">{label}</p>
      {payload.map((entry, i) => (
        <div key={i} className="flex items-center gap-2.5 py-0.5">
          <span className="w-3 h-3 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="text-muted-foreground">{toTitleCase(entry.name)}</span>
          <span className="ml-auto font-bold text-foreground">{entry.value}</span>
        </div>
      ))}
    </div>
  );
};

export function DefectDashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard", "defects"],
    queryFn: getDefectDashboard,
    refetchInterval: 60_000,
  });

  if (isLoading || !data) {
    return (
      <div className="p-6 lg:p-8 space-y-6">
        <div className="grid grid-cols-2 gap-6">
          <Card><CardContent className="pt-5"><Skeleton className="h-64 w-full rounded-lg" /></CardContent></Card>
          <Card><CardContent className="pt-5"><Skeleton className="h-64 w-full rounded-lg" /></CardContent></Card>
        </div>
      </div>
    );
  }

  // Prepare trend data grouped by date
  const trendByDate: Record<string, Record<string, number>> = {};
  for (const t of data.trends) {
    if (!trendByDate[t.date]) trendByDate[t.date] = {};
    trendByDate[t.date][t.defect_class] = t.count;
  }
  const trendData = Object.entries(trendByDate).map(([date, classes]) => {
    const d = new Date(date + "T00:00:00");
    const formatted = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    return { date: formatted, ...classes };
  });
  const trendClasses = [...new Set(data.trends.map((t) => t.defect_class))];

  // Sort pareto data
  const paretoData = [...data.pareto].sort((a, b) => b.count - a.count);

  return (
    <div className="p-6 lg:p-8 space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-xl font-semibold text-foreground tracking-tight">Defect Analytics</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Defect classification, trends, and part family analysis</p>
      </div>

      {/* Top row: Pareto + Severity */}
      <div className="grid grid-cols-2 gap-6">
        {/* Defect Pareto */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle>Defect Pareto</CardTitle>
            <CardDescription>Top defect types by occurrence count</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={paretoData} layout="vertical" margin={{ left: 10, right: 20, top: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={true} vertical={false} />
                <XAxis type="number" tick={{ fontSize: 13, fill: "#374151" }} axisLine={false} tickLine={false} />
                <YAxis
                  type="category"
                  dataKey="defect_class"
                  tick={{ fontSize: 13, fill: "#1f2937" }}
                  width={130}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(val: string) => toTitleCase(val)}
                />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(0,0,0,0.03)" }} />
                <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={24}>
                  {paretoData.map((entry) => (
                    <Cell key={entry.defect_class} fill={DEFECT_COLORS[entry.defect_class] || "#94a3b8"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Severity Distribution */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle>Severity Distribution</CardTitle>
            <CardDescription>Breakdown by defect severity level</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-center">
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie
                    data={data.severity_distribution}
                    cx="50%"
                    cy="50%"
                    innerRadius={65}
                    outerRadius={105}
                    dataKey="count"
                    nameKey="severity"
                    stroke="none"
                    paddingAngle={3}
                  >
                    {data.severity_distribution.map((entry) => (
                      <Cell
                        key={entry.severity}
                        fill={SEVERITY_COLORS[entry.severity] || "#94a3b8"}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const d = payload[0].payload;
                      return (
                        <div className="bg-card border border-border rounded-lg shadow-elevated px-4 py-2.5 text-sm">
                          <span className="font-semibold">{toTitleCase(d.severity)}</span>
                          <span className="ml-2 text-muted-foreground">{d.count} defects</span>
                        </div>
                      );
                    }}
                  />
                  <Legend
                    verticalAlign="bottom"
                    height={40}
                    formatter={(value: string) => (
                      <span className="text-sm text-foreground">{toTitleCase(value)}</span>
                    )}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Trend Chart — Area chart for a more polished look */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle>Defect Trends</CardTitle>
          <CardDescription>7-day rolling defect count by classification</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={trendData} margin={{ top: 10, right: 20, bottom: 20, left: 20 }}>
              <defs>
                {trendClasses.map((cls) => (
                  <linearGradient key={cls} id={`gradient-${cls}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={DEFECT_COLORS[cls] || "#94a3b8"} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={DEFECT_COLORS[cls] || "#94a3b8"} stopOpacity={0} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 13, fill: "#374151" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 13, fill: "#374151" }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend
                verticalAlign="top"
                height={40}
                formatter={(value: string) => (
                  <span className="text-sm text-foreground">{toTitleCase(value)}</span>
                )}
              />
              {trendClasses.map((cls) => (
                <Area
                  key={cls}
                  type="monotone"
                  dataKey={cls}
                  stroke={DEFECT_COLORS[cls] || "#94a3b8"}
                  strokeWidth={2}
                  fill={`url(#gradient-${cls})`}
                  dot={{ r: 3, fill: DEFECT_COLORS[cls] || "#94a3b8", strokeWidth: 0 }}
                  activeDot={{ r: 5, strokeWidth: 2, stroke: "#fff" }}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Family Heatmap */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle>Defect Density by Part Family</CardTitle>
          <CardDescription>Higher density indicates more quality issues per inspected unit</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-5 gap-3">
            {data.family_heatmap.map((f) => {
              const intensity = Math.min(f.density, 1);
              const bgR = Math.round(239 * intensity + 241 * (1 - intensity));
              const bgG = Math.round(68 * intensity + 245 * (1 - intensity));
              const bgB = Math.round(68 * intensity + 245 * (1 - intensity));
              const isHigh = intensity > 0.5;
              return (
                <div
                  key={f.family}
                  className="p-4 rounded-xl text-center transition-all hover:scale-[1.02]"
                  style={{ backgroundColor: `rgb(${bgR}, ${bgG}, ${bgB})` }}
                >
                  <p className={`text-[11px] font-bold uppercase tracking-wider ${isHigh ? "text-white" : "text-foreground/80"}`}>
                    {f.family}
                  </p>
                  <p className={`text-3xl font-bold mt-2 ${isHigh ? "text-white" : "text-foreground"}`}>
                    {(f.density * 100).toFixed(0)}%
                  </p>
                  <p className={`text-sm font-medium mt-1.5 ${isHigh ? "text-white" : "text-foreground/80"}`}>
                    {toTitleCase(f.top_defect)}
                  </p>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
