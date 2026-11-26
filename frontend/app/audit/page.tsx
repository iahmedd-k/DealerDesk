"use client";

import { useEffect, useMemo, useState } from "react";
import { Eye, FileCode, Search, X, AlertCircle } from "lucide-react";
import Shell from "../components/Shell";
import { api } from "../api";
import { useAuth } from "../providers";
import type { AuditLogItem } from "../lib/types";

function getActionBadge(action: string) {
  const lower = action.toLowerCase();
  if (lower.includes("created") || lower.includes("invited")) {
    return "crm-badge crm-badge-info";
  }
  if (lower.includes("booked") || lower.includes("confirmed") || lower.includes("won")) {
    return "crm-badge crm-badge-success";
  }
  if (lower.includes("deleted") || lower.includes("cancelled") || lower.includes("revoked")) {
    return "crm-badge crm-badge-danger";
  }
  return "crm-badge crm-badge-neutral";
}

export default function AuditPage() {
  const { user, authReady, activeDealershipId } = useAuth();
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionFilter, setActionFilter] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedLog, setSelectedLog] = useState<AuditLogItem | null>(null);

  useEffect(() => {
    if (!authReady || !user) return;
    if (!activeDealershipId) {
      setLoading(false);
      setError("Select a dealership workspace to inspect audit logs.");
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError("");
    api<{ items: AuditLogItem[] }>(
      `/dealerships/${activeDealershipId}/audit-logs`,
    )
      .then((res) => {
        if (!cancelled) setLogs(res.items);
      })
      .catch((cause: unknown) => {
        if (!cancelled)
          setError(cause instanceof Error ? cause.message : "Could not load audit logs.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [authReady, user, activeDealershipId]);

  const distinctActions = useMemo(
    () => Array.from(new Set(logs.map((l) => l.action))).sort(),
    [logs],
  );

  const filteredLogs = logs.filter((log) => {
    const matchesAction = actionFilter === "all" || log.action === actionFilter;
    const q = searchTerm.trim().toLowerCase();
    const matchesSearch =
      !q ||
      log.actor_email.toLowerCase().includes(q) ||
      log.action.toLowerCase().includes(q) ||
      log.resource_type.toLowerCase().includes(q) ||
      (log.ip_address || "").toLowerCase().includes(q);
    return matchesAction && matchesSearch;
  });

  return (
    <Shell>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-medium tracking-tight text-[#171717]">
            Compliance & Audit Trail
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Immutable activity log of dealership mutations, bookings, and staff actions
          </p>
        </div>
      </div>

      {error && (
        <div className="mb-5 flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-xs font-medium text-rose-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="crm-card p-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
          <div className="md:col-span-7 relative">
            <Search className="h-4 w-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by actor email, action, resource, or IP..."
              className="crm-input pl-9"
            />
          </div>
          <div className="md:col-span-5">
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="crm-select"
            >
              <option value="all">All Actions ({logs.length})</option>
              {distinctActions.map((action) => (
                <option key={action} value={action}>
                  {action}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="crm-card p-12 text-center text-sm text-slate-500">
          Loading audit trail...
        </div>
      ) : (
        <div className="crm-table-wrap">
          <table className="crm-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Resource</th>
                <th>IP Address</th>
                <th className="text-right">Payload</th>
              </tr>
            </thead>
            <tbody>
              {filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-10 text-center text-sm text-slate-500">
                    No audit events match the current filter.
                  </td>
                </tr>
              ) : (
                filteredLogs.map((log) => (
                  <tr key={log.id}>
                    <td className="font-mono text-xs text-slate-600">
                      {new Date(log.created_at).toLocaleString([], {
                        dateStyle: "short",
                        timeStyle: "medium",
                      })}
                    </td>
                    <td>
                      <div className="font-semibold text-slate-900 text-xs">
                        {log.actor_email}
                      </div>
                      <div className="text-[11px] text-slate-500 font-mono">
                        Actor ID: {log.actor_id ?? "system"}
                      </div>
                    </td>
                    <td>
                      <span className={getActionBadge(log.action)}>{log.action}</span>
                    </td>
                    <td className="font-mono text-xs text-slate-700">
                      {log.resource_type} (#{log.resource_id})
                    </td>
                    <td className="font-mono text-xs text-slate-500">{log.ip_address}</td>
                    <td className="text-right">
                      <button
                        type="button"
                        onClick={() => setSelectedLog(log)}
                        className="crm-btn-secondary py-1 px-2.5 text-xs"
                      >
                        <Eye className="h-3.5 w-3.5" />
                        View JSON
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {selectedLog && (
        <div className="crm-modal-overlay">
          <div className="crm-modal max-w-xl p-6">
            <div className="flex items-start justify-between border-b border-slate-200 pb-4 mb-4">
              <div>
                <h3 className="text-base font-medium text-[#171717] flex items-center gap-2">
                  <FileCode className="h-4 w-4 text-blue-600" />
                  Audit Record #{selectedLog.id}
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  {selectedLog.action} by {selectedLog.actor_email}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedLog(null)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs mb-4">
              <div>
                <span className="text-slate-500">Timestamp</span>
                <p className="font-mono text-slate-900 text-[11px] mt-0.5">
                  {selectedLog.created_at}
                </p>
              </div>
              <div>
                <span className="text-slate-500">Resource</span>
                <p className="font-mono text-slate-900 text-[11px] mt-0.5">
                  {selectedLog.resource_type} #{selectedLog.resource_id}
                </p>
              </div>
            </div>

            <pre className="rounded-lg border border-slate-200 bg-slate-900 text-slate-100 p-4 text-xs overflow-x-auto max-h-72">
              {JSON.stringify(selectedLog.details ?? {}, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </Shell>
  );
}
