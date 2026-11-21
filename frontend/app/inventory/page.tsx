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
} from "lucide-react";
import Shell from "../components/Shell";
import { useAuth } from "../providers";
import { api } from "../api";
import { MOCK_BRANDS, MOCK_VEHICLES, Vehicle, Brand } from "../lib/mockData";

export default function InventoryPage() {
  const { user, activeDealershipId } = useAuth();
  const [vehicles, setVehicles] = useState<Vehicle[]>(MOCK_VEHICLES);
  const [brands, setBrands] = useState<Brand[]>(MOCK_BRANDS);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedBrand, setSelectedBrand] = useState<number | "all">("all");
  const [availabilityFilter, setAvailabilityFilter] = useState<"all" | "available" | "unavailable">("all");
  const [viewMode, setViewMode] = useState<"table" | "grid">("table");

  // Modal states
  const [showAddModal, setShowAddModal] = useState(false);
  const [inspectVehicle, setInspectVehicle] = useState<Vehicle | null>(null);

  // New vehicle form state
  const [newVehicle, setNewVehicle] = useState({
    brand_id: 1,
    model: "",
    model_year: 2024,
    variant: "",
    description: "",
    price: 35000,
    stock_number: `STK-${Date.now().toString().slice(-4)}`,
    test_drive_enabled: true,
  });

  const isStaff = user && user.role !== "customer";

  useEffect(() => {
    api<Vehicle[]>(`/dealerships/${activeDealershipId}/vehicles`)
      .then((data) => {
        if (Array.isArray(data) && data.length) setVehicles(data);
      })
      .catch(() => {});

    api<Brand[]>(`/dealerships/${activeDealershipId}/brands`)
      .then((data) => {
        if (Array.isArray(data) && data.length) setBrands(data);
      })
      .catch(() => {});
  }, [activeDealershipId]);

  // Filtering
  const filteredVehicles = vehicles.filter((v) => {
    const matchesSearch =
      v.model.toLowerCase().includes(searchTerm.toLowerCase()) ||
      v.make.toLowerCase().includes(searchTerm.toLowerCase()) ||
      v.stock_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (v.variant && v.variant.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesBrand = selectedBrand === "all" || v.brand_id === selectedBrand;
    const matchesAvailability =
      availabilityFilter === "all" ||
      (availabilityFilter === "available" && v.is_available) ||
      (availabilityFilter === "unavailable" && !v.is_available);

    return matchesSearch && matchesBrand && matchesAvailability;
  });

  function handleCreateVehicle(e: React.FormEvent) {
    e.preventDefault();
    const brand = brands.find((b) => b.id === Number(newVehicle.brand_id)) || brands[0];
    const created: Vehicle = {
      id: Math.floor(Math.random() * 9000) + 1000,
      dealership_id: activeDealershipId,
      brand_id: Number(newVehicle.brand_id),
      make: brand.name,
      model: newVehicle.model,
      model_year: Number(newVehicle.model_year),
      variant: newVehicle.variant,
      description: newVehicle.description,
      price: Number(newVehicle.price),
      stock_number: newVehicle.stock_number,
      is_available: true,
      test_drive_enabled: newVehicle.test_drive_enabled,
      images: [
        {
          id: 99,
          vehicle_id: 1000,
          public_url: "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?auto=format&fit=crop&w=800&q=80",
          media_type: "image/jpeg",
          alt_text: newVehicle.model,
          position: 0,
        },
      ],
    };

    setVehicles([created, ...vehicles]);
    setShowAddModal(false);
    setNewVehicle({
      brand_id: 1,
      model: "",
      model_year: 2024,
      variant: "",
      description: "",
      price: 35000,
      stock_number: `STK-${Date.now().toString().slice(-4)}`,
      test_drive_enabled: true,
    });
  }

  function toggleAvailability(id: number) {
    setVehicles(
      vehicles.map((v) => (v.id === id ? { ...v, is_available: !v.is_available } : v))
    );
  }

  function toggleTestDrive(id: number) {
    setVehicles(
      vehicles.map((v) => (v.id === id ? { ...v, test_drive_enabled: !v.test_drive_enabled } : v))
    );
  }

  return (
    <Shell>
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="h-2 w-2 rounded-full bg-blue-500" />
            <p className="text-xs font-bold uppercase tracking-wider text-blue-400">
              ERP Fleet Master
            </p>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Vehicle Inventory</h1>
          <p className="text-xs text-slate-400">
            {filteredVehicles.length} vehicles matching criteria • Multi-image galleries & test-drive controls
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
              <option value="available">Available Only</option>
              <option value="unavailable">Reserved / Unavailable</option>
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
                <th>Availability</th>
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
                      onClick={() => isStaff && toggleAvailability(v.id)}
                      disabled={!isStaff}
                      className={`badge cursor-pointer ${
                        v.is_available ? "badge-success" : "badge-neutral"
                      }`}
                    >
                      {v.is_available ? "In Stock" : "Reserved"}
                    </button>
                  </td>
                  <td>
                    <button
                      onClick={() => isStaff && toggleTestDrive(v.id)}
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
                        onClick={() => setInspectVehicle(v)}
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
                    className={`badge ${v.is_available ? "badge-success" : "badge-danger"} bg-slate-900/80 backdrop-blur-md`}
                  >
                    {v.is_available ? "In Stock" : "Unavailable"}
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
                      onClick={() => setInspectVehicle(v)}
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
                      <div key={img.id} className="relative rounded-lg overflow-hidden border border-slate-700 h-32 bg-slate-800">
                        <img src={img.public_url} alt={img.alt_text || "Vehicle image"} className="h-full w-full object-cover" />
                        <span className="absolute bottom-1.5 left-1.5 bg-slate-900/80 px-1.5 py-0.5 rounded text-[10px] text-slate-300">
                          Pos #{img.position}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
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
                  <span className="text-slate-400">Fleet Availability:</span>
                  <p className="font-semibold text-emerald-400">{inspectVehicle.is_available ? "In Stock" : "Unavailable"}</p>
                </div>
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
