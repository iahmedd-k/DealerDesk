"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  CalendarClock,
  CheckCircle2,
  CircleAlert,
  ClipboardList,
  Plus,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import Shell from "../components/Shell";
import { api } from "../api";
import { useAuth } from "../providers";
import type {
  ServiceAppointment,
  ServiceWorkOrder,
  Vehicle,
  VehicleWarranty,
} from "../lib/types";

function localDateTimeValue(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 16);
}

function formatDateTime(value: string | null): string {
  if (!value) return "Not scheduled";
  return new Date(value).toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function vehicleLabel(vehicle: Vehicle): string {
  return `${vehicle.stock_number} · ${vehicle.model_year} ${vehicle.make} ${vehicle.model}`;
}

export default function ServicePage() {
  const { authReady, activeDealershipId } = useAuth();
  const [appointments, setAppointments] = useState<ServiceAppointment[]>([]);
  const [workOrders, setWorkOrders] = useState<ServiceWorkOrder[]>([]);
  const [warranties, setWarranties] = useState<VehicleWarranty[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [appointmentName, setAppointmentName] = useState("");
  const [appointmentEmail, setAppointmentEmail] = useState("");
  const [appointmentPhone, setAppointmentPhone] = useState("");
  const [appointmentVehicleId, setAppointmentVehicleId] = useState("");
  const [appointmentAt, setAppointmentAt] = useState(() =>
    localDateTimeValue(new Date(Date.now() + 60 * 60 * 1000)),
  );
  const [appointmentConcern, setAppointmentConcern] = useState("");

  const [workAppointmentId, setWorkAppointmentId] = useState("");
  const [workVehicleId, setWorkVehicleId] = useState("");
  const [workCustomerName, setWorkCustomerName] = useState("");
  const [workConcern, setWorkConcern] = useState("");
  const [workDiagnosis, setWorkDiagnosis] = useState("");

  const [warrantyVehicleId, setWarrantyVehicleId] = useState("");
  const [warrantyProvider, setWarrantyProvider] = useState("");
  const [warrantyPolicy, setWarrantyPolicy] = useState("");
  const [warrantyCoverage, setWarrantyCoverage] = useState("");
  const [warrantyStart, setWarrantyStart] = useState("");
  const [warrantyEnd, setWarrantyEnd] = useState("");
  const [warrantyMileage, setWarrantyMileage] = useState("");

  const [followUpDrafts, setFollowUpDrafts] = useState<Record<number, string>>({});

  const loadData = useCallback(async () => {
    if (!activeDealershipId) {
      setLoading(false);
      setError("Select a dealership workspace to view service records.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const [nextAppointments, nextWorkOrders, nextWarranties, nextVehicles] =
        await Promise.all([
          api<ServiceAppointment[]>(
            `/dealerships/${activeDealershipId}/service-appointments`,
          ),
          api<ServiceWorkOrder[]>(
            `/dealerships/${activeDealershipId}/service-work-orders`,
          ),
          api<VehicleWarranty[]>(
            `/dealerships/${activeDealershipId}/vehicle-warranties`,
          ),
          api<Vehicle[]>(`/dealerships/${activeDealershipId}/vehicles`),
        ]);
      setAppointments(nextAppointments);
      setWorkOrders(nextWorkOrders);
      setWarranties(nextWarranties);
      setVehicles(nextVehicles);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load service records.");
      throw cause;
    } finally {
      setLoading(false);
    }
  }, [activeDealershipId]);

  useEffect(() => {
    if (authReady) void loadData().catch(() => undefined);
  }, [authReady, loadData]);

  const vehicleById = useMemo(
    () => new Map(vehicles.map((vehicle) => [vehicle.id, vehicle])),
    [vehicles],
  );

  async function runAction(key: string, action: () => Promise<void>, success: string) {
    setBusy(key);
    setError("");
    setNotice("");
    try {
      await action();
      await loadData();
      setNotice(success);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The service action failed.");
    } finally {
      setBusy("");
    }
  }

  async function createAppointment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeDealershipId) return;
    await runAction(
      "appointment",
      async () => {
        await api(`/dealerships/${activeDealershipId}/service-appointments`, {
          method: "POST",
          body: JSON.stringify({
            customer_name: appointmentName.trim(),
            customer_email: appointmentEmail.trim() || null,
            customer_phone: appointmentPhone.trim() || null,
            vehicle_id: appointmentVehicleId ? Number(appointmentVehicleId) : null,
            scheduled_at: new Date(appointmentAt).toISOString(),
            concern: appointmentConcern.trim(),
          }),
        });
        setAppointmentName("");
        setAppointmentEmail("");
        setAppointmentPhone("");
        setAppointmentVehicleId("");
        setAppointmentConcern("");
      },
      "Service appointment created.",
    );
  }

  async function createWorkOrder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeDealershipId) return;
    const linkedAppointment = appointments.find(
      (appointment) => appointment.id === Number(workAppointmentId),
    );
    const selectedVehicleId = linkedAppointment?.vehicle_id
      ? String(linkedAppointment.vehicle_id)
      : workVehicleId;
    const customerName = linkedAppointment?.customer_name || workCustomerName.trim();
    await runAction(
      "work-order",
      async () => {
        await api(`/dealerships/${activeDealershipId}/service-work-orders`, {
          method: "POST",
          body: JSON.stringify({
            appointment_id: linkedAppointment?.id ?? null,
            vehicle_id: selectedVehicleId ? Number(selectedVehicleId) : null,
            customer_name: customerName,
            customer_email: linkedAppointment?.customer_email ?? null,
            customer_phone: linkedAppointment?.customer_phone ?? null,
            concern: workConcern.trim(),
            diagnosis: workDiagnosis.trim() || null,
          }),
        });
        setWorkAppointmentId("");
        setWorkVehicleId("");
        setWorkCustomerName("");
        setWorkConcern("");
        setWorkDiagnosis("");
      },
      "Work order created.",
    );
  }

  async function createWarranty(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeDealershipId) return;
    await runAction(
      "warranty",
      async () => {
        await api(`/dealerships/${activeDealershipId}/vehicle-warranties`, {
          method: "POST",
          body: JSON.stringify({
            vehicle_id: Number(warrantyVehicleId),
            provider: warrantyProvider.trim(),
            policy_number: warrantyPolicy.trim() || null,
            coverage: warrantyCoverage.trim(),
            start_date: warrantyStart,
            end_date: warrantyEnd,
            mileage_limit: warrantyMileage ? Number(warrantyMileage) : null,
          }),
        });
        setWarrantyProvider("");
        setWarrantyPolicy("");
        setWarrantyCoverage("");
        setWarrantyStart("");
        setWarrantyEnd("");
        setWarrantyMileage("");
      },
      "Warranty record added.",
    );
  }

  async function updateAppointment(
    appointment: ServiceAppointment,
    status: ServiceAppointment["status"],
  ) {
    if (!activeDealershipId) return;
    await runAction(
      `appointment-${appointment.id}`,
      async () => {
        await api(
          `/dealerships/${activeDealershipId}/service-appointments/${appointment.id}`,
          { method: "PATCH", body: JSON.stringify({ status }) },
        );
      },
      "Appointment updated.",
    );
  }

  async function updateWorkOrder(
    workOrder: ServiceWorkOrder,
    changes: Record<string, unknown>,
    success: string,
  ) {
    if (!activeDealershipId) return;
    await runAction(
      `work-order-${workOrder.id}`,
      async () => {
        await api(
          `/dealerships/${activeDealershipId}/service-work-orders/${workOrder.id}`,
          { method: "PATCH", body: JSON.stringify(changes) },
        );
      },
      success,
    );
  }

  if (!authReady || loading) {
    return (
      <Shell>
        <div className="p-8 text-sm text-slate-500">Loading service workspace…</div>
      </Shell>
    );
  }

  return (
    <Shell>
      <div className="mx-auto max-w-[1500px] space-y-6 p-4 md:p-8">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-blue-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-blue-700">
              <Wrench className="h-3.5 w-3.5" /> After-sales
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Service & warranty
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Coordinate customer visits, repair work, warranty coverage, and follow-ups.
            </p>
          </div>
          <div className="flex gap-2 text-xs">
            <span className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-slate-600">
              {appointments.filter((item) => !["completed", "cancelled", "no_show"].includes(item.status)).length} upcoming
            </span>
            <span className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-amber-800">
              {workOrders.filter((item) => item.follow_up_status === "pending").length} follow-ups
            </span>
          </div>
        </header>

        {error && (
          <div role="alert" className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
            <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" /> {error}
          </div>
        )}
        {notice && (
          <div role="status" className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
            <CheckCircle2 className="h-4 w-4" /> {notice}
          </div>
        )}

        <div className="grid gap-5 xl:grid-cols-3">
          <form onSubmit={createAppointment} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-1 flex items-center gap-2">
              <CalendarClock className="h-4 w-4 text-blue-700" />
              <h2 className="text-sm font-bold text-slate-900">Schedule service</h2>
            </div>
            <input required value={appointmentName} onChange={(event) => setAppointmentName(event.target.value)} placeholder="Customer name" className="crm-input text-sm" />
            <div className="grid grid-cols-2 gap-2">
              <input type="email" value={appointmentEmail} onChange={(event) => setAppointmentEmail(event.target.value)} placeholder="Email" className="crm-input text-sm" />
              <input value={appointmentPhone} onChange={(event) => setAppointmentPhone(event.target.value)} placeholder="Phone" className="crm-input text-sm" />
            </div>
            <select value={appointmentVehicleId} onChange={(event) => setAppointmentVehicleId(event.target.value)} className="crm-select text-sm">
              <option value="">Vehicle (optional)</option>
              {vehicles.map((vehicle) => <option key={vehicle.id} value={vehicle.id}>{vehicleLabel(vehicle)}</option>)}
            </select>
            <input required type="datetime-local" value={appointmentAt} onChange={(event) => setAppointmentAt(event.target.value)} className="crm-input text-sm" />
            <textarea required value={appointmentConcern} onChange={(event) => setAppointmentConcern(event.target.value)} placeholder="Service concern or requested work" rows={3} className="crm-input resize-y text-sm" />
            <button disabled={busy !== ""} className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-blue-700 px-3 py-2.5 text-sm font-semibold text-white hover:bg-blue-800 disabled:opacity-50">
              <Plus className="h-4 w-4" /> Schedule appointment
            </button>
          </form>

          <form onSubmit={createWorkOrder} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-1 flex items-center gap-2">
              <ClipboardList className="h-4 w-4 text-violet-700" />
              <h2 className="text-sm font-bold text-slate-900">Open work order</h2>
            </div>
            <select value={workAppointmentId} onChange={(event) => setWorkAppointmentId(event.target.value)} className="crm-select text-sm">
              <option value="">No linked appointment</option>
              {appointments.filter((item) => !["cancelled", "no_show"].includes(item.status)).map((item) => (
                <option key={item.id} value={item.id}>Appointment #{item.id} · {item.customer_name}</option>
              ))}
            </select>
            {!workAppointmentId && (
              <>
                <input required value={workCustomerName} onChange={(event) => setWorkCustomerName(event.target.value)} placeholder="Customer name" className="crm-input text-sm" />
                <select value={workVehicleId} onChange={(event) => setWorkVehicleId(event.target.value)} className="crm-select text-sm">
                  <option value="">Vehicle (optional)</option>
                  {vehicles.map((vehicle) => <option key={vehicle.id} value={vehicle.id}>{vehicleLabel(vehicle)}</option>)}
                </select>
              </>
            )}
            <textarea required value={workConcern} onChange={(event) => setWorkConcern(event.target.value)} placeholder="Customer concern / work requested" rows={2} className="crm-input resize-y text-sm" />
            <textarea value={workDiagnosis} onChange={(event) => setWorkDiagnosis(event.target.value)} placeholder="Initial diagnosis (optional)" rows={2} className="crm-input resize-y text-sm" />
            <button disabled={busy !== ""} className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-violet-700 px-3 py-2.5 text-sm font-semibold text-white hover:bg-violet-800 disabled:opacity-50">
              <Plus className="h-4 w-4" /> Create work order
            </button>
          </form>

          <form onSubmit={createWarranty} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-1 flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-700" />
              <h2 className="text-sm font-bold text-slate-900">Record warranty</h2>
            </div>
            <select required value={warrantyVehicleId} onChange={(event) => setWarrantyVehicleId(event.target.value)} className="crm-select text-sm">
              <option value="">Select vehicle</option>
              {vehicles.map((vehicle) => <option key={vehicle.id} value={vehicle.id}>{vehicleLabel(vehicle)}</option>)}
            </select>
            <div className="grid grid-cols-2 gap-2">
              <input required value={warrantyProvider} onChange={(event) => setWarrantyProvider(event.target.value)} placeholder="Provider" className="crm-input text-sm" />
              <input value={warrantyPolicy} onChange={(event) => setWarrantyPolicy(event.target.value)} placeholder="Policy number" className="crm-input text-sm" />
            </div>
            <textarea required value={warrantyCoverage} onChange={(event) => setWarrantyCoverage(event.target.value)} placeholder="Coverage summary" rows={2} className="crm-input resize-y text-sm" />
            <div className="grid grid-cols-2 gap-2">
              <label className="text-[11px] text-slate-500">Starts<input required type="date" value={warrantyStart} onChange={(event) => setWarrantyStart(event.target.value)} className="crm-input mt-1 text-sm" /></label>
              <label className="text-[11px] text-slate-500">Ends<input required type="date" value={warrantyEnd} onChange={(event) => setWarrantyEnd(event.target.value)} className="crm-input mt-1 text-sm" /></label>
            </div>
            <input type="number" min={0} value={warrantyMileage} onChange={(event) => setWarrantyMileage(event.target.value)} placeholder="Mileage limit (optional)" className="crm-input text-sm" />
            <button disabled={busy !== ""} className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-700 px-3 py-2.5 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-50">
              <Plus className="h-4 w-4" /> Save warranty
            </button>
          </form>
        </div>

        <div className="grid gap-5 xl:grid-cols-2">
          <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 px-5 py-4">
              <h2 className="text-sm font-bold text-slate-900">Service appointments</h2>
              <p className="mt-1 text-xs text-slate-500">Track bookings through confirmation and completion.</p>
            </div>
            <div className="divide-y divide-slate-100">
              {appointments.length === 0 ? (
                <p className="p-5 text-sm text-slate-500">No service appointments yet.</p>
              ) : appointments.map((item) => (
                <article key={item.id} className="flex flex-wrap items-start justify-between gap-3 p-5">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold text-slate-900">{item.customer_name}</p>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600">{item.status.replaceAll("_", " ")}</span>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">{formatDateTime(item.scheduled_at)}{item.vehicle_id && vehicleById.has(item.vehicle_id) ? ` · ${vehicleLabel(vehicleById.get(item.vehicle_id)!)}` : ""}</p>
                    <p className="mt-2 text-sm text-slate-700">{item.concern}</p>
                    {(item.customer_email || item.customer_phone) && <p className="mt-1 text-xs text-slate-400">{[item.customer_email, item.customer_phone].filter(Boolean).join(" · ")}</p>}
                  </div>
                  <div className="flex gap-2">
                    {item.status === "scheduled" && (
                      <button disabled={busy !== ""} onClick={() => void updateAppointment(item, "confirmed")} className="rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50">Confirm</button>
                    )}
                    {item.status === "confirmed" && (
                      <button disabled={busy !== ""} onClick={() => void updateAppointment(item, "completed")} className="rounded-lg bg-emerald-700 px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-emerald-800 disabled:opacity-50">Complete</button>
                    )}
                    {["scheduled", "confirmed"].includes(item.status) && (
                      <>
                        <button disabled={busy !== ""} onClick={() => void updateAppointment(item, "no_show")} className="rounded-lg border border-amber-200 px-2.5 py-1.5 text-xs font-semibold text-amber-800 hover:bg-amber-50 disabled:opacity-50">No-show</button>
                        <button disabled={busy !== ""} onClick={() => void updateAppointment(item, "cancelled")} className="rounded-lg border border-rose-200 px-2.5 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-50">Cancel</button>
                      </>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 px-5 py-4">
              <h2 className="text-sm font-bold text-slate-900">Work orders & customer follow-up</h2>
              <p className="mt-1 text-xs text-slate-500">Record diagnosis, costs, and the next customer touchpoint.</p>
            </div>
            <div className="divide-y divide-slate-100">
              {workOrders.length === 0 ? (
                <p className="p-5 text-sm text-slate-500">No work orders yet.</p>
              ) : workOrders.map((item) => (
                <article key={item.id} className="space-y-3 p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-semibold text-slate-900">{item.customer_name} · #{item.id}</p>
                        <span className="rounded-full bg-violet-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-700">{item.status.replaceAll("_", " ")}</span>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">{item.vehicle_id && vehicleById.has(item.vehicle_id) ? vehicleLabel(vehicleById.get(item.vehicle_id)!) : "Vehicle not linked"}{item.appointment_id ? ` · Appointment #${item.appointment_id}` : ""}</p>
                    </div>
                    <p className="text-sm font-semibold tabular-nums text-slate-900">${Number(item.total_cost).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                  </div>
                  <p className="text-sm text-slate-700">{item.concern}</p>
                  {item.diagnosis && <p className="text-xs text-slate-500">Diagnosis: {item.diagnosis}</p>}
                  <div className="flex flex-wrap items-center gap-2">
                    {item.status === "open" && (
                      <button disabled={busy !== ""} onClick={() => void updateWorkOrder(item, { status: "in_progress" }, "Work order started.")} className="rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50">Start work</button>
                    )}
                    {["open", "in_progress"].includes(item.status) && (
                      <button disabled={busy !== ""} onClick={() => void updateWorkOrder(item, { status: "completed" }, "Work order completed.")} className="rounded-lg bg-emerald-700 px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-emerald-800 disabled:opacity-50">Complete</button>
                    )}
                    <label className="flex items-center gap-2 text-xs text-slate-500">
                      <span>Follow-up</span>
                      <input
                        type="datetime-local"
                        value={followUpDrafts[item.id] ?? (item.follow_up_at ? localDateTimeValue(item.follow_up_at) : "")}
                        onChange={(event) => setFollowUpDrafts((drafts) => ({ ...drafts, [item.id]: event.target.value }))}
                        className="crm-input max-w-[190px] text-xs"
                      />
                    </label>
                    <button
                      disabled={busy !== "" || !followUpDrafts[item.id]}
                      onClick={() => {
                        const value = followUpDrafts[item.id];
                        if (value) void updateWorkOrder(item, { follow_up_at: new Date(value).toISOString(), follow_up_status: "pending" }, "Follow-up scheduled.");
                      }}
                      className="rounded-lg border border-amber-200 px-2.5 py-1.5 text-xs font-semibold text-amber-800 hover:bg-amber-50 disabled:opacity-50"
                    >Schedule</button>
                    {item.follow_up_status === "pending" && (
                      <button disabled={busy !== ""} onClick={() => void updateWorkOrder(item, { follow_up_status: "completed" }, "Customer follow-up marked complete.")} className="rounded-lg border border-emerald-200 px-2.5 py-1.5 text-xs font-semibold text-emerald-700 hover:bg-emerald-50 disabled:opacity-50">Follow-up done</button>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-400">{item.follow_up_status === "pending" ? `Follow-up due ${formatDateTime(item.follow_up_at)}` : `Follow-up ${item.follow_up_status.replaceAll("_", " ")}`}</p>
                </article>
              ))}
            </div>
          </section>
        </div>

        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 px-5 py-4">
            <h2 className="text-sm font-bold text-slate-900">Vehicle warranty register</h2>
            <p className="mt-1 text-xs text-slate-500">Warranty coverage and expiry dates are tracked per vehicle.</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[700px] text-left text-sm">
              <thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
                <tr><th className="px-5 py-3">Vehicle</th><th className="px-5 py-3">Provider / policy</th><th className="px-5 py-3">Coverage</th><th className="px-5 py-3">Term</th><th className="px-5 py-3">Status</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {warranties.length === 0 ? (
                  <tr><td colSpan={5} className="px-5 py-6 text-center text-sm text-slate-500">No warranties recorded.</td></tr>
                ) : warranties.map((item) => (
                  <tr key={item.id}>
                    <td className="px-5 py-3 font-medium text-slate-800">{vehicleById.has(item.vehicle_id) ? vehicleLabel(vehicleById.get(item.vehicle_id)!) : `Vehicle #${item.vehicle_id}`}</td>
                    <td className="px-5 py-3 text-slate-700">{item.provider}{item.policy_number && <span className="block text-xs text-slate-400">{item.policy_number}</span>}</td>
                    <td className="max-w-[280px] truncate px-5 py-3 text-slate-600" title={item.coverage}>{item.coverage}</td>
                    <td className="px-5 py-3 text-xs text-slate-600">{item.start_date} – {item.end_date}{item.mileage_limit != null && <span className="block text-slate-400">{item.mileage_limit.toLocaleString()} mi limit</span>}</td>
                    <td className="px-5 py-3"><span className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase ${item.is_active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>{item.is_active ? "Active" : "Expired"}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </Shell>
  );
}
