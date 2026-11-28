"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowDown,
  ArrowUp,
  Calendar,
  Car,
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  Download,
  Eye,
  History,
  Maximize2,
  Plus,
  Search,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import Shell from "../components/Shell";
import { useAuth } from "../providers";
import { api } from "../api";
import type { Brand, Vehicle, VehicleImage, VehicleStatusHistory } from "../lib/types";

type SortOption = "newest" | "price_asc" | "price_desc" | "year_desc";

function getStatusBadge(status?: string, isAvailable?: boolean) {
  const s = status || (isAvailable ? "available" : "unavailable");
  switch (s) {
    case "available":
      return { label: "Available", className: "crm-badge crm-badge-success", dots: 5, dotColor: "bg-emerald-500" };
    case "reserved":
      return { label: "Reserved", className: "crm-badge crm-badge-warning", dots: 3, dotColor: "bg-amber-500" };
    case "sold":
      return { label: "Sold", className: "crm-badge crm-badge-purple", dots: 2, dotColor: "bg-slate-500" };
    case "in_transit":
      return { label: "In Transit", className: "crm-badge crm-badge-info", dots: 4, dotColor: "bg-blue-500" };
    case "unavailable":
    default:
      return { label: "Unavailable", className: "crm-badge crm-badge-neutral", dots: 1, dotColor: "bg-slate-400" };
  }
}

