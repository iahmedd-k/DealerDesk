"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Car,
  Search,
  Plus,
  X,
  Eye,
  Calendar,
  LayoutGrid,
  Table as TableIcon,
  History,
  ArrowRight,
  Upload,
  Trash2,
  ArrowUp,
  ArrowDown,
  AlertCircle,
} from "lucide-react";
import Shell from "../components/Shell";
import { useAuth } from "../providers";
import { api } from "../api";
import type { Vehicle, VehicleImage, Brand, VehicleStatusHistory } from "../lib/types";

function getStatusBadge(status?: string, isAvailable?: boolean) {
  const s = status || (isAvailable ? "available" : "unavailable");
  switch (s) {
    case "available":
      return { label: "Available", className: "crm-badge crm-badge-success" };
    case "reserved":
      return { label: "Reserved", className: "crm-badge crm-badge-warning" };
    case "sold":
      return { label: "Sold", className: "crm-badge crm-badge-purple" };
    case "in_transit":
      return { label: "In Transit", className: "crm-badge crm-badge-info" };
    case "unavailable":
    default:
      return { label: "Unavailable", className: "crm-badge crm-badge-neutral" };
  }
}

export default function InventoryPage() {
  const { user, authReady, activeDealershipId } = useAuth();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedBrand, setSelectedBrand] = useState<number | "all">("all");
  const [availabilityFilter, setAvailabilityFilter] = useState<
    "all" | "available" | "reserved" | "sold" | "in_transit" | "unavailable"
  >("all");
  const [viewMode, setViewMode] = useState<"table" | "grid">("table");

  const [showAddModal, setShowAddModal] = useState(false);
  const [inspectVehicle, setInspectVehicle] = useState<Vehicle | null>(null);
  const [statusHistory, setStatusHistory] = useState<VehicleStatusHistory[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [transitionStatus, setTransitionStatus] = useState<string>("available");
  const [transitionNotes, setTransitionNotes] = useState("");
  const [transitionBusy, setTransitionBusy] = useState(false);
  const [imageBusy, setImageBusy] = useState(false);
  const [imageFile, setImageFile] = useState<File | null>(null);

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

  const isStaff = Boolean(user && user.role !== "customer");

  useEffect(() => {
    if (!authReady || !user) return;
    if (!activeDealershipId) {
      setLoading(false);
      setError("Select a dealership workspace to view inventory.");
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError("");
    const loadInventory =
      user.role === "customer"
        ? api<Vehicle[]>(`/dealerships/${activeDealershipId}/vehicles/public`).then((items) => {
          const nextBrands = Array.from(
            new Map(
              items.map((item) => [
                item.brand_id,
                {
                  id: item.brand_id,
                  dealership_id: item.dealership_id,
                  name: item.make,
                  logo_url: null,
                  is_active: true,
                  is_deleted: false,
                },
              ]),
            ).values(),
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
        if (nextBrands.length > 0) {
          setNewVehicle((prev) => (prev.brand_id ? prev : { ...prev, brand_id: nextBrands[0].id }));
        }
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
  }, [authReady, user, activeDealershipId]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const bName = new URLSearchParams(window.location.search).get("brand");
    const found = brands.find((brand) => brand.name.toLowerCase() === bName?.toLowerCase());
    if (found) setSelectedBrand(found.id);
  }, [brands]);

  const filteredVehicles = vehicles.filter((v) => {
    const q = searchTerm.toLowerCase();
    const matchesSearch =
      v.model.toLowerCase().includes(q) ||
      v.make.toLowerCase().includes(q) ||
      v.stock_number.toLowerCase().includes(q) ||
      (v.variant && v.variant.toLowerCase().includes(q));

    const matchesBrand = selectedBrand === "all" || v.brand_id === selectedBrand;
    const effectiveStatus = v.status || (v.is_available ? "available" : "unavailable");
    const matchesAvailability = availabilityFilter === "all" || effectiveStatus === availabilityFilter;

    return matchesSearch && matchesBrand && matchesAvailability;
  });

  async function openInspectVehicle(vehicle: Vehicle) {
    setInspectVehicle(vehicle);
    setTransitionStatus(vehicle.status || (vehicle.is_available ? "available" : "unavailable"));
    setTransitionNotes("");
    if (activeDealershipId && isStaff) {
      setLoadingHistory(true);
      try {
        const history = await api<VehicleStatusHistory[]>(
          `/dealerships/${activeDealershipId}/vehicles/${vehicle.id}/history`,
        );
        setStatusHistory(history);
      } catch {
        setStatusHistory([]);
      } finally {
        setLoadingHistory(false);
      }
    } else {
      setStatusHistory([]);
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
        },
      );
      setVehicles((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setInspectVehicle(updated);
      const history = await api<VehicleStatusHistory[]>(
        `/dealerships/${activeDealershipId}/vehicles/${inspectVehicle.id}/history`,
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
      setVehicles((current) => current.map((item) => (item.id === updated.id ? updated : item)));
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
      setVehicles((current) => current.map((item) => (item.id === updated.id ? updated : item)));
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
      current.map((item) => (item.id === vehicleId ? { ...item, images } : item)),
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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-medium tracking-tight text-[#171717]">Vehicle Inventory</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            {filteredVehicles.length} vehicle{filteredVehicles.length === 1 ? "" : "s"} matching active filters
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <div className="inline-flex items-center rounded-lg border border-slate-200 bg-white p-0.5">
            <button
              type="button"
              onClick={() => setViewMode("table")}
              className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${viewMode === "table"
                ? "bg-slate-900 text-white"
                : "text-slate-600 hover:text-slate-900"
                }`}
            >
              <TableIcon className="h-3.5 w-3.5" />
              Table
            </button>
            <button
              type="button"
              onClick={() => setViewMode("grid")}
              className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${viewMode === "grid"
                ? "bg-slate-900 text-white"
                : "text-slate-600 hover:text-slate-900"
                }`}
            >
              <LayoutGrid className="h-3.5 w-3.5" />
              Grid
            </button>
          </div>

          {isStaff && (
            <button
              type="button"
              onClick={() => setShowAddModal(true)}
              className="crm-btn-primary"
            >
              <Plus className="h-4 w-4" />
              Add Vehicle
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-5 flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-xs font-medium text-rose-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Filter Bar */}
      <div className="crm-card p-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
          <div className="md:col-span-5 relative">
            <Search className="h-4 w-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search model, make, variant, or stock #..."
              className="crm-input pl-9"
            />
          </div>

          <div className="md:col-span-4">
            <select
              value={selectedBrand}
              onChange={(e) => setSelectedBrand(e.target.value === "all" ? "all" : Number(e.target.value))}
              className="crm-select"
            >
              <option value="all">All Brands ({brands.length})</option>
              {brands.map((brand) => (
                <option key={brand.id} value={brand.id}>
                  {brand.name}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-3">
            <select
              value={availabilityFilter}
              onChange={(e) =>
                setAvailabilityFilter(
                  e.target.value as
                  | "all"
                  | "available"
                  | "reserved"
                  | "sold"
                  | "in_transit"
                  | "unavailable",
                )
              }
              className="crm-select"
            >
              <option value="all">All Statuses</option>
              <option value="available">Available</option>
              <option value="in_transit">In Transit</option>
              <option value="reserved">Reserved</option>
              <option value="sold">Sold</option>
              <option value="unavailable">Unavailable</option>
            </select>
          </div>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="crm-card p-12 text-center text-sm text-slate-500">
          Loading dealership inventory...
        </div>
      ) : filteredVehicles.length === 0 ? (
        <div className="crm-card p-12 text-center">
          <Car className="h-10 w-10 text-slate-300 mx-auto mb-3" />
          <p className="text-sm font-semibold text-slate-900">No vehicles found</p>
          <p className="text-xs text-slate-500 mt-1">
            Adjust your filters or add a new vehicle to this dealership catalog.
          </p>
        </div>
      ) : viewMode === "table" ? (
        <div className="crm-table-wrap">
          <table className="crm-table">
            <thead>
              <tr>
                <th>Vehicle</th>
                <th>Stock #</th>
                <th>Price</th>
                <th>Status</th>
                <th>Test Drive</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredVehicles.map((vehicle) => {
                const badge = getStatusBadge(vehicle.status, vehicle.is_available);
                const primaryImg = vehicle.images?.[0]?.public_url;
                return (
                  <tr key={vehicle.id}>
                    <td>
                      <div className="flex items-center gap-3">
                        <div className="h-11 w-16 rounded-lg border border-slate-200 bg-slate-100 overflow-hidden shrink-0 flex items-center justify-center">
                          {primaryImg ? (
                            <img
                              src={primaryImg}
                              alt={`${vehicle.make} ${vehicle.model}`}
                              className="h-full w-full object-cover"
                            />
                          ) : (
                            <Car className="h-5 w-5 text-slate-400" />
                          )}
                        </div>
                        <div>
                          <div className="font-semibold text-slate-900">
                            {vehicle.model_year} {vehicle.make} {vehicle.model}
                          </div>
                          <div className="text-xs text-slate-500">
                            {vehicle.variant || "Standard trim"}
                            {vehicle.images && vehicle.images.length > 0
                              ? ` · ${vehicle.images.length} photo${vehicle.images.length > 1 ? "s" : ""}`
                              : ""}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className="font-mono text-xs text-slate-700 bg-slate-100 px-2 py-1 rounded">
                        {vehicle.stock_number}
                      </span>
                    </td>
                    <td className="font-semibold text-slate-900">
                      ${Number(vehicle.price).toLocaleString()}
                    </td>
                    <td>
                      <span className={badge.className}>{badge.label}</span>
                    </td>
                    <td>
                      {isStaff ? (
                        <button
                          type="button"
                          onClick={() => toggleTestDrive(vehicle)}
                          className={`crm-badge cursor-pointer ${vehicle.test_drive_enabled
                            ? "crm-badge-info"
                            : "crm-badge-neutral"
                            }`}
                        >
                          {vehicle.test_drive_enabled ? "Enabled" : "Disabled"}
                        </button>
                      ) : (
                        <span
                          className={`crm-badge ${vehicle.test_drive_enabled
                            ? "crm-badge-info"
                            : "crm-badge-neutral"
                            }`}
                        >
                          {vehicle.test_drive_enabled ? "Bookable" : "Unavailable"}
                        </span>
                      )}
                    </td>
                    <td className="text-right">
                      <div className="inline-flex items-center gap-1.5">
                        {isStaff && (
                          <button
                            type="button"
                            onClick={() => toggleAvailability(vehicle)}
                            className="crm-btn-secondary py-1.5 px-2.5 text-xs"
                          >
                            {vehicle.is_available ? "Set Unavail." : "Set Avail."}
                          </button>
                        )}
                        {vehicle.test_drive_enabled && (
                          <Link
                            href={`/bookings?vehicle=${vehicle.id}`}
                            className="crm-btn-secondary py-1.5 px-2.5 text-xs"
                          >
                            <Calendar className="h-3.5 w-3.5" />
                            Book
                          </Link>
                        )}
                        <button
                          type="button"
                          onClick={() => openInspectVehicle(vehicle)}
                          className="crm-btn-secondary py-1.5 px-2.5 text-xs"
                        >
                          <Eye className="h-3.5 w-3.5" />
                          Inspect
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredVehicles.map((vehicle) => {
            const badge = getStatusBadge(vehicle.status, vehicle.is_available);
            const primaryImg = vehicle.images?.[0]?.public_url;
            return (
              <div key={vehicle.id} className="crm-card overflow-hidden flex flex-col justify-between">
                <div>
                  <div className="h-44 bg-slate-100 border-b border-slate-200 relative flex items-center justify-center">
                    {primaryImg ? (
                      <img
                        src={primaryImg}
                        alt={`${vehicle.make} ${vehicle.model}`}
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <Car className="h-10 w-10 text-slate-300" />
                    )}
                    <div className="absolute top-3 left-3">
                      <span className={badge.className}>{badge.label}</span>
                    </div>
                    <div className="absolute top-3 right-3 rounded-md bg-white/90 px-2 py-0.5 text-[11px] font-mono text-slate-700 border border-slate-200">
                      #{vehicle.stock_number}
                    </div>
                  </div>
                  <div className="p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h3 className="text-sm font-medium text-[#171717]">
                          {vehicle.model_year} {vehicle.make} {vehicle.model}
                        </h3>
                        <p className="text-xs text-slate-500">{vehicle.variant || "Standard trim"}</p>
                      </div>
                      <span className="text-base font-medium text-[#171717]">
                        ${Number(vehicle.price).toLocaleString()}
                      </span>
                    </div>
                    {vehicle.description && (
                      <p className="text-xs text-slate-600 mt-2 line-clamp-2">{vehicle.description}</p>
                    )}
                  </div>
                </div>

                <div className="px-4 pb-4 pt-2 border-t border-slate-100 flex items-center justify-between gap-2">
                  <span
                    className={`crm-badge ${vehicle.test_drive_enabled ? "crm-badge-info" : "crm-badge-neutral"
                      }`}
                  >
                    {vehicle.test_drive_enabled ? "Test Drive Open" : "No Test Drive"}
                  </span>
                  <div className="flex items-center gap-1.5">
                    {vehicle.test_drive_enabled && (
                      <Link
                        href={`/bookings?vehicle=${vehicle.id}`}
                        className="crm-btn-secondary py-1.5 px-2.5 text-xs"
                      >
                        Book
                      </Link>
                    )}
                    <button
                      type="button"
                      onClick={() => openInspectVehicle(vehicle)}
                      className="crm-btn-primary py-1.5 px-2.5 text-xs"
                    >
                      Inspect
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Add Vehicle Modal */}
      {showAddModal && (
        <div className="crm-modal-overlay">
          <div className="crm-modal max-w-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-medium text-[#171717]">Add Vehicle to Inventory</h2>
                <p className="text-xs text-slate-500">Register a unit under an active dealership brand.</p>
              </div>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleCreateVehicle} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Brand</label>
                  <select
                    required
                    value={newVehicle.brand_id}
                    onChange={(e) => setNewVehicle({ ...newVehicle, brand_id: Number(e.target.value) })}
                    className="crm-select"
                  >
                    <option value={0} disabled>
                      Select brand...
                    </option>
                    {brands.map((brand) => (
                      <option key={brand.id} value={brand.id}>
                        {brand.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Model Year</label>
                  <input
                    type="number"
                    required
                    min={1980}
                    max={2035}
                    value={newVehicle.model_year}
                    onChange={(e) => setNewVehicle({ ...newVehicle, model_year: Number(e.target.value) })}
                    className="crm-input"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Model</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Civic"
                    value={newVehicle.model}
                    onChange={(e) => setNewVehicle({ ...newVehicle, model: e.target.value })}
                    className="crm-input"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Variant / Trim</label>
                  <input
                    type="text"
                    placeholder="e.g. Touring"
                    value={newVehicle.variant}
                    onChange={(e) => setNewVehicle({ ...newVehicle, variant: e.target.value })}
                    className="crm-input"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Price ($)</label>
                  <input
                    type="number"
                    required
                    min={0}
                    step="0.01"
                    value={newVehicle.price}
                    onChange={(e) => setNewVehicle({ ...newVehicle, price: Number(e.target.value) })}
                    className="crm-input"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Stock Number</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. STK-1042"
                    value={newVehicle.stock_number}
                    onChange={(e) => setNewVehicle({ ...newVehicle, stock_number: e.target.value })}
                    className="crm-input"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Description</label>
                <textarea
                  rows={3}
                  placeholder="Optional specs, mileage, or dealer notes..."
                  value={newVehicle.description}
                  onChange={(e) => setNewVehicle({ ...newVehicle, description: e.target.value })}
                  className="crm-textarea"
                />
              </div>

              <label className="flex items-center gap-2 text-xs font-medium text-slate-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={newVehicle.test_drive_enabled}
                  onChange={(e) =>
                    setNewVehicle({ ...newVehicle, test_drive_enabled: e.target.checked })
                  }
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                />
                Enable test-drive scheduling for this vehicle
              </label>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="crm-btn-secondary"
                >
                  Cancel
                </button>
                <button type="submit" className="crm-btn-primary">
                  Save Vehicle
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Inspect Vehicle Modal */}
      {inspectVehicle && (
        <div className="crm-modal-overlay">
          <div className="crm-modal max-w-2xl p-6 space-y-6">
            <div className="flex items-start justify-between gap-4 border-b border-slate-200 pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className={getStatusBadge(inspectVehicle.status, inspectVehicle.is_available).className}>
                    {getStatusBadge(inspectVehicle.status, inspectVehicle.is_available).label}
                  </span>
                  <span className="font-mono text-xs text-slate-500">
                    #{inspectVehicle.stock_number}
                  </span>
                </div>
                <h2 className="text-xl font-medium text-[#171717] tabular-nums mt-1">
                  {inspectVehicle.model_year} {inspectVehicle.make} {inspectVehicle.model}
                </h2>
                <p className="text-xs text-slate-500">
                  {inspectVehicle.variant || "Standard trim"} · ${Number(inspectVehicle.price).toLocaleString()}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setInspectVehicle(null)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {inspectVehicle.description && (
              <p className="text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-lg p-3">
                {inspectVehicle.description}
              </p>
            )}

            {/* Vehicle Photos */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-[#171717]">Vehicle Photos</h3>
                <span className="text-xs text-slate-500">
                  {inspectVehicle.images?.length || 0} uploaded
                </span>
              </div>

              {inspectVehicle.images && inspectVehicle.images.length > 0 ? (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
                  {inspectVehicle.images.map((img, idx) => (
                    <div
                      key={img.id}
                      className="rounded-lg border border-slate-200 bg-slate-50 overflow-hidden"
                    >
                      <img
                        src={img.public_url}
                        alt={img.alt_text || `${inspectVehicle.make} ${inspectVehicle.model}`}
                        className="h-28 w-full object-cover"
                      />
                      {isStaff && (
                        <div className="p-1.5 flex items-center justify-between gap-1 bg-white border-t border-slate-200">
                          <div className="flex items-center gap-1">
                            <button
                              type="button"
                              disabled={imageBusy || idx === 0}
                              onClick={() => updateImage(img, { position: Math.max(0, idx - 1) })}
                              className="p-1 rounded hover:bg-slate-100 text-slate-600 disabled:opacity-40"
                              title="Move up"
                            >
                              <ArrowUp className="h-3.5 w-3.5" />
                            </button>
                            <button
                              type="button"
                              disabled={imageBusy || idx === (inspectVehicle.images?.length ?? 1) - 1}
                              onClick={() => updateImage(img, { position: idx + 1 })}
                              className="p-1 rounded hover:bg-slate-100 text-slate-600 disabled:opacity-40"
                              title="Move down"
                            >
                              <ArrowDown className="h-3.5 w-3.5" />
                            </button>
                          </div>
                          <button
                            type="button"
                            disabled={imageBusy}
                            onClick={() => deleteImage(img)}
                            className="p-1 rounded hover:bg-rose-50 text-rose-600 disabled:opacity-40"
                            title="Delete photo"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500 mb-3">No photos uploaded for this vehicle yet.</p>
              )}

              {isStaff && (
                <form onSubmit={handleUploadImage} className="flex flex-wrap items-center gap-2">
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(e) => setImageFile(e.target.files?.[0] || null)}
                    className="text-xs text-slate-600 file:mr-3 file:rounded-lg file:border file:border-slate-200 file:bg-white file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-slate-700 hover:file:bg-slate-50"
                  />
                  <button
                    type="submit"
                    disabled={imageBusy || !imageFile}
                    className="crm-btn-secondary py-1.5 px-3 text-xs"
                  >
                    <Upload className="h-3.5 w-3.5" />
                    {imageBusy ? "Uploading..." : "Upload Photo"}
                  </button>
                </form>
              )}
            </div>

            {/* Lifecycle Transition + History (Staff only) */}
            {isStaff && (
              <div className="border-t border-slate-200 pt-4 space-y-4">
                <h3 className="text-sm font-medium text-[#171717]">Status Lifecycle</h3>
                <form onSubmit={handleStatusTransition} className="grid grid-cols-1 sm:grid-cols-12 gap-2.5">
                  <div className="sm:col-span-4">
                    <select
                      value={transitionStatus}
                      onChange={(e) => setTransitionStatus(e.target.value)}
                      className="crm-select"
                    >
                      <option value="available">Available</option>
                      <option value="in_transit">In Transit</option>
                      <option value="reserved">Reserved</option>
                      <option value="sold">Sold</option>
                      <option value="unavailable">Unavailable</option>
                    </select>
                  </div>
                  <div className="sm:col-span-5">
                    <input
                      type="text"
                      placeholder="Transition note (optional)..."
                      value={transitionNotes}
                      onChange={(e) => setTransitionNotes(e.target.value)}
                      className="crm-input"
                    />
                  </div>
                  <div className="sm:col-span-3">
                    <button
                      type="submit"
                      disabled={transitionBusy}
                      className="crm-btn-primary w-full"
                    >
                      {transitionBusy ? "Saving..." : "Update Status"}
                    </button>
                  </div>
                </form>

                <div>
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700 mb-2">
                    <History className="h-3.5 w-3.5 text-slate-400" />
                    Status History
                  </div>
                  {loadingHistory ? (
                    <p className="text-xs text-slate-500">Loading history...</p>
                  ) : statusHistory.length === 0 ? (
                    <p className="text-xs text-slate-500">No status transitions recorded.</p>
                  ) : (
                    <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                      {statusHistory.map((item) => (
                        <div
                          key={item.id}
                          className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs flex items-center justify-between gap-2"
                        >
                          <div>
                            <div className="font-semibold text-slate-800 flex items-center gap-1.5">
                              <span>{item.previous_status || "initial"}</span>
                              <ArrowRight className="h-3 w-3 text-slate-400" />
                              <span>{item.new_status}</span>
                            </div>
                            {item.notes && <p className="text-slate-600 mt-0.5">{item.notes}</p>}
                          </div>
                          <span className="text-[11px] text-slate-400 shrink-0">
                            {new Date(item.created_at).toLocaleString()}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </Shell>
  );
}
