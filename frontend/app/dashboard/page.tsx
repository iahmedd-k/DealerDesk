"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowUpRight,
  Bot,
  Building2,
  Calendar,
  Car,
  CheckCircle2,
  Download,
  MessageSquare,
  MoreHorizontal,
  Plus,
  Search,
  ShieldCheck,
  TrendingUp,
  Users,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import Shell from "../components/Shell";
import { useAuth } from "../providers";
import { api } from "../api";
import type {
  ConversationSummary,
  CustomerLead,
  DealershipAnalytics,
  HealthStatus,
  OperationsSummary,
  StaffUser,
  TestDriveBooking,
  Vehicle,
} from "../lib/types";

type DashboardTab = "overview" | "pipeline" | "bookings" | "handoffs";
type SortBy = "newest" | "value_desc" | "name_asc";

const STAGE_ORDER = [
  { key: "new", label: "New", dot: "bg-slate-400", badge: "bg-slate-100 text-slate-700" },
  { key: "contacted", label: "Contacted", dot: "bg-amber-500", badge: "bg-amber-50 text-amber-800" },
  { key: "qualified", label: "Qualified", dot: "bg-violet-500", badge: "bg-violet-50 text-violet-700" },
  { key: "test_drive_scheduled", label: "Test Drive", dot: "bg-blue-600", badge: "bg-blue-50 text-blue-700" },
  { key: "follow_up", label: "Follow-up", dot: "bg-orange-500", badge: "bg-orange-50 text-orange-800" },
  { key: "won", label: "Won", dot: "bg-emerald-500", badge: "bg-emerald-50 text-emerald-700" },
  { key: "lost", label: "Lost", dot: "bg-rose-500", badge: "bg-rose-50 text-rose-700" },
] as const;

