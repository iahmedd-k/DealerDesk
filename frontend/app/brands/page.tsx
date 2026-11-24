"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Shell from "../components/Shell";
import { useAuth } from "../providers";
import { api } from "../api";
import type { Brand } from "../lib/types";
import {
  Layers,
  Plus,
  Car,
  CheckCircle2,
  XCircle,
  ArrowRight,
  Sparkles,
  Building2,
  Tag,
  ShieldCheck,
} from "lucide-react";

export default function BrandsManagementPage() {
  const { user, activeDealershipId } = useAuth();
  const [brands, setBrands] = useState<Brand[]>([]);
  const [dealershipName, setDealershipName] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newBrandName, setNewBrandName] = useState("");

  useEffect(() => {
    if (!activeDealershipId) {
      setLoading(false);
      setError("Select a dealership workspace to manage brands.");
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError("");
    async function load() {
      try {
        const [nextBrands, dealership] = await Promise.all([
          api<Brand[]>(`/dealerships/${activeDealershipId}/brands`),
          api<{ name: string }>(`/dealerships/${activeDealershipId}`),
        ]);
        if (cancelled) return;
        setBrands(nextBrands);
        setDealershipName(dealership.name);
      } catch (cause) {
        if (!cancelled) setError(cause instanceof Error ? cause.message : "Could not load brands.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [activeDealershipId]);

  async function handleAddBrand(e: React.FormEvent) {
    e.preventDefault();
    if (!activeDealershipId || !newBrandName.trim()) return;
    setError("");
    try {
      const created = await api<Brand>(`/dealerships/${activeDealershipId}/brands`, {
        method: "POST",
        body: JSON.stringify({ name: newBrandName.trim() }),
      });
      setBrands((current) => [...current, created]);
      setNewBrandName("");
      setIsAddModalOpen(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create the brand.");
    }
  }

  async function toggleBrandStatus(brand: Brand) {
    if (!activeDealershipId) return;
    setError("");
    try {
      const updated = await api<Brand>(
        `/dealerships/${activeDealershipId}/brands/${brand.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({ is_active: !brand.is_active }),
        },
      );
      setBrands((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update the brand.");
    }
  }

  const activeBrandsCount = brands.filter((b) => b.is_active).length;
  const totalVehicles = brands.reduce((sum, b) => sum + (b.vehicles_count || 0), 0);

  return (
    <Shell>
      <div className="space-y-6">
        {/* Workspace Brand Header */}
        <div className="rounded-xl border border-slate-800 bg-gradient-to-r from-slate-900 via-slate-850 to-slate-900 p-6 shadow-xl">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="flex h-6 items-center gap-1.5 rounded-full bg-blue-500/20 px-3 text-xs font-semibold uppercase tracking-wider text-blue-400 border border-blue-500/30">
                  <Building2 className="h-3 w-3" />
                  {dealershipName || "Dealership Workspace"}
                </span>
                <span className="text-xs text-slate-400">Single Tenant • Multi-Brand Fleet</span>
              </div>
              <h1 className="text-2xl font-bold tracking-tight text-white">
                Multi-Brand Portfolio
              </h1>
              <p className="mt-1 text-sm text-slate-300">
                Your dealership operates in one isolated workspace. You can carry and manage multiple automotive brands within this single workspace.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setIsAddModalOpen(true)}
                className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-xs font-semibold text-white shadow-md hover:bg-blue-500 transition-colors"
              >
                <Plus className="h-4 w-4" />
                Add Brand to Workspace
              </button>
            </div>
          </div>
        </div>

        {error && <div role="alert" className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">{error}</div>}
        {loading && <p className="text-xs text-slate-400">Loading brands...</p>}
        {!loading && !error && brands.length === 0 && (
          <p className="rounded-lg border border-slate-800 bg-slate-900 p-4 text-sm text-slate-400">No brands are registered in this dealership yet.</p>
        )}

        {/* Workspace Portfolio Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="erp-card flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <Layers className="h-6 w-6" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Brands in Workspace</p>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-2xl font-black text-white">{brands.length}</span>
                <span className="text-xs font-semibold text-emerald-400">({activeBrandsCount} active)</span>
              </div>
            </div>
          </div>

          <div className="erp-card flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Car className="h-6 w-6" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Total Fleet in Portfolio</p>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-2xl font-black text-white">{totalVehicles}</span>
                <span className="text-[11px] text-slate-400">vehicles</span>
              </div>
            </div>
          </div>

          <div className="erp-card flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <ShieldCheck className="h-6 w-6" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Workspace Plan</p>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-xl font-black text-white capitalize">
                  {"Dealership plan"}
                </span>
                <span className="text-[11px] text-emerald-400 font-semibold">(Multi-Brand Enabled)</span>
              </div>
            </div>
          </div>
        </div>

        {/* Brands Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {brands.map((brand) => (
            <div
              key={brand.id}
              className={`erp-card relative flex flex-col justify-between transition-all border ${
                brand.is_active ? "border-slate-800 hover:border-slate-700" : "border-slate-800/40 opacity-70"
              }`}
            >
              <div>
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    {brand.logo_url ? (
                      <img
                        src={brand.logo_url}
                        alt={brand.name}
                        className="h-12 w-12 rounded-lg object-cover border border-slate-700 bg-slate-800"
                      />
                    ) : (
                      <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-600/20 font-black text-blue-400 text-lg border border-blue-500/30">
                        {brand.name.slice(0, 2).toUpperCase()}
                      </div>
                    )}
                    <div>
                      <h3 className="font-bold text-base text-white">{brand.name}</h3>
                      <span className="text-[10px] text-slate-400">Brand ID #{brand.id}</span>
                    </div>
                  </div>

                  <span
                    className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                      brand.is_active
                        ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                        : "bg-slate-700/50 text-slate-400 border border-slate-700"
                    }`}
                  >
                    {brand.is_active ? "Active" : "Disabled"}
                  </span>
                </div>

                <div className="rounded-lg bg-slate-900/60 p-3 mb-4 border border-slate-800/80">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-400 flex items-center gap-1.5">
                      <Car className="h-3.5 w-3.5 text-blue-400" /> Fleet Inventory:
                    </span>
                    <strong className="text-white font-mono">{brand.vehicles_count || 0} cars</strong>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 pt-2 border-t border-slate-800">
                <Link
                  href={`/inventory?brand=${encodeURIComponent(brand.name)}`}
                  className="flex-1 flex items-center justify-center gap-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 px-3 py-2 text-xs font-semibold text-slate-200 transition-colors"
                >
                  <span>View Fleet</span>
                  <ArrowRight className="h-3 w-3" />
                </Link>
                <button
                  onClick={() => toggleBrandStatus(brand)}
                  title={brand.is_active ? "Disable Brand" : "Activate Brand"}
                  className={`rounded-lg px-2.5 py-2 text-xs font-semibold transition-colors ${
                    brand.is_active
                      ? "bg-slate-850 text-slate-400 hover:text-rose-400"
                      : "bg-emerald-950 text-emerald-400 hover:bg-emerald-900"
                  }`}
                >
                  {brand.is_active ? "Disable" : "Enable"}
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Add Brand Modal */}
        {isAddModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
            <div className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
              <div className="flex items-center gap-2 text-blue-400 mb-1">
                <Layers className="h-4 w-4" />
                <span className="text-xs font-bold uppercase tracking-wider">Multi-Brand Expansion</span>
              </div>
              <h2 className="text-lg font-bold text-white mb-2">
                Add Brand to {dealershipName || "Dealership"}
              </h2>
              <p className="text-xs text-slate-400 mb-4">
                Enter the name of the new automotive brand you want to carry and manage inside this workspace.
              </p>

              <form onSubmit={handleAddBrand} className="space-y-4">
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">
                    Brand Name *
                  </label>
                  <input
                    type="text"
                    required
                    autoFocus
                    placeholder="e.g. Mercedes-Benz, Land Rover, Lexus, Hyundai"
                    value={newBrandName}
                    onChange={(e) => setNewBrandName(e.target.value)}
                    className="w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-xs text-white placeholder-slate-500 outline-none focus:border-blue-500"
                  />
                </div>

                <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={() => setIsAddModalOpen(false)}
                    className="rounded-lg bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-500"
                  >
                    Add Brand
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
