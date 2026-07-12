import { useQuery } from "@tanstack/react-query";
import { getInspectionDashboard } from "../../api/dashboard";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

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
    <div className="space-y-6">
      {/* KPI Strip */}
      <div className="grid grid-cols-4 gap-4">
        <KPITile label="Inspections Today" value={data.today_count} />
        <KPITile label="Pass Rate" value={`${data.pass_rate}%`} color={data.pass_rate > 90 ? "green" : "amber"} />
        <KPITile label="Avg Cycle Time" value={`${data.avg_cycle_time_seconds.toFixed(1)}s`} />
        <KPITile label="Queue Depth" value={data.queue_depth} color={data.queue_depth > 5 ? "red" : "green"} />
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Station Status */}
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Station Status</h3>
          <div className="space-y-3">
            {data.stations.map((station) => (
              <div key={station.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-2">
                  <div className={`w-3 h-3 rounded-full ${
                    station.status === "active" ? "bg-avip-pass" : station.status === "idle" ? "bg-gray-400" : "bg-avip-fail"
                  }`} />
                  <span className="text-sm font-medium text-gray-700">{station.name}</span>
                </div>
                <div className="text-right">
                  <span className="text-sm text-gray-500">{station.parts_per_hour} parts/h</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Cycle Time Distribution */}
        <div className="card col-span-2">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Cycle Time Distribution</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={cycleTimeData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="range" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#156082" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Recent Decisions Stream */}
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">Recent Decisions</h3>
        {data.recent_decisions.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-6">No inspections yet. Run a demo scenario to see activity.</p>
        ) : (
          <div className="space-y-2">
            {data.recent_decisions.map((d) => (
              <div key={d.inspection_id} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                <div className="flex items-center gap-3">
                  <span className={`badge ${
                    d.decision === "PASS" ? "badge-pass" : d.decision === "FAIL" ? "badge-fail" : "badge-review"
                  }`}>
                    {d.decision}
                  </span>
                  <span className="text-sm font-mono text-gray-700">{d.part_number}</span>
                </div>
                <span className="text-xs text-gray-400">
                  {d.timestamp ? new Date(d.timestamp).toLocaleTimeString() : "—"}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function KPITile({ label, value, color }: { label: string; value: string | number; color?: string }) {
  const colorClass = color === "green" ? "text-avip-pass" : color === "red" ? "text-avip-fail" : color === "amber" ? "text-avip-review" : "text-gray-900";
  return (
    <div className="card text-center">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${colorClass}`}>{value}</p>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="grid grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="card h-24 bg-gray-100" />
        ))}
      </div>
      <div className="card h-64 bg-gray-100" />
    </div>
  );
}
