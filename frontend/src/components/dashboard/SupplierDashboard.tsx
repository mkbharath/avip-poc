import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { getSupplierDashboard } from "../../api/dashboard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";

export function SupplierDashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard", "suppliers"],
    queryFn: getSupplierDashboard,
    refetchInterval: 60_000,
  });

  if (isLoading || !data) {
    return (
      <div className="p-6">
        <Card><CardContent className="pt-4"><Skeleton className="h-64 w-full" /></CardContent></Card>
      </div>
    );
  }

  const breached = data.suppliers.filter((s) => s.threshold_breached);

  return (
    <div className="p-6 space-y-6">
      {/* Threshold breach banner */}
      {breached.length > 0 && (
        <div className="bg-destructive/10 border border-destructive/30 rounded-xl p-4 flex items-center gap-3">
          <AlertTriangle className="w-6 h-6 text-destructive flex-shrink-0" />
          <div>
            <p className="text-sm font-semibold text-destructive">
              DPPM Threshold Breached — {breached.length} supplier{breached.length > 1 ? "s" : ""}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {breached.map((s) => s.name).join(", ")}
            </p>
          </div>
        </div>
      )}

      {/* Supplier league table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Supplier Quality League Table</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs uppercase">#</TableHead>
                <TableHead className="text-xs uppercase">Supplier</TableHead>
                <TableHead className="text-xs uppercase text-right">DPPM</TableHead>
                <TableHead className="text-xs uppercase text-center">Trend</TableHead>
                <TableHead className="text-xs uppercase text-right">Volume</TableHead>
                <TableHead className="text-xs uppercase">Top Defect</TableHead>
                <TableHead className="text-xs uppercase text-center">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.suppliers
                .sort((a, b) => b.dppm - a.dppm)
                .map((supplier, idx) => (
                  <TableRow key={supplier.name} className={supplier.threshold_breached ? "bg-destructive/5" : ""}>
                    <TableCell className="text-muted-foreground">{idx + 1}</TableCell>
                    <TableCell>
                      <span className="font-medium text-foreground">{supplier.name}</span>
                    </TableCell>
                    <TableCell className="text-right">
                      <span className={`font-bold ${
                        supplier.dppm > 6000 ? "text-avip-fail" : supplier.dppm > 4000 ? "text-avip-review" : "text-avip-pass"
                      }`}>
                        {supplier.dppm.toLocaleString()}
                      </span>
                    </TableCell>
                    <TableCell className="text-center">
                      <TrendArrow trend={supplier.trend} />
                    </TableCell>
                    <TableCell className="text-right text-muted-foreground">
                      {supplier.volume}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-xs">{supplier.top_defect}</Badge>
                    </TableCell>
                    <TableCell className="text-center">
                      {supplier.threshold_breached ? (
                        <Badge variant="destructive" className="text-xs">BREACH</Badge>
                      ) : (
                        <Badge variant="secondary" className="text-xs bg-emerald-50 text-emerald-700">OK</Badge>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Summary KPIs */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="text-center">
          <CardContent className="pt-4 pb-4">
            <p className="text-xs font-medium text-muted-foreground uppercase">Total Suppliers</p>
            <p className="text-2xl font-bold text-foreground mt-1">{data.suppliers.length}</p>
          </CardContent>
        </Card>
        <Card className="text-center">
          <CardContent className="pt-4 pb-4">
            <p className="text-xs font-medium text-muted-foreground uppercase">Avg DPPM</p>
            <p className="text-2xl font-bold text-avip-review mt-1">
              {Math.round(data.suppliers.reduce((s, v) => s + v.dppm, 0) / data.suppliers.length).toLocaleString()}
            </p>
          </CardContent>
        </Card>
        <Card className="text-center">
          <CardContent className="pt-4 pb-4">
            <p className="text-xs font-medium text-muted-foreground uppercase">Threshold Breaches</p>
            <p className={`text-2xl font-bold mt-1 ${breached.length > 0 ? "text-avip-fail" : "text-avip-pass"}`}>
              {breached.length}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function TrendArrow({ trend }: { trend: string }) {
  if (trend === "up") {
    return <span className="text-avip-fail text-lg font-bold">↑</span>;
  }
  if (trend === "down") {
    return <span className="text-avip-pass text-lg font-bold">↓</span>;
  }
  return <span className="text-muted-foreground text-lg">→</span>;
}
