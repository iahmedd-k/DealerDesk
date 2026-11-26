"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Calendar,
  Clock,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Plus,
  X,
} from "lucide-react";
import Shell from "../components/Shell";
import { useAuth } from "../providers";
import { api } from "../api";
import type { TestDriveBooking, TestDriveSlot, Vehicle } from "../lib/types";

function getBookingBadge(status: string) {
  switch (status) {
    case "booked":
      return "crm-badge crm-badge-success";
    case "cancelled":
      return "crm-badge crm-badge-danger";
    case "completed":
      return "crm-badge crm-badge-info";
    default:
      return "crm-badge crm-badge-neutral";
  }
}

function BookingsInner() {
  const searchParams = useSearchParams();
  const { user, authReady, activeDealershipId } = useAuth();
  const preselectedVehicleId = searchParams.get("vehicle");

  const [activeTab, setActiveTab] = useState<"slots" | "bookings">("slots");
  const [slots, setSlots] = useState<TestDriveSlot[]>([]);
  const [bookings, setBookings] = useState<TestDriveBooking[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [loading, setLoading] = useState(true);

  const [bookingSlot, setBookingSlot] = useState<TestDriveSlot | null>(null);
  const [confirmedCheck, setConfirmedCheck] = useState(true);

  const [actionBooking, setActionBooking] = useState<{
    booking: TestDriveBooking;
    type: "cancel" | "reschedule";
  } | null>(null);
  const [verificationEmail, setVerificationEmail] = useState("");
  const [cancelReason, setCancelReason] = useState("");
  const [newSlotId, setNewSlotId] = useState<number | "">("");

  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const [showCreateSlotModal, setShowCreateSlotModal] = useState(false);
  const [newSlotVehicleId, setNewSlotVehicleId] = useState<number | "">("");
  const [newSlotStart, setNewSlotStart] = useState("");
  const [newSlotEnd, setNewSlotEnd] = useState("");
  const [newSlotCapacity, setNewSlotCapacity] = useState(1);

  const canManageSlots =
    user?.role === "dealership_admin" || user?.role === "manager";

  useEffect(() => {
    if (!authReady || !user) return;
    if (!activeDealershipId) {
      setLoading(false);
      setErrorMsg("Select a dealership workspace to view test drives.");
      return;
    }

    let cancelled = false;
    setLoading(true);
    setErrorMsg("");
    Promise.all([
      api<TestDriveSlot[]>(`/dealerships/${activeDealershipId}/test-drive-slots?include_inactive=true`),
      api<TestDriveBooking[]>(`/dealerships/${activeDealershipId}/test-drive-bookings`),
      api<Vehicle[] | Vehicle>(
        user.role === "customer"
          ? `/dealerships/${activeDealershipId}/vehicles/public`
          : `/dealerships/${activeDealershipId}/vehicles`,
      ).then((result) => (Array.isArray(result) ? result : [result])),
    ])
      .then(([nextSlots, nextBookings, nextVehicles]) => {
        if (cancelled) return;
        setSlots(nextSlots);
        setBookings(nextBookings);
        setVehicles(nextVehicles);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setErrorMsg(cause instanceof Error ? cause.message : "Could not load test drives.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [authReady, user, activeDealershipId]);

  async function handleBookSlot(e: React.FormEvent) {
    e.preventDefault();
    if (!bookingSlot || !activeDealershipId) return;
    setErrorMsg("");
    try {
      const created = await api<TestDriveBooking>(
        `/dealerships/${activeDealershipId}/test-drive-slots/${bookingSlot.id}/bookings`,
        { method: "POST", body: JSON.stringify({ confirmed: confirmedCheck }) },
      );
      setBookings((current) => [created, ...current]);
      setSlots((current) =>
        current.map((slot) =>
          slot.id === bookingSlot.id ? { ...slot, booked_count: slot.booked_count + 1 } : slot,
        ),
      );
      const vehicle = vehicles.find((item) => item.id === bookingSlot.vehicle_id);
      setBookingSlot(null);
      setSuccessMsg(
        `Test drive confirmed${vehicle ? ` for ${vehicle.model_year} ${vehicle.make} ${vehicle.model}` : ""}.`,
      );
    } catch (cause) {
      setErrorMsg(cause instanceof Error ? cause.message : "Could not book this test drive.");
    }
  }

  async function handleCancelBooking(e: React.FormEvent) {
    e.preventDefault();
    if (!actionBooking || !activeDealershipId) return;
    setErrorMsg("");
    try {
      await api<void>(
        `/dealerships/${activeDealershipId}/test-drive-bookings/${actionBooking.booking.id}/cancel`,
        {
          method: "POST",
          body: JSON.stringify({
            verification_email: verificationEmail || undefined,
            reason: cancelReason || undefined,
          }),
        },
      );
      setBookings((current) =>
        current.map((booking) =>
          booking.id === actionBooking.booking.id
            ? { ...booking, status: "cancelled", cancelled_at: new Date().toISOString() }
            : booking,
        ),
      );
      setActionBooking(null);
      setCancelReason("");
      setVerificationEmail("");
      setSuccessMsg("Test drive cancelled.");
    } catch (cause) {
      setErrorMsg(cause instanceof Error ? cause.message : "Could not cancel this test drive.");
    }
  }

  async function handleRescheduleBooking(e: React.FormEvent) {
    e.preventDefault();
    if (!actionBooking || !newSlotId || !activeDealershipId) return;
    setErrorMsg("");
    try {
      const updated = await api<TestDriveBooking>(
        `/dealerships/${activeDealershipId}/test-drive-bookings/${actionBooking.booking.id}/reschedule`,
        {
          method: "POST",
          body: JSON.stringify({
            new_slot_id: Number(newSlotId),
            verification_email: verificationEmail || undefined,
            confirmed: true,
          }),
        },
      );
      setBookings((current) =>
        current.map((booking) => (booking.id === updated.id ? updated : booking)),
      );
      setActionBooking(null);
      setNewSlotId("");
      setVerificationEmail("");
      setSuccessMsg("Test drive rescheduled.");
    } catch (cause) {
      setErrorMsg(cause instanceof Error ? cause.message : "Could not reschedule this test drive.");
    }
  }

  async function handleCreateSlot(e: React.FormEvent) {
    e.preventDefault();
    if (!activeDealershipId || !newSlotVehicleId || !newSlotStart || !newSlotEnd) return;
    setErrorMsg("");
    setSuccessMsg("");
    try {
      const created = await api<TestDriveSlot>(
        `/dealerships/${activeDealershipId}/test-drive-slots`,
        {
          method: "POST",
          body: JSON.stringify({
            vehicle_id: Number(newSlotVehicleId),
            starts_at: new Date(newSlotStart).toISOString(),
            ends_at: new Date(newSlotEnd).toISOString(),
            capacity: Number(newSlotCapacity),
          }),
        },
      );
      setSlots((current) => [created, ...current]);
      setShowCreateSlotModal(false);
      setNewSlotVehicleId("");
      setNewSlotStart("");
      setNewSlotEnd("");
      setNewSlotCapacity(1);
      setSuccessMsg("Custom test-drive slot created.");
    } catch (cause) {
      setErrorMsg(cause instanceof Error ? cause.message : "Could not create slot.");
    }
  }

  async function handleIncreaseCapacity(slot: TestDriveSlot) {
    if (!activeDealershipId) return;
    setErrorMsg("");
    setSuccessMsg("");
    try {
      const updated = await api<TestDriveSlot>(
        `/dealerships/${activeDealershipId}/test-drive-slots/${slot.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({ capacity: slot.capacity + 1 }),
        },
      );
      setSlots((current) => current.map((s) => (s.id === updated.id ? updated : s)));
      setSuccessMsg(`Increased slot #${slot.id} capacity to ${updated.capacity}.`);
    } catch (cause) {
      setErrorMsg(cause instanceof Error ? cause.message : "Could not update slot capacity.");
    }
  }

  const filteredSlots = slots.filter((slot) => {
    const remaining = slot.remaining_capacity ?? slot.capacity - slot.booked_count;
    return (
      slot.is_active &&
      (canManageSlots || remaining > 0) &&
      new Date(slot.starts_at).getTime() > Date.now() &&
      (!preselectedVehicleId || String(slot.vehicle_id) === preselectedVehicleId)
    );
  });

  return (
    <Shell>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-medium tracking-tight text-[#171717]">
            Test-Drive Schedule & Bookings
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Live slot capacity, overlap checks, and verified booking rescheduling or cancellation
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {canManageSlots && (
            <>
              <button
                type="button"
                onClick={() => setShowCreateSlotModal(true)}
                className="crm-btn-primary text-xs"
              >
                <Plus className="h-3.5 w-3.5" />
                Create Slot
              </button>
              <Link href="/operations" className="crm-btn-secondary text-xs">
                Generate Slots
              </Link>
            </>
          )}
          <div className="inline-flex items-center rounded-lg border border-slate-200 bg-white p-1">
          <button
            type="button"
            onClick={() => setActiveTab("slots")}
            className={`rounded-md px-3.5 py-1.5 text-xs font-semibold transition-colors ${activeTab === "slots"
              ? "bg-blue-600 text-white"
              : "text-slate-600 hover:text-slate-900"
              }`}
          >
            Available Slots ({filteredSlots.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("bookings")}
            className={`rounded-md px-3.5 py-1.5 text-xs font-semibold transition-colors ${activeTab === "bookings"
              ? "bg-blue-600 text-white"
              : "text-slate-600 hover:text-slate-900"
              }`}
          >
            Bookings ({bookings.length})
          </button>
          </div>
        </div>
      </div>

      {successMsg && (
        <div className="mb-5 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs font-medium text-emerald-700">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div className="mb-5 flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-xs font-medium text-rose-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {preselectedVehicleId && (
        <div className="mb-5 flex items-center justify-between rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-xs font-medium text-blue-700">
          <span>Filtering test-drive slots for Vehicle #{preselectedVehicleId}</span>
          <Link href="/bookings" className="font-semibold underline hover:text-blue-900">
            Clear Filter
          </Link>
        </div>
      )}

      {loading ? (
        <div className="crm-card p-12 text-center text-sm text-slate-500">
          Loading test-drive schedule...
        </div>
      ) : activeTab === "slots" ? (
        filteredSlots.length === 0 ? (
          <div className="crm-card p-12 text-center">
            <Calendar className="h-10 w-10 text-slate-300 mx-auto mb-3" />
            <p className="text-sm font-semibold text-slate-900">No upcoming slots available</p>
            <p className="text-xs text-slate-500 mt-1">
              Staff can generate upcoming slots from the Operations & Outbox console.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredSlots.map((slot) => {
              const matchedVehicle = vehicles.find((v) => v.id === slot.vehicle_id);
              const remaining = slot.remaining_capacity ?? slot.capacity - slot.booked_count;
              const isAvailable = remaining > 0 && slot.is_active;
              const pct = Math.min(100, Math.round((slot.booked_count / Math.max(1, slot.capacity)) * 100));

              return (
                <div key={slot.id} className="crm-card p-5 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
                        <Calendar className="h-3.5 w-3.5 text-blue-600" />
                        {new Date(slot.starts_at).toLocaleDateString([], {
                          weekday: "short",
                          month: "short",
                          day: "numeric",
                        })}
                      </span>
                      <span
                        className={`crm-badge ${isAvailable ? "crm-badge-success" : "crm-badge-neutral"
                          }`}
                      >
                        {isAvailable ? `${remaining} Left` : "Full"}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 text-sm font-medium text-[#171717] mb-3">
                      <Clock className="h-4 w-4 text-slate-400" />
                      <span>
                        {new Date(slot.starts_at).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}{" "}
                        -{" "}
                        {new Date(slot.ends_at).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    </div>

                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-2.5 mb-3 text-xs">
                      <div className="text-[11px] text-slate-500">Assigned Vehicle</div>
                      <div className="font-semibold text-slate-900">
                        {matchedVehicle
                          ? `${matchedVehicle.model_year} ${matchedVehicle.make} ${matchedVehicle.model}`
                          : `Vehicle #${slot.vehicle_id}`}
                      </div>
                    </div>

                    <div className="space-y-1.5 mb-4">
                      <div className="flex justify-between text-[11px] text-slate-500">
                        <span>Slot Utilization</span>
                        <span className="font-mono text-slate-700">
                          {slot.booked_count}/{slot.capacity}
                        </span>
                      </div>
                      <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-blue-600 transition-colors"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={!isAvailable}
                      onClick={() => {
                        setBookingSlot(slot);
                        setConfirmedCheck(true);
                      }}
                      className="crm-btn-primary flex-1"
                    >
                      {isAvailable ? "Book Test Drive" : "Slot Full"}
                    </button>
                    {canManageSlots && (
                      <button
                        type="button"
                        onClick={() => void handleIncreaseCapacity(slot)}
                        className="crm-btn-secondary px-2.5 text-xs shrink-0"
                        title="Add 1 more spot to this slot"
                      >
                        +1 Spot
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )
      ) : bookings.length === 0 ? (
        <div className="crm-card p-12 text-center">
          <Calendar className="h-10 w-10 text-slate-300 mx-auto mb-3" />
          <p className="text-sm font-semibold text-slate-900">No bookings recorded yet</p>
          <p className="text-xs text-slate-500 mt-1">
            Switch to Available Slots to schedule a new test drive.
          </p>
        </div>
      ) : (
        <div className="crm-table-wrap">
          <table className="crm-table">
            <thead>
              <tr>
                <th>Booking</th>
                <th>Vehicle</th>
                <th>Schedule</th>
                <th>Status</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {bookings.map((booking) => {
                const vehicle = vehicles.find((v) => v.id === booking.vehicle_id);
                const slot = slots.find((s) => s.id === booking.slot_id);
                const startsAt = booking.starts_at || slot?.starts_at;
                return (
                  <tr key={booking.id}>
                    <td>
                      <div className="font-semibold text-slate-900">Booking #{booking.id}</div>
                      <div className="text-xs text-slate-500">
                        {booking.customer_email || `Customer #${booking.customer_id}`}
                      </div>
                    </td>
                    <td className="text-slate-700">
                      {vehicle
                        ? `${vehicle.model_year} ${vehicle.make} ${vehicle.model}`
                        : `Vehicle #${booking.vehicle_id}`}
                    </td>
                    <td className="text-xs text-slate-600">
                      {startsAt ? new Date(startsAt).toLocaleString() : `Slot #${booking.slot_id}`}
                    </td>
                    <td>
                      <span className={getBookingBadge(booking.status)}>{booking.status}</span>
                    </td>
                    <td className="text-right">
                      {booking.status === "booked" && (
                        <div className="inline-flex items-center gap-1.5">
                          <button
                            type="button"
                            onClick={() =>
                              setActionBooking({ booking, type: "reschedule" })
                            }
                            className="crm-btn-secondary py-1.5 px-2.5 text-xs"
                          >
                            <RefreshCw className="h-3.5 w-3.5" />
                            Reschedule
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              setActionBooking({ booking, type: "cancel" })
                            }
                            className="crm-btn-danger py-1.5 px-2.5 text-xs"
                          >
                            Cancel
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Confirm Booking Modal */}
      {bookingSlot && (
        <div className="crm-modal-overlay">
          <div className="crm-modal max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-medium text-[#171717]">Confirm Test Drive</h2>
              <button
                type="button"
                onClick={() => setBookingSlot(null)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleBookSlot} className="space-y-4">
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs space-y-1">
                <div className="font-semibold text-slate-900">
                  {new Date(bookingSlot.starts_at).toLocaleString()}
                </div>
                <div className="text-slate-600">
                  Remaining capacity:{" "}
                  {bookingSlot.remaining_capacity ?? bookingSlot.capacity - bookingSlot.booked_count}
                </div>
              </div>
              <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={confirmedCheck}
                  onChange={(e) => setConfirmedCheck(e.target.checked)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                />
                Confirm booking and send appointment notification
              </label>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setBookingSlot(null)}
                  className="crm-btn-secondary"
                >
                  Cancel
                </button>
                <button type="submit" className="crm-btn-primary">
                  Confirm Booking
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Cancel / Reschedule Modal */}
      {actionBooking && (
        <div className="crm-modal-overlay">
          <div className="crm-modal max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-medium text-[#171717]">
                {actionBooking.type === "cancel" ? "Cancel Booking" : "Reschedule Booking"}
              </h2>
              <button
                type="button"
                onClick={() => setActionBooking(null)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {actionBooking.type === "cancel" ? (
              <form onSubmit={handleCancelBooking} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Verification Email (if required)
                  </label>
                  <input
                    type="email"
                    placeholder="customer@example.com"
                    value={verificationEmail}
                    onChange={(e) => setVerificationEmail(e.target.value)}
                    className="crm-input"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Cancellation Reason
                  </label>
                  <textarea
                    rows={3}
                    placeholder="Optional reason..."
                    value={cancelReason}
                    onChange={(e) => setCancelReason(e.target.value)}
                    className="crm-textarea"
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setActionBooking(null)}
                    className="crm-btn-secondary"
                  >
                    Keep Booking
                  </button>
                  <button type="submit" className="crm-btn-danger">
                    Confirm Cancel
                  </button>
                </div>
              </form>
            ) : (
              <form onSubmit={handleRescheduleBooking} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    New Time Slot
                  </label>
                  <select
                    required
                    value={newSlotId}
                    onChange={(e) => setNewSlotId(e.target.value ? Number(e.target.value) : "")}
                    className="crm-select"
                  >
                    <option value="">Select an available slot...</option>
                    {filteredSlots
                      .filter((slot) => (slot.remaining_capacity ?? slot.capacity - slot.booked_count) > 0)
                      .map((slot) => (
                        <option key={slot.id} value={slot.id}>
                          Slot #{slot.id} · {new Date(slot.starts_at).toLocaleString()}
                        </option>
                      ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Verification Email (if required)
                  </label>
                  <input
                    type="email"
                    placeholder="customer@example.com"
                    value={verificationEmail}
                    onChange={(e) => setVerificationEmail(e.target.value)}
                    className="crm-input"
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setActionBooking(null)}
                    className="crm-btn-secondary"
                  >
                    Cancel
                  </button>
                  <button type="submit" className="crm-btn-primary">
                    Confirm Reschedule
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Create Custom Slot Modal */}
      {showCreateSlotModal && (
        <div className="crm-modal-overlay">
          <div className="crm-modal max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-medium text-[#171717]">Create Test-Drive Slot</h2>
                <p className="text-xs text-slate-500">
                  Add a custom slot for a specific test-drive-enabled vehicle.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowCreateSlotModal(false)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleCreateSlot} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Vehicle
                </label>
                <select
                  required
                  value={newSlotVehicleId}
                  onChange={(e) =>
                    setNewSlotVehicleId(e.target.value ? Number(e.target.value) : "")
                  }
                  className="crm-select"
                >
                  <option value="">Select an available vehicle...</option>
                  {vehicles
                    .filter((v) => v.is_available && v.test_drive_enabled)
                    .map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.model_year} {v.make} {v.model} (#{v.stock_number})
                      </option>
                    ))}
                </select>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Starts At
                  </label>
                  <input
                    type="datetime-local"
                    required
                    value={newSlotStart}
                    onChange={(e) => setNewSlotStart(e.target.value)}
                    className="crm-input"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Ends At
                  </label>
                  <input
                    type="datetime-local"
                    required
                    value={newSlotEnd}
                    onChange={(e) => setNewSlotEnd(e.target.value)}
                    className="crm-input"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Capacity (Spots)
                </label>
                <input
                  type="number"
                  min={1}
                  max={20}
                  required
                  value={newSlotCapacity}
                  onChange={(e) => setNewSlotCapacity(Number(e.target.value))}
                  className="crm-input"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateSlotModal(false)}
                  className="crm-btn-secondary"
                >
                  Cancel
                </button>
                <button type="submit" className="crm-btn-primary">
                  Create Slot
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Shell>
  );
}

export default function BookingsPage() {
  return (
    <Suspense
      fallback={
        <Shell>
          <div className="crm-card p-12 text-center text-sm text-slate-500">
            Loading test-drive schedule...
          </div>
        </Shell>
      }
    >
      <BookingsInner />
    </Suspense>
  );
}
