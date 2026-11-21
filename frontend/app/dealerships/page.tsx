"use client";

import { useState, useEffect } from "react";
import Shell from "../components/Shell";
import { useAuth } from "../providers";
import { api } from "../api";
import type { Dealership } from "../lib/types";
import {
  Building2,
  Plus,
  DollarSign,
  Car,
  Layers,
  Search,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Ban,
  Filter,
  ArrowUpRight,
  TrendingUp,
  Settings,
  Sparkles,
  RefreshCw,
} from "lucide-react";

export default function DealershipsSaaSPage() {
  const { user } = useAuth();
  const [dealerships, setDealerships] = useState<Dealership[]>([]);
  const [metrics, setMetrics] = useState<{
    total_dealerships: number;
    active_dealerships: number;
    total_mrr: number;
    total_vehicles: number;
    total_brands: number;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [planFilter, setPlanFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [isProvisionModalOpen, setIsProvisionModalOpen] = useState(false);
  const [selectedDealershipForSub, setSelectedDealershipForSub] = useState<Dealership | null>(null);

  // Form state for new dealership provisioning
  const [newDealership, setNewDealership] = useState({
    name: "",
    email: "",
    phone: "",
    address: "",
    timezone: "America/New_York",
    brands: "Toyota, BMW, Audi",
    plan: "pro",
    adminName: "",
    adminEmail: "",
    adminPassword: "",
  });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [data, nextMetrics] = await Promise.all([
          api<Dealership[]>("/dealerships"),
          api<{
            total_dealerships: number;
            active_dealerships: number;
            total_mrr: number;
            total_vehicles: number;
            total_brands: number;
          }>("/dealerships/metrics"),
        ]);
        if (cancelled) return;
        setDealerships(data);
        setMetrics(nextMetrics);
      } catch (cause) {
        if (!cancelled) setError(cause instanceof Error ? cause.message : "Could not load platform data.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  // Filtered dealerships
  const filtered = dealerships.filter((d) => {
    const matchesSearch =
      d.name.toLowerCase().includes(search.toLowerCase()) ||
      d.email.toLowerCase().includes(search.toLowerCase()) ||
      (d.address && d.address.toLowerCase().includes(search.toLowerCase()));
    const matchesPlan =
      planFilter === "all" || (d.subscription_plan || "pro").toLowerCase() === planFilter.toLowerCase();
    const matchesStatus =
      statusFilter === "all" ||
      (d.subscription_status || "active").toLowerCase() === statusFilter.toLowerCase();
    return matchesSearch && matchesPlan && matchesStatus;
  });

  // Calculate SaaS KPIs
  const totalDealerships = metrics?.total_dealerships ?? dealerships.length;
  const activeDealerships = metrics?.active_dealerships ?? 0;
  const totalConfiguredMonthlyPrice = metrics?.total_mrr ?? 0;
  const totalVehicles = metrics?.total_vehicles ?? 0;
  const totalBrands = metrics?.total_brands ?? 0;

  async function handleUpdateSubscription(dId: number, newPlan: string, newStatus: string, newPrice: number) {
    setError("");
    try {
      const updated = await api<Dealership>(`/dealerships/${dId}/subscription`, {
        method: "PATCH",
        body: JSON.stringify({
          subscription_plan: newPlan,
          subscription_status: newStatus,
          monthly_price: newPrice,
          is_active: newStatus !== "suspended",
        }),
      });
      setDealerships((current) => current.map((dealership) => dealership.id === dId
        ? { ...dealership, ...updated }
        : dealership));
      setSelectedDealershipForSub(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update dealership plan settings.");
    }
  }

  async function handleProvision(e: React.FormEvent) {
    e.preventDefault();
    const brandsArr = newDealership.brands.split(",").map((b) => b.trim()).filter(Boolean);
    setError("");
    try {
      const createdUser = await api<{ dealership_id: number }>("/dealerships/register", {
        method: "POST",
        body: JSON.stringify({
          dealership_name: newDealership.name.trim(),
          dealership_email: newDealership.email.trim(),
          dealership_phone: newDealership.phone.trim() || null,
          dealership_address: newDealership.address.trim() || null,
          timezone: newDealership.timezone,
          brands: brandsArr,
          admin_name: newDealership.adminName.trim(),
          admin_email: newDealership.adminEmail.trim(),
          admin_password: newDealership.adminPassword,
        }),
      });
      if (createdUser.dealership_id && newDealership.plan !== "pro") {
        await api(`/dealerships/${createdUser.dealership_id}/subscription`, {
          method: "PATCH",
          body: JSON.stringify({ subscription_plan: newDealership.plan }),
        });
      }
      const [updatedDealerships, updatedMetrics] = await Promise.all([
        api<Dealership[]>("/dealerships"),
        api<{
          total_dealerships: number;
          active_dealerships: number;
          total_mrr: number;
          total_vehicles: number;
          total_brands: number;
        }>("/dealerships/metrics"),
      ]);
      setDealerships(updatedDealerships);
      setMetrics(updatedMetrics);
      setIsProvisionModalOpen(false);
      setNewDealership({
        name: "",
        email: "",
        phone: "",
        address: "",
        timezone: "America/New_York",
        brands: "",
        plan: "pro",
        adminName: "",
        adminEmail: "",
        adminPassword: "",
      });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not provision the dealership.");
    }
  }

  return (
    <Shell>
      <div className="space-y-6">
        {error && <div role="alert" className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">{error}</div>}
        {loading && <p className="text-xs text-slate-400">Loading platform data...</p>}
        {/* SuperAdmin Header Banner */}
        <div className="rounded-xl border border-indigo-500/30 bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 p-6 shadow-xl">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="flex h-6 items-center gap-1.5 rounded-full bg-indigo-500/20 px-3 text-xs font-semibold uppercase tracking-wider text-indigo-400 border border-indigo-500/30">
                  <Sparkles className="h-3 w-3" />
                  DealerDesk SaaS Platform SuperAdmin
                </span>
                <span className="text-xs text-slate-400">Master Control Tower</span>
              </div>
              <h1 className="text-2xl font-bold tracking-tight text-white">
                Dealership Workspaces & Subscriptions
              </h1>
              <p className="mt-1 text-sm text-slate-300">
                You oversee all automotive dealerships subscribed to DealerDesk. Each dealership gets 1 workspace with multi-brand fleet capabilities.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setIsProvisionModalOpen(true)}
                className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-xs font-semibold text-white shadow-md hover:bg-indigo-500 transition-colors"
              >
                <Plus className="h-4 w-4" />
                Provision Dealership Workspace
              </button>
            </div>
          </div>
        </div>

        {/* Platform SaaS KPIs */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <div className="erp-card flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Building2 className="h-6 w-6" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Total Dealerships</p>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-2xl font-black text-white">{totalDealerships}</span>
                <span className="text-xs font-semibold text-emerald-400">({activeDealerships} active)</span>
              </div>
            </div>
          </div>

          <div className="erp-card flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <DollarSign className="h-6 w-6" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Configured Monthly Price</p>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-2xl font-black text-white">${totalConfiguredMonthlyPrice.toLocaleString()}</span>
                <span className="text-[11px] text-slate-400">/mo</span>
              </div>
              <p className="text-[10px] text-slate-500">Not billed or collected</p>
            </div>
          </div>

          <div className="erp-card flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <Car className="h-6 w-6" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Fleet Listed</p>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-2xl font-black text-white">{totalVehicles}</span>
                <span className="text-[11px] text-slate-400">cars</span>
              </div>
            </div>
          </div>

          <div className="erp-card flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
              <Layers className="h-6 w-6" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Brand Accounts</p>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-2xl font-black text-white">{totalBrands}</span>
                <span className="text-[11px] text-slate-400">multi-brands</span>
              </div>
            </div>
          </div>

          <div className="erp-card flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <TrendingUp className="h-6 w-6" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">SaaS Health</p>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-xl font-black text-emerald-400">98.4%</span>
                <span className="text-[11px] text-slate-400">retention</span>
              </div>
            </div>
          </div>
        </div>

        {/* Filter and Search Controls */}
        <div className="erp-card flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3 flex-1">
            <div className="relative flex-1 max-w-md">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search by dealership name, email, or city..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full rounded-lg bg-slate-900 border border-slate-700 pl-9 pr-3 py-2 text-xs text-white placeholder-slate-400 focus:border-indigo-500 outline-none"
              />
            </div>

            <div className="flex items-center gap-2">
              <select
                value={planFilter}
                onChange={(e) => setPlanFilter(e.target.value)}
                className="rounded-lg bg-slate-900 border border-slate-700 px-3 py-2 text-xs text-slate-200 outline-none focus:border-indigo-500"
              >
                <option value="all">All Plan Tiers</option>
                <option value="enterprise">Enterprise ($999/mo)</option>
                <option value="pro">Pro ($499/mo)</option>
                <option value="starter">Starter ($199/mo)</option>
              </select>

              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="rounded-lg bg-slate-900 border border-slate-700 px-3 py-2 text-xs text-slate-200 outline-none focus:border-indigo-500"
              >
                <option value="all">All Subscription Statuses</option>
                <option value="active">Active</option>
                <option value="trialing">Trialing</option>
                <option value="past_due">Past Due</option>
                <option value="suspended">Suspended</option>
              </select>
            </div>
          </div>

          <div className="text-xs text-slate-400 flex items-center gap-1.5">
            Showing <strong className="text-white">{filtered.length}</strong> of {dealerships.length} dealerships
          </div>
        </div>

        {/* Dealerships Table */}
        <div className="erp-card overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="erp-table">
              <thead>
                <tr>
                  <th>Dealership Workspace</th>
                  <th>Contact & Location</th>
                  <th>Plan Tier</th>
                  <th>Subscription Status</th>
                  <th>Fleet / Brands</th>
                  <th>Configured Monthly Price</th>
                  <th>Workspace Health</th>
                  <th className="text-right">Manage</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((d) => {
                  const plan = d.subscription_plan || "pro";
                  const status = d.subscription_status || "active";
                  return (
                    <tr key={d.id} className="hover:bg-slate-800/40">
                      <td>
                        <div className="flex items-center gap-3">
                          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500/10 font-bold text-indigo-400 border border-indigo-500/20">
                            {d.name.slice(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <div className="font-semibold text-white flex items-center gap-2">
                              {d.name}
                              <span className="text-[10px] text-slate-400 font-mono">#{d.id}</span>
                            </div>
                            <div className="text-[11px] text-slate-400">{d.email}</div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <div className="text-xs text-slate-300">{d.address || "No address provided"}</div>
                        <div className="text-[11px] text-slate-400">{d.timezone}</div>
                      </td>
                      <td>
                        {plan === "enterprise" ? (
                          <span className="inline-flex items-center gap-1 rounded-md bg-purple-500/20 px-2 py-1 text-[11px] font-semibold text-purple-400 border border-purple-500/30">
                            Enterprise Tier
                          </span>
                        ) : plan === "starter" ? (
                          <span className="inline-flex items-center gap-1 rounded-md bg-emerald-500/20 px-2 py-1 text-[11px] font-semibold text-emerald-400 border border-emerald-500/30">
                            Starter Tier
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-md bg-blue-500/20 px-2 py-1 text-[11px] font-semibold text-blue-400 border border-blue-500/30">
                            Pro Tier
                          </span>
                        )}
                      </td>
                      <td>
                        {status === "active" ? (
                          <span className="badge badge-success flex items-center gap-1">
                            <CheckCircle2 className="h-3 w-3" /> Active
                          </span>
                        ) : status === "trialing" ? (
                          <span className="badge badge-warning flex items-center gap-1">
                            <Clock className="h-3 w-3" /> Trialing
                          </span>
                        ) : status === "past_due" ? (
                          <span className="badge badge-danger flex items-center gap-1">
                            <AlertTriangle className="h-3 w-3" /> Past Due
                          </span>
                        ) : (
                          <span className="badge badge-neutral flex items-center gap-1">
                            <Ban className="h-3 w-3" /> Suspended
                          </span>
                        )}
                      </td>
                      <td>
                        <div className="text-xs text-white font-medium">
                          {d.vehicles_count ?? 0} vehicles
                        </div>
                        <div className="text-[11px] text-slate-400">
                          {d.brands_count ?? 0} brands inside
                        </div>
                      </td>
                      <td>
                        <span className="font-mono font-bold text-emerald-400 text-xs">
                          ${(d.monthly_price ?? 0).toLocaleString()}
                        </span>
                        <span className="text-[10px] text-slate-400">/mo</span>
                      </td>
                      <td>
                        <div className="flex items-center gap-1 text-[11px] text-slate-300">
                          <span className="h-2 w-2 rounded-full bg-emerald-400"></span>
                          Operational
                        </div>
                      </td>
                      <td className="text-right">
                        <button
                          onClick={() => setSelectedDealershipForSub(d)}
                          className="rounded-lg bg-slate-800 border border-slate-700 px-2.5 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-700 hover:text-white transition-colors"
                        >
                          Modify Plan
                        </button>
                      </td>
                    </tr>
                  );
                })}
                {!loading && filtered.length === 0 && (
                  <tr><td colSpan={8} className="py-8 text-center text-sm text-slate-400">No dealerships match the current filters.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Subscription Modification Modal */}
        {selectedDealershipForSub && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
            <div className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
              <h2 className="text-lg font-bold text-white mb-1">
                Modify SaaS Subscription
              </h2>
              <p className="text-xs text-slate-400 mb-4">
                Managing tenant: <strong className="text-white">{selectedDealershipForSub.name}</strong>
              </p>

              <div className="space-y-4">
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">
                    Subscription Tier
                  </label>
                  <select
                    id="plan-select"
                    defaultValue={selectedDealershipForSub.subscription_plan || "pro"}
                    className="w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-xs text-white outline-none focus:border-indigo-500"
                  >
                    <option value="starter">Starter Plan ($199/month)</option>
                    <option value="pro">Pro Plan ($499/month)</option>
                    <option value="enterprise">Enterprise Plan ($999/month)</option>
                  </select>
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">
                    Subscription Status
                  </label>
                  <select
                    id="status-select"
                    defaultValue={selectedDealershipForSub.subscription_status || "active"}
                    className="w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-xs text-white outline-none focus:border-indigo-500"
                  >
                    <option value="active">Active (Full Access)</option>
                    <option value="trialing">Trialing (30-day grace)</option>
                    <option value="past_due">Past Due (Payment Pending)</option>
                    <option value="suspended">Suspended (Access Blocked)</option>
                  </select>
                </div>

                <div className="flex justify-end gap-2 pt-4 border-t border-slate-800">
                  <button
                    onClick={() => setSelectedDealershipForSub(null)}
                    className="rounded-lg bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => {
                      const planSel = (document.getElementById("plan-select") as HTMLSelectElement).value;
                      const statSel = (document.getElementById("status-select") as HTMLSelectElement).value;
                      const price = planSel === "enterprise" ? 999 : planSel === "starter" ? 199 : 499;
                      handleUpdateSubscription(selectedDealershipForSub.id, planSel, statSel, price);
                    }}
                    className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500"
                  >
                    Save Changes
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Provision Dealership Modal */}
        {isProvisionModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
            <div className="w-full max-w-lg rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
              <h2 className="text-lg font-bold text-white mb-1">
                Provision New Dealership Workspace
              </h2>
              <p className="text-xs text-slate-400 mb-4">
                Onboard a new automotive customer with a dedicated multi-brand workspace.
              </p>

              <form onSubmit={handleProvision} className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[11px] font-semibold text-slate-300 block mb-1">
                      Dealership Name *
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Prestige Motorworks"
                      value={newDealership.name}
                      onChange={(e) => setNewDealership({ ...newDealership, name: e.target.value })}
                      className="w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-xs text-white placeholder-slate-500 outline-none focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-slate-300 block mb-1">
                      Dealership Email *
                    </label>
                    <input
                      type="email"
                      required
                      placeholder="contact@prestigemotors.com"
                      value={newDealership.email}
                      onChange={(e) => setNewDealership({ ...newDealership, email: e.target.value })}
                      className="w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-xs text-white placeholder-slate-500 outline-none focus:border-indigo-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-[11px] font-semibold text-slate-300 block mb-1">
                    Initial Brands (Comma-separated) *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. BMW, Mercedes, Porsche"
                    value={newDealership.brands}
                    onChange={(e) => setNewDealership({ ...newDealership, brands: e.target.value })}
                    className="w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-xs text-white placeholder-slate-500 outline-none focus:border-indigo-500"
                  />
                  <p className="text-[10px] text-slate-400 mt-1">
                    The dealership can add more brands anytime inside their workspace.
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[11px] font-semibold text-slate-300 block mb-1">
                      SaaS Plan Tier
                    </label>
                    <select
                      value={newDealership.plan}
                      onChange={(e) => setNewDealership({ ...newDealership, plan: e.target.value })}
                      className="w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-xs text-white outline-none focus:border-indigo-500"
                    >
                      <option value="starter">Starter Plan ($199/mo)</option>
                      <option value="pro">Pro Plan ($499/mo)</option>
                      <option value="enterprise">Enterprise Plan ($999/mo)</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-slate-300 block mb-1">
                      Timezone
                    </label>
                    <select
                      value={newDealership.timezone}
                      onChange={(e) => setNewDealership({ ...newDealership, timezone: e.target.value })}
                      className="w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-xs text-white outline-none focus:border-indigo-500"
                    >
                      <option value="America/New_York">America/New_York (EST)</option>
                      <option value="America/Chicago">America/Chicago (CST)</option>
                      <option value="America/Denver">America/Denver (MST)</option>
                      <option value="America/Los_Angeles">America/Los_Angeles (PST)</option>
                    </select>
                  </div>
                </div>

                <div className="rounded-lg bg-slate-800/60 border border-slate-700/60 p-3 space-y-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-400">
                    Primary Dealership Admin Account
                  </span>
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="text"
                      required
                      placeholder="Admin Name"
                      value={newDealership.adminName}
                      onChange={(e) => setNewDealership({ ...newDealership, adminName: e.target.value })}
                      className="rounded bg-slate-900 border border-slate-700 px-2.5 py-1.5 text-xs text-white placeholder-slate-500"
                    />
                    <input
                      type="email"
                      required
                      placeholder="Admin Email"
                      value={newDealership.adminEmail}
                      onChange={(e) => setNewDealership({ ...newDealership, adminEmail: e.target.value })}
                      className="rounded bg-slate-900 border border-slate-700 px-2.5 py-1.5 text-xs text-white placeholder-slate-500"
                    />
                  </div>
                  <input
                    type="password"
                    required
                    placeholder="Admin Initial Password"
                    value={newDealership.adminPassword}
                    onChange={(e) => setNewDealership({ ...newDealership, adminPassword: e.target.value })}
                    className="w-full rounded bg-slate-900 border border-slate-700 px-2.5 py-1.5 text-xs text-white placeholder-slate-500"
                  />
                </div>

                <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={() => setIsProvisionModalOpen(false)}
                    className="rounded-lg bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500"
                  >
                    Provision Workspace
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </Shell>
  );
}