export default function InventoryPage() {
  const { user, authReady, activeDealershipId } = useAuth();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Left-sidebar filters
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedBrand, setSelectedBrand] = useState<number | "all">("all");
  const [availabilityFilter, setAvailabilityFilter] = useState<
    "all" | "available" | "reserved" | "sold" | "in_transit" | "unavailable"
  >("all");
  const [yearFrom, setYearFrom] = useState("");
  const [yearTo, setYearTo] = useState("");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [testDriveOnly, setTestDriveOnly] = useState(false);
  const [fuelFilter, setFuelFilter] = useState("");
  const [transmissionFilter, setTransmissionFilter] = useState("");
  const [locationFilter, setLocationFilter] = useState("");
  const [reconditioningFilter, setReconditioningFilter] = useState<
    "all" | "not_required" | "needed" | "in_progress" | "complete"
  >("all");
  const [sortBy, setSortBy] = useState<SortOption>("newest");

  // Modals & Drawers
  const [showAddModal, setShowAddModal] = useState(false);
  const [inspectVehicle, setInspectVehicle] = useState<Vehicle | null>(null);
  const [activeImageIdx, setActiveImageIdx] = useState(0);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [copiedStock, setCopiedStock] = useState(false);

  // Staff detail actions
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
    vin: "",
    mileage: "",
    transmission: "",
    fuel_type: "",
    drivetrain: "",
    exterior_color: "",
    interior_color: "",
    test_drive_enabled: false,
  });
  const [vinDecodeBusy, setVinDecodeBusy] = useState(false);
  const [vinDecodeMessage, setVinDecodeMessage] = useState("");
  const [csvImportBusy, setCsvImportBusy] = useState(false);
  const [csvImportMessage, setCsvImportMessage] = useState("");

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

  // Keyboard support for fullscreen lightbox
  useEffect(() => {
    if (!lightboxOpen || !inspectVehicle?.images?.length) return;
    const total = inspectVehicle.images.length;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setLightboxOpen(false);
      if (e.key === "ArrowRight") setActiveImageIdx((i) => (i + 1) % total);
      if (e.key === "ArrowLeft") setActiveImageIdx((i) => (i - 1 + total) % total);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [lightboxOpen, inspectVehicle]);

  const statusCounts = useMemo(() => {
    const counts = { all: vehicles.length, available: 0, sold: 0, reserved: 0, in_transit: 0, unavailable: 0 };
    vehicles.forEach((v) => {
      const s = v.status || (v.is_available ? "available" : "unavailable");
      if (s in counts) {
        counts[s as keyof typeof counts] += 1;
      }
    });
    return counts;
  }, [vehicles]);

  const locationOptions = useMemo(
    () =>
      Array.from(
        new Set(
          vehicles
            .map((vehicle) => vehicle.location?.trim())
            .filter((location): location is string => Boolean(location)),
        ),
      ).sort((a, b) => a.localeCompare(b)),
    [vehicles],
  );

  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (searchTerm.trim()) count += 1;
    if (selectedBrand !== "all") count += 1;
    if (availabilityFilter !== "all") count += 1;
    if (yearFrom) count += 1;
    if (yearTo) count += 1;
    if (minPrice) count += 1;
    if (maxPrice) count += 1;
    if (testDriveOnly) count += 1;
    if (fuelFilter) count += 1;
    if (transmissionFilter) count += 1;
    if (locationFilter) count += 1;
    if (reconditioningFilter !== "all") count += 1;
    return count;
  }, [availabilityFilter, fuelFilter, locationFilter, maxPrice, minPrice, reconditioningFilter, searchTerm, selectedBrand, testDriveOnly, transmissionFilter, yearFrom, yearTo]);

  const filteredVehicles = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    const list = vehicles.filter((v) => {
      const matchesSearch =
        !q ||
        v.model.toLowerCase().includes(q) ||
        v.make.toLowerCase().includes(q) ||
        v.stock_number.toLowerCase().includes(q) ||
        (v.vin && v.vin.toLowerCase().includes(q)) ||
        (v.variant && v.variant.toLowerCase().includes(q));

      const matchesBrand = selectedBrand === "all" || v.brand_id === selectedBrand;
      const effectiveStatus = v.status || (v.is_available ? "available" : "unavailable");
      const matchesAvailability = availabilityFilter === "all" || effectiveStatus === availabilityFilter;
      const matchesYearFrom = !yearFrom || v.model_year >= Number(yearFrom);
      const matchesYearTo = !yearTo || v.model_year <= Number(yearTo);
      const matchesMinPrice = !minPrice || Number(v.price) >= Number(minPrice);
      const matchesMaxPrice = !maxPrice || Number(v.price) <= Number(maxPrice);
      const matchesTestDrive = !testDriveOnly || v.test_drive_enabled;
      const matchesFuel = !fuelFilter || v.fuel_type?.toLowerCase() === fuelFilter.toLowerCase();
      const matchesTransmission =
        !transmissionFilter || v.transmission?.toLowerCase() === transmissionFilter.toLowerCase();
      const matchesLocation =
        !locationFilter || v.location?.trim().toLowerCase() === locationFilter.toLowerCase();
      const matchesReconditioning =
        reconditioningFilter === "all" ||
        (v.reconditioning_status || "not_required") === reconditioningFilter;

      return (
        matchesSearch &&
        matchesBrand &&
        matchesAvailability &&
        matchesYearFrom &&
        matchesYearTo &&
        matchesMinPrice &&
        matchesMaxPrice &&
        matchesTestDrive &&
        matchesFuel &&
        matchesTransmission &&
        matchesLocation &&
        matchesReconditioning
      );
    });

    return [...list].sort((a, b) => {
      if (sortBy === "price_asc") return Number(a.price) - Number(b.price);
      if (sortBy === "price_desc") return Number(b.price) - Number(a.price);
      if (sortBy === "year_desc") return b.model_year - a.model_year;
      return b.id - a.id;
    });
  }, [
    availabilityFilter,
    fuelFilter,
    locationFilter,
    maxPrice,
    minPrice,
    reconditioningFilter,
    searchTerm,
    selectedBrand,
    sortBy,
    testDriveOnly,
    transmissionFilter,
    vehicles,
    yearFrom,
    yearTo,
  ]);

  function clearFilters() {
    setSearchTerm("");
    setSelectedBrand("all");
    setAvailabilityFilter("all");
    setYearFrom("");
    setYearTo("");
    setMinPrice("");
    setMaxPrice("");
    setTestDriveOnly(false);
    setFuelFilter("");
    setTransmissionFilter("");
    setLocationFilter("");
    setReconditioningFilter("all");
  }

  function exportCsv() {
    const headers = [
      "ID", "Stock #", "VIN", "Year", "Make", "Model", "Variant", "Mileage",
      "Transmission", "Fuel Type", "Drivetrain", "Exterior Color", "Interior Color",
      "Price", "Acquisition Cost", "Location", "Reconditioning Status", "Acquired At",
      "Days in Stock", "Status", "Test Drive",
    ];
    const rows = filteredVehicles.map((v) => [
      v.id,
      v.stock_number,
      v.vin || "",
      v.model_year,
      v.make,
      v.model,
      v.variant || "",
      v.mileage ?? "",
      v.transmission || "",
      v.fuel_type || "",
      v.drivetrain || "",
      v.exterior_color || "",
      v.interior_color || "",
      v.price,
      v.acquisition_cost ?? "",
      v.location || "",
      v.reconditioning_status || "not_required",
      v.acquired_at || "",
      v.days_in_stock ?? "",
      v.status || (v.is_available ? "available" : "unavailable"),
      v.test_drive_enabled ? "yes" : "no",
    ]);
    const escapeCell = (value: string | number) =>
      `"${String(value).replaceAll('"', '""')}"`;
    const csv = [headers, ...rows]
      .map((row) => row.map(escapeCell).join(","))
      .join("\r\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `dealerdesk-inventory-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function openInspectVehicle(vehicle: Vehicle, initialImageIndex = 0) {
    setInspectVehicle(vehicle);
    setActiveImageIdx(initialImageIndex);
    setLightboxOpen(false);
    setCopiedStock(false);
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
          vin: newVehicle.vin.trim() || null,
          mileage: newVehicle.mileage !== "" ? Number(newVehicle.mileage) : null,
          transmission: newVehicle.transmission || null,
          fuel_type: newVehicle.fuel_type || null,
          drivetrain: newVehicle.drivetrain || null,
          exterior_color: newVehicle.exterior_color || null,
          interior_color: newVehicle.interior_color || null,
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
        vin: "",
        mileage: "",
        transmission: "",
        fuel_type: "",
        drivetrain: "",
        exterior_color: "",
        interior_color: "",
        test_drive_enabled: false,
      });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save this vehicle.");
    }
  }

  async function decodeVin() {
    if (!activeDealershipId) return;
    setVinDecodeBusy(true);
    setVinDecodeMessage("");
    setError("");
    try {
      const decoded = await api<{
        make: string | null;
        model: string | null;
        model_year: number | null;
        variant: string | null;
        fuel_type: string | null;
        drivetrain: string | null;
        transmission: string | null;
      }>(
        `/dealerships/${activeDealershipId}/vehicles/vin/${encodeURIComponent(newVehicle.vin)}/decode`,
      );
      const matchingBrand = brands.find(
        (brand) => brand.name.toLowerCase() === decoded.make?.toLowerCase(),
      );
      setNewVehicle((current) => ({
        ...current,
        brand_id: matchingBrand?.id ?? current.brand_id,
        model: decoded.model ?? current.model,
        model_year: decoded.model_year ?? current.model_year,
        variant: decoded.variant ?? current.variant,
        fuel_type: decoded.fuel_type ?? current.fuel_type,
        drivetrain: decoded.drivetrain ?? current.drivetrain,
        transmission: decoded.transmission ?? current.transmission,
      }));
      setVinDecodeMessage(
        matchingBrand || !decoded.make
          ? "Vehicle details decoded. Verify all values before saving."
          : `Decoded ${decoded.make}; add that brand to this dealership before saving.`,
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not decode this VIN.");
    } finally {
      setVinDecodeBusy(false);
    }
  }

  async function importInventoryCsv(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Choose a .csv inventory file.");
      return;
    }
    if (file.size > 2_000_000) {
      setError("CSV files must be smaller than 2 MB.");
      return;
    }
    if (!activeDealershipId) return;
    setCsvImportBusy(true);
    setError("");
    setCsvImportMessage("");
    try {
      const csvContent = await file.text();
      const preview = await api<{
        creates: number;
        updates: number;
        failed: number;
        errors: { row: number; error: string }[];
      }>(`/dealerships/${activeDealershipId}/vehicles/import/preview`, {
        method: "POST",
        body: JSON.stringify({ csv_content: csvContent, mode: "upsert" }),
      });
      if (preview.creates + preview.updates === 0) {
        const firstIssue = preview.errors[0];
        setCsvImportMessage(
          `No vehicles are ready to import; ${preview.failed} rows need attention.` +
            (firstIssue ? ` First issue: row ${firstIssue.row} — ${firstIssue.error}` : ""),
        );
        return;
      }
      const shouldImport = window.confirm(
        `CSV preview: create ${preview.creates} vehicles and update ${preview.updates}. ` +
          `${preview.failed} rows will be skipped. Continue?`,
      );
      if (!shouldImport) {
        setCsvImportMessage("Import cancelled. No inventory changes were made.");
        return;
      }
      const result = await api<{
        created: number;
        updated: number;
        failed: number;
        errors: { row: number; error: string }[];
      }>(`/dealerships/${activeDealershipId}/vehicles/import`, {
        method: "POST",
        body: JSON.stringify({ csv_content: csvContent, mode: "upsert" }),
      });
      const nextVehicles = await api<Vehicle[]>(
        `/dealerships/${activeDealershipId}/vehicles`,
      );
      setVehicles(nextVehicles);
      const firstIssue = result.errors[0];
      setCsvImportMessage(
        `Created ${result.created} and updated ${result.updated} vehicles; ${result.failed} rows skipped.` +
          (firstIssue ? ` First issue: row ${firstIssue.row} — ${firstIssue.error}` : ""),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not import inventory CSV.");
    } finally {
      setCsvImportBusy(false);
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
      if (inspectVehicle?.id === updated.id) setInspectVehicle(updated);
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
    setActiveImageIdx((idx) => Math.min(idx, Math.max(0, images.length - 1)));
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

  function copyStockId(stockNumber: string) {
    if (typeof navigator === "undefined") return;
    void navigator.clipboard.writeText(stockNumber);
    setCopiedStock(true);
    setTimeout(() => setCopiedStock(false), 1800);
  }

  const drawerImages = inspectVehicle?.images ?? [];
  const activeImage = drawerImages[activeImageIdx] ?? null;
  const fuelOptions = [
    ...new Set(
      vehicles
        .map((vehicle) => vehicle.fuel_type)
        .filter((value): value is string => Boolean(value)),
    ),
  ].sort();
  const transmissionOptions = [
    ...new Set(
      vehicles
        .map((vehicle) => vehicle.transmission)
        .filter((value): value is string => Boolean(value)),
    ),
  ].sort();

  return (
    <Shell>
      {/* Top Bar */}
      <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="crm-page-title">My Inventory</h1>
          <p className="mt-0.5 text-xs text-slate-500">
            {filteredVehicles.length} vehicle{filteredVehicles.length === 1 ? "" : "s"} in catalog
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={exportCsv} className="crm-btn-secondary text-xs">
            <Download className="h-3.5 w-3.5" /> Export as CSV
          </button>
          {(user?.role === "dealership_admin" || user?.role === "manager") && (
            <label className="crm-btn-secondary cursor-pointer text-xs">
              <Upload className="h-3.5 w-3.5" />
              {csvImportBusy ? "Importing…" : "Import CSV"}
              <input
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                disabled={csvImportBusy}
                onChange={(event) => void importInventoryCsv(event)}
              />
            </label>
          )}
          {isStaff && (
            <button
              type="button"
              onClick={() => setShowAddModal(true)}
              className="crm-btn-primary text-xs"
            >
              <Plus className="h-4 w-4" /> Add Vehicle
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
      {csvImportMessage && (
        <div role="status" className="mb-5 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-xs text-blue-800">
          {csvImportMessage}
        </div>
      )}

      {/* 2-Column AutoUncle-Style Layout: Left Filters + Right Cars List */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        {/* LEFT FILTER SIDEBAR */}
        <aside className="crm-card h-fit p-4 lg:col-span-3 space-y-5">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <span className="text-sm font-semibold text-slate-900">
              Filters ({activeFilterCount})
            </span>
            {activeFilterCount > 0 && (
              <button
                type="button"
                onClick={clearFilters}
                className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:underline"
              >
                <X className="h-3 w-3" /> Clear all
              </button>
            )}
          </div>

          {/* Search */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-slate-700">Search</label>
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Model, VIN, variant, stock #..."
                className="crm-input pl-8 text-xs"
              />
            </div>
          </div>

          {/* Brands */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-slate-700">Brand</label>
            <select
              value={selectedBrand}
              onChange={(e) =>
                setSelectedBrand(e.target.value === "all" ? "all" : Number(e.target.value))
              }
              className="crm-select text-xs"
            >
              <option value="all">All Brands ({brands.length})</option>
              {brands.map((brand) => (
                <option key={brand.id} value={brand.id}>
                  {brand.name}
                </option>
              ))}
            </select>
          </div>

          {/* For Sale / Sold Radio Group */}
          <div>
            <div className="mb-2 text-xs font-semibold text-slate-700">For Sale / Status</div>
            <div className="space-y-1.5 text-xs">
              {[
                { id: "all", label: "All", count: statusCounts.all },
                { id: "available", label: "For sale only", count: statusCounts.available },
                { id: "sold", label: "Sold only", count: statusCounts.sold },
                { id: "reserved", label: "Reserved", count: statusCounts.reserved },
                { id: "in_transit", label: "In Transit", count: statusCounts.in_transit },
              ].map((opt) => (
                <label
                  key={opt.id}
                  className="flex cursor-pointer items-center justify-between rounded-lg px-2 py-1 hover:bg-slate-50"
                >
                  <span className="flex items-center gap-2 text-slate-700">
                    <input
                      type="radio"
                      name="availabilityFilter"
                      checked={availabilityFilter === opt.id}
                      onChange={() =>
                        setAvailabilityFilter(opt.id as typeof availabilityFilter)
                      }
                      className="accent-blue-600"
                    />
                    {opt.label}
                  </span>
                  <span className="text-[11px] text-slate-400 tabular-nums">{opt.count}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Year Range */}
          <div>
            <div className="mb-1.5 text-xs font-semibold text-slate-700">Year</div>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="number"
                placeholder="From"
                value={yearFrom}
                onChange={(e) => setYearFrom(e.target.value)}
                className="crm-input text-xs"
              />
              <input
                type="number"
                placeholder="To"
                value={yearTo}
                onChange={(e) => setYearTo(e.target.value)}
                className="crm-input text-xs"
              />
            </div>
          </div>

          {/* Price Range */}
          <div>
            <div className="mb-1.5 text-xs font-semibold text-slate-700">Price ($)</div>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="number"
                min={0}
                placeholder="Min"
                value={minPrice}
                onChange={(e) => setMinPrice(e.target.value)}
                className="crm-input text-xs"
              />
              <input
                type="number"
                min={0}
                placeholder="Max"
                value={maxPrice}
                onChange={(e) => setMaxPrice(e.target.value)}
                className="crm-input text-xs"
              />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold text-slate-700">Fuel Type</span>
              <select
                value={fuelFilter}
                onChange={(event) => setFuelFilter(event.target.value)}
                className="crm-select text-xs"
              >
                <option value="">All fuel types</option>
                {fuelOptions.map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold text-slate-700">Transmission</span>
              <select
                value={transmissionFilter}
                onChange={(event) => setTransmissionFilter(event.target.value)}
                className="crm-select text-xs"
              >
                <option value="">All transmissions</option>
                {transmissionOptions.map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold text-slate-700">Location</span>
              <select
                value={locationFilter}
                onChange={(event) => setLocationFilter(event.target.value)}
                className="crm-select text-xs"
              >
                <option value="">All locations</option>
                {locationOptions.map((location) => (
                  <option key={location} value={location}>{location}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold text-slate-700">Reconditioning</span>
              <select
                value={reconditioningFilter}
                onChange={(event) =>
                  setReconditioningFilter(
                    event.target.value as typeof reconditioningFilter,
                  )
                }
                className="crm-select text-xs"
              >
                <option value="all">All statuses</option>
                <option value="not_required">Not required</option>
                <option value="needed">Needed</option>
                <option value="in_progress">In progress</option>
                <option value="complete">Complete</option>
              </select>
            </label>
          </div>

          {/* Test Drive Toggle */}
          <label className="flex cursor-pointer items-center gap-2 border-t border-slate-100 pt-3 text-xs text-slate-700">
            <input
              type="checkbox"
              checked={testDriveOnly}
              onChange={(e) => setTestDriveOnly(e.target.checked)}
              className="accent-blue-600"
            />
            Test drive enabled only
          </label>
        </aside>

        {/* RIGHT MAIN LIST */}
        <section className="crm-card overflow-hidden lg:col-span-9">
          {/* Header Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-3.5">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-slate-900">My Cars</h2>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                {filteredVehicles.length}
              </span>
            </div>

            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-500">Sort by:</span>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortOption)}
                className="crm-select w-auto py-1.5 text-xs"
              >
                <option value="newest">Created at: Descending</option>
                <option value="price_asc">Price: Low to High</option>
                <option value="price_desc">Price: High to Low</option>
                <option value="year_desc">Year: Newest First</option>
              </select>
            </div>
          </div>

          {/* Column Subheader */}
          <div className="hidden border-b border-slate-100 bg-slate-50/70 px-5 py-2 text-[11px] font-medium text-slate-500 md:grid md:grid-cols-12">
            <div className="col-span-6">Make &amp; Model</div>
            <div className="col-span-2">Variant / Year</div>
            <div className="col-span-2">Stock &amp; Photos</div>
            <div className="col-span-2 text-right">Price</div>
          </div>

          {/* Car Rows */}
          {loading ? (
            <div className="p-5 space-y-3" aria-label="Loading inventory">
              {[1, 2, 3].map((row) => (
                <div key={row} className="grid grid-cols-12 items-center gap-3 rounded-lg border border-slate-100 p-3">
                  <span className="crm-skeleton col-span-2 h-14 w-full" />
                  <span className="crm-skeleton col-span-4 h-4" />
                  <span className="crm-skeleton col-span-3 h-4" />
                  <span className="crm-skeleton col-span-3 h-5" />
                </div>
              ))}
            </div>
          ) : filteredVehicles.length === 0 ? (
            <div className="p-12 text-center">
              <Car className="mx-auto mb-3 h-10 w-10 text-slate-300" />
              <p className="text-sm font-semibold text-slate-900">No vehicles found</p>
              <p className="mt-1 text-xs text-slate-500">
                Adjust your filters or add a new vehicle to this dealership catalog.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-200">
              {filteredVehicles.map((vehicle) => {
                const badge = getStatusBadge(vehicle.status, vehicle.is_available);
                const primaryImg = vehicle.images?.[0]?.public_url;
                const photoCount = vehicle.images?.length ?? 0;

                return (
                  <div
                    key={vehicle.id}
                    className="p-4 sm:px-5 transition-colors hover:bg-slate-50/60"
                  >
                    <div className="grid grid-cols-1 gap-4 md:grid-cols-12 md:items-start">
                      {/* Thumbnail + Make/Model + Summary */}
                      <div className="flex gap-4 md:col-span-6">
                        <button
                          type="button"
                          onClick={() => void openInspectVehicle(vehicle, 0)}
                          className="group relative h-20 w-28 shrink-0 overflow-hidden rounded-lg border border-slate-200 bg-slate-100"
                          title="View car details & photos"
                        >
                          {primaryImg ? (
                            <img
                              src={primaryImg}
                              alt={`${vehicle.make} ${vehicle.model}`}
                              className="h-full w-full object-cover transition-transform group-hover:scale-105"
                            />
                          ) : (
                            <div className="flex h-full w-full items-center justify-center">
                              <Car className="h-6 w-6 text-slate-400" />
                            </div>
                          )}
                          {photoCount > 1 && (
                            <span className="absolute bottom-1 right-1 rounded bg-black/65 px-1.5 py-0.5 text-[10px] font-medium text-white">
                              {photoCount}
                            </span>
                          )}
                        </button>

                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <button
                              type="button"
                              onClick={() => void openInspectVehicle(vehicle, 0)}
                              className="text-left text-sm font-semibold text-slate-900 hover:text-blue-600"
                            >
                              {vehicle.make} {vehicle.model}
                            </button>
                            <span className={badge.className}>{badge.label}</span>
                          </div>
                          <p className="mt-1 line-clamp-1 text-xs text-slate-600">
                            {vehicle.description || `${vehicle.model_year} ${vehicle.make} ${vehicle.model} ${vehicle.variant || ""}`}
                          </p>
                          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                            <span>Stock #{vehicle.stock_number}</span>
                            {vehicle.vin && <span>· VIN {vehicle.vin}</span>}
                            {vehicle.mileage != null && <span>· {vehicle.mileage.toLocaleString()} mi</span>}
                            {vehicle.transmission && <span>· {vehicle.transmission}</span>}
                            {vehicle.fuel_type && <span>· {vehicle.fuel_type}</span>}
                            {vehicle.location && <span>· {vehicle.location}</span>}
                            {vehicle.days_in_stock != null && (
                              <span>· {vehicle.days_in_stock} days in stock</span>
                            )}
                            <span>·</span>
                            <span>{vehicle.test_drive_enabled ? "Test Drive Ready" : "No Test Drive"}</span>
                          </div>
                        </div>
                      </div>

                      {/* Variant / Year */}
                      <div className="md:col-span-2 text-xs">
                        <div className="font-medium text-slate-800">{vehicle.variant || "Standard"}</div>
                        <div className="text-slate-500 mt-0.5">{vehicle.model_year}</div>
                      </div>

                      {/* Stock & Photos */}
                      <div className="md:col-span-2 text-xs text-slate-600">
                        <div>{photoCount} photo{photoCount === 1 ? "" : "s"}</div>
                        {vehicle.reconditioning_status &&
                          vehicle.reconditioning_status !== "not_required" && (
                            <div className="mt-1 text-[10px] capitalize text-amber-700">
                              Reconditioning: {vehicle.reconditioning_status.replaceAll("_", " ")}
                            </div>
                          )}
                        {isStaff && (
                          <button
                            type="button"
                            onClick={() => void toggleTestDrive(vehicle)}
                            className="mt-1 text-[11px] font-medium text-blue-600 hover:underline"
                          >
                            {vehicle.test_drive_enabled ? "Disable TD" : "Enable TD"}
                          </button>
                        )}
                      </div>

                      {/* Price + Indicator Dots + View Details Button */}
                      <div className="flex flex-row items-center justify-between gap-2 md:col-span-2 md:flex-col md:items-end">
                        <div className="md:text-right">
                          <div className="text-sm font-semibold text-slate-900 tabular-nums">
                            ${Number(vehicle.price).toLocaleString()}
                          </div>
                          {vehicle.acquisition_cost != null && (
                            <div className="mt-0.5 text-[10px] text-slate-500">
                              Cost ${Number(vehicle.acquisition_cost).toLocaleString()}
                            </div>
                          )}
                          <div className="mt-1 flex items-center gap-1 md:justify-end">
                            {[1, 2, 3, 4, 5].map((dot) => (
                              <span
                                key={dot}
                                className={`h-1.5 w-1.5 rounded-full ${
                                  dot <= badge.dots ? badge.dotColor : "bg-slate-200"
                                }`}
                              />
                            ))}
                          </div>
                        </div>

                        <button
                          type="button"
                          onClick={() => void openInspectVehicle(vehicle, 0)}
                          className="crm-btn-primary min-h-8 px-3 py-1.5 text-xs"
                        >
                          <Eye className="h-3.5 w-3.5" /> View details
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </div>

      {/* Add Vehicle Modal */}
      {showAddModal && isStaff && (
        <div className="crm-modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="crm-modal max-w-lg p-6" onClick={(e) => e.stopPropagation()}>
            <div className="mb-5 flex items-center justify-between">
              <h2 className="text-lg font-medium text-[#171717]">Add Vehicle to Catalog</h2>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleCreateVehicle} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Brand</label>
                  <select
                    required
                    value={newVehicle.brand_id}
                    onChange={(e) =>
                      setNewVehicle({ ...newVehicle, brand_id: Number(e.target.value) })
                    }
                    className="crm-select"
                  >
                    {brands.map((brand) => (
                      <option key={brand.id} value={brand.id}>
                        {brand.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Model</label>
                  <input
                    required
                    type="text"
                    value={newVehicle.model}
                    onChange={(e) => setNewVehicle({ ...newVehicle, model: e.target.value })}
                    placeholder="e.g. Civic"
                    className="crm-input"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">VIN</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    maxLength={17}
                    value={newVehicle.vin}
                    onChange={(e) => setNewVehicle({ ...newVehicle, vin: e.target.value.toUpperCase() })}
                    placeholder="17-character VIN"
                    className="crm-input flex-1 uppercase"
                  />
                  <button
                    type="button"
                    disabled={vinDecodeBusy || newVehicle.vin.trim().length !== 17}
                    onClick={() => void decodeVin()}
                    className="crm-btn-secondary shrink-0"
                  >
                    {vinDecodeBusy ? "Decoding…" : "Decode VIN"}
                  </button>
                </div>
                {vinDecodeMessage && (
                  <p role="status" className="mt-1 text-[11px] text-blue-700">{vinDecodeMessage}</p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Variant / Trim</label>
                  <input
                    type="text"
                    value={newVehicle.variant}
                    onChange={(e) => setNewVehicle({ ...newVehicle, variant: e.target.value })}
                    placeholder="e.g. Touring"
                    className="crm-input"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Year</label>
                  <input
                    required
                    type="number"
                    min={1990}
                    max={2030}
                    value={newVehicle.model_year}
                    onChange={(e) =>
                      setNewVehicle({ ...newVehicle, model_year: Number(e.target.value) })
                    }
                    className="crm-input"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Price ($)</label>
                  <input
                    required
                    type="number"
                    min={1}
                    value={newVehicle.price || ""}
                    onChange={(e) =>
                      setNewVehicle({ ...newVehicle, price: Number(e.target.value) })
                    }
                    className="crm-input"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Stock #</label>
                  <input
                    required
                    type="text"
                    value={newVehicle.stock_number}
                    onChange={(e) =>
                      setNewVehicle({ ...newVehicle, stock_number: e.target.value })
                    }
                    placeholder="e.g. STK-1042"
                    className="crm-input"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Mileage</label>
                  <input
                    type="number"
                    min={0}
                    value={newVehicle.mileage}
                    onChange={(e) => setNewVehicle({ ...newVehicle, mileage: e.target.value })}
                    className="crm-input"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Transmission</label>
                  <input
                    type="text"
                    maxLength={32}
                    value={newVehicle.transmission}
                    onChange={(e) => setNewVehicle({ ...newVehicle, transmission: e.target.value })}
                    placeholder="Automatic"
                    className="crm-input"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Fuel Type</label>
                  <input
                    type="text"
                    maxLength={32}
                    value={newVehicle.fuel_type}
                    onChange={(e) => setNewVehicle({ ...newVehicle, fuel_type: e.target.value })}
                    placeholder="Gasoline, hybrid, electric…"
                    className="crm-input"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Drivetrain</label>
                  <input
                    type="text"
                    maxLength={32}
                    value={newVehicle.drivetrain}
                    onChange={(e) => setNewVehicle({ ...newVehicle, drivetrain: e.target.value })}
                    placeholder="FWD, AWD, 4WD…"
                    className="crm-input"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Exterior Color</label>
                  <input
                    type="text"
                    maxLength={64}
                    value={newVehicle.exterior_color}
                    onChange={(e) => setNewVehicle({ ...newVehicle, exterior_color: e.target.value })}
                    className="crm-input"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Interior Color</label>
                  <input
                    type="text"
                    maxLength={64}
                    value={newVehicle.interior_color}
                    onChange={(e) => setNewVehicle({ ...newVehicle, interior_color: e.target.value })}
                    className="crm-input"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Description / Specs
                </label>
                <textarea
                  rows={2}
                  value={newVehicle.description}
                  onChange={(e) =>
                    setNewVehicle({ ...newVehicle, description: e.target.value })
                  }
                  placeholder="Mileage, transmission, trim highlights, or dealer notes..."
                  className="crm-input"
                />
              </div>

              <label className="flex items-center gap-2 text-xs font-medium text-slate-700">
                <input
                  type="checkbox"
                  checked={newVehicle.test_drive_enabled}
                  onChange={(e) =>
                    setNewVehicle({ ...newVehicle, test_drive_enabled: e.target.checked })
                  }
                  className="rounded border-slate-300"
                />
                Enable test drives for this vehicle immediately
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

      {/* Slide-Over Car Details Drawer (Reference Style) */}
      {inspectVehicle && (
        <div
          className="fixed inset-0 z-50 flex justify-end bg-black/40"
          onClick={() => setInspectVehicle(null)}
        >
          <div
            className="flex h-full w-full max-w-2xl flex-col bg-white shadow-2xl border-l border-slate-200"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Drawer Header */}
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
              <h2 className="text-base font-semibold text-slate-900">Car Details</h2>
              <button
                type="button"
                onClick={() => setInspectVehicle(null)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Drawer Scroll Body */}
            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
              {/* Hero Image Carousel */}
              <div>
                <div className="relative aspect-[16/10] w-full overflow-hidden rounded-xl border border-slate-200 bg-slate-100">
                  {activeImage ? (
                    <img
                      src={activeImage.public_url}
                      alt={activeImage.alt_text || `${inspectVehicle.make} ${inspectVehicle.model}`}
                      onClick={() => setLightboxOpen(true)}
                      className="h-full w-full cursor-zoom-in object-cover"
                    />
                  ) : (
                    <div className="flex h-full w-full flex-col items-center justify-center text-slate-400">
                      <Car className="h-12 w-12 mb-2" />
                      <span className="text-xs">No photos uploaded yet</span>
                    </div>
                  )}

                  {drawerImages.length > 1 && (
                    <>
                      <button
                        type="button"
                        onClick={() =>
                          setActiveImageIdx(
                            (i) => (i - 1 + drawerImages.length) % drawerImages.length,
                          )
                        }
                        className="absolute left-3 top-1/2 -translate-y-1/2 flex h-8 w-8 items-center justify-center rounded-lg bg-white/90 text-slate-700 shadow hover:bg-white"
                      >
                        <ChevronLeft className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          setActiveImageIdx((i) => (i + 1) % drawerImages.length)
                        }
                        className="absolute right-3 top-1/2 -translate-y-1/2 flex h-8 w-8 items-center justify-center rounded-lg bg-white/90 text-slate-700 shadow hover:bg-white"
                      >
                        <ChevronRight className="h-4 w-4" />
                      </button>
                    </>
                  )}

                  {activeImage && (
                    <button
                      type="button"
                      onClick={() => setLightboxOpen(true)}
                      className="absolute bottom-3 right-3 inline-flex items-center gap-1.5 rounded-lg bg-black/70 px-2.5 py-1.5 text-[11px] font-medium text-white hover:bg-black/85"
                    >
                      <Maximize2 className="h-3.5 w-3.5" /> Full View
                    </button>
                  )}
                </div>

                {/* Thumbnails Strip */}
                {drawerImages.length > 0 && (
                  <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
                    {drawerImages.map((img, idx) => (
                      <button
                        key={img.id}
                        type="button"
                        onClick={() => setActiveImageIdx(idx)}
                        className={`h-16 w-24 shrink-0 overflow-hidden rounded-lg border-2 transition-all ${
                          idx === activeImageIdx
                            ? "border-blue-600 ring-2 ring-blue-100"
                            : "border-slate-200 opacity-75 hover:opacity-100"
                        }`}
                      >
                        <img
                          src={img.public_url}
                          alt={img.alt_text || "Vehicle thumbnail"}
                          className="h-full w-full object-cover"
                        />
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Title + Price + StockID */}
              <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-100 pb-4">
                <div>
                  <h3 className="text-lg font-semibold text-slate-900">
                    {inspectVehicle.model_year} {inspectVehicle.make} {inspectVehicle.model}{" "}
                    {inspectVehicle.variant || ""}
                  </h3>
                  <div className="mt-1.5 flex items-center gap-2 text-xs text-slate-500">
                    <span>StockID:</span>
                    <span className="font-mono font-medium text-slate-800">
                      {inspectVehicle.stock_number}
                    </span>
                    <button
                      type="button"
                      onClick={() => copyStockId(inspectVehicle.stock_number)}
                      className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-slate-500 hover:bg-slate-100 hover:text-slate-800"
                      title="Copy Stock ID"
                    >
                      {copiedStock ? (
                        <Check className="h-3.5 w-3.5 text-emerald-600" />
                      ) : (
                        <Copy className="h-3.5 w-3.5" />
                      )}
                    </button>
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-xl font-bold text-slate-900 tabular-nums">
                    ${Number(inspectVehicle.price).toLocaleString()}
                  </div>
                  <div className="mt-1 flex items-center justify-end gap-1.5">
                    <span
                      className={
                        getStatusBadge(inspectVehicle.status, inspectVehicle.is_available).className
                      }
                    >
                      {getStatusBadge(inspectVehicle.status, inspectVehicle.is_available).label}
                    </span>
                  </div>
                </div>
              </div>

              {/* Car Stats & Equipment Grid (Reference 3-column grid) */}
              <div>
                <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Car Stats &amp; Equipment
                </h4>
                <div className="grid grid-cols-2 gap-4 rounded-xl border border-slate-200 bg-slate-50/50 p-4 sm:grid-cols-3 text-xs">
                  <div>
                    <div className="text-[11px] text-slate-400">Make / Brand</div>
                    <div className="mt-0.5 font-semibold text-slate-900">{inspectVehicle.make}</div>
                  </div>
                  <div>
                    <div className="text-[11px] text-slate-400">Model</div>
                    <div className="mt-0.5 font-semibold text-slate-900">{inspectVehicle.model}</div>
                  </div>
                  <div>
                    <div className="text-[11px] text-slate-400">Model Year</div>
                    <div className="mt-0.5 font-semibold text-slate-900">{inspectVehicle.model_year}</div>
                  </div>
                  <div>
                    <div className="text-[11px] text-slate-400">Variant</div>
                    <div className="mt-0.5 font-semibold text-slate-900">
                      {inspectVehicle.variant || "Standard"}
                    </div>
                  </div>
                  <div>
                    <div className="text-[11px] text-slate-400">Test Drive</div>
                    <div className="mt-0.5 font-semibold text-slate-900">
                      {inspectVehicle.test_drive_enabled ? "Enabled" : "Disabled"}
                    </div>
                  </div>
                  <div>
                    <div className="text-[11px] text-slate-400">Gallery Photos</div>
                    <div className="mt-0.5 font-semibold text-slate-900">
                      {drawerImages.length} uploaded
                    </div>
                  </div>
                </div>
              </div>

              {inspectVehicle.description && (
                <div>
                  <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Description &amp; Notes
                  </h4>
                  <p className="rounded-xl border border-slate-200 bg-white p-3.5 text-xs leading-relaxed text-slate-700 whitespace-pre-wrap">
                    {inspectVehicle.description}
                  </p>
                </div>
              )}

              {/* Staff Controls: Photo Manager & Status History */}
              {isStaff && (
                <div className="space-y-5 border-t border-slate-200 pt-5">
                  {/* Photo Upload & Reorder */}
                  <div>
                    <h4 className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
                      Manage Vehicle Photos
                    </h4>
                    <form onSubmit={handleUploadImage} className="flex flex-wrap items-center gap-2">
                      <input
                        type="file"
                        accept="image/*"
                        onChange={(e) => setImageFile(e.target.files?.[0] ?? null)}
                        className="crm-input flex-1 text-xs"
                      />
                      <button
                        type="submit"
                        disabled={!imageFile || imageBusy}
                        className="crm-btn-secondary text-xs"
                      >
                        <Upload className="h-3.5 w-3.5" />
                        {imageBusy ? "Uploading..." : "Upload"}
                      </button>
                    </form>

                    {drawerImages.length > 0 && (
                      <div className="mt-3 space-y-1.5">
                        {drawerImages.map((img, idx) => (
                          <div
                            key={img.id}
                            className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs"
                          >
                            <span className="font-medium text-slate-700">
                              Photo #{idx + 1} {idx === 0 ? "(Primary)" : ""}
                            </span>
                            <div className="flex items-center gap-1">
                              <button
                                type="button"
                                disabled={idx === 0 || imageBusy}
                                onClick={() => void updateImage(img, { position: idx - 1 })}
                                className="rounded p-1 text-slate-500 hover:bg-white disabled:opacity-30"
                                title="Move up"
                              >
                                <ArrowUp className="h-3.5 w-3.5" />
                              </button>
                              <button
                                type="button"
                                disabled={idx === drawerImages.length - 1 || imageBusy}
                                onClick={() => void updateImage(img, { position: idx + 1 })}
                                className="rounded p-1 text-slate-500 hover:bg-white disabled:opacity-30"
                                title="Move down"
                              >
                                <ArrowDown className="h-3.5 w-3.5" />
                              </button>
                              <button
                                type="button"
                                disabled={imageBusy}
                                onClick={() => void deleteImage(img)}
                                className="rounded p-1 text-rose-600 hover:bg-rose-50"
                                title="Delete photo"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Lifecycle Status Transition */}
                  <div>
                    <h4 className="mb-2.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
                      <History className="h-3.5 w-3.5" /> Lifecycle Status &amp; History
                    </h4>
                    <form onSubmit={handleStatusTransition} className="grid gap-2 sm:grid-cols-3">
                      <select
                        value={transitionStatus}
                        onChange={(e) => setTransitionStatus(e.target.value)}
                        className="crm-select text-xs"
                      >
                        <option value="available">Available</option>
                        <option value="in_transit">In Transit</option>
                        <option value="reserved">Reserved</option>
                        <option value="sold">Sold</option>
                        <option value="unavailable">Unavailable</option>
                      </select>
                      <input
                        type="text"
                        value={transitionNotes}
                        onChange={(e) => setTransitionNotes(e.target.value)}
                        placeholder="Transition note..."
                        className="crm-input text-xs"
                      />
                      <button type="submit" disabled={transitionBusy} className="crm-btn-primary text-xs">
                        {transitionBusy ? "Saving..." : "Update Status"}
                      </button>
                    </form>

                    {loadingHistory ? (
                      <p className="mt-2 text-xs text-slate-400">Loading history...</p>
                    ) : statusHistory.length > 0 ? (
                      <div className="mt-3 space-y-1.5 max-h-40 overflow-y-auto">
                        {statusHistory.map((h) => (
                          <div
                            key={h.id}
                            className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-[11px]"
                          >
                            <div>
                              <span className="font-semibold text-slate-800">
                                {h.previous_status} → {h.new_status}
                              </span>
                              {h.notes && <span className="ml-2 text-slate-500">({h.notes})</span>}
                            </div>
                            <span className="text-slate-400">
                              {new Date(h.created_at).toLocaleDateString()}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>
              )}
            </div>

            {/* Drawer Footer */}
            <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50 px-6 py-3.5">
              {inspectVehicle.test_drive_enabled ? (
                <Link
                  href={`/bookings?vehicle=${inspectVehicle.id}`}
                  className="crm-btn-primary text-xs"
                >
                  <Calendar className="h-3.5 w-3.5" /> Book Test Drive
                </Link>
              ) : (
                <span className="text-xs text-slate-400">Test drive disabled</span>
              )}
              <button
                type="button"
                onClick={() => setInspectVehicle(null)}
                className="crm-btn-secondary text-xs"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Full-Screen Image Lightbox */}
      {lightboxOpen && inspectVehicle && activeImage && (
        <div
          className="fixed inset-0 z-[60] flex flex-col bg-black/95 text-white"
          onClick={() => setLightboxOpen(false)}
        >
          <div
            className="flex items-center justify-between px-6 py-4 border-b border-white/10"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-sm font-medium">
              {inspectVehicle.model_year} {inspectVehicle.make} {inspectVehicle.model} · Photo{" "}
              {activeImageIdx + 1} of {drawerImages.length}
            </div>
            <button
              type="button"
              onClick={() => setLightboxOpen(false)}
              className="rounded-lg p-2 text-white/80 hover:bg-white/10 hover:text-white"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <div
            className="relative flex flex-1 items-center justify-center p-4 sm:p-10"
            onClick={(e) => e.stopPropagation()}
          >
            <img
              src={activeImage.public_url}
              alt={activeImage.alt_text || "Vehicle full view"}
              className="max-h-[82vh] max-w-full rounded-lg object-contain shadow-2xl"
            />

            {drawerImages.length > 1 && (
              <>
                <button
                  type="button"
                  onClick={() =>
                    setActiveImageIdx((i) => (i - 1 + drawerImages.length) % drawerImages.length)
                  }
                  className="absolute left-4 top-1/2 -translate-y-1/2 flex h-11 w-11 items-center justify-center rounded-full bg-white/15 text-white hover:bg-white/25"
                >
                  <ChevronLeft className="h-6 w-6" />
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setActiveImageIdx((i) => (i + 1) % drawerImages.length)
                  }
                  className="absolute right-4 top-1/2 -translate-y-1/2 flex h-11 w-11 items-center justify-center rounded-full bg-white/15 text-white hover:bg-white/25"
                >
                  <ChevronRight className="h-6 w-6" />
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </Shell>
  );
}
