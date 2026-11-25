"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";
import { CheckCircle2, History, Loader2, Plus, RefreshCw, Sparkles, UserRound, X } from "lucide-react";
import Shell from "../components/Shell";
import { api } from "../api";
import { useAuth } from "../providers";
import type { CustomerLead, LeadActivity, StaffUser } from "../lib/types";

type LeadStatus =
  | "new"
  | "contacted"
  | "qualified"
  | "test_drive_scheduled"
  | "won"
  | "lost"
  | "follow_up";

function toLocalDateTime(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 16);
}

function LeadRow({
  lead,
  staff,
  saving,
  canAutoAssign,
  onSave,
  onConvert,
  onAutoAssign,
  onViewActivities,
}: {
  lead: CustomerLead;
  staff: StaffUser[];
  saving: boolean;
  canAutoAssign: boolean;
  onSave: (
    leadId: number,
    status: LeadStatus | null,
    assignedToUserId: number | null,
    followUp: string | null,
    dealValue: number | null,
  ) => Promise<void>;
  onConvert: (leadId: number, bookingId: number) => Promise<void>;
  onAutoAssign: (leadId: number) => Promise<void>;
  onViewActivities: (lead: CustomerLead) => void;
}) {
  const [status, setStatus] = useState<LeadStatus>(lead.status);
  const [assignee, setAssignee] = useState(
    lead.assigned_to_user_id ? String(lead.assigned_to_user_id) : "",
  );
  const [followUp, setFollowUp] = useState(toLocalDateTime(lead.next_follow_up_at));
  const [dealValue, setDealValue] = useState(
    lead.deal_value != null ? String(lead.deal_value) : "",
  );
  const [bookingId, setBookingId] = useState("");

  useEffect(() => {
    setStatus(lead.status);
    setAssignee(lead.assigned_to_user_id ? String(lead.assigned_to_user_id) : "");
    setFollowUp(toLocalDateTime(lead.next_follow_up_at));
    setDealValue(lead.deal_value != null ? String(lead.deal_value) : "");
  }, [lead]);

  return (
    <tr className="border-t border-slate-800 align-top">
      <td className="px-4 py-4">
        <div className="font-semibold text-white">{lead.name}</div>
        <a className="text-sm text-blue-300 hover:text-blue-200" href={`mailto:${lead.email}`}>
          {lead.email}
        </a>
        <div className="text-xs text-slate-400">{lead.phone || "No phone provided"}</div>
        <p className="mt-2 max-w-xs whitespace-pre-wrap text-xs text-slate-300">{lead.message}</p>
        {(lead.budget != null || lead.purchase_timeline) ? (
          <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
            {lead.budget != null ? (
              <span className="rounded bg-slate-800 px-2 py-0.5 text-emerald-300">
                Budget: ${Number(lead.budget).toLocaleString()}
              </span>
            ) : null}
            {lead.purchase_timeline ? (
              <span className="rounded bg-slate-800 px-2 py-0.5 text-blue-300">
                Timeline: {lead.purchase_timeline}
              </span>
            ) : null}
          </div>
        ) : null}
        <div className="mt-2 text-[11px] text-slate-500">
          {lead.source} · {new Date(lead.created_at).toLocaleDateString()}
          {lead.conversation_id ? ` · Conv #${lead.conversation_id}` : ""}
        </div>
      </td>
      <td className="px-4 py-4">
        <label className="mb-1 block text-[11px] text-slate-400">Status</label>
        <select
          value={status}
          onChange={(event) => setStatus(event.target.value as LeadStatus)}
          className="rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-white"
        >
          {lead.test_drive_booking_id || lead.status === "test_drive_scheduled" ? (
            <>
              <option value="test_drive_scheduled">Test drive scheduled</option>
              <option value="follow_up">Follow-up</option>
              <option value="won">Won (Car Sold)</option>
              <option value="lost">Lost</option>
            </>
          ) : (
            <>
              <option value="new">New</option>
              <option value="contacted">Contacted</option>
              <option value="qualified">Qualified</option>
              <option value="follow_up">Follow-up</option>
              <option value="won">Won (Car Sold)</option>
              <option value="lost">Lost</option>
            </>
          )}
        </select>
        {lead.test_drive_booking_id ? (
          <div className="mt-1.5 text-xs font-medium text-emerald-300">
            Booking #{lead.test_drive_booking_id}
          </div>
        ) : null}
        {lead.requested_vehicle_id ? (
          <div className="mt-1 text-xs text-slate-400">Vehicle #{lead.requested_vehicle_id}</div>
        ) : null}
      </td>
      <td className="px-4 py-4">
        <label className="mb-1 block text-[11px] text-slate-400">Assigned to</label>
        <select
          value={assignee}
          onChange={(event) => setAssignee(event.target.value)}
          className="rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-white"
        >
          <option value="">Unassigned</option>
          {staff.map((member) => (
            <option key={member.id} value={member.id}>
              {member.name}
            </option>
          ))}
        </select>
        <label className="mb-1 mt-3 block text-[11px] text-slate-400">Next follow-up</label>
        <input
          type="datetime-local"
          value={followUp}
          onChange={(event) => setFollowUp(event.target.value)}
          className="w-full rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-xs text-white"
        />
        <label className="mb-1 mt-3 block text-[11px] text-slate-400">Deal Value ($)</label>
        <input
          type="number"
          min={0}
          step="100"
          placeholder="Optional"
          value={dealValue}
          onChange={(event) => setDealValue(event.target.value)}
          className="w-full rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-xs text-white"
        />
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={saving}
            onClick={() =>
              onSave(
                lead.id,
                status,
                assignee ? Number(assignee) : null,
                followUp ? new Date(followUp).toISOString() : null,
                dealValue !== "" ? Number(dealValue) : null,
              )
            }
            className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-500 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save changes"}
          </button>
          {canAutoAssign && !assignee ? (
            <button
              type="button"
              disabled={saving}
              onClick={() => void onAutoAssign(lead.id)}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-700 px-2.5 py-2 text-xs text-slate-200 hover:bg-slate-800 disabled:opacity-50"
            >
              <Sparkles className="h-3.5 w-3.5 text-amber-300" /> Auto-assign
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => onViewActivities(lead)}
            className="inline-flex items-center gap-1 rounded-lg border border-slate-700 px-2.5 py-2 text-xs text-slate-200 hover:bg-slate-800"
          >
            <History className="h-3.5 w-3.5" /> Timeline
          </button>
        </div>
      </td>
      <td className="px-4 py-4">
        {lead.test_drive_booking_id || lead.status === "test_drive_scheduled" ? (
          <span className="text-xs text-slate-500">Linked test drive</span>
        ) : (
          <div className="flex items-end gap-2">
            <label className="text-[11px] text-slate-400">
              Booking ID
              <input
                type="number"
                min={1}
                value={bookingId}
                onChange={(event) => setBookingId(event.target.value)}
                className="mt-1 block w-24 rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-white"
              />
            </label>
            <button
              type="button"
              disabled={!bookingId}
              onClick={() => onConvert(lead.id, Number(bookingId))}
              className="rounded-lg border border-slate-700 px-3 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-800 disabled:opacity-50"
            >
              Link booking
            </button>
          </div>
        )}
        <div className="mt-3 text-[11px] text-slate-500">
          {lead.consent_to_contact ? "Contact consent recorded" : "No contact consent"}
        </div>
      </td>
    </tr>
  );
}

export default function LeadsPage() {
  const { activeDealershipId, user } = useAuth();
  const [leads, setLeads] = useState<CustomerLead[]>([]);
  const [staff, setStaff] = useState<StaffUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingLeadId, setSavingLeadId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [budget, setBudget] = useState("");
  const [purchaseTimeline, setPurchaseTimeline] = useState("");
  const [autoAssign, setAutoAssign] = useState(false);
  const [message, setMessage] = useState("");
  const [consent, setConsent] = useState(false);
  const [activityLead, setActivityLead] = useState<CustomerLead | null>(null);
  const [activities, setActivities] = useState<LeadActivity[]>([]);
  const [loadingActivities, setLoadingActivities] = useState(false);
  const [noteSummary, setNoteSummary] = useState("");

  const canManageTeam = user?.role === "dealership_admin" || user?.role === "manager";

  const loadLeads = useCallback(async () => {
    if (!activeDealershipId) {
      setLoading(false);
      setError("Select a dealership workspace to view leads.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const [nextLeads, team] = await Promise.all([
        api<CustomerLead[]>(`/dealerships/${activeDealershipId}/leads?limit=500`),
        canManageTeam
          ? api<StaffUser[]>(`/dealerships/${activeDealershipId}/staff`)
          : Promise.resolve(
              user?.role === "sales_rep"
                ? [{
                    id: user.id,
                    dealership_id: activeDealershipId,
                    name: user.name,
                    email: user.email,
                    role: "sales_rep" as const,
                    is_active: true,
                  }]
                : [],
            ),
      ]);
      setLeads(nextLeads);
      setStaff(team);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load customer leads.");
    } finally {
      setLoading(false);
    }
  }, [activeDealershipId, canManageTeam, user]);

  useEffect(() => {
    void loadLeads();
  }, [loadLeads]);

  async function createLead(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeDealershipId || !consent) return;
    setSubmitting(true);
    setError("");
    setNotice("");
    try {
      const lead = await api<CustomerLead>(`/dealerships/${activeDealershipId}/leads`, {
        method: "POST",
        body: JSON.stringify({
          name,
          email,
          phone: phone || null,
          budget: budget !== "" ? Number(budget) : null,
          purchase_timeline: purchaseTimeline || null,
          auto_assign: autoAssign,
          message,
          source: "phone",
          consent_to_contact: true,
        }),
      });
      setLeads((current) => [lead, ...current]);
      setName("");
      setEmail("");
      setPhone("");
      setBudget("");
      setPurchaseTimeline("");
      setAutoAssign(false);
      setMessage("");
      setConsent(false);
      setNotice("Lead created and contact consent recorded.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create the lead.");
    } finally {
      setSubmitting(false);
    }
  }

  async function saveLead(
    leadId: number,
    status: LeadStatus | null,
    assignedToUserId: number | null,
    followUp: string | null,
    dealValue: number | null,
  ) {
    if (!activeDealershipId) return;
    setSavingLeadId(leadId);
    setError("");
    setNotice("");
    try {
      const updated = await api<CustomerLead>(
        `/dealerships/${activeDealershipId}/leads/${leadId}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            ...(status ? { status } : {}),
            assigned_to_user_id: assignedToUserId,
            next_follow_up_at: followUp,
            ...(dealValue !== null ? { deal_value: dealValue } : {}),
          }),
        },
      );
      setLeads((current) => current.map((lead) => lead.id === leadId ? updated : lead));
      setNotice("Lead updated.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update the lead.");
    } finally {
      setSavingLeadId(null);
    }
  }

  async function autoAssignLead(leadId: number) {
    if (!activeDealershipId) return;
    setSavingLeadId(leadId);
    setError("");
    setNotice("");
    try {
      const updated = await api<CustomerLead>(
        `/dealerships/${activeDealershipId}/leads/${leadId}/auto-assign`,
        { method: "POST" },
      );
      setLeads((current) => current.map((lead) => lead.id === leadId ? updated : lead));
      setNotice("Lead auto-assigned to least-loaded sales rep.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not auto-assign lead.");
    } finally {
      setSavingLeadId(null);
    }
  }

  async function openActivities(lead: CustomerLead) {
    if (!activeDealershipId) return;
    setActivityLead(lead);
    setNoteSummary("");
    setLoadingActivities(true);
    try {
      const items = await api<LeadActivity[]>(
        `/dealerships/${activeDealershipId}/leads/${lead.id}/activities`,
      );
      setActivities(items);
    } catch {
      setActivities([]);
    } finally {
      setLoadingActivities(false);
    }
  }

  async function addNoteActivity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeDealershipId || !activityLead || !noteSummary.trim()) return;
    try {
      const created = await api<LeadActivity>(
        `/dealerships/${activeDealershipId}/leads/${activityLead.id}/activities`,
        {
          method: "POST",
          body: JSON.stringify({ activity_type: "note", summary: noteSummary.trim() }),
        },
      );
      setActivities((prev) => [created, ...prev]);
      setNoteSummary("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not add activity note.");
    }
  }

  async function convertLead(leadId: number, bookingId: number) {
    if (!activeDealershipId) return;
    setError("");
    setNotice("");
    try {
      const updated = await api<CustomerLead>(
        `/dealerships/${activeDealershipId}/leads/${leadId}/convert`,
        { method: "POST", body: JSON.stringify({ booking_id: bookingId }) },
      );
      setLeads((current) => current.map((lead) => lead.id === leadId ? updated : lead));
      setNotice("Lead linked to its test-drive booking.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not link the booking.");
    }
  }

  return (
    <Shell>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-1 text-xs font-bold uppercase tracking-wider text-blue-300">
            Customer relationship management
          </p>
          <h1 className="text-2xl font-bold text-white">Customer Leads</h1>
          <p className="mt-1 text-sm text-slate-400">
            Capture inquiries, record consent, assign follow-ups, and connect leads to test drives.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadLeads()}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800"
        >
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
      </div>

      {error ? <div role="alert" className="mb-4 rounded-lg border border-rose-700 bg-rose-950/40 p-3 text-sm text-rose-200">{error}</div> : null}
      {notice ? <div role="status" className="mb-4 flex items-center gap-2 rounded-lg border border-emerald-700 bg-emerald-950/40 p-3 text-sm text-emerald-200"><CheckCircle2 className="h-4 w-4" />{notice}</div> : null}

      <form onSubmit={createLead} className="mb-6 rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <div className="mb-4 flex items-center gap-2 font-semibold text-white">
          <Plus className="h-4 w-4 text-blue-300" /> Add an inquiry
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <input required maxLength={100} value={name} onChange={(event) => setName(event.target.value)} placeholder="Customer name" className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" />
          <input required type="email" maxLength={320} value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Email address" className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" />
          <input maxLength={32} value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="Phone (optional)" className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" />
          <input type="number" min={0} step="100" value={budget} onChange={(event) => setBudget(event.target.value)} placeholder="Budget $ (optional)" className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" />
          <select value={purchaseTimeline} onChange={(event) => setPurchaseTimeline(event.target.value)} className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white">
            <option value="">Timeline (optional)</option>
            <option value="immediate">Immediate</option>
            <option value="this_month">This Month</option>
            <option value="1_3_months">1-3 Months</option>
            <option value="researching">Researching</option>
          </select>
          <button disabled={submitting || !consent} className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:opacity-50">
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserRound className="h-4 w-4" />}
            Create lead
          </button>
          <textarea required maxLength={2000} value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Inquiry details" className="min-h-20 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white md:col-span-2 xl:col-span-3" />
          <div className="flex flex-col justify-center gap-2 text-xs leading-5 text-slate-400 xl:col-span-1">
            <label className="flex items-start gap-2">
              <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} className="mt-1 accent-blue-500" />
              Customer agreed to be contacted about this inquiry.
            </label>
            <label className="flex items-start gap-2">
              <input type="checkbox" checked={autoAssign} onChange={(event) => setAutoAssign(event.target.checked)} className="mt-1 accent-blue-500" />
              Auto-assign to least-loaded sales rep.
            </label>
          </div>
        </div>
      </form>

      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/40">
        <table className="w-full min-w-[1000px] border-collapse text-left">
          <thead className="bg-slate-900 text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-4 py-3">Customer inquiry</th>
              <th className="px-4 py-3">Pipeline status</th>
              <th className="px-4 py-3">Ownership & follow-up</th>
              <th className="px-4 py-3">Test drive</th>
            </tr>
          </thead>
          <tbody>
            {leads.map((lead) => (
              <LeadRow
                key={lead.id}
                lead={lead}
                staff={staff}
                saving={savingLeadId === lead.id}
                canAutoAssign={canManageTeam}
                onSave={saveLead}
                onConvert={convertLead}
                onAutoAssign={autoAssignLead}
                onViewActivities={openActivities}
              />
            ))}
          </tbody>
        </table>
        {loading ? (
          <div className="p-8 text-center text-sm text-slate-400">Loading customer leads...</div>
        ) : leads.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-400">No leads yet. Add an inquiry above to start the CRM workflow.</div>
        ) : null}
      </div>

      {activityLead ? (
        <div className="modal-overlay">
          <div className="modal-content p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-white">
                  Lead Activity Timeline · {activityLead.name}
                </h3>
                <p className="text-xs text-slate-400">Lead #{activityLead.id} · {activityLead.email}</p>
              </div>
              <button onClick={() => setActivityLead(null)} className="text-slate-400 hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={addNoteActivity} className="flex gap-2">
              <input
                type="text"
                required
                value={noteSummary}
                onChange={(e) => setNoteSummary(e.target.value)}
                placeholder="Add a call log or sales note..."
                className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
              />
              <button type="submit" className="btn-primary text-xs">
                Add Note
              </button>
            </form>
            {loadingActivities ? (
              <p className="text-xs text-slate-400">Loading activity timeline...</p>
            ) : activities.length === 0 ? (
              <p className="text-xs text-slate-500">No activity events recorded yet.</p>
            ) : (
              <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
                {activities.map((act) => (
                  <div key={act.id} className="rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs">
                    <div className="flex items-center justify-between text-[11px] text-slate-400">
                      <span className="font-semibold uppercase text-blue-300">{act.activity_type}</span>
                      <span>{new Date(act.created_at).toLocaleString()}</span>
                    </div>
                    <p className="mt-1 text-slate-200">{act.summary}</p>
                    {act.actor_user_email ? (
                      <p className="mt-1 text-[10px] text-slate-500">By: {act.actor_user_email}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : null}
    </Shell>
  );
}
