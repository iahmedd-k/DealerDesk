"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Car,
  Search,
  Filter,
  Plus,
  Check,
  X,
  Eye,
  Calendar,
  Layers,
  LayoutGrid,
  Table as TableIcon,
  Tag,
  ChevronRight,
  Sparkles,
  Clock,
  History,
  ArrowRight,
} from "lucide-react";
import Shell from "../components/Shell";
import { useAuth } from "../providers";
import { api } from "../api";
import type { Vehicle, VehicleImage, Brand, VehicleStatusHistory } from "../lib/types";

function getStatusBadge(status?: string, isAvailable?: boolean) {
  const s = status || (isAvailable ? "available" : "unavailable");
  switch (s) {
    case "available":
      return { label: "Available", className: "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" };
    case "reserved":
      return { label: "Reserved", className: "bg-amber-500/20 text-amber-300 border border-amber-500/30" };
    case "sold":
      return { label: "Sold", className: "bg-purple-500/20 text-purple-300 border border-purple-500/30" };
    case "in_transit":
      return { label: "In Transit", className: "bg-blue-500/20 text-blue-300 border border-blue-500/30" };
    case "unavailable":
    default:
      return { label: "Unavailable", className: "bg-slate-500/20 text-slate-300 border border-slate-500/30" };
  }
}

