import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getReviewQueue } from "../../api/inspections";
import { LamResearchLogo, IdeyaLabsLogo } from "../common/Logo";
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
    <div className="min-h-screen bg-gray-900">
      {/* Header */}
      <header className="bg-lam-navy px-6 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <LamResearchLogo variant="light" className="h-8" />
            <div className="w-px h-5 bg-white/20" />
            <span className="text-white/60 text-xs font-medium">AI Vision Inspection Platform</span>
            <div className="w-px h-5 bg-white/10" />
            <div>
              <h1 className="text-sm font-bold text-white">IQA Review Queue</h1>
              <p className="text-xs text-white/50">
                {filtered.length} items pending review
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/kiosk" className="text-sm text-white/50 hover:text-white">
              ← Station
            </Link>
            <Link to="/dashboard" className="text-sm text-white/50 hover:text-white">
              Dashboard →
            </Link>
            <div className="w-px h-4 bg-white/10" />
            <div className="flex items-center gap-1.5">
              <span className="text-white/30 text-[10px]">Powered by</span>
              <IdeyaLabsLogo variant="light" className="h-4" />
            </div>
          </div>
        </div>
      </header>

      <div className="flex">
        {/* Filter sidebar */}
        <aside className="w-56 bg-gray-800 border-r border-gray-700 p-4 min-h-[calc(100vh-73px)]">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Filters</h3>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Part Family</label>
              <select
                value={familyFilter}
                onChange={(e) => setFamilyFilter(e.target.value)}
                className="w-full border border-gray-600 bg-gray-700 text-gray-200 rounded-lg px-3 py-2 text-sm"
              >
                <option value="">All families</option>
                {families.map((f) => (
                  <option key={f} value={f}>{f}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Defect Class</label>
              <select
                value={classFilter}
                onChange={(e) => setClassFilter(e.target.value)}
                className="w-full border border-gray-600 bg-gray-700 text-gray-200 rounded-lg px-3 py-2 text-sm"
              >
                <option value="">All classes</option>
                {allClasses.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            <button
              onClick={() => { setFamilyFilter(""); setClassFilter(""); }}
              className="text-sm text-lam-green hover:underline"
            >
              Clear filters
            </button>
          </div>
        </aside>

        {/* Queue table */}
        <main className="flex-1 p-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-20">
              <div className="animate-spin w-8 h-8 border-4 border-avip-info border-t-transparent rounded-full" />
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
            <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="bg-gray-800 border-b border-gray-700">
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase">Priority</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase">Age</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase">Part Number</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase">Family</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase">Supplier</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase">Defects</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase">Confidence</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase">Decision</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {filtered.map((item) => (
                    <QueueRow key={item.id} item={item} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

function QueueRow({ item }: { item: ReviewQueueItem }) {
  const ageMinutes = Math.floor(item.age_seconds / 60);
  const ageDisplay = ageMinutes < 60 ? `${ageMinutes}m` : `${Math.floor(ageMinutes / 60)}h ${ageMinutes % 60}m`;

  const ageSLA = ageMinutes > 240; // 4 hour SLA
  const ageWarning = ageMinutes > 120;

  return (
    <tr className="hover:bg-gray-700/50 transition-colors cursor-pointer group">
      <td className="px-4 py-3">
        <PriorityBadge priority={item.priority} />
      </td>
      <td className="px-4 py-3">
        <span className={`text-sm font-medium ${ageSLA ? "text-avip-fail" : ageWarning ? "text-avip-review" : "text-gray-300"}`}>
          {ageDisplay}
        </span>
      </td>
      <td className="px-4 py-3">
        <span className="text-sm font-mono font-bold text-white">{item.part_number}</span>
      </td>
      <td className="px-4 py-3">
        <span className="text-sm text-gray-400">{item.family_name}</span>
      </td>
      <td className="px-4 py-3">
        <span className="text-sm text-gray-400">{item.supplier}</span>
      </td>
      <td className="px-4 py-3">
        <div className="flex gap-1 flex-wrap">
          {item.defect_classes.map((dc) => (
            <span key={dc} className="badge bg-gray-700 text-gray-300 text-xs">{dc}</span>
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
