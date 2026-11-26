"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";
import {
  CheckCircle2,
  History,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Bot,
  Trash2,
  UserRound,
  X,
} from "lucide-react";
import Shell from "../components/Shell";
import { api } from "../api";
import { useAuth } from "../providers";
import type { CustomerLead, LeadActivity, StaffUser, Vehicle } from "../lib/types";

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

function leadStatusBadge(status: LeadStatus) {
  switch (status) {
    case "won":
      return "crm-badge-success";
    case "lost":
      return "crm-badge-danger";
    case "test_drive_scheduled":
      return "crm-badge-info";
    case "qualified":
      return "crm-badge-purple";
    case "follow_up":
    case "contacted":
      return "crm-badge-warning";
    case "new":
    default:
      return "crm-badge-neutral";
  }
}

function LeadRow({
  lead,
  staff,
  saving,
  canManage,
  onSave,
  onConvert,
  onAutoAssign,
  onDelete,
  onViewActivities,
}: {
  lead: CustomerLead;
  staff: StaffUser[];
  saving: boolean;
  canManage: boolean;
  onSave: (
    leadId: number,
    status: LeadStatus | null,
    assignedToUserId: number | null,
    followUp: string | null,
    dealValue: number | null,
    dealNotes: string | null,
  ) => Promise<void>;
  onConvert: (leadId: number, bookingId: number) => Promise<void>;
  onAutoAssign: (leadId: number) => Promise<void>;
  onDelete: (leadId: number) => Promise<void>;
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
  const [dealNotes, setDealNotes] = useState(lead.deal_notes || "");
  const [bookingId, setBookingId] = useState("");

  useEffect(() => {
    setStatus(lead.status);
    setAssignee(lead.assigned_to_user_id ? String(lead.assigned_to_user_id) : "");
    setFollowUp(toLocalDateTime(lead.next_follow_up_at));
    setDealValue(lead.deal_value != null ? String(lead.deal_value) : "");
    setDealNotes(lead.deal_notes || "");
  }, [lead]);

  return (
    <tr>
      <td className="align-top">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-slate-900">{lead.name}</span>
          <span className={`crm-badge ${leadStatusBadge(lead.status)}`}>
            {lead.status.replaceAll("_", " ")}
          </span>
        </div>
        <a className="block text-xs font-medium text-blue-600 hover:underline mt-0.5" href={`mailto:${lead.email}`}>
          {lead.email}
        </a>
        <div className="text-xs text-slate-500">{lead.phone || "No phone"}</div>
        <p className="mt-2 max-w-xs whitespace-pre-wrap text-xs text-slate-600">{lead.message}</p>
        {(lead.budget != null || lead.purchase_timeline) && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {lead.budget != null && (
              <span className="crm-badge crm-badge-success">
                Budget: ${Number(lead.budget).toLocaleString()}
              </span>
            )}
            {lead.purchase_timeline && (
              <span className="crm-badge crm-badge-info">
                Timeline: {lead.purchase_timeline.replaceAll("_", " ")}
              </span>
            )}
          </div>
        )}
        <div className="mt-2 text-[11px] text-slate-400">
          {lead.source} · {new Date(lead.created_at).toLocaleDateString()}
          {lead.conversation_id ? ` · Conv #${lead.conversation_id}` : ""}
        </div>
      </td>

      <td className="align-top min-w-[200px]">
        <label className="block text-[11px] font-semibold text-slate-500 mb-1">Pipeline Status</label>
        <select
          value={status}
          onChange={(event) => setStatus(event.target.value as LeadStatus)}
          className="crm-select text-xs"
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

        {lead.test_drive_booking_id && (
          <div className="mt-1.5 text-xs font-medium text-emerald-700">
            Booking #{lead.test_drive_booking_id}
          </div>
        )}
        {lead.requested_vehicle_id && (
          <div className="mt-1 text-xs text-slate-500">Vehicle #{lead.requested_vehicle_id}</div>
        )}

        <label className="block text-[11px] font-semibold text-slate-500 mt-3 mb-1">Deal Value ($)</label>
        <input
          type="number"
          min={0}
          step="100"
          placeholder="Agreed price"
          value={dealValue}
          onChange={(event) => setDealValue(event.target.value)}
          className="crm-input text-xs"
        />
        <input
          type="text"
          placeholder="Deal / financing notes"
          value={dealNotes}
          onChange={(event) => setDealNotes(event.target.value)}
          className="crm-input text-xs mt-1.5"
        />
      </td>

      <td className="align-top min-w-[220px]">
        <label className="block text-[11px] font-semibold text-slate-500 mb-1">Assigned Rep</label>
        <select
          value={assignee}
          onChange={(event) => setAssignee(event.target.value)}
          className="crm-select text-xs"
        >
          <option value="">Unassigned</option>
          {staff.map((member) => (
            <option key={member.id} value={member.id}>
              {member.name}
            </option>
          ))}
        </select>

        <label className="block text-[11px] font-semibold text-slate-500 mt-3 mb-1">Next Follow-up</label>
        <input
          type="datetime-local"
          value={followUp}
          onChange={(event) => setFollowUp(event.target.value)}
          className="crm-input text-xs"
        />

        <div className="mt-3 flex flex-wrap gap-1.5">
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
                dealNotes.trim() || null,
              )
            }
            className="crm-btn-primary min-h-8 px-2.5 text-xs"
          >
            {saving ? "Saving..." : "Save"}
          </button>
          {canManage && !assignee && (
            <button
              type="button"
              disabled={saving}
              onClick={() => void onAutoAssign(lead.id)}
              className="crm-btn-secondary min-h-8 px-2.5 text-xs"
            >
              <Bot className="h-3.5 w-3.5 text-amber-500" /> Auto
            </button>
          )}
          <button
            type="button"
            onClick={() => onViewActivities(lead)}
            className="crm-btn-secondary min-h-8 px-2.5 text-xs"
          >
            <History className="h-3.5 w-3.5" /> Timeline
          </button>
          {canManage && (
            <button
              type="button"
              disabled={saving}
              onClick={() => void onDelete(lead.id)}
              className="crm-btn-danger min-h-8 px-2 text-xs"
              title="Delete lead"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </td>

      <td className="align-top min-w-[200px]">
        {lead.test_drive_booking_id || lead.status === "test_drive_scheduled" ? (
          <span className="crm-badge crm-badge-info">Linked to Booking</span>
        ) : (
          <div className="flex items-end gap-1.5">
            <label className="text-[11px] font-semibold text-slate-500">
              Link Booking ID
              <input
                type="number"
                min={1}
                value={bookingId}
                onChange={(event) => setBookingId(event.target.value)}
                className="crm-input mt-1 w-24 text-xs"
              />
            </label>
            <button
              type="button"
              disabled={!bookingId}
              onClick={() => onConvert(lead.id, Number(bookingId))}
              className="crm-btn-secondary min-h-8 px-2.5 text-xs"
            >
              Link
            </button>
          </div>
        )}
        <div className="mt-2.5 text-[11px] text-slate-500">
          {lead.consent_to_contact ? "Consent recorded" : "No consent"}
        </div>
      </td>
    </tr>
  );
}

