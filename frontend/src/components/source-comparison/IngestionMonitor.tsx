import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AlertTriangle } from "lucide-react";
import { getStatus } from "../../api/source-comparison";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { SCAssumption } from "../../types";

export function IngestionMonitor() {
  const { data, isLoading } = useQuery({
    queryKey: ["sc", "status"],
    queryFn: getStatus,
    refetchInterval: 5000,
  });

  if (isLoading || !data) {
    return <MonitorSkeleton />;
  }

  const groupData = [
    { label: "Partial", count: data.groups_partial },
    { label: "Complete", count: data.groups_complete },
  ];

  return (
    <div className="p-6 space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-bold text-foreground tracking-tight">Ingestion Monitor</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Live status of the LAIR / FAIR / SHQ record feed
        </p>
      </div>

      {/* Assumptions banner (Req 8.5) */}
      <AssumptionsBanner assumptions={data.assumptions} />

      {/* Metric cards */}
      <div className="grid grid-cols-4 gap-4">
        <MetricTile label="Records Ingested" value={data.ingested} />
        <MetricTile
          label="Records Rejected"
          value={data.rejected}
          color={data.rejected > 0 ? "red" : "green"}
        />
        <MetricTile
          label="Groups Partial"
          value={data.groups_partial}
          color={data.groups_partial > 0 ? "amber" : "green"}
        />
        <MetricTile label="Groups Complete" value={data.groups_complete} color="green" />
      </div>

      {/* Alignment progress chart */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle>Aligned Groups</CardTitle>
          <CardDescription>Partial vs. complete alignment across all sources</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={groupData} margin={{ top: 10, right: 20, bottom: 20, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 13, fill: "#374151" }}
                axisLine={false}
                tickLine={false}
                dy={8}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fontSize: 13, fill: "#374151" }}
                axisLine={false}
                tickLine={false}
                dx={-5}
              />
              <Tooltip
                content={({ active, payload, label }) => {
                  if (!active || !payload?.length) return null;
                  return (
                    <div className="bg-card border border-border rounded-lg shadow-elevated px-4 py-2.5 text-sm">
                      <p className="font-semibold">{label}</p>
                      <p className="text-muted-foreground">{payload[0].value} groups</p>
                    </div>
                  );
                }}
                cursor={{ fill: "rgba(0,0,0,0.03)" }}
              />
              <Bar dataKey="count" radius={[6, 6, 0, 0]} barSize={64}>
                {groupData.map((entry) => (
                  <Cell
                    key={entry.label}
                    fill={entry.label === "Complete" ? "#10b981" : "#f59e0b"}
                  />
                ))}
                <LabelList
                  dataKey="count"
                  position="top"
                  style={{ fontSize: 13, fontWeight: 600, fill: "#374151" }}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}

function MetricTile({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color?: "green" | "red" | "amber";
}) {
  const colorClass =
    color === "green"
      ? "text-avip-pass"
      : color === "red"
      ? "text-avip-fail"
      : color === "amber"
      ? "text-avip-review"
      : "text-foreground";

  return (
    <Card className="relative overflow-hidden">
      <CardContent className="pt-5 pb-5 text-center relative z-10">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          {label}
        </p>
        <p className={`text-3xl font-bold mt-2 tracking-tight ${colorClass}`}>{value}</p>
      </CardContent>
      {color && (
        <div
          className={`absolute inset-0 opacity-[0.04] ${
            color === "green" ? "bg-avip-pass" : color === "red" ? "bg-avip-fail" : "bg-avip-review"
          }`}
        />
      )}
    </Card>
  );
}

function AssumptionsBanner({ assumptions }: { assumptions: SCAssumption[] }) {
  if (assumptions.length === 0) return null;

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
        <div className="space-y-2">
          <p className="text-sm font-semibold text-amber-900">
            Assumptions in effect — pending client confirmation
          </p>
          <ul className="space-y-1.5">
            {assumptions.map((a) => (
              <li key={a.key} className="flex items-start gap-2 text-xs text-amber-900">
                <Badge
                  variant="outline"
                  className="border-amber-300 bg-amber-100 text-amber-800"
                >
                  {a.status === "unresolved" ? "unresolved" : "assumed"}
                </Badge>
                <span>
                  <span className="font-medium">{a.label}</span>
                  {a.value ? <span className="text-amber-800/80"> — {a.value}</span> : null}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

function MonitorSkeleton() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-4 w-72 mt-2" />
      </div>
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
          <Skeleton className="h-48 w-full rounded-lg" />
        </CardContent>
      </Card>
    </div>
  );
}
