"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Building2,
  Layers,
  Plus,
  Trash2,
  Upload,
  X,
  AlertCircle,
  Car,
} from "lucide-react";
import Shell from "../components/Shell";
import { api } from "../api";
import { useAuth } from "../providers";
import type { Brand, Dealership } from "../lib/types";

export default function BrandsPage() {
  const { user, authReady, activeDealershipId } = useAuth();
  const [brands, setBrands] = useState<Brand[]>([]);
  const [dealershipName, setDealershipName] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newBrandName, setNewBrandName] = useState("");

  useEffect(() => {
    if (!authReady || !user) return;
    if (!activeDealershipId) {
      setLoading(false);
      setError("Select a dealership workspace to manage brands.");
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError("");
    Promise.all([
      api<Brand[]>(`/dealerships/${activeDealershipId}/brands`),
      api<Dealership>(`/dealerships/${activeDealershipId}`).catch(() => null),
    ])
      .then(([nextBrands, dealership]) => {
        if (cancelled) return;
        setBrands(nextBrands);
        setDealershipName(dealership?.name ?? "");
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : "Could not load brands.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [authReady, user, activeDealershipId]);

  async function handleAddBrand(e: React.FormEvent) {
    e.preventDefault();
    if (!activeDealershipId || !newBrandName.trim()) return;
    setError("");
    try {
      const created = await api<Brand>(`/dealerships/${activeDealershipId}/brands`, {
        method: "POST",
        body: JSON.stringify({ name: newBrandName.trim() }),
      });
      setBrands((current) => [created, ...current]);
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
      setBrands((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update the brand.");
    }
  }

  async function uploadLogo(brand: Brand, file: File) {
    if (!activeDealershipId) return;
    setError("");
    const form = new FormData();
    form.append("file", file);
    try {
      const updated = await api<Brand>(
        `/dealerships/${activeDealershipId}/brands/${brand.id}/logo`,
        { method: "PUT", body: form },
      );
      setBrands((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not upload the brand logo.");
    }
  }

  async function deleteLogo(brand: Brand) {
    if (!activeDealershipId) return;
    setError("");
    try {
      await api<void>(`/dealerships/${activeDealershipId}/brands/${brand.id}/logo`, {
        method: "DELETE",
      });
      setBrands((current) =>
        current.map((item) => (item.id === brand.id ? { ...item, logo_url: null } : item)),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not remove the brand logo.");
    }
  }

  async function deleteBrand(brand: Brand) {
    if (!activeDealershipId || !window.confirm(`Remove ${brand.name} from this workspace?`)) return;
    setError("");
    try {
      await api<void>(`/dealerships/${activeDealershipId}/brands/${brand.id}`, {
        method: "DELETE",
      });
      setBrands((current) => current.filter((item) => item.id !== brand.id));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not remove the brand.");
    }
  }

  const activeBrandsCount = brands.filter((b) => b.is_active).length;
  const totalVehicles = brands.reduce((sum, b) => sum + (b.vehicles_count || 0), 0);

  return (
    <Shell>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="crm-page-title">
            Multi-Brand Portfolio
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Manage OEM brands, brand logos, and catalog availability for this dealership
          </p>
        </div>

        <button
          type="button"
          onClick={() => setIsAddModalOpen(true)}
          className="crm-btn-primary"
        >
          <Plus className="h-4 w-4" />
          Add Brand
        </button>
      </div>

      {error && (
        <div className="mb-5 flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-xs font-medium text-rose-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Portfolio KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="crm-kpi flex items-center gap-4">
          <div className="h-10 w-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
            <Layers className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-medium text-slate-500">Total Brands</p>
            <p className="text-xl font-medium text-[#171717] tabular-nums">
              {brands.length}{" "}
              <span className="text-xs font-medium text-emerald-600">
                ({activeBrandsCount} active)
              </span>
            </p>
          </div>
        </div>
        <div className="crm-kpi flex items-center gap-4">
          <div className="h-10 w-10 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <Car className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-medium text-slate-500">Catalog Vehicles</p>
            <p className="text-xl font-medium text-[#171717] tabular-nums">{totalVehicles}</p>
          </div>
        </div>
        <div className="crm-kpi flex items-center gap-4">
          <div className="h-10 w-10 rounded-lg bg-slate-100 text-slate-700 flex items-center justify-center">
            <Building2 className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-medium text-slate-500">Workspace Isolation</p>
            <p className="text-sm font-medium text-[#171717] mt-0.5">Single-Tenant Scoped</p>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="crm-card p-12 text-center text-sm text-slate-500">
          Loading brands...
        </div>
      ) : brands.length === 0 ? (
        <div className="crm-card p-12 text-center">
          <Layers className="h-10 w-10 text-slate-300 mx-auto mb-3" />
          <p className="text-sm font-semibold text-slate-900">No brands registered</p>
          <p className="text-xs text-slate-500 mt-1">
            Add your first automotive brand to start listing vehicles.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {brands.map((brand) => (
            <div key={brand.id} className="crm-card p-5 flex flex-col justify-between gap-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="h-12 w-12 rounded-xl border border-slate-200 bg-slate-50 flex items-center justify-center overflow-hidden shrink-0">
                    {brand.logo_url ? (
                      <img
                        src={brand.logo_url}
                        alt={brand.name}
                        className="h-full w-full object-contain p-1"
                      />
                    ) : (
                      <span className="text-sm font-bold text-slate-500">
                        {brand.name.slice(0, 2).toUpperCase()}
                      </span>
                    )}
                  </div>
                  <div>
                    <h3 className="text-base font-medium text-[#171717]">{brand.name}</h3>
                    <p className="text-xs text-slate-500">
                      {brand.vehicles_count ?? 0} vehicle
                      {(brand.vehicles_count ?? 0) === 1 ? "" : "s"}
                    </p>
                  </div>
                </div>

                <span
                  className={`crm-badge ${brand.is_active ? "crm-badge-success" : "crm-badge-neutral"
                    }`}
                >
                  {brand.is_active ? "Active" : "Paused"}
                </span>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 pt-3 border-t border-slate-100">
                <div className="flex items-center gap-1.5">
                  <label className="crm-btn-secondary py-1 px-2.5 text-xs cursor-pointer">
                    <Upload className="h-3.5 w-3.5" />
                    Logo
                    <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) void uploadLogo(brand, file);
                      }}
                    />
                  </label>
                  {brand.logo_url && (
                    <button
                      type="button"
                      onClick={() => deleteLogo(brand)}
                      className="crm-btn-secondary py-1 px-2 text-xs text-rose-600"
                      title="Remove logo"
                    >
                      Remove Logo
                    </button>
                  )}
                </div>

                <div className="flex items-center gap-1.5">
                  <Link
                    href={`/inventory?brand=${encodeURIComponent(brand.name)}`}
                    className="crm-btn-secondary py-1 px-2.5 text-xs"
                  >
                    Inventory
                  </Link>
                  <button
                    type="button"
                    onClick={() => toggleBrandStatus(brand)}
                    className="crm-btn-secondary py-1 px-2.5 text-xs"
                  >
                    {brand.is_active ? "Pause" : "Activate"}
                  </button>
                  <button
                    type="button"
                    onClick={() => deleteBrand(brand)}
                    className="crm-btn-danger py-1 px-2 text-xs"
                    title="Delete brand"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Brand Modal */}
      {isAddModalOpen && (
        <div className="crm-modal-overlay">
          <div className="crm-modal max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-medium text-[#171717]">Add Brand</h2>
              <button
                type="button"
                onClick={() => setIsAddModalOpen(false)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleAddBrand} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Brand Name
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Toyota"
                  value={newBrandName}
                  onChange={(e) => setNewBrandName(e.target.value)}
                  className="crm-input"
                />
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="crm-btn-secondary"
                >
                  Cancel
                </button>
                <button type="submit" className="crm-btn-primary">
                  Save Brand
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Shell>
  );
}