export default function LeadsPage() {
  const { activeDealershipId, authReady, user } = useAuth();
  const [leads, setLeads] = useState<CustomerLead[]>([]);
  const [staff, setStaff] = useState<StaffUser[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingLeadId, setSavingLeadId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [showCreateForm, setShowCreateForm] = useState(false);

  // Create form state
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [budget, setBudget] = useState("");
  const [purchaseTimeline, setPurchaseTimeline] = useState("");
  const [requestedVehicleId, setRequestedVehicleId] = useState("");
  const [autoAssign, setAutoAssign] = useState(false);
  const [message, setMessage] = useState("");
  const [consent, setConsent] = useState(false);

  // Activity modal
  const [activityLead, setActivityLead] = useState<CustomerLead | null>(null);
  const [activities, setActivities] = useState<LeadActivity[]>([]);
  const [loadingActivities, setLoadingActivities] = useState(false);
  const [noteSummary, setNoteSummary] = useState("");

  const canManageTeam = user?.role === "dealership_admin" || user?.role === "manager";

  const loadLeads = useCallback(async () => {
    if (!authReady || !user) return;
    if (!activeDealershipId) {
      setLoading(false);
      setError("Select a dealership workspace to view leads.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const statusParam = statusFilter !== "all" ? `&status=${statusFilter}` : "";
      const [nextLeads, team, nextVehicles] = await Promise.all([
        api<CustomerLead[]>(`/dealerships/${activeDealershipId}/leads?limit=200${statusParam}`),
        canManageTeam
          ? api<StaffUser[]>(`/dealerships/${activeDealershipId}/staff`)
          : Promise.resolve(
              user?.role === "sales_rep"
                ? [
                    {
                      id: user.id,
                      dealership_id: activeDealershipId,
                      name: user.name,
                      email: user.email,
                      role: "sales_rep" as const,
                      is_active: true,
                    },
                  ]
                : [],
            ),
        api<Vehicle[]>(`/dealerships/${activeDealershipId}/vehicles`),
      ]);
      setLeads(nextLeads);
      setStaff(team);
      setVehicles(nextVehicles);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load customer leads.");
    } finally {
      setLoading(false);
    }
  }, [activeDealershipId, authReady, canManageTeam, statusFilter, user]);

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
          requested_vehicle_id: requestedVehicleId ? Number(requestedVehicleId) : null,
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
      setRequestedVehicleId("");
      setAutoAssign(false);
      setMessage("");
      setConsent(false);
      setShowCreateForm(false);
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
    dealNotes: string | null,
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
            ...(dealNotes !== null ? { deal_notes: dealNotes } : {}),
          }),
        },
      );
      setLeads((current) => current.map((lead) => (lead.id === leadId ? updated : lead)));
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
      setLeads((current) => current.map((lead) => (lead.id === leadId ? updated : lead)));
      setNotice("Lead auto-assigned to least-loaded available rep.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not auto-assign lead.");
    } finally {
      setSavingLeadId(null);
    }
  }

  async function deleteLead(leadId: number) {
    if (!activeDealershipId) return;
    setSavingLeadId(leadId);
    setError("");
    setNotice("");
    try {
      await api<void>(`/dealerships/${activeDealershipId}/leads/${leadId}`, {
        method: "DELETE",
      });
      setLeads((current) => current.filter((lead) => lead.id !== leadId));
      setNotice(`Lead #${leadId} deleted.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete lead.");
    } finally {
      setSavingLeadId(null);
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
      setLeads((current) => current.map((lead) => (lead.id === leadId ? updated : lead)));
      setNotice("Lead linked to its test-drive booking.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not link the booking.");
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

  const visibleLeads = leads.filter((lead) => {
    const q = searchTerm.trim().toLowerCase();
    if (!q) return true;
    return (
      lead.name.toLowerCase().includes(q) ||
      lead.email.toLowerCase().includes(q) ||
      (lead.phone && lead.phone.toLowerCase().includes(q)) ||
      lead.message.toLowerCase().includes(q)
    );
  });

  return (
    <Shell>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="mt-1 text-2xl font-medium text-[#171717] tabular-nums">Customer Leads</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            Capture inquiries, track budgets &amp; timelines, assign reps, and convert test drives into closed deals.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void loadLeads()}
            className="crm-btn-secondary"
          >
            <RefreshCw className="h-4 w-4" /> Refresh
          </button>
          <button
            type="button"
            onClick={() => setShowCreateForm((v) => !v)}
            className="crm-btn-primary"
          >
            <Plus className="h-4 w-4" /> {showCreateForm ? "Hide Form" : "New Lead"}
          </button>
        </div>
      </div>

      {error && (
        <div role="alert" className="mb-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
          {error}
        </div>
      )}
      {notice && (
        <div role="status" className="mb-4 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
          <CheckCircle2 className="h-4 w-4" />
          {notice}
        </div>
      )}

      {showCreateForm && (
        <form onSubmit={createLead} className="crm-card mb-6 p-5">
          <div className="mb-4 flex items-center gap-2 text-sm font-medium text-[#171717]">
            <UserRound className="h-4 w-4 text-blue-600" /> Add Customer Inquiry
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <input required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} placeholder="Customer name *" className="crm-input" />
            <input required type="email" maxLength={320} value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email address *" className="crm-input" />
            <input maxLength={32} value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Phone (optional)" className="crm-input" />
            <input type="number" min={0} step="100" value={budget} onChange={(e) => setBudget(e.target.value)} placeholder="Budget $ (optional)" className="crm-input" />
            <select value={purchaseTimeline} onChange={(e) => setPurchaseTimeline(e.target.value)} className="crm-select">
              <option value="">Timeline (optional)</option>
              <option value="immediate">Immediate</option>
              <option value="this_month">This Month</option>
              <option value="1_3_months">1-3 Months</option>
              <option value="researching">Researching</option>
            </select>
            <select value={requestedVehicleId} onChange={(e) => setRequestedVehicleId(e.target.value)} className="crm-select">
              <option value="">Vehicle of interest (optional)</option>
              {vehicles.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.model_year} {v.make} {v.model} ({v.stock_number})
                </option>
              ))}
            </select>
            <textarea required maxLength={2000} value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Inquiry details *" className="crm-textarea min-h-20 md:col-span-2" />
            <div className="flex flex-col justify-between gap-2 text-xs text-slate-600">
              <label className="flex items-start gap-2">
                <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-0.5 accent-blue-600" />
                Customer agreed to be contacted.
              </label>
              <label className="flex items-start gap-2">
                <input type="checkbox" checked={autoAssign} onChange={(e) => setAutoAssign(e.target.checked)} className="mt-0.5 accent-blue-600" />
                Auto-assign to available sales rep.
              </label>
              <button disabled={submitting || !consent} className="crm-btn-primary">
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                Create Lead
              </button>
            </div>
          </div>
        </form>
      )}

      {/* Filter Bar */}
      <div className="crm-card mb-5 p-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="relative w-full md:w-80">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search name, email, phone, message..."
            className="crm-input pl-9"
          />
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="font-medium text-slate-500">Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="crm-select w-auto"
          >
            <option value="all">All Statuses</option>
            <option value="new">New</option>
            <option value="contacted">Contacted</option>
            <option value="qualified">Qualified</option>
            <option value="test_drive_scheduled">Test Drive Scheduled</option>
            <option value="follow_up">Follow-up</option>
            <option value="won">Won (Car Sold)</option>
            <option value="lost">Lost</option>
          </select>
        </div>
      </div>

      {/* Leads Table */}
      <div className="crm-table-wrap">
        <table className="crm-table min-w-[980px]">
          <thead>
            <tr>
              <th>Customer Inquiry</th>
              <th>Pipeline &amp; Deal</th>
              <th>Ownership &amp; Actions</th>
              <th>Test Drive</th>
            </tr>
          </thead>
          <tbody>
            {visibleLeads.map((lead) => (
              <LeadRow
                key={lead.id}
                lead={lead}
                staff={staff}
                saving={savingLeadId === lead.id}
                canManage={canManageTeam}
                onSave={saveLead}
                onConvert={convertLead}
                onAutoAssign={autoAssignLead}
                onDelete={deleteLead}
                onViewActivities={openActivities}
              />
            ))}
          </tbody>
        </table>
        {loading ? (
          <div className="p-8 text-center text-sm text-slate-500">Loading customer leads...</div>
        ) : visibleLeads.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-500">
            No leads matched the current filters.
          </div>
        ) : null}
      </div>

      {/* Activity Timeline Modal */}
      {activityLead && (
        <div className="crm-modal-overlay">
          <div className="crm-modal p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <div>
                <h3 className="text-base font-medium text-[#171717]">
                  Activity Timeline · {activityLead.name}
                </h3>
                <p className="text-xs text-slate-500">
                  Lead #{activityLead.id} · {activityLead.email}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setActivityLead(null)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={addNoteActivity} className="flex gap-2">
              <input
                type="text"
                required
                value={noteSummary}
                onChange={(e) => setNoteSummary(e.target.value)}
                placeholder="Log a call summary, customer preference, or follow-up note..."
                className="crm-input flex-1"
              />
              <button type="submit" className="crm-btn-primary">
                Add Note
              </button>
            </form>

            {loadingActivities ? (
              <p className="text-xs text-slate-500">Loading activity timeline...</p>
            ) : activities.length === 0 ? (
              <p className="text-xs text-slate-500">No activity events recorded yet.</p>
            ) : (
              <div className="max-h-72 space-y-2.5 overflow-y-auto pr-1">
                {activities.map((act) => (
                  <div key={act.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs">
                    <div className="flex items-center justify-between text-[11px] text-slate-500">
                      <span className="crm-badge crm-badge-info uppercase">
                        {act.activity_type.replaceAll("_", " ")}
                      </span>
                      <span>{new Date(act.created_at).toLocaleString()}</span>
                    </div>
                    <p className="mt-1.5 text-slate-800">{act.summary}</p>
                    {act.actor_user_email && (
                      <p className="mt-1 text-[11px] text-slate-400">By: {act.actor_user_email}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </Shell>
  );
}
