import { useQuery } from "@tanstack/react-query";
import { getDefectDashboard } from "../../api/dashboard";
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const DEFECT_COLORS: Record<string, string> = {
  scratch: "#e74c3c",
  contamination: "#f39c12",
  dent: "#3498db",
  missing_component: "#9b59b6",
  crack: "#e67e22",
  surface_anomaly: "#1abc9c",
};

const SEVERITY_COLORS = {
  minor: "#f1c40f",
  major: "#e67e22",
  critical: "#e74c3c",
};

export function DefectDashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard", "defects"],
    queryFn: getDefectDashboard,
    refetchInterval: 60_000,
  });

  if (isLoading || !data) {
    return (
      <div className="p-6">
        <Card><CardContent className="pt-4"><Skeleton className="h-64 w-full" /></CardContent></Card>
      </div>
    );
  }

  // Prepare trend data grouped by date
  const trendByDate: Record<string, Record<string, number>> = {};
  for (const t of data.trends) {
    if (!trendByDate[t.date]) trendByDate[t.date] = {};
    trendByDate[t.date][t.defect_class] = t.count;
  }
  const trendData = Object.entries(trendByDate).map(([date, classes]) => ({
    date: date.slice(5),
    ...classes,
  }));
  const trendClasses = [...new Set(data.trends.map((t) => t.defect_class))];

  return (
    <div className="p-6 space-y-6">
      <div className="grid grid-cols-2 gap-6">
        {/* Defect Pareto */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Defect Pareto (by count)</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={data.pareto} layout="vertical" margin={{ left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="defect_class" tick={{ fontSize: 11 }} width={120} />
                <Tooltip />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {data.pareto.map((entry) => (
                    <Cell key={entry.defect_class} fill={DEFECT_COLORS[entry.defect_class] || "#95a5a6"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Severity Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Severity Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={data.severity_distribution}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  dataKey="count"
                  nameKey="severity"
                  label={({ severity, count }) => `${severity}: ${count}`}
                >
                  {data.severity_distribution.map((entry) => (
                    <Cell
                      key={entry.severity}
                      fill={SEVERITY_COLORS[entry.severity as keyof typeof SEVERITY_COLORS] || "#95a5a6"}
                    />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Trend lines */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Defect Trends (7 days)</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              {trendClasses.map((cls) => (
                <Line
                  key={cls}
                  type="monotone"
                  dataKey={cls}
                  stroke={DEFECT_COLORS[cls] || "#95a5a6"}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Family Heatmap */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Defect Density by Part Family</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-5 gap-3">
            {data.family_heatmap.map((f) => {
              const bgColor = `rgba(231, 76, 60, ${f.density * 0.7})`;
              return (
                <div
                  key={f.family}
                  className="p-4 rounded-lg text-center border border-border"
                  style={{ backgroundColor: bgColor }}
                >
                  <p className={`text-xs font-medium ${f.density > 0.5 ? "text-white" : "text-foreground"}`}>
                    {f.family}
                  </p>
                  <p className={`text-lg font-bold mt-1 ${f.density > 0.5 ? "text-white" : "text-foreground"}`}>
                    {(f.density * 100).toFixed(0)}%
                  </p>
                  <p className={`text-xs mt-0.5 ${f.density > 0.5 ? "text-white/80" : "text-muted-foreground"}`}>
                    Top: {f.top_defect}
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
