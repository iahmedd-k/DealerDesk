"use client";

import { useEffect, useState } from "react";
import {
  ShieldAlert,
  Search,
  Filter,
  CheckCircle2,
  Lock,
  Eye,
  X,
  FileCode,
  Activity,
} from "lucide-react";
import Shell from "../components/Shell";
import { useAuth } from "../providers";
import { api } from "../api";
import { MOCK_AUDIT_LOGS, AuditLogItem } from "../lib/mockData";

export default function AuditPage() {
  const { activeDealershipId } = useAuth();
  const [logs, setLogs] = useState<AuditLogItem[]>(MOCK_AUDIT_LOGS);
  const [filterAction, setFilterAction] = useState<string>("all");
  const [selectedLog, setSelectedLog] = useState<AuditLogItem | null>(null);

  useEffect(() => {
    api<{ items: AuditLogItem[] }>(`/dealerships/${activeDealershipId}/audit-logs`)
      .then((data) => {
        if (data && Array.isArray(data.items) && data.items.length) {
          setLogs(data.items);
        }
      })
      .catch(() => {});
  }, [activeDealershipId]);

  const filteredLogs = logs.filter((log) => {
    return filterAction === "all" || log.action === filterAction;
  });

  return (
    <Shell>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            <p className="text-xs font-bold uppercase tracking-wider text-emerald-400">
              Enterprise Compliance & Governance
            </p>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Security & System Audit Logs
          </h1>
          <p className="text-xs text-slate-400">
            Immutable audit trails capturing actor, IP, timestamp, action, and JSON event metadata
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="text-slate-400">Filter Action:</span>
          <select
            value={filterAction}
            onChange={(e) => setFilterAction(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 outline-none"
          >
            <option value="all">All Security Events</option>
            <option value="VEHICLE_CREATED">VEHICLE_CREATED</option>
            <option value="TEST_DRIVE_BOOKED">TEST_DRIVE_BOOKED</option>
            <option value="DOCUMENT_INGESTED">DOCUMENT_INGESTED</option>
            <option value="STAFF_INVITED">STAFF_INVITED</option>
            <option value="LOGIN_SUCCESS">LOGIN_SUCCESS</option>
          </select>
        </div>
      </div>

      {/* Audit Logs Table */}
      <div className="erp-table-container">
        <table className="erp-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Actor & Identity</th>
              <th>Action Event</th>
              <th>Resource Target</th>
              <th>IP Address</th>
              <th>Inspect Payload</th>
            </tr>
          </thead>
          <tbody>
            {filteredLogs.map((log) => (
              <tr key={log.id}>
                <td className="font-mono text-slate-300 text-xs">
                  {new Date(log.created_at).toLocaleString([], {
                    dateStyle: "short",
                    timeStyle: "medium",
                  })}
                </td>
                <td>
                  <div className="font-bold text-white text-xs">{log.actor_email}</div>
                  <div className="text-[10px] text-slate-500 font-mono">Actor ID: {log.actor_id ?? "system"}</div>
                </td>
                <td>
                  <span
                    className={`badge ${
                      log.action.includes("CREATED") || log.action.includes("INVITED")
                        ? "badge-info"
                        : log.action.includes("BOOKED")
                        ? "badge-success"
                        : "badge-neutral"
                    }`}
                  >
                    {log.action}
                  </span>
                </td>
                <td>
                  <span className="font-mono text-slate-300 text-xs">
                    {log.resource_type} (#{log.resource_id})
                  </span>
                </td>
                <td className="font-mono text-slate-400 text-xs">{log.ip_address}</td>
                <td>
                  <button
                    onClick={() => setSelectedLog(log)}
                    className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 font-semibold"
                  >
                    <Eye className="h-3.5 w-3.5" />
                    <span>View JSON</span>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!filteredLogs.length && (
          <div className="p-8 text-center text-xs text-slate-400">
            No audit records found matching selected action.
          </div>
        )}
      </div>

      {/* Payload Inspection Modal */}
      {selectedLog && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="p-5 border-b border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <FileCode className="h-4 w-4 text-blue-400" />
                  Audit Record #{selectedLog.id}
                </h3>
                <p className="text-xs text-slate-400">
                  {selectedLog.action} executed by {selectedLog.actor_email}
                </p>
              </div>
              <button onClick={() => setSelectedLog(null)} className="text-slate-400 hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-5 space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3 bg-slate-950 p-3 rounded-lg border border-slate-800">
                <div>
                  <span className="text-slate-400">Timestamp:</span>
                  <p className="font-mono text-white text-[11px]">{selectedLog.created_at}</p>
                </div>
                <div>
                  <span className="text-slate-400">Client IP:</span>
                  <p className="font-mono text-white text-[11px]">{selectedLog.ip_address}</p>
                </div>
                <div>
                  <span className="text-slate-400">Resource Target:</span>
                  <p className="font-mono text-slate-200 text-[11px]">
                    {selectedLog.resource_type}:{selectedLog.resource_id}
                  </p>
                </div>
                <div>
                  <span className="text-slate-400">Dealership Workspace:</span>
                  <p className="font-mono text-slate-200 text-[11px]">Dealership #{selectedLog.dealership_id}</p>
                </div>
              </div>

              <div>
                <span className="text-slate-400 font-semibold mb-1 block">Event Detail Payload:</span>
                <pre className="bg-slate-950 p-4 rounded-xl border border-slate-800 text-emerald-400 font-mono text-[11px] overflow-x-auto">
                  {JSON.stringify(selectedLog.details, null, 2)}
                </pre>
              </div>
            </div>

            <div className="p-4 border-t border-slate-800 flex justify-end bg-slate-950">
              <button onClick={() => setSelectedLog(null)} className="btn-secondary">
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </Shell>
  );
}
