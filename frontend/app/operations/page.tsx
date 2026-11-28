"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  Bell,
  CalendarClock,
  CheckCircle2,
  AlertCircle,
  Send,
  Sliders,
  Bot,
  Code2,
  Copy,
} from "lucide-react";
import Shell from "../components/Shell";
import { api } from "../api";
import { useAuth } from "../providers";
import type {
  NotificationDelivery,
  OperationsSummary,
  OutboxEvent,
  TestDriveSettings,
} from "../lib/types";

export default function OperationsPage() {
  const { user, authReady, activeDealershipId } = useAuth();
  const [summary, setSummary] = useState<OperationsSummary | null>(null);
  const [settings, setSettings] = useState<TestDriveSettings | null>(null);
  const [outbox, setOutbox] = useState<OutboxEvent[]>([]);
  const [notifications, setNotifications] = useState<NotificationDelivery[]>([]);
  const [daysAhead, setDaysAhead] = useState(7);
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    if (!activeDealershipId) return;
    setLoading(true);
    setError("");
    try {
      const [nextSummary, nextSettings, nextOutbox, nextNotifications] = await Promise.all([
        api<OperationsSummary>(`/dealerships/${activeDealershipId}/reports/summary`),
        api<TestDriveSettings>(`/dealerships/${activeDealershipId}/test-drive-settings`),
        api<OutboxEvent[]>(`/dealerships/${activeDealershipId}/outbox`),
        api<NotificationDelivery[]>(`/dealerships/${activeDealershipId}/notifications`),
      ]);
      setSummary(nextSummary);
      setSettings(nextSettings);
      setOutbox(nextOutbox);
      setNotifications(nextNotifications);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load operations data.");
    } finally {
      setLoading(false);
    }
  }, [activeDealershipId]);

  useEffect(() => {
    if (!authReady || !user) return;
    if (!activeDealershipId) {
      setLoading(false);
      return;
    }
    void loadData();
  }, [authReady, user, activeDealershipId, loadData]);

  async function saveSettings(e: React.FormEvent) {
    e.preventDefault();
    if (!activeDealershipId || !settings) return;
    setBusyAction("settings");
    setError("");
    setNotice("");
    try {
      const updated = await api<TestDriveSettings>(
        `/dealerships/${activeDealershipId}/test-drive-settings`,
        {
          method: "PUT",
          body: JSON.stringify({
            slot_duration_minutes: Number(settings.slot_duration_minutes),
            capacity_per_slot: Number(settings.capacity_per_slot),
            opening_time: settings.opening_time,
            closing_time: settings.closing_time,
            days_open: settings.days_open,
          }),
        },
      );
      setSettings(updated);
      setNotice("Test-drive scheduling settings saved.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save settings.");
    } finally {
      setBusyAction(null);
    }
  }

  async function generateSlots() {
    if (!activeDealershipId) return;
    setBusyAction("slots");
    setError("");
    setNotice("");
    try {
      const start = new Date();
      const end = new Date();
      end.setDate(start.getDate() + Math.max(1, Number(daysAhead)));
      const startDate = start.toISOString().slice(0, 10);
      const endDate = end.toISOString().slice(0, 10);
      const res = await api<Array<{ id: number }>>(
        `/dealerships/${activeDealershipId}/test-drive-slots/generate?start_date=${startDate}&end_date=${endDate}`,
        { method: "POST" },
      );
      setNotice(
        `Generated ${res.length} upcoming test-drive slot(s) from ${startDate} to ${endDate}.`,
      );
      await loadData();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not generate slots.");
    } finally {
      setBusyAction(null);
    }
  }

  async function dispatchOutbox() {
    if (!activeDealershipId) return;
    setBusyAction("outbox");
    setError("");
    setNotice("");
    try {
      const res = await api<{ dispatched_count?: number }>(
        `/dealerships/${activeDealershipId}/outbox/dispatch`,
        { method: "POST" },
      );
      setNotice(`Dispatched ${res.dispatched_count ?? 0} outbox event(s).`);
      await loadData();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not dispatch outbox events.");
    } finally {
      setBusyAction(null);
    }
  }

  async function runReminders() {
    if (!activeDealershipId) return;
    setBusyAction("reminders");
    setError("");
    setNotice("");
    try {
      const res = await api<{ sent_count?: number }>(
        `/dealerships/${activeDealershipId}/notifications/run-reminders`,
        { method: "POST" },
      );
      setNotice(`Processed ${res.sent_count ?? 0} test-drive reminder(s).`);
      await loadData();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not run reminders.");
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <Shell>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="crm-page-title">
            Operations & Outbox
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Configure test-drive slot generation, dispatch webhook outbox events, and trigger reminders
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={busyAction !== null}
            onClick={runReminders}
            className="crm-btn-secondary"
          >
            <Bell className="h-4 w-4" />
            {busyAction === "reminders" ? "Running..." : "Run Reminders"}
          </button>
          <button
            type="button"
            disabled={busyAction !== null}
            onClick={dispatchOutbox}
            className="crm-btn-primary"
          >
            <Send className="h-4 w-4" />
            {busyAction === "outbox" ? "Dispatching..." : "Dispatch Outbox"}
          </button>
        </div>
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

      {loading ? (
        <div className="crm-card p-12 text-center text-sm text-slate-500">
          Loading dealership operations...
        </div>
      ) : (
        <div className="space-y-6">
          {/* Summary KPIs */}
          {summary && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="crm-kpi">
                <p className="text-xs font-medium text-slate-500">Inventory Units</p>
                <p className="text-2xl font-medium text-[#171717] tabular-nums mt-1">
                  {summary.inventory.total}
                </p>
                <p className="text-xs text-emerald-600 mt-1">
                  {summary.inventory.by_status?.available ?? 0} available ·{" "}
                  {summary.inventory.by_status?.sold ?? 0} sold
                </p>
              </div>
              <div className="crm-kpi">
                <p className="text-xs font-medium text-slate-500">Pipeline Leads</p>
                <p className="text-2xl font-medium text-[#171717] tabular-nums mt-1">{summary.leads.total}</p>
                <p className="text-xs text-blue-600 mt-1">
                  {summary.leads.by_status?.won ?? 0} won · $
                  {Number(summary.leads.won_deal_value || 0).toLocaleString()}
                </p>
              </div>
              <div className="crm-kpi">
                <p className="text-xs font-medium text-slate-500">Booked Test Drives</p>
                <p className="text-2xl font-medium text-[#171717] tabular-nums mt-1">
                  {summary.test_drives.by_status?.booked ?? 0}
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  {summary.conversations.handoff_queue} active handoffs
                </p>
              </div>
              <div className="crm-kpi">
                <p className="text-xs font-medium text-slate-500">Outbox & Notifications</p>
                <p className="text-2xl font-medium text-[#171717] tabular-nums mt-1">
                  {summary.observability.outbox_by_status?.pending ?? 0}
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  pending · {summary.observability.outbox_by_status?.no_target ?? 0} without target ·{" "}
                  {summary.observability.notifications_by_status?.sent ?? 0} notifications sent
                </p>
              </div>
            </div>
          )}

          {/* Settings + Slot Generator */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 crm-card p-6">
              <div className="flex items-center gap-2 mb-4">
                <Sliders className="h-4 w-4 text-slate-500" />
                <h2 className="text-base font-medium text-[#171717]">
                  Test-Drive Scheduling Policy
                </h2>
              </div>

              {settings ? (
                <form onSubmit={saveSettings} className="space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        Slot Duration (mins)
                      </label>
                      <input
                        type="number"
                        min={15}
                        max={240}
                        value={settings.slot_duration_minutes}
                        onChange={(e) =>
                          setSettings({
                            ...settings,
                            slot_duration_minutes: Number(e.target.value),
                          })
                        }
                        className="crm-input"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        Capacity Per Slot
                      </label>
                      <input
                        type="number"
                        min={1}
                        max={20}
                        value={settings.capacity_per_slot}
                        onChange={(e) =>
                          setSettings({
                            ...settings,
                            capacity_per_slot: Number(e.target.value),
                          })
                        }
                        className="crm-input"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        Opening Time (HH:MM)
                      </label>
                      <input
                        type="time"
                        value={settings.opening_time}
                        onChange={(e) =>
                          setSettings({ ...settings, opening_time: e.target.value })
                        }
                        className="crm-input"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        Closing Time (HH:MM)
                      </label>
                      <input
                        type="time"
                        value={settings.closing_time}
                        onChange={(e) =>
                          setSettings({ ...settings, closing_time: e.target.value })
                        }
                        className="crm-input"
                      />
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2 pt-1">
                    {[
                      { id: 0, label: "Mon" },
                      { id: 1, label: "Tue" },
                      { id: 2, label: "Wed" },
                      { id: 3, label: "Thu" },
                      { id: 4, label: "Fri" },
                      { id: 5, label: "Sat" },
                      { id: 6, label: "Sun" },
                    ].map((day) => {
                      const active = settings.days_open.includes(day.id);
                      return (
                        <button
                          key={day.id}
                          type="button"
                          onClick={() =>
                            setSettings({
                              ...settings,
                              days_open: active
                                ? settings.days_open.filter((d) => d !== day.id)
                                : [...settings.days_open, day.id].sort((a, b) => a - b),
                            })
                          }
                          className={`rounded-lg px-2.5 py-1 text-xs font-semibold border transition-colors ${active
                            ? "bg-blue-600 text-white border-blue-600"
                            : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                            }`}
                        >
                          {day.label}
                        </button>
                      );
                    })}
                  </div>

                  <div className="flex justify-end">
                    <button
                      type="submit"
                      disabled={busyAction !== null}
                      className="crm-btn-primary"
                    >
                      {busyAction === "settings" ? "Saving..." : "Save Policy"}
                    </button>
                  </div>
                </form>
              ) : (
                <p className="text-xs text-slate-500">Settings unavailable for this workspace.</p>
              )}
            </div>

            <div className="crm-card p-6 flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <CalendarClock className="h-4 w-4 text-slate-500" />
                  <h2 className="text-base font-medium text-[#171717]">Slot Generator</h2>
                </div>
                <p className="text-xs text-slate-500 mb-4">
                  Automatically populate bookable test-drive slots for all enabled vehicles using the
                  dealership&apos;s operating hours.
                </p>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Days Ahead to Generate
                </label>
                <input
                  type="number"
                  min={1}
                  max={60}
                  value={daysAhead}
                  onChange={(e) => setDaysAhead(Number(e.target.value))}
                  className="crm-input mb-4"
                />
              </div>
              <button
                type="button"
                disabled={busyAction !== null}
                onClick={generateSlots}
                className="crm-btn-primary w-full"
              >
                <Bot className="h-4 w-4" />
                {busyAction === "slots" ? "Generating..." : "Generate Test-Drive Slots"}
              </button>
            </div>
          </div>

          {/* Outbox + Notifications Tables */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="crm-card overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Activity className="h-4 w-4 text-slate-500" />
                  <h2 className="text-sm font-medium text-[#171717]">
                    Webhook Outbox ({outbox.length})
                  </h2>
                </div>
              </div>
              {outbox.length === 0 ? (
                <p className="p-6 text-xs text-slate-500 text-center">No outbox events queued.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="crm-table">
                    <thead>
                      <tr>
                        <th>Event</th>
                        <th>Status</th>
                        <th>Attempts</th>
                      </tr>
                    </thead>
                    <tbody>
                      {outbox.slice(0, 12).map((evt) => (
                        <tr key={evt.id}>
                          <td>
                            <div className="font-semibold text-slate-900 text-xs">
                              {evt.event_type}
                            </div>
                            <div className="text-[11px] text-slate-500">
                              {new Date(evt.created_at).toLocaleString()}
                            </div>
                          </td>
                          <td>
                            <span
                              className={`crm-badge ${evt.status === "dispatched"
                                ? "crm-badge-success"
                                : evt.status === "failed"
                                  ? "crm-badge-danger"
                                  : "crm-badge-warning"
                                }`}
                            >
                              {evt.status}
                            </span>
                          </td>
                          <td className="text-xs text-slate-600">{evt.attempts}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="crm-card overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Bell className="h-4 w-4 text-slate-500" />
                  <h2 className="text-sm font-medium text-[#171717]">
                    Notification Deliveries ({notifications.length})
                  </h2>
                </div>
              </div>
              {notifications.length === 0 ? (
                <p className="p-6 text-xs text-slate-500 text-center">
                  No notification deliveries recorded.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="crm-table">
                    <thead>
                      <tr>
                        <th>Recipient</th>
                        <th>Type</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {notifications.slice(0, 12).map((item) => (
                        <tr key={item.id}>
                          <td>
                            <div className="font-semibold text-slate-900 text-xs">
                              {item.recipient}
                            </div>
                            <div className="text-[11px] text-slate-500">{item.channel}</div>
                          </td>
                          <td className="text-xs text-slate-600">{item.notification_type}</td>
                          <td>
                            <span
                              className={`crm-badge ${item.status === "sent"
                                ? "crm-badge-success"
                                : item.status === "failed"
                                  ? "crm-badge-danger"
                                  : "crm-badge-warning"
                                }`}
                            >
                              {item.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

          {/* Website AI Widget Embed */}
          {activeDealershipId && (
            <div className="crm-card p-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
                <div>
                  <div className="flex items-center gap-2">
                    <Code2 className="h-4 w-4 text-slate-500" />
                    <h2 className="text-base font-medium text-[#171717]">
                      Website AI Widget Embed
                    </h2>
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Paste this scoped iframe into your dealership&apos;s website. It starts
                    minimized and connects directly to this dealership&apos;s inventory &amp;
                    CRM inbox.
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={() => {
                      const origin =
                        typeof window !== "undefined" ? window.location.origin : "";
                      const snippet = `<iframe src="${origin}/embed/${activeDealershipId}" title="Dealership AI Assistant" style="position:fixed;bottom:16px;right:16px;width:400px;max-width:calc(100vw - 32px);height:580px;border:0;z-index:9999;" allow="clipboard-write"></iframe>`;
                      void navigator.clipboard?.writeText(snippet);
                      setNotice("Website widget embed snippet copied to clipboard.");
                    }}
                    className="crm-btn-secondary py-1.5 px-3 text-xs"
                  >
                    <Copy className="h-3.5 w-3.5" />
                    Copy Embed Code
                  </button>
                  <a
                    href={`/embed/${activeDealershipId}`}
                    target="_blank"
                    rel="noreferrer"
                    className="crm-btn-primary py-1.5 px-3 text-xs"
                  >
                    Preview Widget
                  </a>
                </div>
              </div>
              <pre className="rounded-lg bg-slate-900 text-slate-100 p-3.5 text-xs overflow-x-auto">
                {`<iframe src="${typeof window !== "undefined" ? window.location.origin : "https://your-domain.com"}/embed/${activeDealershipId}" title="Dealership AI Assistant" style="position:fixed;bottom:16px;right:16px;width:400px;max-width:calc(100vw - 32px);height:580px;border:0;z-index:9999;" allow="clipboard-write"></iframe>`}
              </pre>
            </div>
          )}
        </div>
      )}
    </Shell>
  );
}
