"use client";

import { useEffect, useState } from "react";
import {
  Building2,
  Plus,
  Search,
  Settings,
  X,
  AlertCircle,
  CheckCircle2,
  Layers,
  Car,
} from "lucide-react";
import Shell from "../components/Shell";
import { api } from "../api";
import { useAuth } from "../providers";
import type { Dealership } from "../lib/types";

export default function DealershipsPage() {
  const { user, authReady } = useAuth();
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
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [planFilter, setPlanFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const [isProvisionModalOpen, setIsProvisionModalOpen] = useState(false);
  const [selectedDealershipForSub, setSelectedDealershipForSub] =
    useState<Dealership | null>(null);

  const [subPlan, setSubPlan] = useState("pro");
  const [subStatus, setSubStatus] = useState("active");
  const [subPrice, setSubPrice] = useState(299);

  const [newDealership, setNewDealership] = useState({
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

  useEffect(() => {
    if (!authReady || !user) return;
    let cancelled = false;
    setLoading(true);
    setError("");
    Promise.all([
      api<Dealership[]>("/dealerships"),
      api<{
        total_dealerships: number;
        active_dealerships: number;
        total_mrr: number;
        total_vehicles: number;
        total_brands: number;
      }>("/dealerships/metrics"),
    ])
      .then(([list, m]) => {
        if (cancelled) return;
        setDealerships(list);
        setMetrics(m);
      })
      .catch((cause: unknown) => {
        if (!cancelled)
          setError(cause instanceof Error ? cause.message : "Could not load dealerships.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [authReady, user]);

  const filtered = dealerships.filter((d) => {
    const q = search.toLowerCase();
    const matchesSearch =
      d.name.toLowerCase().includes(q) ||
      d.email.toLowerCase().includes(q) ||
      (d.address && d.address.toLowerCase().includes(q));
    const matchesPlan =
      planFilter === "all" ||
      (d.subscription_plan || "pro").toLowerCase() === planFilter.toLowerCase();
    const matchesStatus =
      statusFilter === "all" ||
      (d.subscription_status || "active").toLowerCase() === statusFilter.toLowerCase();
    return matchesSearch && matchesPlan && matchesStatus;
  });

  const totalDealerships = metrics?.total_dealerships ?? dealerships.length;
  const activeDealerships = metrics?.active_dealerships ?? 0;
  const totalConfiguredMonthlyPrice = metrics?.total_mrr ?? 0;
  const totalVehicles = metrics?.total_vehicles ?? 0;
  const totalBrands = metrics?.total_brands ?? 0;

  async function handleUpdateSubscription(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedDealershipForSub) return;
    setError("");
    setNotice("");
    try {
      const updated = await api<Dealership>(
        `/dealerships/${selectedDealershipForSub.id}/subscription`,
        {
          method: "PATCH",
          body: JSON.stringify({
            subscription_plan: subPlan,
            subscription_status: subStatus,
            monthly_price: Number(subPrice),
            is_active: subStatus !== "suspended",
          }),
        },
      );
      setDealerships((current) =>
        current.map((d) => (d.id === selectedDealershipForSub.id ? { ...d, ...updated } : d)),
      );
      setSelectedDealershipForSub(null);
      setNotice("Subscription plan updated.");
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not update dealership plan settings.",
      );
    }
  }

  async function handleProvision(e: React.FormEvent) {
    e.preventDefault();
    const brandsArr = newDealership.brands
      .split(",")
      .map((b) => b.trim())
      .filter(Boolean);
    setError("");
    setNotice("");
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
      setNotice("Dealership tenant provisioned.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not provision dealership.");
    }
  }

  return (
    <Shell>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-medium tracking-tight text-[#171717]">
            SaaS Dealerships & Plans
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Provision tenant workspaces, monitor platform inventory, and manage subscription tiers
          </p>
        </div>

        <button
          type="button"
          onClick={() => setIsProvisionModalOpen(true)}
          className="crm-btn-primary"
        >
          <Plus className="h-4 w-4" />
          Provision Dealership
        </button>
      </div>

      {notice && (
        <div className="mb-5 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs font-medium text-emerald-700">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{notice}</span>
        </div>
      )}

      {error && (
        <div className="mb-5 flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-xs font-medium text-rose-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Platform KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="crm-kpi">
          <p className="text-xs font-medium text-slate-500">Dealership Tenants</p>
          <p className="text-2xl font-medium text-[#171717] tabular-nums mt-1">{totalDealerships}</p>
          <p className="text-xs text-emerald-600 mt-1">{activeDealerships} active</p>
        </div>
        <div className="crm-kpi">
          <p className="text-xs font-medium text-slate-500">Configured MRR</p>
          <p className="text-2xl font-medium text-[#171717] tabular-nums mt-1">
            ${Number(totalConfiguredMonthlyPrice).toLocaleString()}
          </p>
          <p className="text-xs text-slate-500 mt-1">Monthly recurring billing</p>
        </div>
        <div className="crm-kpi">
          <p className="text-xs font-medium text-slate-500">Platform Vehicles</p>
          <p className="text-2xl font-medium text-[#171717] tabular-nums mt-1 flex items-center gap-2">
            <Car className="h-5 w-5 text-blue-600" />
            {totalVehicles}
          </p>
        </div>
        <div className="crm-kpi">
          <p className="text-xs font-medium text-slate-500">Registered Brands</p>
          <p className="text-2xl font-medium text-[#171717] tabular-nums mt-1 flex items-center gap-2">
            <Layers className="h-5 w-5 text-indigo-600" />
            {totalBrands}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="crm-card p-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
          <div className="md:col-span-6 relative">
            <Search className="h-4 w-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search dealership name, email, or address..."
              className="crm-input pl-9"
            />
          </div>
          <div className="md:col-span-3">
            <select
              value={planFilter}
              onChange={(e) => setPlanFilter(e.target.value)}
              className="crm-select"
            >
              <option value="all">All Plans</option>
              <option value="starter">Starter</option>
              <option value="pro">Pro</option>
              <option value="enterprise">Enterprise</option>
            </select>
          </div>
          <div className="md:col-span-3">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="crm-select"
            >
              <option value="all">All Statuses</option>
              <option value="active">Active</option>
              <option value="trialing">Trialing</option>
              <option value="suspended">Suspended</option>
            </select>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="crm-card p-12 text-center text-sm text-slate-500">
          Loading dealership tenants...
        </div>
      ) : (
        <div className="crm-table-wrap">
          <table className="crm-table">
            <thead>
              <tr>
                <th>Dealership</th>
                <th>Plan</th>
                <th>Monthly Price</th>
                <th>Status</th>
                <th>Footprint</th>
                <th className="text-right">Manage</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-10 text-center text-sm text-slate-500">
                    No dealerships match the current filters.
                  </td>
                </tr>
              ) : (
                filtered.map((d) => (
                  <tr key={d.id}>
                    <td>
                      <div className="font-semibold text-slate-900 flex items-center gap-1.5">
                        <Building2 className="h-3.5 w-3.5 text-blue-600" />
                        {d.name}
                      </div>
                      <div className="text-xs text-slate-500">
                        {d.email} {d.timezone ? `· ${d.timezone}` : ""}
                      </div>
                    </td>
                    <td>
                      <span className="crm-badge crm-badge-info uppercase">
                        {d.subscription_plan || "pro"}
                      </span>
                    </td>
                    <td className="font-semibold text-slate-900">
                      ${Number(d.monthly_price ?? 0).toLocaleString()}/mo
                    </td>
                    <td>
                      <span
                        className={`crm-badge ${
                          (d.subscription_status || "active") === "active"
                            ? "crm-badge-success"
                            : d.subscription_status === "suspended"
                            ? "crm-badge-danger"
                            : "crm-badge-warning"
                        }`}
                      >
                        {d.subscription_status || "active"}
                      </span>
                    </td>
                    <td className="text-xs text-slate-600">
                      {d.brands_count ?? 0} brands · {d.vehicles_count ?? 0} vehicles ·{" "}
                      {d.staff_count ?? 0} staff
                    </td>
                    <td className="text-right">
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedDealershipForSub(d);
                          setSubPlan(d.subscription_plan || "pro");
                          setSubStatus(d.subscription_status || "active");
                          setSubPrice(Number(d.monthly_price ?? 299));
                        }}
                        className="crm-btn-secondary py-1.5 px-2.5 text-xs"
                      >
                        <Settings className="h-3.5 w-3.5" />
                        Plan
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Subscription Modal */}
      {selectedDealershipForSub && (
        <div className="crm-modal-overlay">
          <div className="crm-modal max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-medium text-[#171717]">
                  Manage Plan · {selectedDealershipForSub.name}
                </h2>
                <p className="text-xs text-slate-500">
                  Update billing tier, monthly price, and workspace status.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedDealershipForSub(null)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleUpdateSubscription} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Subscription Plan
                </label>
                <select
                  value={subPlan}
                  onChange={(e) => setSubPlan(e.target.value)}
                  className="crm-select"
                >
                  <option value="starter">Starter</option>
                  <option value="pro">Pro</option>
                  <option value="enterprise">Enterprise</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Status
                </label>
                <select
                  value={subStatus}
                  onChange={(e) => setSubStatus(e.target.value)}
                  className="crm-select"
                >
                  <option value="active">Active</option>
                  <option value="trialing">Trialing</option>
                  <option value="suspended">Suspended</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Monthly Price ($)
                </label>
                <input
                  type="number"
                  min={0}
                  value={subPrice}
                  onChange={(e) => setSubPrice(Number(e.target.value))}
                  className="crm-input"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setSelectedDealershipForSub(null)}
                  className="crm-btn-secondary"
                >
                  Cancel
                </button>
                <button type="submit" className="crm-btn-primary">
                  Save Plan
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Provision Dealership Modal */}
      {isProvisionModalOpen && (
        <div className="crm-modal-overlay">
          <div className="crm-modal max-w-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-medium text-[#171717]">Provision Dealership</h2>
                <p className="text-xs text-slate-500">
                  Create a new tenant workspace and initial dealership administrator.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsProvisionModalOpen(false)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleProvision} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Dealership Name
                  </label>
                  <input
                    type="text"
                    required
                    value={newDealership.name}
                    onChange={(e) =>
                      setNewDealership({ ...newDealership, name: e.target.value })
                    }
                    className="crm-input"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Dealership Email
                  </label>
                  <input
                    type="email"
                    required
                    value={newDealership.email}
                    onChange={(e) =>
                      setNewDealership({ ...newDealership, email: e.target.value })
                    }
                    className="crm-input"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Phone
                  </label>
                  <input
                    type="text"
                    value={newDealership.phone}
                    onChange={(e) =>
                      setNewDealership({ ...newDealership, phone: e.target.value })
                    }
                    className="crm-input"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Plan
                  </label>
                  <select
                    value={newDealership.plan}
                    onChange={(e) =>
                      setNewDealership({ ...newDealership, plan: e.target.value })
                    }
                    className="crm-select"
                  >
                    <option value="starter">Starter</option>
                    <option value="pro">Pro</option>
                    <option value="enterprise">Enterprise</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Initial Brands (comma-separated)
                </label>
                <input
                  type="text"
                  placeholder="Toyota, Honda, Lexus"
                  value={newDealership.brands}
                  onChange={(e) =>
                    setNewDealership({ ...newDealership, brands: e.target.value })
                  }
                  className="crm-input"
                />
              </div>

              <div className="grid grid-cols-3 gap-3 pt-2 border-t border-slate-200">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Admin Name
                  </label>
                  <input
                    type="text"
                    required
                    value={newDealership.adminName}
                    onChange={(e) =>
                      setNewDealership({ ...newDealership, adminName: e.target.value })
                    }
                    className="crm-input"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Admin Email
                  </label>
                  <input
                    type="email"
                    required
                    value={newDealership.adminEmail}
                    onChange={(e) =>
                      setNewDealership({ ...newDealership, adminEmail: e.target.value })
                    }
                    className="crm-input"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Admin Password
                  </label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    value={newDealership.adminPassword}
                    onChange={(e) =>
                      setNewDealership({
                        ...newDealership,
                        adminPassword: e.target.value,
                      })
                    }
                    className="crm-input"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsProvisionModalOpen(false)}
                  className="crm-btn-secondary"
                >
                  Cancel
                </button>
                <button type="submit" className="crm-btn-primary">
                  Provision Workspace
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Shell>
  );
}
