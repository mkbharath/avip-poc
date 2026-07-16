import { useQuery } from "@tanstack/react-query";
import { getInspectionDashboard } from "../../api/dashboard";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

  const cycleTimeData = [
    { range: "0-20s", count: 5 },
    { range: "20-40s", count: 18 },
    { range: "40-60s", count: 42 },
    { range: "60-80s", count: 12 },
    { range: "80-100s", count: 3 },
  ];

  return (
    <div className="p-6 space-y-6">
      {/* KPI Strip */}
      <div className="grid grid-cols-4 gap-4">
        <KPITile label="Inspections Today" value={data.today_count} />
        <KPITile label="Pass Rate" value={`${data.pass_rate}%`} color={data.pass_rate > 90 ? "green" : "amber"} />
        <KPITile label="Avg Cycle Time" value={`${data.avg_cycle_time_seconds.toFixed(1)}s`} />
        <KPITile label="Queue Depth" value={data.queue_depth} color={data.queue_depth > 5 ? "red" : "green"} />
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Station Status */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Station Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.stations.map((station) => (
              <div key={station.id} className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                <div className="flex items-center gap-2">
                  <div className={`w-3 h-3 rounded-full ${
                    station.status === "active" ? "bg-avip-pass" : station.status === "idle" ? "bg-muted-foreground/40" : "bg-avip-fail"
                  }`} />
                  <span className="text-sm font-medium text-foreground">{station.name}</span>
                </div>
                <span className="text-sm text-muted-foreground">{station.parts_per_hour} parts/h</span>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Cycle Time Distribution */}
        <Card className="col-span-2">
          <CardHeader>
            <CardTitle className="text-sm">Cycle Time Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={cycleTimeData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="range" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#156082" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Recent Decisions Stream */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Recent Decisions</CardTitle>
        </CardHeader>
        <CardContent>
          {data.recent_decisions.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">
              No inspections yet. Run a demo scenario to see activity.
            </p>
          ) : (
            <div className="space-y-2">
              {data.recent_decisions.map((d) => (
                <div key={d.inspection_id} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
                  <div className="flex items-center gap-3">
                    <Badge
                      variant={d.decision === "PASS" ? "secondary" : d.decision === "FAIL" ? "destructive" : "outline"}
                      className={d.decision === "PASS" ? "bg-emerald-50 text-emerald-700" : ""}
                    >
                      {d.decision}
                    </Badge>
                    <span className="text-sm font-mono text-foreground">{d.part_number}</span>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {d.timestamp ? new Date(d.timestamp).toLocaleTimeString() : "—"}
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
    <Card className="text-center relative overflow-hidden">
      <CardContent className="pt-5 pb-5 relative z-10">
        <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">{label}</p>
        <p className={`text-3xl font-bold mt-2 tracking-tight ${colorClass}`}>{value}</p>
      </CardContent>
      {color && (
        <div className={`absolute inset-0 opacity-[0.03] ${
          color === "green" ? "bg-avip-pass" : color === "red" ? "bg-avip-fail" : color === "amber" ? "bg-avip-review" : ""
        }`} />
      )}
    </Card>
  );
}

function DashboardSkeleton() {
  return (
    <div className="p-6 space-y-6">
      <div className="grid grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardContent className="pt-4 pb-4">
              <Skeleton className="h-4 w-24 mx-auto mb-2" />
              <Skeleton className="h-8 w-16 mx-auto" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardContent className="pt-4">
          <Skeleton className="h-64 w-full" />
        </CardContent>
      </Card>
    </div>
  );
}
