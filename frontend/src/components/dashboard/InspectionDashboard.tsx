import { useQuery } from "@tanstack/react-query";
import { getInspectionDashboard } from "../../api/dashboard";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LabelList, Cell,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

export function InspectionDashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard", "inspection"],
    queryFn: getInspectionDashboard,
    refetchInterval: 30_000,
  });

  if (isLoading || !data) {
    return <DashboardSkeleton />;
  }

  const cycleTimeData = data.cycle_time_distribution ?? [
    { range: "0–20s", count: 4 },
    { range: "20–40s", count: 18 },
    { range: "40–60s", count: 22 },
    { range: "60–80s", count: 8 },
    { range: "80–100s", count: 3 },
  ];

  return (
    <div className="p-6 lg:p-8 space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-xl font-semibold text-foreground tracking-tight">Inspection Operations</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Real-time station activity and throughput metrics</p>
      </div>

      {/* KPI Strip */}
      <div className="grid grid-cols-4 gap-4">
        <KPITile label="Inspections Today" value={data.today_count} />
        <KPITile label="Pass Rate" value={`${data.pass_rate}%`} color={data.pass_rate > 90 ? "green" : data.pass_rate > 70 ? "amber" : "red"} />
        <KPITile label="Avg Cycle Time" value={`${data.avg_cycle_time_seconds}s`} />
        <KPITile label="Queue Depth" value={data.queue_depth} color={data.queue_depth > 5 ? "red" : data.queue_depth > 2 ? "amber" : "green"} />
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Station Status */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle>Station Status</CardTitle>
            <CardDescription>Active inspection stations</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.stations.map((station) => (
              <div key={station.id} className="flex items-center justify-between p-3.5 bg-muted/40 rounded-lg">
                <div className="flex items-center gap-3">
                  <div className={`w-3 h-3 rounded-full ${
                    station.status === "active" ? "bg-avip-pass" : "bg-muted-foreground/30"
                  }`} />
                  <div>
                    <p className="text-sm font-medium text-foreground">{station.name}</p>
                    {station.current_part && (
                      <p className="text-xs text-muted-foreground font-mono">{station.current_part}</p>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold text-foreground">{station.parts_per_hour}</p>
                  <p className="text-[11px] text-muted-foreground">parts/h</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Cycle Time Distribution */}
        <Card className="col-span-2">
          <CardHeader className="pb-2">
            <CardTitle>Cycle Time Distribution</CardTitle>
            <CardDescription>Inspection duration histogram (today)</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={cycleTimeData} margin={{ top: 10, right: 20, bottom: 20, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                <XAxis dataKey="range" tick={{ fontSize: 13, fill: "#374151" }} axisLine={false} tickLine={false} dy={8} />
                <YAxis tick={{ fontSize: 13, fill: "#374151" }} axisLine={false} tickLine={false} dx={-5} />
                <Tooltip
                  content={({ active, payload, label }) => {
                    if (!active || !payload?.length) return null;
                    return (
                      <div className="bg-card border border-border rounded-lg shadow-elevated px-4 py-2.5 text-sm">
                        <p className="font-semibold">{label}</p>
                        <p className="text-muted-foreground">{payload[0].value} inspections</p>
                      </div>
                    );
                  }}
                  cursor={{ fill: "rgba(0,0,0,0.03)" }}
                />
                <Bar dataKey="count" radius={[6, 6, 0, 0]} barSize={40}>
                  {cycleTimeData.map((entry) => {
                    // Color: green for fast, amber for mid, red for slow
                    const color =
                      entry.range === "0–20s" ? "#10b981" :
                      entry.range === "20–40s" ? "#3b82f6" :
                      entry.range === "40–60s" ? "#1B2A4A" :
                      entry.range === "60–80s" ? "#f59e0b" :
                      "#ef4444";
                    return <Cell key={entry.range} fill={color} />;
                  })}
                  <LabelList dataKey="count" position="top" style={{ fontSize: 13, fontWeight: 600, fill: "#374151" }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Recent Decisions Stream */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle>Recent Decisions</CardTitle>
          <CardDescription>Latest inspection outcomes across all stations</CardDescription>
        </CardHeader>
        <CardContent>
          {data.recent_decisions.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              No inspections yet. Run a demo scenario to see activity.
            </p>
          ) : (
            <div className="divide-y divide-border/50">
              {data.recent_decisions.map((d, i) => (
                <div key={d.inspection_id || i} className="flex items-center justify-between py-3">
                  <div className="flex items-center gap-3">
                    <Badge
                      variant={d.decision === "PASS" ? "secondary" : d.decision === "FAIL" ? "destructive" : "outline"}
                      className={`w-16 justify-center text-xs font-semibold ${d.decision === "PASS" ? "bg-emerald-50 text-emerald-700" : ""}`}
                    >
                      {d.decision}
                    </Badge>
                    <span className="text-sm font-mono font-medium text-foreground">{d.part_number}</span>
                  </div>
                  <span className="text-sm text-muted-foreground">
                    {d.timestamp ? new Date(d.timestamp).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" }) + ", " + new Date(d.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function KPITile({ label, value, color }: { label: string; value: string | number; color?: string }) {
  const colorClass = color === "green" ? "text-avip-pass" : color === "red" ? "text-avip-fail" : color === "amber" ? "text-avip-review" : "text-foreground";
  return (
    <Card className="relative overflow-hidden">
      <CardContent className="pt-5 pb-5 text-center relative z-10">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{label}</p>
        <p className={`text-3xl font-bold mt-2 tracking-tight ${colorClass}`}>{value}</p>
      </CardContent>
      {color && (
        <div className={`absolute inset-0 opacity-[0.04] ${
          color === "green" ? "bg-avip-pass" : color === "red" ? "bg-avip-fail" : color === "amber" ? "bg-avip-review" : ""
        }`} />
      )}
    </Card>
  );
}

function DashboardSkeleton() {
  return (
    <div className="p-6 lg:p-8 space-y-6">
      <div className="grid grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardContent className="pt-5 pb-5">
              <Skeleton className="h-4 w-24 mx-auto mb-3" />
              <Skeleton className="h-9 w-16 mx-auto" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardContent className="pt-5">
          <Skeleton className="h-56 w-full rounded-lg" />
        </CardContent>
      </Card>
    </div>
  );
}
