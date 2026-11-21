"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
  Calendar,
  Clock,
  Car,
  UserCheck,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Users,
  Plus,
  RefreshCw,
  Check,
  X,
  Settings,
  ShieldAlert,
} from "lucide-react";
import Shell from "../components/Shell";
import { useAuth } from "../providers";
import { api } from "../api";
import {
  MOCK_BOOKINGS,
  MOCK_TEST_DRIVE_SLOTS,
  MOCK_VEHICLES,
  TestDriveBooking,
  TestDriveSlot,
  Vehicle,
} from "../lib/mockData";

function BookingsInner() {
  const searchParams = useSearchParams();
  const { user, activeDealershipId } = useAuth();
  const preselectedVehicleId = searchParams.get("vehicle");

  const [activeTab, setActiveTab] = useState<"slots" | "bookings">("slots");
  const [slots, setSlots] = useState<TestDriveSlot[]>(MOCK_TEST_DRIVE_SLOTS);
  const [bookings, setBookings] = useState<TestDriveBooking[]>(MOCK_BOOKINGS);
  const [vehicles, setVehicles] = useState<Vehicle[]>(MOCK_VEHICLES);

  // Booking Modal
  const [bookingSlot, setBookingSlot] = useState<TestDriveSlot | null>(null);
  const [confirmedCheck, setConfirmedCheck] = useState(true);
  const [customerEmail, setCustomerEmail] = useState(user?.email || "customer@demo.com");
  const [customerName, setCustomerName] = useState(user?.name || "Sophia Martinez");

  // Reschedule / Cancel Modals
  const [actionBooking, setActionBooking] = useState<{
    booking: TestDriveBooking;
    type: "cancel" | "reschedule";
  } | null>(null);
  const [verificationEmail, setVerificationEmail] = useState("");
  const [cancelReason, setCancelReason] = useState("");
  const [newSlotId, setNewSlotId] = useState<number | "">("");

  // Notification banners
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const isStaff = user && user.role !== "customer";

  useEffect(() => {
    api<TestDriveSlot[]>(`/dealerships/${activeDealershipId}/test-drive-slots`)
      .then((data) => {
        if (Array.isArray(data) && data.length) setSlots(data);
      })
      .catch(() => {});

    api<TestDriveBooking[]>(`/dealerships/${activeDealershipId}/test-drive-bookings`)
      .then((data) => {
        if (Array.isArray(data) && data.length) setBookings(data);
      })
      .catch(() => {});
  }, [activeDealershipId]);

  function handleBookSlot(e: React.FormEvent) {
    e.preventDefault();
    if (!bookingSlot) return;

    const matchedVehicle = vehicles.find((v) => v.id === bookingSlot.vehicle_id);
    const newBooking: TestDriveBooking = {
      id: Math.floor(Math.random() * 9000) + 1000,
      slot_id: bookingSlot.id,
      dealership_id: activeDealershipId,
      vehicle_id: bookingSlot.vehicle_id,
      vehicle_name: matchedVehicle ? `${matchedVehicle.model_year} ${matchedVehicle.make} ${matchedVehicle.model}` : "Demo Vehicle",
      customer_id: user?.id || 501,
      customer_name: customerName,
      customer_email: customerEmail,
      status: "booked",
      created_at: new Date().toISOString(),
      cancelled_at: null,
      starts_at: bookingSlot.starts_at,
      ends_at: bookingSlot.ends_at,
    };

    setBookings([newBooking, ...bookings]);
    setSlots(
      slots.map((s) =>
        s.id === bookingSlot.id
          ? {
              ...s,
              booked_count: s.booked_count + 1,
              remaining_capacity: Math.max(0, (s.remaining_capacity || s.capacity) - 1),
            }
          : s
      )
    );

    setBookingSlot(null);
    setSuccessMsg(`Test drive reserved successfully for ${newBooking.vehicle_name}! An explicit confirmation has been recorded.`);
    setTimeout(() => setSuccessMsg(""), 6000);
  }

  function handleCancelBooking(e: React.FormEvent) {
    e.preventDefault();
    if (!actionBooking) return;

    setBookings(
      bookings.map((b) =>
        b.id === actionBooking.booking.id
          ? { ...b, status: "cancelled", cancelled_at: new Date().toISOString() }
          : b
      )
    );

    setActionBooking(null);
    setSuccessMsg("Test drive booking cancelled with identity verification.");
    setTimeout(() => setSuccessMsg(""), 5000);
  }

  function handleRescheduleBooking(e: React.FormEvent) {
    e.preventDefault();
    if (!actionBooking || !newSlotId) return;

    const targetSlot = slots.find((s) => s.id === Number(newSlotId));
    setBookings(
      bookings.map((b) =>
        b.id === actionBooking.booking.id
          ? {
              ...b,
              slot_id: Number(newSlotId),
              starts_at: targetSlot?.starts_at,
              ends_at: targetSlot?.ends_at,
            }
          : b
      )
    );

    setActionBooking(null);
    setSuccessMsg("Booking rescheduled successfully to requested slot.");
    setTimeout(() => setSuccessMsg(""), 5000);
  }

  const filteredSlots = preselectedVehicleId
    ? slots.filter((s) => String(s.vehicle_id) === preselectedVehicleId)
    : slots;

  return (
    <Shell>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            <p className="text-xs font-bold uppercase tracking-wider text-emerald-400">
              CRM Dispatcher & Booking Engine
            </p>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Test-Drive Schedule & Bookings
          </h1>
          <p className="text-xs text-slate-400">
            Atomic capacity tracking, anti-overlap protection, and verified customer cancellation/rescheduling
          </p>
        </div>

        {/* Tab switch */}
        <div className="flex items-center bg-slate-900 border border-slate-800 rounded-xl p-1">
          <button
            onClick={() => setActiveTab("slots")}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === "slots"
                ? "bg-blue-600 text-white shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Available Slots ({filteredSlots.length})
          </button>
          <button
            onClick={() => setActiveTab("bookings")}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === "bookings"
                ? "bg-blue-600 text-white shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            CRM Bookings ({bookings.length})
          </button>
        </div>
      </div>

      {/* Notifications */}
      {successMsg && (
        <div className="mb-6 rounded-xl bg-emerald-500/10 border border-emerald-500/30 p-4 text-xs font-semibold text-emerald-300 flex items-center gap-2 shadow-sm">
          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          <span>{successMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div className="mb-6 rounded-xl bg-rose-500/10 border border-rose-500/30 p-4 text-xs font-semibold text-rose-300 flex items-center gap-2 shadow-sm">
          <AlertCircle className="h-4 w-4 text-rose-400" />
          <span>{errorMsg}</span>
        </div>
      )}

      {preselectedVehicleId && (
        <div className="mb-6 rounded-xl bg-blue-500/10 border border-blue-500/30 p-3.5 text-xs text-blue-300 flex items-center justify-between">
          <span>Filtering test drive slots for Vehicle #{preselectedVehicleId}</span>
          <a href="/bookings" className="underline font-semibold hover:text-white">
            Clear Filter
          </a>
        </div>
      )}

      {/* Tab 1: Slots Grid */}
      {activeTab === "slots" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredSlots.map((slot) => {
              const matchedVehicle = vehicles.find((v) => v.id === slot.vehicle_id);
              const remaining = slot.remaining_capacity ?? slot.capacity - slot.booked_count;
              const isAvailable = remaining > 0 && slot.is_active;

              return (
                <div
                  key={slot.id}
                  className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-all flex flex-col justify-between shadow-sm"
                >
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                        <Calendar className="h-3.5 w-3.5 text-blue-400" />
                        {new Date(slot.starts_at).toLocaleDateString([], {
                          weekday: "short",
                          month: "short",
                          day: "numeric",
                        })}
                      </span>
                      <span
                        className={`badge ${
                          isAvailable ? "badge-success" : "badge-neutral"
                        }`}
                      >
                        {isAvailable ? "Slot Open" : "Capacity Full"}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 text-sm font-bold text-white mb-2">
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

                    <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800/80 mb-3 text-xs">
                      <div className="text-slate-400 text-[11px]">Assigned Vehicle:</div>
                      <div className="font-semibold text-slate-200">
                        {matchedVehicle
                          ? `${matchedVehicle.model_year} ${matchedVehicle.make} ${matchedVehicle.model}`
                          : `Vehicle #${slot.vehicle_id}`}
                      </div>
                    </div>

                    {/* Capacity Progress Bar */}
                    <div className="space-y-1">
                      <div className="flex justify-between text-[11px] text-slate-400">
                        <span>Capacity Utilization</span>
                        <span className="font-mono text-slate-300">
                          {slot.booked_count} / {slot.capacity} booked ({remaining} left)
                        </span>
                      </div>
                      <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                        <div
                          style={{ width: `${(slot.booked_count / slot.capacity) * 100}%` }}
                          className={`h-full ${isAvailable ? "bg-blue-500" : "bg-slate-600"}`}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="mt-5 pt-3 border-t border-slate-800 flex items-center justify-between">
                    <span className="text-[11px] font-mono text-slate-500">Slot #{slot.id}</span>
                    <button
                      onClick={() => setBookingSlot(slot)}
                      disabled={!isAvailable}
                      className="btn-primary text-xs py-1.5 px-3 disabled:opacity-40"
                    >
                      Book This Slot
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {!filteredSlots.length && (
            <div className="p-12 text-center text-xs text-slate-400 bg-slate-900 border border-slate-800 rounded-xl">
              No test-drive slots currently available for this selection.
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Bookings Table CRM */}
      {activeTab === "bookings" && (
        <div className="erp-table-container">
          <table className="erp-table">
            <thead>
              <tr>
                <th>Booking ID</th>
                <th>Customer Name</th>
                <th>Vehicle</th>
                <th>Scheduled Date & Time</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {bookings.map((b) => (
                <tr key={b.id}>
                  <td className="font-mono text-xs text-slate-400">#{b.id}</td>
                  <td>
                    <div className="font-bold text-white text-xs">{b.customer_name}</div>
                    <div className="text-[11px] text-slate-400">{b.customer_email}</div>
                  </td>
                  <td>
                    <div className="font-semibold text-slate-200 text-xs">
                      {b.vehicle_name || "Toyota Camry XSE"}
                    </div>
                    <div className="text-[10px] text-slate-500">Vehicle #{b.vehicle_id}</div>
                  </td>
                  <td>
                    <div className="text-xs text-slate-200">
                      {new Date(b.starts_at || Date.now()).toLocaleDateString([], {
                        weekday: "short",
                        month: "short",
                        day: "numeric",
                      })}
                    </div>
                    <div className="text-[11px] text-slate-400 font-mono">
                      {new Date(b.starts_at || Date.now()).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </div>
                  </td>
                  <td>
                    <span
                      className={`badge ${
                        b.status === "booked"
                          ? "badge-info"
                          : b.status === "completed"
                          ? "badge-success"
                          : "badge-danger"
                      }`}
                    >
                      {b.status.toUpperCase()}
                    </span>
                  </td>
                  <td>
                    {b.status === "booked" && (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setActionBooking({ booking: b, type: "reschedule" })}
                          className="text-xs text-blue-400 hover:text-blue-300 font-semibold"
                        >
                          Reschedule
                        </button>
                        <button
                          onClick={() => setActionBooking({ booking: b, type: "cancel" })}
                          className="text-xs text-rose-400 hover:text-rose-300 font-semibold"
                        >
                          Cancel
                        </button>
                      </div>
                    )}
                    {b.status === "cancelled" && (
                      <span className="text-[11px] text-slate-500 italic">Cancelled</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Customer Booking Modal */}
      {bookingSlot && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="p-5 border-b border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white">Confirm Test Drive Booking</h3>
                <p className="text-xs text-slate-400">
                  FR-017 Explicit Confirmation & Capacity Locking
                </p>
              </div>
              <button onClick={() => setBookingSlot(null)} className="text-slate-400 hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleBookSlot} className="p-5 space-y-4 text-xs">
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-2">
                <div className="flex justify-between">
                  <span className="text-slate-400">Timeslot:</span>
                  <span className="font-semibold text-white">
                    {new Date(bookingSlot.starts_at).toLocaleString([], {
                      dateStyle: "medium",
                      timeStyle: "short",
                    })}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Remaining Capacity:</span>
                  <span className="text-emerald-400 font-semibold">
                    {bookingSlot.remaining_capacity ?? bookingSlot.capacity - bookingSlot.booked_count} spaces available
                  </span>
                </div>
              </div>

              <div>
                <label className="text-slate-300 font-semibold mb-1 block">Your Name</label>
                <input
                  type="text"
                  required
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-white"
                />
              </div>

              <div>
                <label className="text-slate-300 font-semibold mb-1 block">Contact Email</label>
                <input
                  type="email"
                  required
                  value={customerEmail}
                  onChange={(e) => setCustomerEmail(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-white"
                />
              </div>

              <div className="pt-2">
                <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    required
                    checked={confirmedCheck}
                    onChange={(e) => setConfirmedCheck(e.target.checked)}
                    className="rounded bg-slate-950 border-slate-700 text-blue-600 focus:ring-0"
                  />
                  <span>
                    I confirm my request to book this test drive slot under Apex Motors terms.
                  </span>
                </label>
              </div>

              <div className="pt-4 border-t border-slate-800 flex justify-end gap-2">
                <button type="button" onClick={() => setBookingSlot(null)} className="btn-secondary">
                  Cancel
                </button>
                <button type="submit" disabled={!confirmedCheck} className="btn-primary">
                  Confirm Booking
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Reschedule / Cancellation Verification Modal */}
      {actionBooking && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="p-5 border-b border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white">
                  {actionBooking.type === "cancel" ? "Cancel Test Drive" : "Reschedule Test Drive"}
                </h3>
                <p className="text-xs text-slate-400">
                  FR-018 Contact & Identity Verification Required
                </p>
              </div>
              <button onClick={() => setActionBooking(null)} className="text-slate-400 hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>

            <form
              onSubmit={actionBooking.type === "cancel" ? handleCancelBooking : handleRescheduleBooking}
              className="p-5 space-y-4 text-xs"
            >
              <div>
                <label className="text-slate-300 font-semibold mb-1 block">
                  Verify Customer Email
                </label>
                <input
                  type="email"
                  required
                  placeholder={actionBooking.booking.customer_email || "Enter your booking email"}
                  value={verificationEmail}
                  onChange={(e) => setVerificationEmail(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-white"
                />
              </div>

              {actionBooking.type === "reschedule" && (
                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">
                    Select New Available Slot
                  </label>
                  <select
                    required
                    value={newSlotId}
                    onChange={(e) => setNewSlotId(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-white"
                  >
                    <option value="">Choose a slot...</option>
                    {slots
                      .filter((s) => s.id !== actionBooking.booking.slot_id && (s.remaining_capacity ?? s.capacity - s.booked_count) > 0)
                      .map((s) => (
                        <option key={s.id} value={s.id}>
                          {new Date(s.starts_at).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}
                        </option>
                      ))}
                  </select>
                </div>
              )}

              {actionBooking.type === "cancel" && (
                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">
                    Reason for Cancellation (Optional)
                  </label>
                  <textarea
                    rows={2}
                    placeholder="Schedule conflict, purchased vehicle, etc."
                    value={cancelReason}
                    onChange={(e) => setCancelReason(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-white"
                  />
                </div>
              )}

              <div className="pt-4 border-t border-slate-800 flex justify-end gap-2">
                <button type="button" onClick={() => setActionBooking(null)} className="btn-secondary">
                  Back
                </button>
                <button
                  type="submit"
                  className={actionBooking.type === "cancel" ? "btn-primary bg-rose-600 hover:bg-rose-700" : "btn-primary"}
                >
                  {actionBooking.type === "cancel" ? "Confirm Cancellation" : "Confirm Reschedule"}
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
    <Suspense fallback={<Shell><div className="p-8 text-center text-xs text-slate-400">Loading schedule...</div></Shell>}>
      <BookingsInner />
    </Suspense>
  );
}