export default function InventoryPage() {
  const { user, activeDealershipId } = useAuth();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedBrand, setSelectedBrand] = useState<number | "all">("all");
  const [availabilityFilter, setAvailabilityFilter] = useState<"all" | "available" | "reserved" | "sold" | "in_transit" | "unavailable">("all");
  const [viewMode, setViewMode] = useState<"table" | "grid">("table");

  // Modal states
  const [showAddModal, setShowAddModal] = useState(false);
  const [inspectVehicle, setInspectVehicle] = useState<Vehicle | null>(null);
  const [statusHistory, setStatusHistory] = useState<VehicleStatusHistory[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [transitionStatus, setTransitionStatus] = useState<string>("available");
  const [transitionNotes, setTransitionNotes] = useState("");
  const [transitionBusy, setTransitionBusy] = useState(false);
  const [imageBusy, setImageBusy] = useState(false);
  const [imageFile, setImageFile] = useState<File | null>(null);

  // New vehicle form state
  const [newVehicle, setNewVehicle] = useState({
    brand_id: 0,
    model: "",
    model_year: new Date().getFullYear(),
    variant: "",
    description: "",
    price: 0,
    stock_number: "",
    test_drive_enabled: false,
  });

  const isStaff = user && user.role !== "customer";

  useEffect(() => {
    if (!activeDealershipId) {
      setLoading(false);
      setError("Select a dealership workspace to view inventory.");
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError("");
    const loadInventory = user?.role === "customer"
      ? api<Vehicle[]>(`/dealerships/${activeDealershipId}/vehicles/public`).then((items) => {
          const nextBrands = Array.from(
            new Map(items.map((item) => [item.brand_id, {
              id: item.brand_id,
              dealership_id: item.dealership_id,
              name: item.make,
              logo_url: null,
              is_active: true,
              is_deleted: false,
            }])).values(),
          );
          return [items, nextBrands] as const;
        })
      : Promise.all([
          api<Vehicle[]>(`/dealerships/${activeDealershipId}/vehicles`),
          api<Brand[]>(`/dealerships/${activeDealershipId}/brands`),
        ]);
    loadInventory
      .then(([nextVehicles, nextBrands]) => {
        if (cancelled) return;
        setVehicles(nextVehicles);
        setBrands(nextBrands);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : "Could not load inventory.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [activeDealershipId, user?.role]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const bName = new URLSearchParams(window.location.search).get("brand");
    const found = brands.find((brand) => brand.name.toLowerCase() === bName?.toLowerCase());
    if (found) setSelectedBrand(found.id);
  }, [brands]);

  // Filtering
  const filteredVehicles = vehicles.filter((v) => {
    const matchesSearch =
      v.model.toLowerCase().includes(searchTerm.toLowerCase()) ||
      v.make.toLowerCase().includes(searchTerm.toLowerCase()) ||
      v.stock_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (v.variant && v.variant.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesBrand = selectedBrand === "all" || v.brand_id === selectedBrand;
    const effectiveStatus = v.status || (v.is_available ? "available" : "unavailable");
    const matchesAvailability =
      availabilityFilter === "all" || effectiveStatus === availabilityFilter;

    return matchesSearch && matchesBrand && matchesAvailability;
  });

  async function openInspectVehicle(vehicle: Vehicle) {
    setInspectVehicle(vehicle);
    setTransitionStatus(vehicle.status || (vehicle.is_available ? "available" : "unavailable"));
    setTransitionNotes("");
    if (activeDealershipId) {
      setLoadingHistory(true);
      try {
        const history = await api<VehicleStatusHistory[]>(
          `/dealerships/${activeDealershipId}/vehicles/${vehicle.id}/history`
        );
        setStatusHistory(history);
      } catch {
        setStatusHistory([]);
      } finally {
        setLoadingHistory(false);
      }
    }
  }

  async function handleStatusTransition(e: React.FormEvent) {
    e.preventDefault();
    if (!activeDealershipId || !inspectVehicle) return;
    setTransitionBusy(true);
    setError("");
    try {
      const updated = await api<Vehicle>(
        `/dealerships/${activeDealershipId}/vehicles/${inspectVehicle.id}/status`,
        {
          method: "PATCH",
          body: JSON.stringify({
            status: transitionStatus,
            notes: transitionNotes.trim() || undefined,
          }),
        }
      );
      setVehicles((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setInspectVehicle(updated);
      const history = await api<VehicleStatusHistory[]>(
        `/dealerships/${activeDealershipId}/vehicles/${inspectVehicle.id}/history`
      );
      setStatusHistory(history);
      setTransitionNotes("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update vehicle status.");
    } finally {
      setTransitionBusy(false);
    }
  }

  async function handleCreateVehicle(e: React.FormEvent) {
    e.preventDefault();
    if (!activeDealershipId) return;
    setError("");
    try {
      const created = await api<Vehicle>(`/dealerships/${activeDealershipId}/vehicles`, {
        method: "POST",
        body: JSON.stringify({
          ...newVehicle,
          brand_id: Number(newVehicle.brand_id),
          model_year: Number(newVehicle.model_year),
          price: Number(newVehicle.price),
          variant: newVehicle.variant || null,
          description: newVehicle.description || null,
        }),
      });
      setVehicles((current) => [created, ...current]);
      setShowAddModal(false);
      setNewVehicle({
        brand_id: brands[0]?.id ?? 0,
        model: "",
        model_year: new Date().getFullYear(),
        variant: "",
        description: "",
        price: 0,
        stock_number: "",
        test_drive_enabled: false,
      });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save this vehicle.");
    }
  }

  async function toggleAvailability(vehicle: Vehicle) {
    if (!activeDealershipId) return;
    setError("");
    try {
      const updated = await api<Vehicle>(
        `/dealerships/${activeDealershipId}/vehicles/${vehicle.id}/availability?available=${!vehicle.is_available}`,
        { method: "PATCH" },
      );
      setVehicles((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update vehicle availability.");
    }
  }

  async function toggleTestDrive(vehicle: Vehicle) {
    if (!activeDealershipId) return;
    setError("");
    try {
      const updated = await api<Vehicle>(`/dealerships/${activeDealershipId}/vehicles/${vehicle.id}`, {
        method: "PATCH",
        body: JSON.stringify({ test_drive_enabled: !vehicle.test_drive_enabled }),
      });
      setVehicles((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update test-drive availability.");
    }
  }

  async function refreshVehicleImages(vehicleId: number) {
    if (!activeDealershipId) return;
    const images = await api<VehicleImage[]>(
      `/dealerships/${activeDealershipId}/vehicles/${vehicleId}/images`,
    );
    setVehicles((current) =>
      current.map((item) => item.id === vehicleId ? { ...item, images } : item),
    );
    setInspectVehicle((current) =>
      current?.id === vehicleId ? { ...current, images } : current,
    );
  }

  async function handleUploadImage(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeDealershipId || !inspectVehicle || !imageFile) return;
    const form = event.currentTarget;
    setImageBusy(true);
    setError("");
    try {
      const body = new FormData();
      body.append("file", imageFile);
      await api<VehicleImage>(
        `/dealerships/${activeDealershipId}/vehicles/${inspectVehicle.id}/images`,
        { method: "POST", body },
      );
      setImageFile(null);
      form.reset();
      await refreshVehicleImages(inspectVehicle.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not upload the vehicle image.");
    } finally {
      setImageBusy(false);
    }
  }

  async function updateImage(
    image: VehicleImage,
    changes: { position?: number; alt_text?: string | null },
  ) {
    if (!activeDealershipId || !inspectVehicle) return;
    setImageBusy(true);
    setError("");
    try {
      await api<VehicleImage>(
        `/dealerships/${activeDealershipId}/vehicles/${inspectVehicle.id}/images/${image.id}`,
        { method: "PATCH", body: JSON.stringify(changes) },
      );
      await refreshVehicleImages(inspectVehicle.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update the vehicle image.");
    } finally {
      setImageBusy(false);
    }
  }

  async function deleteImage(image: VehicleImage) {
    if (!activeDealershipId || !inspectVehicle) return;
    setImageBusy(true);
    setError("");
    try {
      await api<void>(
        `/dealerships/${activeDealershipId}/vehicles/${inspectVehicle.id}/images/${image.id}`,
        { method: "DELETE" },
      );
      await refreshVehicleImages(inspectVehicle.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not remove the vehicle image.");
    } finally {
      setImageBusy(false);
    }
  }

  return (
    <Shell>
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="h-2 w-2 rounded-full bg-blue-500" />
            <p className="text-xs font-bold uppercase tracking-wider text-blue-400">
              Dealership Inventory
            </p>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Vehicle Inventory</h1>
          <p className="text-xs text-slate-400">
            {filteredVehicles.length} vehicles match the current filters
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          {/* View Mode Switcher */}
          <div className="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-0.5">
            <button
              onClick={() => setViewMode("table")}
              className={`p-1.5 rounded ${viewMode === "table" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"}`}
              title="Table View"
            >
              <TableIcon className="h-4 w-4" />
            </button>
            <button
              onClick={() => setViewMode("grid")}
              className={`p-1.5 rounded ${viewMode === "grid" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"}`}
              title="Card Grid View"
            >
              <LayoutGrid className="h-4 w-4" />
            </button>
          </div>

          {isStaff && (
            <button
              onClick={() => setShowAddModal(true)}
              className="btn-primary"
            >
              <Plus className="h-4 w-4" />
              <span>Add Vehicle</span>
            </button>
          )}
        </div>
      </div>

      {error && (
        <div role="alert" className="mb-4 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">
          {error}
        </div>
      )}
      {loading && <p className="mb-4 text-xs text-slate-400">Loading inventory...</p>}
      {!loading && !error && vehicles.length === 0 && (
        <p className="mb-4 rounded-lg border border-slate-800 bg-slate-900 p-4 text-sm text-slate-400">
          No vehicles are registered in this dealership yet.
        </p>
      )}

      {/* Filter & Search Toolbar */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 mb-6 flex flex-col md:flex-row gap-3 items-center justify-between shadow-sm">
        <div className="relative w-full md:w-80">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search make, model, VIN, stock #..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700/80 rounded-lg pl-9 pr-3 py-2 text-xs text-white placeholder-slate-500 outline-none focus:border-blue-500"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2.5 w-full md:w-auto">
          {/* Brand Filter */}
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-slate-400">Brand:</span>
            <select
              value={selectedBrand}
              onChange={(e) => setSelectedBrand(e.target.value === "all" ? "all" : Number(e.target.value))}
              className="bg-slate-950 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 outline-none"
            >
              <option value="all">All Brands ({brands.length})</option>
              {brands.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>

          {/* Availability Filter */}
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-slate-400">Status:</span>
            <select
              value={availabilityFilter}
              onChange={(e) => setAvailabilityFilter(e.target.value as any)}
              className="bg-slate-950 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 outline-none"
            >
              <option value="all">All Statuses</option>
              <option value="available">Available</option>
              <option value="reserved">Reserved</option>
              <option value="sold">Sold</option>
              <option value="in_transit">In Transit</option>
              <option value="unavailable">Unavailable</option>
            </select>
          </div>
        </div>
      </div>

      {/* Table View */}
      {viewMode === "table" ? (
        <div className="erp-table-container">
          <table className="erp-table">
            <thead>
              <tr>
                <th>Vehicle & Specs</th>
                <th>Brand</th>
                <th>Year</th>
                <th>Stock Number</th>
                <th>Price</th>
                <th>Lifecycle Status</th>
                <th>Test Drive</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredVehicles.map((v) => (
                <tr key={v.id}>
                  <td>
                    <div className="flex items-center gap-3">
                      <div className="h-10 w-14 rounded bg-slate-800 overflow-hidden flex-shrink-0 border border-slate-700">
                        {v.images && v.images[0] ? (
                          <img
                            src={v.images[0].public_url}
                            alt={v.model}
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <div className="h-full w-full flex items-center justify-center text-slate-500">
                            <Car className="h-4 w-4" />
                          </div>
                        )}
                      </div>
                      <div>
                        <div className="font-bold text-white text-xs">
                          {v.make} {v.model}
                        </div>
                        <div className="text-[11px] text-slate-400">{v.variant || "Base Trim"}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <span className="badge badge-neutral">{v.make}</span>
                  </td>
                  <td>{v.model_year}</td>
                  <td className="font-mono text-xs text-slate-300">{v.stock_number}</td>
                  <td className="font-bold text-white">${Number(v.price).toLocaleString()}</td>
                  <td>
                    <button
                      onClick={() => openInspectVehicle(v)}
                      className={`badge px-2.5 py-0.5 rounded text-xs font-semibold cursor-pointer ${
                        getStatusBadge(v.status, v.is_available).className
                      }`}
                      title="Click to view details & manage lifecycle status"
                    >
                      {getStatusBadge(v.status, v.is_available).label}
                    </button>
                  </td>
                  <td>
                    <button
                      onClick={() => isStaff && toggleTestDrive(v)}
                      disabled={!isStaff}
                      className={`badge cursor-pointer ${
                        v.test_drive_enabled ? "badge-info" : "badge-neutral"
                      }`}
                    >
                      {v.test_drive_enabled ? "Enabled" : "Disabled"}
                    </button>
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => openInspectVehicle(v)}
                        className="text-xs text-slate-300 hover:text-white p-1 rounded bg-slate-800"
                        title="View Details"
                      >
                        <Eye className="h-3.5 w-3.5" />
                      </button>
                      {v.test_drive_enabled && (
                        <Link
                          href={`/bookings?vehicle=${v.id}`}
                          className="text-xs text-blue-400 hover:text-blue-300 font-semibold"
                        >
                          Book Slot
                        </Link>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!filteredVehicles.length && (
            <div className="p-8 text-center text-xs text-slate-400">
              No vehicles matched your search and filter criteria.
            </div>
          )}
        </div>
      ) : (
        /* Card Grid View */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredVehicles.map((v) => (
            <div
              key={v.id}
              className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden hover:border-slate-700 transition-all flex flex-col shadow-sm"
            >
              <div className="h-44 w-full bg-slate-800 relative overflow-hidden">
                {v.images && v.images[0] ? (
                  <img
                    src={v.images[0].public_url}
                    alt={v.model}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="h-full w-full flex items-center justify-center text-slate-500">
                    <Car className="h-8 w-8" />
                  </div>
                )}
                <div className="absolute top-3 left-3 flex gap-1.5">
                  <span className="badge badge-neutral bg-slate-900/80 backdrop-blur-md">
                    {v.make}
                  </span>
                  <span
                    className={`badge px-2 py-0.5 rounded text-xs font-semibold bg-slate-900/90 backdrop-blur-md ${
                      getStatusBadge(v.status, v.is_available).className
                    }`}
                  >
                    {getStatusBadge(v.status, v.is_available).label}
                  </span>
                </div>
                <div className="absolute bottom-3 right-3 bg-slate-900/90 backdrop-blur-md px-2.5 py-1 rounded text-xs font-bold text-white">
                  ${Number(v.price).toLocaleString()}
                </div>
              </div>

              <div className="p-4 flex-1 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between">
                    <h3 className="font-bold text-white text-base">
                      {v.model_year} {v.make} {v.model}
                    </h3>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">{v.variant || "Standard Variant"}</p>
                  <p className="text-xs text-slate-400 mt-2 line-clamp-2">
                    {v.description || "Certified pre-delivery inspection completed."}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
                  <span className="font-mono text-slate-400 text-[11px]">{v.stock_number}</span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => openInspectVehicle(v)}
                      className="text-xs text-slate-300 hover:text-white"
                    >
                      Details
                    </button>
                    {v.test_drive_enabled && (
                      <Link
                        href={`/bookings?vehicle=${v.id}`}
                        className="btn-primary text-xs py-1 px-2.5"
                      >
                        Book Drive
                      </Link>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Vehicle Inspection Modal */}
      {inspectVehicle && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="p-5 border-b border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-white">
                  {inspectVehicle.model_year} {inspectVehicle.make} {inspectVehicle.model}
                </h3>
                <p className="text-xs text-slate-400">Stock ID: {inspectVehicle.stock_number}</p>
              </div>
              <button
                onClick={() => setInspectVehicle(null)}
                className="text-slate-400 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-5 space-y-4 max-h-[75vh] overflow-y-auto text-xs">
              {/* Media gallery preview */}
              {inspectVehicle.images && inspectVehicle.images.length > 0 && (
                <div className="space-y-2">
                  <p className="font-semibold text-slate-300">Media Gallery ({inspectVehicle.images.length})</p>
                  <div className="grid grid-cols-2 gap-2">
                    {inspectVehicle.images.map((img) => (
                      <div key={img.id} className="overflow-hidden rounded-lg border border-slate-700 bg-slate-900">
                        <img src={img.public_url} alt={img.alt_text || "Vehicle image"} className="h-32 w-full object-cover" />
                        <div className="space-y-2 p-2">
                          <label className="block text-[10px] text-slate-400">
                            Alt text
                            <input
                              value={img.alt_text || ""}
                              maxLength={255}
                              disabled={!isStaff || imageBusy}
                              onChange={(event) => {
                                const alt_text = event.target.value || null;
                                setInspectVehicle((current) => current && ({
                                  ...current,
                                  images: current.images?.map((item) =>
                                    item.id === img.id ? { ...item, alt_text } : item,
                                  ),
                                }));
                              }}
                              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-slate-200"
                            />
                          </label>
                          {isStaff && (
                            <div className="flex flex-wrap gap-1">
                              <button
                                disabled={imageBusy || img.position === 0}
                                onClick={() => updateImage(img, { position: img.position - 1 })}
                                className="btn-secondary px-2 py-1"
                              >
                                Move up
                              </button>
                              <button
                                disabled={imageBusy || img.position === (inspectVehicle.images?.length ?? 0) - 1}
                                onClick={() => updateImage(img, { position: img.position + 1 })}
                                className="btn-secondary px-2 py-1"
                              >
                                Move down
                              </button>
                              <button
                                disabled={imageBusy}
                                onClick={() => updateImage(img, { alt_text: img.alt_text })}
                                className="btn-secondary px-2 py-1"
                              >
                                Save alt text
                              </button>
                              <button
                                disabled={imageBusy}
                                onClick={() => deleteImage(img)}
                                className="rounded border border-rose-500/30 px-2 py-1 text-rose-300 disabled:opacity-50"
                              >
                                Remove
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {isStaff && (
                <form onSubmit={handleUploadImage} className="flex flex-wrap items-end gap-2 rounded-lg border border-slate-800 bg-slate-950 p-3">
                  <label className="min-w-[220px] flex-1 text-[10px] text-slate-400">
                    Add vehicle image
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      disabled={imageBusy}
                      required
                      onChange={(event) => setImageFile(event.target.files?.[0] ?? null)}
                      className="mt-1 block w-full text-xs text-slate-300"
                    />
                  </label>
                  <button disabled={imageBusy || !imageFile} className="btn-primary disabled:opacity-50">
                    {imageBusy ? "Saving..." : "Upload image"}
                  </button>
                </form>
              )}

              <div className="grid grid-cols-2 gap-3 bg-slate-950 p-3 rounded-lg border border-slate-800">
                <div>
                  <span className="text-slate-400">Retail Price:</span>
                  <p className="font-bold text-white text-sm">${Number(inspectVehicle.price).toLocaleString()}</p>
                </div>
                <div>
                  <span className="text-slate-400">Trim Variant:</span>
                  <p className="font-semibold text-slate-200">{inspectVehicle.variant || "Standard"}</p>
                </div>
                <div>
                  <span className="text-slate-400">Test Drive Eligible:</span>
                  <p className="font-semibold text-slate-200">{inspectVehicle.test_drive_enabled ? "Yes" : "No"}</p>
                </div>
                <div>
                  <span className="text-slate-400">Lifecycle Status:</span>
                  <div className="mt-1">
                    <span className={`badge px-2.5 py-0.5 rounded text-xs font-semibold ${getStatusBadge(inspectVehicle.status, inspectVehicle.is_available).className}`}>
                      {getStatusBadge(inspectVehicle.status, inspectVehicle.is_available).label}
                    </span>
                  </div>
                </div>
              </div>

              {/* Status Transition Control (Staff Only) */}
              {isStaff && (
                <div className="rounded-lg border border-slate-800 bg-slate-950 p-3.5 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Layers className="h-4 w-4 text-blue-400" />
                      <span className="font-semibold text-white text-xs">Update Status Transition</span>
                    </div>
                    <span className="text-[10px] text-slate-400">Syncs fleet state & records audit log</span>
                  </div>
                  <form onSubmit={handleStatusTransition} className="space-y-2.5">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      <div>
                        <label className="text-[11px] text-slate-400 block mb-1">New Status</label>
                        <select
                          value={transitionStatus}
                          onChange={(e) => setTransitionStatus(e.target.value)}
                          disabled={transitionBusy}
                          className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-xs text-white"
                        >
                          <option value="available">Available</option>
                          <option value="reserved">Reserved</option>
                          <option value="sold">Sold</option>
                          <option value="in_transit">In Transit</option>
                          <option value="unavailable">Unavailable</option>
                        </select>
                      </div>
                      <div>
                        <label className="text-[11px] text-slate-400 block mb-1">Reason / Notes (Optional)</label>
                        <input
                          type="text"
                          placeholder="e.g. Deposit received, in delivery"
                          value={transitionNotes}
                          onChange={(e) => setTransitionNotes(e.target.value)}
                          disabled={transitionBusy}
                          className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-xs text-white"
                        />
                      </div>
                    </div>
                    <div className="flex justify-end">
                      <button
                        type="submit"
                        disabled={transitionBusy || transitionStatus === (inspectVehicle.status || (inspectVehicle.is_available ? "available" : "unavailable"))}
                        className="btn-primary text-xs py-1.5 px-3 disabled:opacity-50"
                      >
                        {transitionBusy ? "Updating..." : "Apply Transition"}
                      </button>
                    </div>
                  </form>
                </div>
              )}

              {/* Status Audit Trail / History Timeline */}
              <div className="rounded-lg border border-slate-800 bg-slate-950 p-3.5 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <History className="h-4 w-4 text-slate-400" />
                    <span className="font-semibold text-white text-xs">Lifecycle Status History</span>
                  </div>
                  <span className="text-[10px] text-slate-500">{statusHistory.length} events</span>
                </div>
                {loadingHistory ? (
                  <p className="text-xs text-slate-400">Loading audit history...</p>
                ) : statusHistory.length === 0 ? (
                  <p className="text-xs text-slate-500 italic">No transition history recorded yet.</p>
                ) : (
                  <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                    {statusHistory.map((h) => (
                      <div
                        key={h.id}
                        className="flex flex-col gap-1 rounded border border-slate-800/80 bg-slate-900/60 p-2 text-xs"
                      >
                        <div className="flex items-center justify-between text-[11px]">
                          <div className="flex items-center gap-1.5">
                            <span className="font-medium text-slate-400 uppercase text-[10px]">{h.previous_status}</span>
                            <ArrowRight className="h-3 w-3 text-slate-500" />
                            <span className={`px-1.5 py-0.5 rounded font-semibold text-[10px] ${getStatusBadge(h.new_status).className}`}>
                              {h.new_status}
                            </span>
                          </div>
                          <span className="text-slate-500 text-[10px]">
                            {new Date(h.created_at).toLocaleString()}
                          </span>
                        </div>
                        {h.notes && (
                          <p className="text-slate-300 text-[11px] italic pl-1 border-l-2 border-slate-700">
                            "{h.notes}"
                          </p>
                        )}
                        {h.changed_by_user_email && (
                          <span className="text-[10px] text-slate-500">By: {h.changed_by_user_email}</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <span className="text-slate-400">Description & Equipment:</span>
                <p className="text-slate-300 mt-1 leading-relaxed bg-slate-950 p-3 rounded-lg border border-slate-800">
                  {inspectVehicle.description || "Standard vehicle configuration with factory warranty."}
                </p>
              </div>
            </div>

            <div className="p-4 border-t border-slate-800 flex justify-end gap-2 bg-slate-950">
              <button onClick={() => setInspectVehicle(null)} className="btn-secondary">
                Close
              </button>
              {inspectVehicle.test_drive_enabled && (
                <Link
                  href={`/bookings?vehicle=${inspectVehicle.id}`}
                  className="btn-primary"
                >
                  Schedule Test Drive
                </Link>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Add Vehicle Drawer/Modal */}
      {showAddModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="p-5 border-b border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-white">Add New Vehicle to Fleet</h3>
                <p className="text-xs text-slate-400">Registers vehicle in Dealership ERP and updates AI Copilot grounding</p>
              </div>
              <button onClick={() => setShowAddModal(false)} className="text-slate-400 hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleCreateVehicle} className="p-5 space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">Brand</label>
                  <select
                    value={newVehicle.brand_id}
                    onChange={(e) => setNewVehicle({ ...newVehicle, brand_id: Number(e.target.value) })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-white"
                  >
                    {brands.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">Model Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Camry, M4, RS6"
                    value={newVehicle.model}
                    onChange={(e) => setNewVehicle({ ...newVehicle, model: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-white"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">Model Year</label>
                  <input
                    type="number"
                    min="1990"
                    max="2030"
                    value={newVehicle.model_year}
                    onChange={(e) => setNewVehicle({ ...newVehicle, model_year: Number(e.target.value) })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-white"
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">Variant / Trim</label>
                  <input
                    type="text"
                    placeholder="e.g. XSE V6"
                    value={newVehicle.variant}
                    onChange={(e) => setNewVehicle({ ...newVehicle, variant: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-white"
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">Price ($)</label>
                  <input
                    type="number"
                    min="0"
                    step="100"
                    value={newVehicle.price}
                    onChange={(e) => setNewVehicle({ ...newVehicle, price: Number(e.target.value) })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-white"
                  />
                </div>
              </div>

              <div>
                <label className="text-slate-300 font-semibold mb-1 block">Stock Number</label>
                <input
                  type="text"
                  required
                  value={newVehicle.stock_number}
                  onChange={(e) => setNewVehicle({ ...newVehicle, stock_number: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-white font-mono"
                />
              </div>

              <div>
                <label className="text-slate-300 font-semibold mb-1 block">Description</label>
                <textarea
                  rows={3}
                  placeholder="Key equipment, packages, vehicle options..."
                  value={newVehicle.description}
                  onChange={(e) => setNewVehicle({ ...newVehicle, description: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-white"
                />
              </div>

              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="enable_td"
                  checked={newVehicle.test_drive_enabled}
                  onChange={(e) => setNewVehicle({ ...newVehicle, test_drive_enabled: e.target.checked })}
                  className="rounded bg-slate-950 border-slate-700 text-blue-600 focus:ring-0"
                />
                <label htmlFor="enable_td" className="text-slate-300 text-xs">
                  Enable Test Drives for this vehicle
                </label>
              </div>

              <div className="pt-4 border-t border-slate-800 flex justify-end gap-2">
                <button type="button" onClick={() => setShowAddModal(false)} className="btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Save Vehicle to Fleet
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Shell>
  );
}
