import { useQuery } from "@tanstack/react-query";
import { getAIPerformanceDashboard } from "../../api/dashboard";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";

export function AIPerformanceDashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard", "ai"],
    queryFn: getAIPerformanceDashboard,
    refetchInterval: 60_000,
  });

  if (isLoading || !data) {
    return <div className="animate-pulse"><div className="card h-64 bg-gray-100" /></div>;
  }

  // Combine FPR/FNR trends for dual-line chart
  const ratesTrend = data.fpr_trend.map((fp, i) => ({
    date: fp.date.slice(5),
    FPR: fp.value,
    FNR: data.fnr_trend[i]?.value || 0,
  }));

  return (
    <div className="space-y-6">
      {/* KPI Strip */}
      <div className="grid grid-cols-4 gap-4">
        <div className="card text-center">
          <p className="text-xs font-medium text-gray-500 uppercase">Overall Accuracy</p>
          <p className="text-3xl font-bold text-avip-pass mt-1">{data.accuracy}%</p>
          <p className="text-xs text-gray-400 mt-1">Target: ≥97%</p>
        </div>
        <div className="card text-center">
          <p className="text-xs font-medium text-gray-500 uppercase">False Positive Rate</p>
          <p className={`text-3xl font-bold mt-1 ${data.fpr <= 5 ? "text-avip-pass" : "text-avip-review"}`}>
            {data.fpr}%
          </p>
          <p className="text-xs text-gray-400 mt-1">Target: ≤5%</p>
        </div>
        <div className="card text-center">
          <p className="text-xs font-medium text-gray-500 uppercase">False Negative Rate</p>
          <p className={`text-3xl font-bold mt-1 ${data.fnr <= 1 ? "text-avip-pass" : "text-avip-fail"}`}>
            {data.fnr}%
          </p>
          <p className="text-xs text-gray-400 mt-1">Target: ≤1%</p>
        </div>
        <div className="card text-center">
          <p className="text-xs font-medium text-gray-500 uppercase">Model Version</p>
          <p className="text-lg font-bold text-gray-900 mt-2">{data.model_info.version}</p>
          <p className="text-xs text-gray-400 mt-1">Updated: {data.model_info.last_updated}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* FPR / FNR Trend */}
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">FPR / FNR Trend (7 days)</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={ratesTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} domain={[0, "auto"]} unit="%" />
              <Tooltip formatter={(value: number) => `${value.toFixed(2)}%`} />
              <ReferenceLine y={5} stroke="#E67E22" strokeDasharray="5 5" label={{ value: "FPR target", position: "right", fontSize: 10 }} />
              <ReferenceLine y={1} stroke="#C0392B" strokeDasharray="5 5" label={{ value: "FNR target", position: "right", fontSize: 10 }} />
              <Line type="monotone" dataKey="FPR" stroke="#E67E22" strokeWidth={2} dot={{ r: 3 }} />
              <Line type="monotone" dataKey="FNR" stroke="#C0392B" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Confidence Distribution */}
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Confidence Score Distribution</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.confidence_histogram}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="range" tick={{ fontSize: 10 }} angle={-30} textAnchor="end" height={50} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#156082" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Override Rate by Class */}
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">
          Override Rate by Defect Class
          <span className="text-xs font-normal text-gray-400 ml-2">
            (% of AI decisions overridden by IQA)
          </span>
        </h3>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data.override_by_class} layout="vertical" margin={{ left: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
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
        <p className="text-xs text-gray-400 mt-2">
          High override rates indicate model disagreement with human reviewers — candidates for retraining focus.
        </p>
      </div>

      {/* Model Info Card */}
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">Active Models</h3>
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="text-xs font-medium text-gray-500 uppercase">Anomaly Detection</p>
            <p className="text-sm font-bold text-gray-900 mt-1">{data.model_info.anomaly_model}</p>
            <p className="text-xs text-gray-400 mt-0.5">PatchCore • ONNX Runtime • Edge inference</p>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="text-xs font-medium text-gray-500 uppercase">Defect Detection</p>
            <p className="text-sm font-bold text-gray-900 mt-1">{data.model_info.detection_model}</p>
            <p className="text-xs text-gray-400 mt-0.5">YOLOv8n • ONNX Runtime • 10 classes</p>
          </div>
        </div>
      </div>
    </div>
  );
}

// Helper component for conditional bar coloring
function BarCell({ overrideRate }: { overrideRate: number }) {
  const fill = overrideRate > 15 ? "#C0392B" : overrideRate > 8 ? "#E67E22" : "#1E8E3E";
  return <rect fill={fill} />;
}
