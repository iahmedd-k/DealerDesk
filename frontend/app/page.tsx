"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Car,
  Calendar,
  Sparkles,
  Users,
  ShieldCheck,
  TrendingUp,
  Clock,
  ArrowRight,
  Plus,
  CheckCircle2,
  AlertCircle,
  FileText,
  DollarSign,
  Activity,
} from "lucide-react";
import Shell from "./components/Shell";
import { useAuth } from "./providers";
import { api } from "./api";
import {
  Vehicle,
  TestDriveBooking,
  TestDriveSlot,
  AuditLogItem,
  HealthStatus,
  KnowledgeDocument,
} from "./lib/types";

export default function DashboardPage() {
  const { user, activeDealershipId } = useAuth();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [bookings, setBookings] = useState<TestDriveBooking[]>([]);
  const [slots, setSlots] = useState<TestDriveSlot[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    if (!activeDealershipId) {
      setLoading(false);
      setLoadError("Select a dealership workspace to view its dashboard.");
      return;
    }

    let cancelled = false;
    setLoading(true);
    setLoadError("");
    Promise.all([
      api<Vehicle[]>(`/dealerships/${activeDealershipId}/vehicles`),
      api<TestDriveSlot[]>(`/dealerships/${activeDealershipId}/test-drive-slots`),
      api<TestDriveBooking[]>(`/dealerships/${activeDealershipId}/test-drive-bookings`),
      api<{ items: AuditLogItem[] }>(`/dealerships/${activeDealershipId}/audit-logs`),
      api<KnowledgeDocument[]>(`/dealerships/${activeDealershipId}/knowledge/documents`),
      api<HealthStatus>("/health"),
    ])
      .then(([nextVehicles, nextSlots, nextBookings, nextAudit, nextDocuments, nextHealth]) => {
        if (cancelled) return;
        setVehicles(nextVehicles);
        setSlots(nextSlots);
        setBookings(nextBookings);
        setAuditLogs(nextAudit.items);
        setDocuments(nextDocuments);
        setHealth(nextHealth);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setLoadError(error instanceof Error ? error.message : "Could not load dashboard data.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [activeDealershipId]);

  // Calculations
  const totalValuation = vehicles.reduce((sum, v) => sum + (Number(v.price) || 0), 0);
  const availableVehiclesCount = vehicles.filter((v) => v.is_available).length;
  const activeBookingsCount = bookings.filter((b) => b.status === "booked").length;

  return (
    <Shell>
      {/* Executive Welcome & Quick Action Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8 bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 border border-slate-700/60 p-6 rounded-2xl shadow-xl">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
            <p className="text-xs font-bold uppercase tracking-wider text-blue-400">
              Executive ERP Command Center
            </p>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Welcome back, {user?.name || "Marcus"}
          </h1>
          <p className="text-xs text-slate-400 mt-1">
          Viewing operations for <strong className="text-slate-300">{user?.dealership_id ? "your dealership" : "selected dealership"}</strong>
          </p>
        </div>

        {loadError && (
          <div role="alert" className="mb-5 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">
            {loadError}
          </div>
        )}
        {loading && <p className="mb-5 text-xs text-slate-400">Loading dashboard data...</p>}

        <div className="flex flex-wrap items-center gap-2.5">
          <Link
            href="/inventory"
            className="btn-primary"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Add Vehicle</span>
          </Link>
          <Link
            href="/bookings"
            className="btn-secondary"
          >
            <Calendar className="h-3.5 w-3.5" />
            <span>Test-Drive Schedule</span>
          </Link>
          <Link
            href="/assistant"
            className="rounded-lg bg-indigo-600/20 border border-indigo-500/40 px-3.5 py-2 text-xs font-semibold text-indigo-300 hover:bg-indigo-600 hover:text-white transition-all flex items-center gap-2 shadow-sm"
          >
            <Sparkles className="h-3.5 w-3.5" />
            <span>Ask AI Assistant</span>
          </Link>
        </div>
      </div>

      {/* Top KPI Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {/* KPI 1 */}
        <div className="kpi-card">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-bold uppercase tracking-wider">Inventory Valuation</span>
            <div className="h-8 w-8 rounded-lg bg-blue-500/10 flex items-center justify-center text-blue-400">
              <DollarSign className="h-4 w-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-white">
            ${totalValuation.toLocaleString()}
          </div>
          <div className="flex items-center gap-1.5 text-xs text-slate-400 mt-2">
            <span className="badge badge-success">
              {vehicles.length} Units In Fleet
            </span>
            <span>• {availableVehiclesCount} Available</span>
          </div>
        </div>

        {/* KPI 2 */}
        <div className="kpi-card">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-bold uppercase tracking-wider">Test Drive Bookings</span>
            <div className="h-8 w-8 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400">
              <Calendar className="h-4 w-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-white">
            {bookings.length} Bookings
          </div>
          <div className="flex items-center gap-1.5 text-xs text-slate-400 mt-2">
            <span className="badge badge-info">{activeBookingsCount} Active Scheduled</span>
          </div>
        </div>

        {/* KPI 3 */}
        <div className="kpi-card">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-bold uppercase tracking-wider">AI Grounding RAG</span>
            <div className="h-8 w-8 rounded-lg bg-purple-500/10 flex items-center justify-center text-purple-400">
              <Sparkles className="h-4 w-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-white">
            {documents.length} Documents
          </div>
          <div className="flex items-center gap-1.5 text-xs text-slate-400 mt-2">
            <span className="badge badge-neutral">{health?.services.embeddings ?? "Unknown"}</span>
          </div>
        </div>

        {/* KPI 4 */}
        <div className="kpi-card">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-bold uppercase tracking-wider">System & DB Health</span>
            <div className="h-8 w-8 rounded-lg bg-cyan-500/10 flex items-center justify-center text-cyan-400">
              <Activity className="h-4 w-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-white">
            {health?.database.latency_ms == null ? "Unavailable" : `${health.database.latency_ms} ms`}
          </div>
          <div className="flex items-center gap-1.5 text-xs text-slate-400 mt-2">
            <span className={`badge ${health?.status === "healthy" ? "badge-success" : "badge-danger"}`}>
              {health?.status ?? "Health unavailable"}
            </span>
          </div>
        </div>
      </div>

      {/* Operations Split Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
        {/* Left Column (2 Cols): Live CRM Test-Drive Schedule */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-white">Upcoming Test-Drive Operations</h2>
              <p className="text-xs text-slate-400">Capacity-controlled slot bookings with identity verification</p>
            </div>
            <Link
              href="/bookings"
              className="text-xs font-semibold text-blue-400 hover:text-blue-300 flex items-center gap-1"
            >
              <span>Manage CRM Schedule</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          <div className="erp-table-container">
            <table className="erp-table">
              <thead>
                <tr>
                  <th>Vehicle & Customer</th>
                  <th>Date & Time</th>
                  <th>Capacity</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {bookings.map((b) => (
                  <tr key={b.id}>
                    <td>
                      <div className="font-bold text-white text-xs">{b.vehicle_name || "Toyota Camry"}</div>
                      <div className="text-[11px] text-slate-400">
                        {b.customer_name} ({b.customer_email})
                      </div>
                    </td>
                    <td>
                      <div className="text-xs text-slate-200">
                        {new Date(b.starts_at || Date.now()).toLocaleDateString([], {
                          month: "short",
                          day: "numeric",
                        })}
                      </div>
                      <div className="text-[11px] text-slate-400">
                        {new Date(b.starts_at || Date.now()).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </div>
                    </td>
                    <td>
                      <div className="w-24 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                        <div className="bg-blue-500 h-1.5 rounded-full w-2/3" />
                      </div>
                      <span className="text-[10px] text-slate-400 block mt-1">1 / 2 Spaces Filled</span>
                    </td>
                    <td>
                      <span
                        className={`badge ${
                          b.status === "booked"
                            ? "badge-info"
                            : b.status === "completed"
                            ? "badge-success"
                            : "badge-danger"
                        }`}
                      >
                        {b.status.toUpperCase()}
                      </span>
                    </td>
                    <td>
                      <Link
                        href={`/bookings?booking_id=${b.id}`}
                        className="text-xs text-blue-400 hover:underline font-semibold"
                      >
                        Inspect
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column (1 Col): Inventory Availability Status */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white">Inventory Health</h2>
            <Link
              href="/inventory"
              className="text-xs font-semibold text-blue-400 hover:text-blue-300"
            >
              Full Catalog
            </Link>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between text-xs font-semibold">
                <span className="text-slate-300">Available For Sale</span>
                <span className="text-emerald-400">
                  {Math.round((availableVehiclesCount / vehicles.length) * 100)}%
                </span>
              </div>
              <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden flex">
                <div
                  style={{ width: `${(availableVehiclesCount / vehicles.length) * 100}%` }}
                  className="bg-emerald-500 h-full"
                />
                <div
                  style={{ width: `${((vehicles.length - availableVehiclesCount) / vehicles.length) * 100}%` }}
                  className="bg-amber-500 h-full"
                />
              </div>
            </div>

            <div className="divide-y divide-slate-800 text-xs">
              {vehicles.slice(0, 4).map((v) => (
                <div key={v.id} className="py-2.5 flex items-center justify-between">
                  <div className="min-w-0">
                    <p className="font-semibold text-white truncate">
                      {v.make} {v.model}
                    </p>
                    <p className="text-[11px] text-slate-400">{v.stock_number}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-bold text-slate-200">${Number(v.price).toLocaleString()}</p>
                    <span
                      className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                        v.is_available ? "text-emerald-400 bg-emerald-500/10" : "text-amber-400 bg-amber-500/10"
                      }`}
                    >
                      {v.is_available ? "In Stock" : "Reserved"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Enterprise Security Audit Trail & Health Probes Banner */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Audit Log Stream */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                Enterprise Audit Trail
              </h3>
            </div>
            <Link href="/audit" className="text-xs text-blue-400 hover:underline">
              View All Logs
            </Link>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 divide-y divide-slate-800/80">
            {auditLogs.slice(0, 4).map((log) => (
              <div key={log.id} className="py-2 flex items-center justify-between text-xs">
                <div className="flex items-center gap-2.5">
                  <span className="font-mono text-[10px] text-slate-400">{log.ip_address}</span>
                  <div>
                    <span className="font-semibold text-slate-200 mr-2">{log.action}</span>
                    <span className="text-slate-400 text-[11px]">{log.actor_email}</span>
                  </div>
                </div>
                <span className="text-[11px] text-slate-400 font-mono">
                  {new Date(log.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* System & Dependency Probes */}
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-cyan-400" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Diagnostic Service Dependency Probes
            </h3>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">PostgreSQL Connection:</span>
              <span className="text-emerald-400 font-mono font-semibold flex items-center gap-1">
                {health?.database.status ?? "Unknown"}
                {health?.database.latency_ms == null ? "" : ` (${health.database.latency_ms}ms)`}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">Supabase Media Storage:</span>
              <span className="text-emerald-400 font-mono font-semibold flex items-center gap-1">
                {health?.services.storage ?? "Unknown"}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">Resend Email Gateway:</span>
              <span className="text-emerald-400 font-mono font-semibold flex items-center gap-1">
                {health?.services.email ?? "Unknown"}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">RAG Semantic Embeddings & LLM:</span>
              <span className="text-emerald-400 font-mono font-semibold flex items-center gap-1">
                Embeddings: {health?.services.embeddings ?? "Unknown"}; LLM: {health?.services.llm ?? "Unknown"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}
