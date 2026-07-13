import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getReviewQueue } from "../../api/inspections";
import type { ReviewQueueItem } from "../../types";

export function ReviewQueue() {
  const [familyFilter, setFamilyFilter] = useState<string>("");
  const [classFilter, setClassFilter] = useState<string>("");

  const { data, isLoading } = useQuery({
    queryKey: ["reviewQueue"],
    queryFn: getReviewQueue,
    refetchInterval: 10_000,
  });

  const queue = data?.data || [];

  const filtered = queue.filter((item) => {
    if (familyFilter && item.family_name !== familyFilter) return false;
    if (classFilter && !item.defect_classes.includes(classFilter)) return false;
    return true;
  });

  const families = [...new Set(queue.map((i) => i.family_name))];
  const allClasses = [...new Set(queue.flatMap((i) => i.defect_classes))];

  return (
    <div className="page-content">
      {/* Page header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">IQA Review Queue</h1>
          <p className="page-subtitle">{filtered.length} items pending review</p>
        </div>
      </div>

      {/* Filters row */}
      <div className="flex items-center gap-4 mb-6">
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Part Family</label>
          <select
            value={familyFilter}
            onChange={(e) => setFamilyFilter(e.target.value)}
            className="bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:border-lam-navy focus:ring-2 focus:ring-lam-navy/10"
          >
            <option value="">All families</option>
            {families.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Defect Class</label>
          <select
            value={classFilter}
            onChange={(e) => setClassFilter(e.target.value)}
            className="bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:border-lam-navy focus:ring-2 focus:ring-lam-navy/10"
          >
            <option value="">All classes</option>
            {allClasses.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>

        <button
          onClick={() => { setFamilyFilter(""); setClassFilter(""); }}
          className="text-sm text-lam-navy hover:underline mt-4"
        >
          Clear filters
        </button>
      </div>

      {/* Queue table */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin w-8 h-8 border-4 border-lam-navy border-t-transparent rounded-full" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20">
          <svg className="w-16 h-16 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h3 className="text-lg font-medium text-gray-500">Queue is empty</h3>
          <p className="text-sm text-gray-400 mt-1">All inspections have been reviewed</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Priority</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Age</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Part Number</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Family</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Supplier</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Defects</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Confidence</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Decision</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.map((item) => (
                <QueueRow key={item.id} item={item} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function QueueRow({ item }: { item: ReviewQueueItem }) {
  const ageMinutes = Math.floor(item.age_seconds / 60);
  const ageDisplay = ageMinutes < 60 ? `${ageMinutes}m` : `${Math.floor(ageMinutes / 60)}h ${ageMinutes % 60}m`;

  const ageSLA = ageMinutes > 240; // 4 hour SLA
  const ageWarning = ageMinutes > 120;

  return (
    <tr className="hover:bg-gray-50 transition-colors cursor-pointer group">
      <td className="px-4 py-3">
        <PriorityBadge priority={item.priority} />
      </td>
      <td className="px-4 py-3">
        <span className={`text-sm font-medium ${ageSLA ? "text-avip-fail" : ageWarning ? "text-avip-review" : "text-gray-900"}`}>
          {ageDisplay}
        </span>
      </td>
      <td className="px-4 py-3">
        <span className="text-sm font-mono font-bold text-gray-900">{item.part_number}</span>
      </td>
      <td className="px-4 py-3">
        <span className="text-sm text-gray-500">{item.family_name}</span>
      </td>
      <td className="px-4 py-3">
        <span className="text-sm text-gray-500">{item.supplier}</span>
      </td>
      <td className="px-4 py-3">
        <div className="flex gap-1 flex-wrap">
          {item.defect_classes.map((dc) => (
            <span key={dc} className="badge bg-gray-100 text-gray-600 border border-gray-200 text-xs">{dc}</span>
          ))}
        </div>
      </td>
      <td className="px-4 py-3">
        <ConfidenceBadge band={item.confidence_band} />
      </td>
      <td className="px-4 py-3">
        <span className={`badge ${item.decision === "FAIL" ? "badge-fail" : "badge-review"}`}>
          {item.decision}
        </span>
      </td>
      <td className="px-4 py-3">
        <Link
          to={`/review/${item.id}`}
          className="opacity-0 group-hover:opacity-100 transition-opacity btn-primary text-xs px-3 py-1.5 min-h-0"
        >
          Review
        </Link>
      </td>
    </tr>
  );
}

function PriorityBadge({ priority }: { priority: number }) {
  const level = priority > 70 ? "high" : priority > 40 ? "medium" : "low";
  const colors = {
    high: "bg-red-100 text-red-700 border-red-200",
    medium: "bg-yellow-100 text-yellow-700 border-yellow-200",
    low: "bg-gray-100 text-gray-600 border-gray-200",
  };

  return (
    <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-xs font-bold border ${colors[level]}`}>
      {priority}
    </span>
  );
}

function ConfidenceBadge({ band }: { band: string }) {
  const colors = {
    high: "bg-red-50 text-red-700",
    medium: "bg-yellow-50 text-yellow-700",
    low: "bg-green-50 text-green-700",
  };

  return (
    <span className={`badge text-xs ${colors[band as keyof typeof colors] || colors.medium}`}>
      {band}
    </span>
  );
}