function DotMatrixSparkline({
  tone = "blue",
  heights,
}: {
  tone?: "blue" | "rose" | "emerald";
  heights: number[];
}) {
  const activeColor =
    tone === "rose"
      ? "bg-rose-500"
      : tone === "emerald"
      ? "bg-emerald-500"
      : "bg-blue-600";
  const softColor =
    tone === "rose"
      ? "bg-rose-200"
      : tone === "emerald"
      ? "bg-emerald-200"
      : "bg-blue-200";

  return (
    <div className="flex items-end gap-1" aria-hidden="true">
      {heights.map((level, colIdx) => (
        <div key={colIdx} className="flex flex-col gap-0.5">
          {[4, 3, 2, 1].map((row) => (
            <span
              key={row}
              className={`h-1 w-1 rounded-full ${
                row <= level
                  ? colIdx === heights.length - 2 || colIdx === heights.length - 1
                    ? activeColor
                    : softColor
                  : "bg-slate-100"
              }`}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function formatDateInput(date: Date): string {
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 10);
}

export default function DashboardPage() {
  const { user, authReady, activeDealershipId } = useAuth();
  const [summary, setSummary] = useState<OperationsSummary | null>(null);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [bookings, setBookings] = useState<TestDriveBooking[]>([]);
  const [leads, setLeads] = useState<CustomerLead[]>([]);
  const [staff, setStaff] = useState<StaffUser[]>([]);
  const [handoffs, setHandoffs] = useState<ConversationSummary[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [analytics, setAnalytics] = useState<DealershipAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyticsEndDate, setAnalyticsEndDate] = useState(() =>
    formatDateInput(new Date()),
  );
  const [analyticsStartDate, setAnalyticsStartDate] = useState(() => {
    const date = new Date();
    date.setDate(date.getDate() - 29);
    return formatDateInput(date);
  });

  const [activeTab, setActiveTab] = useState<DashboardTab>("overview");
  const [tableSearch, setTableSearch] = useState("");
  const [sortBy, setSortBy] = useState<SortBy>("newest");
  const [pipelineMetric, setPipelineMetric] = useState<"count" | "value">("count");

  const canManageTeam = user?.role === "dealership_admin" || user?.role === "manager";

  useEffect(() => {
    if (!authReady || !user) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const healthData = await api<HealthStatus>("/health").catch(() => null);
        if (!cancelled) setHealth(healthData);

        if (!activeDealershipId) {
          if (!cancelled) setLoading(false);
          return;
        }

        if (user?.role === "customer") {
          const [vList, bList] = await Promise.all([
            api<Vehicle[]>(`/dealerships/${activeDealershipId}/vehicles/public`).catch(
              () => [] as Vehicle[],
            ),
            api<TestDriveBooking[]>(
              `/dealerships/${activeDealershipId}/test-drive-bookings`,
            ).catch(() => [] as TestDriveBooking[]),
          ]);
          if (cancelled) return;
          setVehicles(vList);
          setBookings(bList);
        } else if (user?.role === "dealerdesk_admin") {
          // Platform admin primarily uses /dealerships
        } else {
          const analyticsUrl =
            `/dealerships/${activeDealershipId}/reports/analytics` +
            `?start_date=${analyticsStartDate}&end_date=${analyticsEndDate}`;
          const [sumData, vList, bList, lList, cList, sList, analyticsData] =
            await Promise.all([
            api<OperationsSummary>(
              `/dealerships/${activeDealershipId}/reports/summary`,
            ).catch(() => null),
            api<Vehicle[]>(`/dealerships/${activeDealershipId}/vehicles`).catch(
              () => [] as Vehicle[],
            ),
            api<TestDriveBooking[]>(
              `/dealerships/${activeDealershipId}/test-drive-bookings`,
            ).catch(() => [] as TestDriveBooking[]),
            api<CustomerLead[]>(`/dealerships/${activeDealershipId}/leads?limit=200`).catch(
              () => [] as CustomerLead[],
            ),
            api<ConversationSummary[]>(
              `/dealerships/${activeDealershipId}/conversations?status=handed_off`,
            ).catch(() => [] as ConversationSummary[]),
            canManageTeam
              ? api<StaffUser[]>(`/dealerships/${activeDealershipId}/staff`).catch(
                  () => [] as StaffUser[],
                )
              : Promise.resolve([] as StaffUser[]),
            canManageTeam && analyticsStartDate <= analyticsEndDate
              ? api<DealershipAnalytics>(analyticsUrl).catch(() => null)
              : Promise.resolve(null),
          ]);
          if (cancelled) return;
          setSummary(sumData);
          setVehicles(vList);
          setBookings(bList);
          setLeads(lList);
          setHandoffs(cList);
          setStaff(sList);
          setAnalytics(analyticsData);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [
    authReady,
    user,
    activeDealershipId,
    canManageTeam,
    analyticsStartDate,
    analyticsEndDate,
  ]);

  const staffById = useMemo(() => {
    const map = new Map<number, StaffUser>();
    staff.forEach((m) => map.set(m.id, m));
    return map;
  }, [staff]);

  const vehicleById = useMemo(() => {
    const map = new Map<number, Vehicle>();
    vehicles.forEach((v) => map.set(v.id, v));
    return map;
  }, [vehicles]);

  const stageStats = useMemo(() => {
    const counts: Record<string, { count: number; value: number }> = {};
    STAGE_ORDER.forEach((s) => {
      counts[s.key] = { count: 0, value: 0 };
    });
    for (const [status, count] of Object.entries(summary?.leads.by_status ?? {})) {
      const bucket = counts[status] ?? counts.new;
      bucket.count = count;
      bucket.value = summary?.leads.deal_value_by_status[status] ?? 0;
    }
    const maxCount = Math.max(1, ...Object.values(counts).map((c) => c.count));
    return { counts, maxCount };
  }, [summary]);

  const historicalPeak = useMemo(
    () =>
      Math.max(
        1,
        ...(analytics?.historical.daily.map(
          (item) => item.leads_created + item.won + item.lost,
        ) ?? []),
      ),
    [analytics],
  );

  const sourceStats = useMemo(() => {
    const sources = Object.entries(summary?.leads.by_source ?? {});
    const total = Math.max(1, summary?.leads.total ?? 0);
    const colors = ["bg-blue-600", "bg-zinc-900", "bg-zinc-500", "bg-zinc-300"];
    return sources
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4)
      .map(([name, count], i) => ({
        name: name.replaceAll("_", " "),
        count,
        pct: Math.round((count / total) * 100),
        color: colors[i % colors.length],
      }));
  }, [summary]);

  const filteredTableLeads = useMemo(() => {
    const q = tableSearch.trim().toLowerCase();
    const list = leads.filter((l) => {
      if (!q) return true;
      return (
        l.name.toLowerCase().includes(q) ||
        l.email.toLowerCase().includes(q) ||
        l.status.toLowerCase().includes(q)
      );
    });
    return [...list].sort((a, b) => {
      if (sortBy === "value_desc") {
        return Number(b.deal_value ?? b.budget ?? 0) - Number(a.deal_value ?? a.budget ?? 0);
      }
      if (sortBy === "name_asc") {
        return a.name.localeCompare(b.name);
      }
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });
  }, [leads, sortBy, tableSearch]);

  function exportCsv() {
    const headers = ["ID", "Name", "Email", "Phone", "Source", "Status", "Deal Value", "Created At"];
    const rows = filteredTableLeads.map((l) => [
      l.id,
      `"${l.name.replaceAll('"', '""')}"`,
      l.email,
      l.phone || "",
      l.source,
      l.status,
      l.deal_value ?? l.budget ?? "",
      l.created_at,
    ]);
    const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `dealerdesk-pipeline-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  if (user?.role === "dealerdesk_admin") {
    return (
      <Shell>
        <div className="crm-card p-8 max-w-2xl">
          <h1 className="text-2xl font-medium text-[#171717] tabular-nums">
            DealerDesk Control Tower
          </h1>
          <p className="text-sm text-slate-600 mt-2">
            Manage dealership tenants, subscription tiers, platform audit logs, and
            cross-tenant metrics.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href="/dealerships" className="crm-btn-primary">
              <Building2 className="h-4 w-4" />
              Open SaaS Control Tower
            </Link>
            <Link href="/audit" className="crm-btn-secondary">
              <ShieldCheck className="h-4 w-4" />
              Platform Audit Trail
            </Link>
          </div>
        </div>
      </Shell>
    );
  }

  if (user?.role === "customer") {
    return (
      <Shell>
        <div className="space-y-6">
          <div className="crm-card p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h1 className="text-xl font-medium text-[#171717]">
                Showroom &amp; Test Drives
              </h1>
              <p className="text-sm text-[#525252] mt-1">
                Browse dealership vehicles, schedule test drives, or ask the showroom assistant
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link href="/inventory" className="crm-btn-secondary">
                <Car className="h-4 w-4" />
                Browse Vehicles ({vehicles.length})
              </Link>
              <Link href="/bookings" className="crm-btn-primary">
                <Calendar className="h-4 w-4" />
                My Test Drives ({bookings.length})
              </Link>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Link href="/inventory" className="crm-card crm-card-hover block p-5 transition-[border-color,box-shadow]">
              <h2 className="text-sm font-medium text-[#171717] mb-3">
                Featured Showroom Vehicles
              </h2>
              {vehicles.length === 0 ? (
                <p className="text-xs text-slate-500">
                  Select a dealership workspace above to view available vehicles.
                </p>
              ) : (
                <div className="space-y-2.5">
                  {vehicles.slice(0, 5).map((v) => (
                    <div
                      key={v.id}
                      className="flex items-center justify-between rounded-lg border border-slate-200 p-3 text-xs"
                    >
                      <div>
                        <p className="font-semibold text-slate-900">
                          {v.model_year} {v.make} {v.model}
                        </p>
                        <p className="text-slate-500">{v.variant || "Standard"}</p>
                      </div>
                      <span className="font-bold text-slate-900">
                        ${Number(v.price).toLocaleString()}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </Link>

            <Link href="/bookings" className="crm-card crm-card-hover block p-5 transition-[border-color,box-shadow]">
              <h2 className="text-sm font-medium text-[#171717] mb-3">
                Upcoming Test Drives
              </h2>
              {bookings.length === 0 ? (
                <p className="text-xs text-slate-500">No test drives booked yet.</p>
              ) : (
                <div className="space-y-2.5">
                  {bookings.slice(0, 5).map((b) => (
                    <div
                      key={b.id}
                      className="flex items-center justify-between rounded-lg border border-slate-200 p-3 text-xs"
                    >
                      <div>
                        <p className="font-semibold text-slate-900">
                          {b.vehicle_name || `Vehicle #${b.vehicle_id}`}
                        </p>
                        <p className="text-slate-500">
                          {b.starts_at
                            ? new Date(b.starts_at).toLocaleString()
                            : `Slot #${b.slot_id}`}
                        </p>
                      </div>
                      <span className="crm-badge crm-badge-info">{b.status}</span>
                    </div>
                  ))}
                </div>
              )}
            </Link>
          </div>
        </div>
      </Shell>
    );
  }

  const availableVehicles =
    summary?.inventory.by_status?.available ??
    vehicles.filter((v) => v.is_available).length;
  const totalLeads = summary?.leads.total ?? leads.length;
  const wonValue = summary?.leads.won_deal_value ?? 0;
  const wonCount = summary?.leads.by_status?.won ?? leads.filter((l) => l.status === "won").length;
  const bookedDrives =
    summary?.test_drives.by_status?.booked ??
    bookings.filter((b) => b.status === "booked").length;
  const handoffCount = summary?.conversations.handoff_queue ?? handoffs.length;
  const totalPipelineValue = leads
    .filter((l) => l.status !== "lost")
    .reduce((sum, l) => sum + Number(l.deal_value ?? l.budget ?? 0), 0);

  return (
    <Shell>
      {/* Top Segmented Tabs & Actions (Aivox Style) */}
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex items-center rounded-xl border border-slate-200 bg-white p-1">
          {[
            { id: "overview", label: "Overview" },
            { id: "pipeline", label: "Pipeline" },
            { id: "bookings", label: `Test Drives (${bookedDrives})` },
            { id: "handoffs", label: `Handoffs (${handoffCount})` },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id as DashboardTab)}
              className={`rounded-lg px-3.5 py-1.5 text-xs font-medium transition-colors ${
                activeTab === tab.id
                  ? "bg-slate-100 text-slate-900 shadow-xs"
                  : "text-slate-500 hover:text-slate-800"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={exportCsv}
            className="crm-btn-secondary min-h-9 px-3 text-xs"
          >
            <Download className="h-3.5 w-3.5" /> Export CSV
          </button>
          <Link href="/leads" className="crm-btn-primary min-h-9 px-3.5 text-xs">
            <Plus className="h-3.5 w-3.5" /> Manage Leads
          </Link>
        </div>
      </div>

      <section className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3">
        <div>
          <p className="text-xs font-semibold text-slate-900">Today&apos;s workspace</p>
          <p className="mt-0.5 text-[11px] text-slate-500">
            {handoffCount > 0
              ? `${handoffCount} conversation${handoffCount === 1 ? "" : "s"} need a response`
              : "All conversations are up to date"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/leads" className="crm-btn-secondary min-h-9 px-3 text-xs">
            <Plus className="h-3.5 w-3.5" /> Add lead
          </Link>
          <Link href="/inventory" className="crm-btn-secondary min-h-9 px-3 text-xs">
            <Car className="h-3.5 w-3.5" /> Add vehicle
          </Link>
          <Link href="/bookings" className="crm-btn-primary min-h-9 px-3 text-xs">
            <Calendar className="h-3.5 w-3.5" /> Schedule test drive
          </Link>
        </div>
      </section>

      {/* 3-Column KPI Cards with Dot-Matrix Sparklines */}
      <div className="mb-5 grid grid-cols-1 gap-4 md:grid-cols-3">
        <Link href="/leads" className="crm-card crm-card-hover block p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Won &amp; Pipeline Value</span>
            <MoreHorizontal className="h-4 w-4 text-slate-400" />
          </div>
          <div className="mt-4 flex items-end justify-between gap-3">
            {loading ? (
              <span className="crm-skeleton h-8 w-28" />
            ) : (
              <p className="text-2xl font-semibold tracking-tight text-slate-900 tabular-nums">
                ${Number(wonValue || totalPipelineValue).toLocaleString()}
              </p>
            )}
            <DotMatrixSparkline tone="blue" heights={[1, 2, 1, 3, 2, 4, 3, 2]} />
            <div className="text-right text-[11px]">
              <span className="inline-flex items-center gap-0.5 font-semibold text-blue-600">
                <ArrowUpRight className="h-3 w-3" /> {wonCount} won
              </span>
              <div className="text-slate-400">closed deals</div>
            </div>
          </div>
        </Link>

        <Link href="/leads" className="crm-card crm-card-hover block p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Active Leads</span>
            <MoreHorizontal className="h-4 w-4 text-slate-400" />
          </div>
          <div className="mt-4 flex items-end justify-between gap-3">
            {loading ? (
              <span className="crm-skeleton h-8 w-20" />
            ) : (
              <p className="text-2xl font-semibold tracking-tight text-slate-900 tabular-nums">
                {totalLeads.toLocaleString()}
              </p>
            )}
            <DotMatrixSparkline tone="emerald" heights={[2, 1, 3, 2, 4, 3, 4, 3]} />
            <div className="text-right text-[11px]">
              <span className="inline-flex items-center gap-0.5 font-semibold text-emerald-600">
                <TrendingUp className="h-3 w-3" /> {bookedDrives}
              </span>
              <div className="text-slate-400">test drives</div>
            </div>
          </div>
        </Link>

        <Link href="/inventory" className="crm-card crm-card-hover block p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Available Inventory</span>
            <MoreHorizontal className="h-4 w-4 text-slate-400" />
          </div>
          <div className="mt-4 flex items-end justify-between gap-3">
            {loading ? (
              <span className="crm-skeleton h-8 w-16" />
            ) : (
              <p className="text-2xl font-semibold tracking-tight text-slate-900 tabular-nums">
                {availableVehicles}
              </p>
            )}
            <DotMatrixSparkline tone="rose" heights={[2, 3, 2, 4, 2, 3, 2, 1]} />
            <div className="text-right text-[11px]">
              <span className="font-semibold text-slate-700">
                {summary?.inventory.total ?? vehicles.length} units
              </span>
              <div className="text-slate-400">{handoffCount} handoffs</div>
            </div>
          </div>
        </Link>
      </div>

      {/* 2-Column Analytics Row: Pipeline Stage Chart + Lead Source Mix */}
      <div className="mb-5 grid grid-cols-1 gap-5 lg:grid-cols-12">
        {/* Left: Pipeline Stage Chart (Recharts) */}
        <section className="crm-card p-5 lg:col-span-7">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Pipeline Breakdown</h2>
              <p className="text-xs text-slate-400">Lead volume &amp; deal value across CRM stages</p>
            </div>
            <div className="flex items-center gap-2">
              <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-[11px] font-medium">
                <button
                  type="button"
                  onClick={() => setPipelineMetric("count")}
                  className={`rounded-md px-2.5 py-1 transition-colors ${
                    pipelineMetric === "count"
                      ? "bg-white text-slate-900 shadow-xs"
                      : "text-slate-500 hover:text-slate-800"
                  }`}
                >
                  Volume
                </button>
                <button
                  type="button"
                  onClick={() => setPipelineMetric("value")}
                  className={`rounded-md px-2.5 py-1 transition-colors ${
                    pipelineMetric === "value"
                      ? "bg-white text-slate-900 shadow-xs"
                      : "text-slate-500 hover:text-slate-800"
                  }`}
                >
                  Value ($)
                </button>
              </div>
              <Link href="/leads" className="crm-btn-secondary min-h-8 px-3 py-1 text-xs">
                View Pipeline
              </Link>
            </div>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={STAGE_ORDER.map((stage) => {
                  const stat = stageStats.counts[stage.key];
                  const fillMap: Record<string, string> = {
                    new: "#94a3b8",
                    contacted: "#f59e0b",
                    qualified: "#8b5cf6",
                    test_drive_scheduled: "#2563eb",
                    follow_up: "#f97316",
                    won: "#10b981",
                    lost: "#f43f5e",
                  };
                  return {
                    stage: stage.label,
                    count: stat.count,
                    value: stat.value,
                    fill: fillMap[stage.key] ?? "#3b82f6",
                  };
                })}
                margin={{ top: 10, right: 8, left: -12, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis
                  dataKey="stage"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#64748b", fontSize: 11 }}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  allowDecimals={false}
                  tick={{ fill: "#94a3b8", fontSize: 11 }}
                  tickFormatter={(val: number) =>
                    pipelineMetric === "value"
                      ? val >= 1000
                        ? `$${Math.round(val / 1000)}k`
                        : `$${val}`
                      : String(val)
                  }
                />
                <Tooltip
                  cursor={{ fill: "#f8fafc" }}
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const item = payload[0].payload as {
                      stage: string;
                      count: number;
                      value: number;
                      fill: string;
                    };
                    return (
                      <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg">
                        <div className="flex items-center gap-1.5 font-semibold text-slate-900">
                          <span
                            className="h-2 w-2 rounded-full"
                            style={{ backgroundColor: item.fill }}
                          />
                          {item.stage}
                        </div>
                        <div className="mt-1 flex items-center justify-between gap-4 text-slate-600">
                          <span>Leads:</span>
                          <span className="font-semibold text-slate-900 tabular-nums">
                            {item.count}
                          </span>
                        </div>
                        <div className="flex items-center justify-between gap-4 text-slate-600">
                          <span>Value:</span>
                          <span className="font-semibold text-slate-900 tabular-nums">
                            ${item.value.toLocaleString()}
                          </span>
                        </div>
                      </div>
                    );
                  }}
                />
                <Bar
                  dataKey={pipelineMetric}
                  radius={[8, 8, 0, 0]}
                  maxBarSize={44}
                >
                  {STAGE_ORDER.map((stage) => {
                    const fillMap: Record<string, string> = {
                      new: "#94a3b8",
                      contacted: "#f59e0b",
                      qualified: "#8b5cf6",
                      test_drive_scheduled: "#2563eb",
                      follow_up: "#f97316",
                      won: "#10b981",
                      lost: "#f43f5e",
                    };
                    return <Cell key={stage.key} fill={fillMap[stage.key] ?? "#3b82f6"} />;
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Right: Source & Channel Donut Chart (Recharts) + Health */}
        <section className="crm-card flex flex-col justify-between p-5 lg:col-span-5">
          <div>
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-slate-900">Lead Sources</h2>
                <p className="text-xs text-slate-400">Channel attribution mix</p>
              </div>
              <span className="crm-badge crm-badge-success">
                <Activity className="h-3 w-3" /> {health?.status || "ok"}
              </span>
            </div>

            {sourceStats.length === 0 ? (
              <div className="flex h-48 items-center justify-center text-xs text-slate-400">
                No source breakdown yet.
              </div>
            ) : (
              <div className="mt-3 grid grid-cols-1 items-center gap-4 sm:grid-cols-12">
                <div className="relative h-44 sm:col-span-6">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={sourceStats.map((src, i) => {
                          const hexColors = ["#2563eb", "#18181b", "#8b5cf6", "#06b6d4"];
                          return {
                            name: src.name,
                            value: src.count,
                            pct: src.pct,
                            fill: hexColors[i % hexColors.length],
                          };
                        })}
                        dataKey="value"
                        nameKey="name"
                        innerRadius={48}
                        outerRadius={70}
                        paddingAngle={4}
                        cornerRadius={6}
                        stroke="none"
                      >
                        {sourceStats.map((src, i) => {
                          const hexColors = ["#2563eb", "#18181b", "#8b5cf6", "#06b6d4"];
                          return (
                            <Cell key={src.name} fill={hexColors[i % hexColors.length]} />
                          );
                        })}
                      </Pie>
                      <Tooltip
                        content={({ active, payload }) => {
                          if (!active || !payload?.length) return null;
                          const item = payload[0].payload as {
                            name: string;
                            value: number;
                            pct: number;
                          };
                          return (
                            <div className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs shadow-lg">
                              <span className="font-semibold capitalize text-slate-900">
                                {item.name}
                              </span>
                              <span className="ml-2 text-slate-600 tabular-nums">
                                {item.value} ({item.pct}%)
                              </span>
                            </div>
                          );
                        }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-2xl font-semibold tracking-tight text-slate-900 tabular-nums">
                      {totalLeads.toLocaleString()}
                    </span>
                    <span className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
                      Leads
                    </span>
                  </div>
                </div>

                <div className="space-y-2.5 sm:col-span-6">
                  {sourceStats.map((src, i) => {
                    const hexColors = ["#2563eb", "#18181b", "#8b5cf6", "#06b6d4"];
                    return (
                      <div key={src.name} className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2 min-w-0">
                          <span
                            className="h-2.5 w-2.5 shrink-0 rounded-full"
                            style={{ backgroundColor: hexColors[i % hexColors.length] }}
                          />
                          <span className="truncate capitalize text-slate-600">{src.name}</span>
                        </div>
                        <div className="flex items-center gap-1.5 tabular-nums shrink-0">
                          <span className="font-semibold text-slate-900">{src.count}</span>
                          <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
                            {src.pct}%
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3">
            <Link
              href="/assistant"
              className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-blue-600"
            >
              <Bot className="h-3.5 w-3.5 text-blue-600" /> AI Copilot Active
            </Link>
            <Link
              href="/inbox"
              className="text-xs font-semibold text-blue-600 hover:underline"
            >
              Open Inbox ({handoffCount})
            </Link>
          </div>
        </section>
      </div>

      {canManageTeam && (
        <section className="mb-5">
          <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Performance analytics</h2>
              <p className="mt-1 text-xs text-slate-500">
                Leads created in the period, grouped by their current status.
                Historical bars use the date of each recorded transition.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs text-slate-500">
                From
                <input
                  type="date"
                  aria-label="Analytics start date"
                  value={analyticsStartDate}
                  max={analyticsEndDate}
                  onChange={(event) => setAnalyticsStartDate(event.target.value)}
                  className="crm-input ml-2 min-h-8 py-1 text-xs"
                />
              </label>
              <label className="text-xs text-slate-500">
                To
                <input
                  type="date"
                  aria-label="Analytics end date"
                  value={analyticsEndDate}
                  min={analyticsStartDate}
                  onChange={(event) => setAnalyticsEndDate(event.target.value)}
                  className="crm-input ml-2 min-h-8 py-1 text-xs"
                />
              </label>
            </div>
          </div>

          {analyticsStartDate > analyticsEndDate ? (
            <p className="crm-card p-5 text-sm text-rose-700">
              The start date must be on or before the end date.
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
              <div className="crm-card overflow-hidden xl:col-span-2">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-3.5">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-900">Historical pipeline activity</h3>
                    <p className="mt-1 text-[11px] text-slate-500">Lead creation and won/lost transitions by event date.</p>
                  </div>
                  <div className="flex flex-wrap gap-3 text-[10px] text-slate-500">
                    <span className="flex items-center gap-1"><i className="h-2 w-2 rounded-full bg-blue-500" /> Created</span>
                    <span className="flex items-center gap-1"><i className="h-2 w-2 rounded-full bg-emerald-500" /> Won</span>
                    <span className="flex items-center gap-1"><i className="h-2 w-2 rounded-full bg-rose-500" /> Lost</span>
                  </div>
                </div>
                {analytics?.historical.daily.length ? (
                  <div className="overflow-x-auto px-5 py-4">
                    <div className="flex min-w-max items-end gap-3">
                      {analytics.historical.daily.map((day) => {
                        const activityTotal = day.leads_created + day.won + day.lost;
                        const barHeight = (count: number) =>
                          count === 0 ? 0 : Math.max(4, (count / historicalPeak) * 68);
                        return (
                          <div key={day.date} className="flex w-12 flex-col items-center gap-2" title={`${day.date}: ${day.leads_created} created, ${day.won} won, ${day.lost} lost`}>
                            <span className="text-[10px] tabular-nums text-slate-500">{activityTotal}</span>
                            <div className="flex h-[72px] w-6 flex-col justify-end gap-px">
                              <span className="w-full rounded-t bg-rose-500" style={{ height: `${barHeight(day.lost)}px` }} />
                              <span className="w-full bg-emerald-500" style={{ height: `${barHeight(day.won)}px` }} />
                              <span className="w-full rounded-b bg-blue-500" style={{ height: `${barHeight(day.leads_created)}px` }} />
                            </div>
                            <span className="text-[10px] text-slate-400">{day.date.slice(5)}</span>
                          </div>
                        );
                      })}
                    </div>
                    {Object.keys(analytics.historical.stage_transitions).length > 0 && (
                      <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-3">
                        {Object.entries(analytics.historical.stage_transitions).map(([stage, count]) => (
                          <span key={stage} className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] text-slate-600">
                            {stage.replaceAll("_", " ")} · {count}
                          </span>
                        ))}
                      </div>
                    )}
                    {Object.keys(analytics.historical.lost_by_reason).length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {Object.entries(analytics.historical.lost_by_reason).map(([reason, count]) => (
                          <span key={reason} className="rounded-full bg-rose-50 px-2.5 py-1 text-[10px] text-rose-700">
                            Lost: {reason.replaceAll("_", " ")} · {count}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="px-5 py-6 text-center text-xs text-slate-500">
                    No historical lead events in this date range.
                  </p>
                )}
              </div>

              <div className="crm-card overflow-hidden">
                <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3.5">
                  <h3 className="text-sm font-semibold text-slate-900">Lead source conversion</h3>
                  <span className="text-xs text-slate-500">
                    {analytics?.leads.total ?? 0} leads ·{" "}
                    {analytics?.leads.conversion_rate ?? 0}% overall
                  </span>
                </div>
                {analytics?.by_source.length ? (
                  <div className="overflow-x-auto">
                    <table className="crm-table crm-mobile-cards">
                      <thead>
                        <tr>
                          <th>Source</th>
                          <th>Leads</th>
                          <th>Won</th>
                          <th>Conversion</th>
                          <th>Won value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analytics.by_source.map((source) => (
                          <tr key={source.source}>
                            <td className="capitalize">{source.source.replaceAll("_", " ")}</td>
                            <td>{source.leads}</td>
                            <td>{source.won}</td>
                            <td>{source.conversion_rate}%</td>
                            <td>${source.won_deal_value.toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="px-5 py-6 text-center text-xs text-slate-500">
                    No leads in this date range.
                  </p>
                )}
              </div>

              <div className="crm-card overflow-hidden">
                <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3.5">
                  <h3 className="text-sm font-semibold text-slate-900">Rep leaderboard</h3>
                  <span className="text-xs text-slate-500">
                    {analytics?.test_drives.total ?? 0} test drives
                  </span>
                </div>
                {analytics?.by_rep.length ? (
                  <div className="overflow-x-auto">
                    <table className="crm-table crm-mobile-cards">
                      <thead>
                        <tr>
                          <th>Sales rep</th>
                          <th>Leads</th>
                          <th>Won</th>
                          <th>Conversion</th>
                          <th>Won value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analytics.by_rep.map((rep) => (
                          <tr key={rep.user_id ?? "unassigned"}>
                            <td>{rep.name}</td>
                            <td>{rep.leads}</td>
                            <td>{rep.won}</td>
                            <td>{rep.conversion_rate}%</td>
                            <td>${rep.won_deal_value.toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="px-5 py-6 text-center text-xs text-slate-500">
                    No assigned lead activity in this date range.
                  </p>
                )}
                <div className="border-t border-slate-100 px-5 py-3.5">
                  <h4 className="text-xs font-semibold text-slate-700">Won deals credited at close</h4>
                  {analytics?.historical.wins_by_rep_at_close.length ? (
                    <div className="mt-2 space-y-2">
                      {analytics.historical.wins_by_rep_at_close.map((rep) => (
                        <div key={rep.user_id ?? "unattributed"} className="flex items-center justify-between gap-3 text-xs">
                          <span className="text-slate-600">{rep.name}</span>
                          <span className="tabular-nums text-slate-700">
                            {rep.won} · ${rep.won_deal_value.toLocaleString()}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-2 text-[11px] text-slate-400">
                      No historical closed-won events in this date range.
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </section>
      )}

      {/* Bottom Data Card: Switches cleanly with top tab */}
      <section className="crm-card overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
          <h2 className="text-sm font-semibold text-slate-900">
            {activeTab === "bookings"
              ? "Recent Test-Drive Bookings"
              : activeTab === "handoffs"
              ? "Inbox Handoff Queue"
              : "Table Data Leads & Deals"}
          </h2>

          {(activeTab === "overview" || activeTab === "pipeline") && (
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-400" />
                <input
                  type="text"
                  value={tableSearch}
                  onChange={(e) => setTableSearch(e.target.value)}
                  placeholder="Search data..."
                  className="crm-input min-h-8 py-1 pl-8 pr-3 text-xs w-48"
                />
              </div>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortBy)}
                className="crm-select min-h-8 w-auto py-1 text-xs"
              >
                <option value="newest">Sort by: Newest</option>
                <option value="value_desc">Sort by: Highest Value</option>
                <option value="name_asc">Sort by: Name</option>
              </select>
            </div>
          )}
        </div>

        {activeTab === "bookings" ? (
          bookings.length === 0 ? (
            <div className="p-10 text-center">
              <Calendar className="mx-auto h-9 w-9 text-slate-300" />
              <p className="mt-3 text-sm font-semibold text-slate-900">No test drives scheduled</p>
              <p className="mt-1 text-xs text-slate-500">Create a booking when a qualified customer is ready.</p>
              <Link href="/bookings" className="crm-btn-primary mt-4 text-xs">Schedule test drive</Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="crm-table crm-mobile-cards">
                <thead>
                  <tr>
                    <th>Customer</th>
                    <th>Vehicle</th>
                    <th>Schedule</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {bookings.slice(0, 8).map((b) => (
                    <tr key={b.id}>
                      <td>
                        <div className="font-medium text-slate-900 text-xs">{b.customer_name || `Customer #${b.customer_id}`}</div>
                        <div className="text-[11px] text-slate-500">{b.customer_email || "—"}</div>
                      </td>
                      <td className="text-xs text-slate-700">{b.vehicle_name || `Vehicle #${b.vehicle_id}`}</td>
                      <td className="text-xs text-slate-500">
                        {b.starts_at ? new Date(b.starts_at).toLocaleString() : `Slot #${b.slot_id}`}
                      </td>
                      <td>
                        <span className="crm-badge crm-badge-info capitalize">{b.status}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : activeTab === "handoffs" ? (
          handoffs.length === 0 ? (
            <div className="p-10 text-center">
              <CheckCircle2 className="mx-auto h-9 w-9 text-emerald-400" />
              <p className="mt-3 text-sm font-semibold text-slate-900">No handoffs waiting</p>
              <p className="mt-1 text-xs text-slate-500">New customer conversations needing staff attention will appear here.</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {handoffs.slice(0, 8).map((conv) => (
                <div key={conv.id} className="flex items-center justify-between px-5 py-3.5 text-xs">
                  <div>
                    <div className="font-semibold text-slate-900">{conv.channel_user_id}</div>
                    <div className="text-slate-500 mt-0.5 line-clamp-1">
                      {conv.last_message_preview || conv.handoff_reason || "Requested agent"}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="crm-badge crm-badge-warning capitalize">{conv.channel}</span>
                    <Link href="/inbox" className="font-semibold text-blue-600 hover:underline">
                      Open
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )
        ) : filteredTableLeads.length === 0 ? (
          <div className="p-10 text-center">
            <Users className="mx-auto h-9 w-9 text-slate-300" />
            <p className="mt-3 text-sm font-semibold text-slate-900">No leads match this view</p>
            <p className="mt-1 text-xs text-slate-500">Add a lead or clear the current search and sort filters.</p>
            <Link href="/leads" className="crm-btn-primary mt-4 text-xs">Open leads</Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="crm-table crm-mobile-cards">
              <thead>
                <tr>
                  <th>Customer</th>
                  <th>Vehicle of Interest</th>
                  <th>Deal / Budget</th>
                  <th>Date Created</th>
                  <th>Owner</th>
                  <th>Stage</th>
                </tr>
              </thead>
              <tbody>
                {filteredTableLeads.slice(0, 8).map((lead) => {
                  const owner = lead.assigned_to_user_id ? staffById.get(lead.assigned_to_user_id) : null;
                  const vehicle = lead.requested_vehicle_id ? vehicleById.get(lead.requested_vehicle_id) : null;
                  const stageMeta = STAGE_ORDER.find((s) => s.key === lead.status) ?? STAGE_ORDER[0];
                  const amount = lead.deal_value ?? lead.budget;

                  return (
                    <tr key={lead.id}>
                      <td>
                        <div className="font-medium text-slate-900 text-xs">{lead.name}</div>
                        <div className="text-[11px] text-slate-500">{lead.email}</div>
                      </td>
                      <td className="text-xs text-slate-700">
                        {vehicle ? `${vehicle.model_year} ${vehicle.make} ${vehicle.model}` : "General Inquiry"}
                      </td>
                      <td className="text-xs font-semibold text-slate-900 tabular-nums">
                        {amount != null ? `$${Number(amount).toLocaleString()}` : "—"}
                      </td>
                      <td className="text-xs text-slate-500">
                        {new Date(lead.created_at).toLocaleDateString([], {
                          weekday: "short",
                          day: "numeric",
                          month: "short",
                          year: "numeric",
                        })}
                      </td>
                      <td>
                        {owner ? (
                          <div className="flex items-center gap-2 text-xs text-slate-700">
                            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-[10px] font-semibold text-slate-700 border border-slate-200">
                              {getInitials(owner.name)}
                            </span>
                            {owner.name}
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400">Unassigned</span>
                        )}
                      </td>
                      <td>
                        <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${stageMeta.badge}`}>
                          <span className={`h-1.5 w-1.5 rounded-full ${stageMeta.dot}`} />
                          {stageMeta.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </Shell>
  );
}
