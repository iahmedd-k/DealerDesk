"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  Building2,
  Calendar,
  Car,
  CheckCircle2,
  DollarSign,
  MessageSquare,
  Plus,
  ShieldCheck,
  Bot,
  TrendingUp,
  Users,
} from "lucide-react";
import Shell from "../components/Shell";
import { useAuth } from "../providers";
import { api } from "../api";
import type {
  ConversationSummary,
  CustomerLead,
  HealthStatus,
  OperationsSummary,
  TestDriveBooking,
  Vehicle,
} from "../lib/types";

export default function DashboardPage() {
  const { user, authReady, activeDealershipId } = useAuth();
  const [summary, setSummary] = useState<OperationsSummary | null>(null);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [bookings, setBookings] = useState<TestDriveBooking[]>([]);
  const [leads, setLeads] = useState<CustomerLead[]>([]);
  const [handoffs, setHandoffs] = useState<ConversationSummary[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);

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
          // Platform admin primarily uses /dealerships; keep overview lightweight
        } else {
          const [sumData, vList, bList, lList, cList] = await Promise.all([
            api<OperationsSummary>(
              `/dealerships/${activeDealershipId}/reports/summary`,
            ).catch(() => null),
            api<Vehicle[]>(`/dealerships/${activeDealershipId}/vehicles`).catch(
              () => [] as Vehicle[],
            ),
            api<TestDriveBooking[]>(
              `/dealerships/${activeDealershipId}/test-drive-bookings`,
            ).catch(() => [] as TestDriveBooking[]),
            api<CustomerLead[]>(`/dealerships/${activeDealershipId}/leads`).catch(
              () => [] as CustomerLead[],
            ),
            api<ConversationSummary[]>(
              `/dealerships/${activeDealershipId}/conversations?status=handed_off`,
            ).catch(() => [] as ConversationSummary[]),
          ]);
          if (cancelled) return;
          setSummary(sumData);
          setVehicles(vList);
          setBookings(bList);
          setLeads(lList);
          setHandoffs(cList);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [authReady, user, activeDealershipId]);

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
            <div className="crm-card p-5">
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
            </div>

            <div className="crm-card p-5">
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
            </div>
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
  const bookedDrives =
    summary?.test_drives.by_status?.booked ??
    bookings.filter((b) => b.status === "booked").length;
  const handoffCount = summary?.conversations.handoff_queue ?? handoffs.length;

  return (
    <Shell>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-medium tracking-tight text-[#171717]">
            Sales &amp; Operations
          </h1>
          <p className="text-xs text-[#525252] mt-1">
            Pipeline, inventory readiness, test drives, and inbox handoffs
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Link href="/leads" className="crm-btn-secondary">
            <Plus className="h-4 w-4" />
            Manage Leads
          </Link>
          <Link href="/inbox" className="crm-btn-primary">
            <MessageSquare className="h-4 w-4" />
            Open Inbox ({handoffCount})
          </Link>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="crm-kpi">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Available Inventory</span>
            <Car className="h-4 w-4 text-blue-600" />
          </div>
          <p className="text-2xl font-medium text-[#171717] tabular-nums mt-2">
            {loading ? "—" : availableVehicles}
          </p>
          <p className="text-xs text-slate-500 mt-1">
            {summary?.inventory.total ?? vehicles.length} total units
          </p>
        </div>

        <div className="crm-kpi">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Active Leads</span>
            <Users className="h-4 w-4 text-indigo-600" />
          </div>
          <p className="text-2xl font-medium text-[#171717] tabular-nums mt-2">
            {loading ? "—" : totalLeads}
          </p>
          <p className="text-xs text-emerald-600 mt-1 flex items-center gap-1">
            <TrendingUp className="h-3 w-3" />
            {summary?.leads.by_status?.won ?? 0} won
          </p>
        </div>

        <div className="crm-kpi">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Won Deal Value</span>
            <DollarSign className="h-4 w-4 text-emerald-600" />
          </div>
          <p className="text-2xl font-medium text-[#171717] tabular-nums mt-2">
            ${Number(wonValue).toLocaleString()}
          </p>
          <p className="text-xs text-slate-500 mt-1">Closed-won pipeline</p>
        </div>

        <div className="crm-kpi">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Booked Test Drives</span>
            <Calendar className="h-4 w-4 text-amber-600" />
          </div>
          <p className="text-2xl font-medium text-[#171717] tabular-nums mt-2">
            {loading ? "—" : bookedDrives}
          </p>
          <p className="text-xs text-slate-500 mt-1">
            {handoffCount} inbox handoffs waiting
          </p>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Leads */}
        <section className="lg:col-span-2 crm-card overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
            <h2 className="text-sm font-medium text-[#171717]">Recent Customer Leads</h2>
            <Link
              href="/leads"
              className="text-xs font-semibold text-blue-600 hover:underline flex items-center gap-1"
            >
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          {leads.length === 0 ? (
            <p className="p-8 text-center text-xs text-slate-500">
              No leads recorded yet for this dealership.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="crm-table">
                <thead>
                  <tr>
                    <th>Customer</th>
                    <th>Source</th>
                    <th>Status</th>
                    <th>Value</th>
                  </tr>
                </thead>
                <tbody>
                  {leads.slice(0, 6).map((lead) => (
                    <tr key={lead.id}>
                      <td>
                        <div className="font-semibold text-slate-900 text-xs">
                          {lead.name}
                        </div>
                        <div className="text-[11px] text-slate-500">{lead.email}</div>
                      </td>
                      <td className="text-xs text-slate-600">{lead.source}</td>
                      <td>
                        <span className="crm-badge crm-badge-info">{lead.status}</span>
                      </td>
                      <td className="text-xs font-semibold text-slate-900">
                        {lead.deal_value ? `$${Number(lead.deal_value).toLocaleString()}` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Right Column: Handoffs + Platform Health */}
        <div className="space-y-6">
          <section className="crm-card p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-medium text-[#171717]">Handoff Queue</h2>
              <Link
                href="/inbox"
                className="text-xs font-semibold text-blue-600 hover:underline"
              >
                Open Inbox
              </Link>
            </div>
            {handoffs.length === 0 ? (
              <p className="text-xs text-slate-500">
                No conversations waiting for human takeover.
              </p>
            ) : (
              <div className="space-y-2.5">
                {handoffs.slice(0, 4).map((conv) => (
                  <div
                    key={conv.id}
                    className="rounded-lg border border-amber-200 bg-amber-50/70 p-3 text-xs"
                  >
                    <div className="flex items-center justify-between font-semibold text-slate-900">
                      <span>{conv.channel_user_id}</span>
                      <span className="uppercase text-[10px] text-amber-700">
                        {conv.channel}
                      </span>
                    </div>
                    <p className="text-slate-600 mt-1 line-clamp-2">
                      {conv.last_message_preview || conv.handoff_reason || "Requested agent"}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="crm-card p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-emerald-600" />
                <h2 className="text-sm font-medium text-[#171717]">Platform Health</h2>
              </div>
              <span className="crm-badge crm-badge-success">
                <CheckCircle2 className="h-3 w-3" />
                {health?.status || "ok"}
              </span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
              <div className="rounded-lg bg-slate-50 border border-slate-200 p-2.5">
                <span className="text-slate-500">Database</span>
                <p className="font-semibold text-slate-900 mt-0.5">
                  {health?.database?.status || "connected"}
                </p>
              </div>
              <div className="rounded-lg bg-slate-50 border border-slate-200 p-2.5">
                <span className="text-slate-500">AI Copilot</span>
                <p className="font-semibold text-slate-900 mt-0.5">
                  <Link
                    href="/assistant"
                    className="inline-flex items-center gap-1 text-blue-600 hover:underline"
                  >
                    <Bot className="h-3 w-3" /> Active
                  </Link>
                </p>
              </div>
            </div>
          </section>
        </div>
      </div>
    </Shell>
  );
}
