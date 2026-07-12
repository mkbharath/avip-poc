import { useQuery } from "@tanstack/react-query";
import { getSupplierDashboard } from "../../api/dashboard";

export function SupplierDashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard", "suppliers"],
    queryFn: getSupplierDashboard,
    refetchInterval: 60_000,
  });

  if (isLoading || !data) {
    return <div className="animate-pulse"><div className="card h-64 bg-gray-100" /></div>;
  }

  const breached = data.suppliers.filter((s) => s.threshold_breached);

  return (
    <div className="space-y-6">
      {/* Threshold breach banner */}
      {breached.length > 0 && (
        <div className="bg-avip-fail/10 border border-avip-fail/30 rounded-xl p-4 flex items-center gap-3">
          <svg className="w-6 h-6 text-avip-fail flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <div>
            <p className="text-sm font-semibold text-avip-fail">
              DPPM Threshold Breached — {breached.length} supplier{breached.length > 1 ? "s" : ""}
            </p>
            <p className="text-xs text-gray-600 mt-0.5">
              {breached.map((s) => s.name).join(", ")}
            </p>
          </div>
        </div>
      )}

      {/* Supplier league table */}
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">Supplier Quality League Table</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 uppercase">#</th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 uppercase">Supplier</th>
                <th className="text-right py-3 px-4 text-xs font-semibold text-gray-500 uppercase">DPPM</th>
                <th className="text-center py-3 px-4 text-xs font-semibold text-gray-500 uppercase">Trend</th>
                <th className="text-right py-3 px-4 text-xs font-semibold text-gray-500 uppercase">Volume</th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 uppercase">Top Defect</th>
                <th className="text-center py-3 px-4 text-xs font-semibold text-gray-500 uppercase">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.suppliers
                .sort((a, b) => b.dppm - a.dppm)
                .map((supplier, idx) => (
                  <tr key={supplier.name} className={`${supplier.threshold_breached ? "bg-red-50" : "hover:bg-gray-50"} transition-colors`}>
                    <td className="py-3 px-4 text-sm text-gray-400">{idx + 1}</td>
                    <td className="py-3 px-4">
                      <span className="text-sm font-medium text-gray-900">{supplier.name}</span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span className={`text-sm font-bold ${
                        supplier.dppm > 6000 ? "text-avip-fail" : supplier.dppm > 4000 ? "text-avip-review" : "text-avip-pass"
                      }`}>
                        {supplier.dppm.toLocaleString()}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <TrendArrow trend={supplier.trend} />
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span className="text-sm text-gray-600">{supplier.volume}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="badge bg-gray-100 text-gray-700 text-xs">{supplier.top_defect}</span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      {supplier.threshold_breached ? (
                        <span className="badge badge-fail text-xs">BREACH</span>
                      ) : (
                        <span className="badge bg-green-50 text-green-700 text-xs">OK</span>
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Summary KPIs */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card text-center">
          <p className="text-xs font-medium text-gray-500 uppercase">Total Suppliers</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{data.suppliers.length}</p>
        </div>
        <div className="card text-center">
          <p className="text-xs font-medium text-gray-500 uppercase">Avg DPPM</p>
          <p className="text-2xl font-bold text-avip-review mt-1">
            {Math.round(data.suppliers.reduce((s, v) => s + v.dppm, 0) / data.suppliers.length).toLocaleString()}
          </p>
        </div>
        <div className="card text-center">
          <p className="text-xs font-medium text-gray-500 uppercase">Threshold Breaches</p>
          <p className={`text-2xl font-bold mt-1 ${breached.length > 0 ? "text-avip-fail" : "text-avip-pass"}`}>
            {breached.length}
          </p>
        </div>
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
  return <span className="text-gray-400 text-lg">→</span>;
}
