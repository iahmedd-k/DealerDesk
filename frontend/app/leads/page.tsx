"use client";

import {
  type ChangeEvent,
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Bot,
  Calendar,
  Car,
  CheckCircle2,
  Clock,
  Download,
  History,
  LayoutGrid,
  Loader2,
  List,
  Mail,
  MessageSquare,
  Phone,
  Plus,
  RefreshCw,
  Search,
  Send,
  SlidersHorizontal,
  Trash2,
  Upload,
  UserRound,
  X,
} from "lucide-react";
import Shell from "../components/Shell";
import { API_URL, api } from "../api";
import { useAuth } from "../providers";
import type {
  CustomerLead,
  LeadActivity,
  LeadQuote,
  StaffUser,
  Vehicle,
} from "../lib/types";

type LeadStatus =
  | "new"
  | "contacted"
  | "qualified"
  | "test_drive_scheduled"
  | "won"
  | "lost"
  | "follow_up";

const STATUS_LABELS: Record<LeadStatus, string> = {
  new: "New",
  contacted: "Contacted",
  qualified: "Qualified",
  test_drive_scheduled: "Test Drive",
  follow_up: "Follow-up",
  won: "Won (Sold)",
  lost: "Lost",
};

const PIPELINE_STAGES: LeadStatus[] = [
  "new",
  "contacted",
  "qualified",
  "test_drive_scheduled",
  "follow_up",
  "won",
  "lost",
];

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

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function formatCurrency(value: number | null | undefined): string {
  if (value == null) return "—";
  return `$${Number(value).toLocaleString()}`;
}

function estimateMonthlyPayment(principal: number, aprPercent: number, months: number): number {
  if (principal <= 0 || months <= 0) return 0;
  const monthlyRate = aprPercent / 1200;
  if (monthlyRate === 0) return principal / months;
  return (principal * monthlyRate) / (1 - (1 + monthlyRate) ** -months);
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
  const [viewMode, setViewMode] = useState<"table" | "board">("table");
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [selectedLeadIds, setSelectedLeadIds] = useState<number[]>([]);
  const [bulkStatus, setBulkStatus] = useState("");
  const [bulkAssignee, setBulkAssignee] = useState("");
  const [draggedLeadId, setDraggedLeadId] = useState<number | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

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
  const [emailConsent, setEmailConsent] = useState(false);
  const [smsConsent, setSmsConsent] = useState(false);
  const [whatsappConsent, setWhatsappConsent] = useState(false);

  // Slide-over drawer state
  const [selectedLead, setSelectedLead] = useState<CustomerLead | null>(null);
  const [drawerTab, setDrawerTab] = useState<"details" | "timeline">("details");
  const [editStatus, setEditStatus] = useState<LeadStatus>("new");
  const [editEmailConsent, setEditEmailConsent] = useState(false);
  const [editSmsConsent, setEditSmsConsent] = useState(false);
  const [editWhatsappConsent, setEditWhatsappConsent] = useState(false);
  const [editLostReason, setEditLostReason] = useState<
    NonNullable<CustomerLead["lost_reason"]> | ""
  >("");
  const [editAssignee, setEditAssignee] = useState("");
  const [editFollowUp, setEditFollowUp] = useState("");
  const [editDealValue, setEditDealValue] = useState("");
  const [editDealNotes, setEditDealNotes] = useState("");
  const [editTradeInVehicle, setEditTradeInVehicle] = useState("");
  const [editTradeInValue, setEditTradeInValue] = useState("");
  const [editDownPayment, setEditDownPayment] = useState("");
  const [editAprPercent, setEditAprPercent] = useState("");
  const [editLoanTermMonths, setEditLoanTermMonths] = useState("60");
  const [linkBookingId, setLinkBookingId] = useState("");

  // Activity timeline state
  const [activities, setActivities] = useState<LeadActivity[]>([]);
  const [loadingActivities, setLoadingActivities] = useState(false);
  const [quotes, setQuotes] = useState<LeadQuote[]>([]);
  const [loadingQuotes, setLoadingQuotes] = useState(false);
  const quoteRequestId = useRef(0);
  const [noteSummary, setNoteSummary] = useState("");
  const [followUpMessage, setFollowUpMessage] = useState("");
  const [composerMessage, setComposerMessage] = useState("");
  const [savingQuote, setSavingQuote] = useState(false);
  const [updatingQuoteId, setUpdatingQuoteId] = useState<number | null>(null);
  const [quoteSaveMessage, setQuoteSaveMessage] = useState("");

  const canManageTeam = user?.role === "dealership_admin" || user?.role === "manager";

  const staffById = useMemo(() => {
    const map = new Map<number, StaffUser>();
    staff.forEach((member) => map.set(member.id, member));
    return map;
  }, [staff]);

  const vehicleById = useMemo(() => {
    const map = new Map<number, Vehicle>();
    vehicles.forEach((v) => map.set(v.id, v));
    return map;
  }, [vehicles]);

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
      const overdueParam = overdueOnly ? "&overdue_only=true" : "";
      const [nextLeads, team, nextVehicles] = await Promise.all([
        api<CustomerLead[]>(
          `/dealerships/${activeDealershipId}/leads?limit=500${statusParam}${overdueParam}`,
        ),
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
      setSelectedLeadIds([]);
      setStaff(team);
      setVehicles(nextVehicles);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load customer leads.");
    } finally {
      setLoading(false);
    }
  }, [activeDealershipId, authReady, canManageTeam, overdueOnly, statusFilter, user]);

  useEffect(() => {
    void loadLeads();
  }, [loadLeads]);

  const syncDrawerFromLead = useCallback((lead: CustomerLead) => {
    setEditStatus(lead.status);
    setEditEmailConsent(lead.email_consent);
    setEditSmsConsent(lead.sms_consent);
    setEditWhatsappConsent(lead.whatsapp_consent);
    setEditLostReason(lead.lost_reason || "");
    setEditAssignee(lead.assigned_to_user_id ? String(lead.assigned_to_user_id) : "");
    setEditFollowUp(toLocalDateTime(lead.next_follow_up_at));
    setEditDealValue(lead.deal_value != null ? String(lead.deal_value) : "");
    setEditDealNotes(lead.deal_notes || "");
    setEditTradeInVehicle(lead.trade_in_vehicle || "");
    setEditTradeInValue(lead.trade_in_value != null ? String(lead.trade_in_value) : "");
    setEditDownPayment(lead.down_payment != null ? String(lead.down_payment) : "");
    setEditAprPercent(lead.apr_percent != null ? String(lead.apr_percent) : "");
    setEditLoanTermMonths(lead.loan_term_months != null ? String(lead.loan_term_months) : "60");
    setLinkBookingId("");
  }, []);

  async function loadActivitiesForLead(leadId: number) {
    if (!activeDealershipId) return;
    setLoadingActivities(true);
    try {
      const items = await api<LeadActivity[]>(
        `/dealerships/${activeDealershipId}/leads/${leadId}/activities`,
      );
      setActivities(items);
    } catch {
      setActivities([]);
    } finally {
      setLoadingActivities(false);
    }
  }

  async function loadQuotesForLead(leadId: number) {
    if (!activeDealershipId) return;
    const requestId = ++quoteRequestId.current;
    setLoadingQuotes(true);
    setQuotes([]);
    try {
      const items = await api<LeadQuote[]>(
        `/dealerships/${activeDealershipId}/leads/${leadId}/quotes`,
      );
      if (requestId === quoteRequestId.current) setQuotes(items);
    } catch (cause) {
      if (requestId === quoteRequestId.current) {
        setError(cause instanceof Error ? cause.message : "Could not load quote history.");
      }
    } finally {
      if (requestId === quoteRequestId.current) setLoadingQuotes(false);
    }
  }

  function openLeadDrawer(lead: CustomerLead, tab: "details" | "timeline" = "details") {
    setSelectedLead(lead);
    setDrawerTab(tab);
    setNoteSummary("");
    setComposerMessage("");
    setQuoteSaveMessage("");
    setFollowUpMessage(
      `Hi ${lead.name}, following up on your vehicle inquiry. Let me know if you have any questions.`,
    );
    syncDrawerFromLead(lead);
    void loadActivitiesForLead(lead.id);
    void loadQuotesForLead(lead.id);
  }

  async function composeLeadFollowUp(channel: "email" | "sms" | "whatsapp") {
    if (!selectedLead || !activeDealershipId || !followUpMessage.trim()) return;
    const channelConsent = {
      email: selectedLead.email_consent,
      sms: selectedLead.sms_consent,
      whatsapp: selectedLead.whatsapp_consent,
    };
    if (!channelConsent[channel]) {
      setComposerMessage(`${channel.toUpperCase()} permission must be recorded before contacting this lead.`);
      return;
    }

    const body = encodeURIComponent(followUpMessage.trim());
    let target: string;
    if (channel === "email") {
      if (!selectedLead.email) {
        setComposerMessage("This lead does not have an email address.");
        return;
      }
      target = `mailto:${encodeURIComponent(selectedLead.email)}?subject=${encodeURIComponent(
        "Following up on your vehicle inquiry",
      )}&body=${body}`;
    } else {
      if (!selectedLead.phone) {
        setComposerMessage("This lead does not have a phone number.");
        return;
      }
      const phoneDigits = selectedLead.phone.replace(/\D/g, "");
      if (channel === "whatsapp" && phoneDigits.length < 7) {
        setComposerMessage("This lead's phone number is not valid for WhatsApp.");
        return;
      }
      target =
        channel === "sms"
          ? `sms:${encodeURIComponent(selectedLead.phone)}?body=${body}`
          : `https://wa.me/${phoneDigits}?text=${body}`;
    }

    setComposerMessage("");
    window.open(
      target,
      "_blank",
      channel === "whatsapp" ? "noopener,noreferrer" : "noopener",
    );

    try {
      const activity = await api<LeadActivity>(
        `/dealerships/${activeDealershipId}/leads/${selectedLead.id}/activities`,
        {
          method: "POST",
          body: JSON.stringify({
            activity_type: channel === "email" ? "email" : "note",
            summary: `Opened ${channel} follow-up composer`,
            details: { channel, action: "composer_opened" },
          }),
        },
      );
      setActivities((current) => [activity, ...current]);
      setComposerMessage(
        `Opened ${channel} composer. Review and send it in your messaging app.`,
      );
    } catch (cause) {
      setComposerMessage(
        cause instanceof Error
          ? cause.message
          : "Could not log the follow-up composer activity.",
      );
    }
  }

  async function saveQuoteSnapshot() {
    if (!selectedLead || !activeDealershipId) return;
    const leadId = selectedLead.id;
    const requestId = ++quoteRequestId.current;
    setLoadingQuotes(false);
    const tradeInValue = Number(editTradeInValue || 0);
    const downPayment = Number(editDownPayment || 0);
    if (
      ![quotePrice, tradeInValue, downPayment, quoteApr, quoteTerm].every(Number.isFinite) ||
      quotePrice < 0 ||
      tradeInValue < 0 ||
      downPayment < 0 ||
      tradeInValue + downPayment > quotePrice ||
      quoteApr < 0 ||
      quoteApr > 50 ||
      quoteTerm < 1 ||
      quoteTerm > 120
    ) {
      setQuoteSaveMessage("Enter valid non-negative prices, APR up to 50%, and a 1-120 month term.");
      return;
    }
    setSavingQuote(true);
    setQuoteSaveMessage("");
    try {
      const vehicleLabel = quoteVehicle
        ? `${quoteVehicle.model_year} ${quoteVehicle.make} ${quoteVehicle.model}`
        : null;
      const quote = await api<LeadQuote>(
        `/dealerships/${activeDealershipId}/leads/${leadId}/quotes`,
        {
          method: "POST",
          body: JSON.stringify({
            vehicle_id: quoteVehicle?.id ?? null,
            vehicle_label: vehicleLabel,
            sale_price: quotePrice,
            trade_in_vehicle: editTradeInVehicle.trim() || null,
            trade_in_value: tradeInValue,
            down_payment: downPayment,
            apr_percent: quoteApr,
            loan_term_months: quoteTerm,
            notes: editDealNotes.trim() || null,
          }),
        },
      );
      if (requestId === quoteRequestId.current) {
        setQuotes((current) => [quote, ...current]);
        setQuoteSaveMessage(`Quote version ${quote.version} saved.`);
        void loadActivitiesForLead(leadId);
      }
    } catch (cause) {
      if (requestId === quoteRequestId.current) {
        setQuoteSaveMessage(
          cause instanceof Error ? cause.message : "Could not save this quote snapshot.",
        );
      }
    } finally {
      setSavingQuote(false);
    }
  }

  async function updateQuoteStatus(quote: LeadQuote, status: LeadQuote["status"]) {
    if (!selectedLead || !activeDealershipId) return;
    const leadId = selectedLead.id;
    const requestId = quoteRequestId.current;
    setUpdatingQuoteId(quote.id);
    try {
      const updated = await api<LeadQuote>(
        `/dealerships/${activeDealershipId}/leads/${leadId}/quotes/${quote.id}`,
        { method: "PATCH", body: JSON.stringify({ status }) },
      );
      if (requestId === quoteRequestId.current) {
        setQuotes((current) =>
          current.map((item) => (item.id === updated.id ? updated : item)),
        );
        setQuoteSaveMessage(`Quote version ${updated.version} marked ${updated.status}.`);
        void loadActivitiesForLead(leadId);
      }
    } catch (cause) {
      if (requestId === quoteRequestId.current) {
        setQuoteSaveMessage(
          cause instanceof Error ? cause.message : "Could not update quote status.",
        );
      }
    } finally {
      setUpdatingQuoteId(null);
    }
  }

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
          email_consent: emailConsent,
          sms_consent: smsConsent,
          whatsapp_consent: whatsappConsent,
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
      setEmailConsent(false);
      setSmsConsent(false);
      setWhatsappConsent(false);
      setShowCreateModal(false);
      setNotice("Lead created and contact consent recorded.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create the lead.");
    } finally {
      setSubmitting(false);
    }
  }

  async function saveSelectedLead(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeDealershipId || !selectedLead) return;
    setSavingLeadId(selectedLead.id);
    setError("");
    setNotice("");
    try {
      const updated = await api<CustomerLead>(
        `/dealerships/${activeDealershipId}/leads/${selectedLead.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            status: editStatus,
            email_consent: editEmailConsent,
            sms_consent: editSmsConsent,
            whatsapp_consent: editWhatsappConsent,
            ...(editStatus === "lost"
              ? { lost_reason: editLostReason || null }
              : {}),
            assigned_to_user_id: editAssignee ? Number(editAssignee) : null,
            next_follow_up_at: editFollowUp ? new Date(editFollowUp).toISOString() : null,
            ...(editDealValue !== "" ? { deal_value: Number(editDealValue) } : {}),
            ...(editDealNotes.trim() !== "" ? { deal_notes: editDealNotes.trim() } : {}),
            trade_in_vehicle: editTradeInVehicle.trim() || null,
            trade_in_value: editTradeInValue !== "" ? Number(editTradeInValue) : null,
            down_payment: editDownPayment !== "" ? Number(editDownPayment) : null,
            apr_percent: editAprPercent !== "" ? Number(editAprPercent) : null,
            loan_term_months: editLoanTermMonths !== "" ? Number(editLoanTermMonths) : null,
          }),
        },
      );
      setLeads((current) => current.map((l) => (l.id === updated.id ? updated : l)));
      setSelectedLead(updated);
      syncDrawerFromLead(updated);
      setNotice(`Saved updates for ${updated.name}.`);
      void loadActivitiesForLead(updated.id);
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
      setLeads((current) => current.map((l) => (l.id === leadId ? updated : l)));
      if (selectedLead?.id === leadId) {
        setSelectedLead(updated);
        syncDrawerFromLead(updated);
        void loadActivitiesForLead(leadId);
      }
      setNotice("Lead auto-assigned to least-loaded available rep.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not auto-assign lead.");
    } finally {
      setSavingLeadId(null);
    }
  }

  async function deleteLead(lead: CustomerLead) {
    if (!activeDealershipId) return;
    if (!window.confirm(`Delete lead "${lead.name}" (#${lead.id})? This cannot be undone.`)) {
      return;
    }
    setSavingLeadId(lead.id);
    setError("");
    setNotice("");
    try {
      await api<void>(`/dealerships/${activeDealershipId}/leads/${lead.id}`, {
        method: "DELETE",
      });
      setLeads((current) => current.filter((l) => l.id !== lead.id));
      if (selectedLead?.id === lead.id) {
        setSelectedLead(null);
      }
      setNotice(`Lead #${lead.id} deleted.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete lead.");
    } finally {
      setSavingLeadId(null);
    }
  }

  async function convertLead(leadId: number, bookingId: number) {
    if (!activeDealershipId) return;
    setSavingLeadId(leadId);
    setError("");
    setNotice("");
    try {
      const updated = await api<CustomerLead>(
        `/dealerships/${activeDealershipId}/leads/${leadId}/convert`,
        { method: "POST", body: JSON.stringify({ booking_id: bookingId }) },
      );
      setLeads((current) => current.map((l) => (l.id === leadId ? updated : l)));
      if (selectedLead?.id === leadId) {
        setSelectedLead(updated);
        syncDrawerFromLead(updated);
        void loadActivitiesForLead(leadId);
      }
      setNotice("Lead linked to its test-drive booking.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not link the booking.");
    } finally {
      setSavingLeadId(null);
    }
  }

  async function addNoteActivity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeDealershipId || !selectedLead || !noteSummary.trim()) return;
    try {
      const created = await api<LeadActivity>(
        `/dealerships/${activeDealershipId}/leads/${selectedLead.id}/activities`,
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

  async function applyBulkChanges() {
    if (!activeDealershipId || selectedLeadIds.length === 0) return;
    if (!bulkStatus && !bulkAssignee) {
      setError("Choose a stage or an owner for the selected leads.");
      return;
    }
    setError("");
    setNotice("");
    setSubmitting(true);
    try {
      const payload: {
        lead_ids: number[];
        status?: string;
        assigned_to_user_id?: number | null;
      } = { lead_ids: selectedLeadIds };
      if (bulkStatus) payload.status = bulkStatus;
      if (bulkAssignee) {
        payload.assigned_to_user_id =
          bulkAssignee === "__unassign__" ? null : Number(bulkAssignee);
      }
      const updated = await api<CustomerLead[]>(
        `/dealerships/${activeDealershipId}/leads/bulk`,
        { method: "POST", body: JSON.stringify(payload) },
      );
      const updatedById = new Map(updated.map((lead) => [lead.id, lead]));
      setLeads((current) => current.map((lead) => updatedById.get(lead.id) ?? lead));
      setSelectedLeadIds([]);
      setBulkStatus("");
      setBulkAssignee("");
      setNotice(`Updated ${updated.length} leads.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update selected leads.");
    } finally {
      setSubmitting(false);
    }
  }

  async function moveLeadToStage(lead: CustomerLead, stage: LeadStatus) {
    if (!activeDealershipId || lead.status === stage) return;
    if (stage === "test_drive_scheduled") {
      setError("Use the test-drive booking action to move a lead into this stage.");
      return;
    }
    if (stage === "lost") {
      openLeadDrawer(lead);
      setEditStatus("lost");
      setNotice("Choose a loss reason and save the lead to close it as lost.");
      return;
    }
    setError("");
    try {
      const updated = await api<CustomerLead>(
        `/dealerships/${activeDealershipId}/leads/${lead.id}`,
        { method: "PATCH", body: JSON.stringify({ status: stage }) },
      );
      setLeads((current) => current.map((item) => item.id === lead.id ? updated : item));
      setNotice(`${lead.name} moved to ${STATUS_LABELS[stage]}.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not move the lead.");
    }
  }

  async function importCsv(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Choose a .csv file.");
      return;
    }
    if (file.size > 2_000_000) {
      setError("CSV files must be smaller than 2 MB.");
      return;
    }
    if (!activeDealershipId) return;
    setError("");
    setNotice("");
    setSubmitting(true);
    try {
      const result = await api<{
        created: number;
        failed: number;
        errors: { row: number; error: string }[];
      }>(`/dealerships/${activeDealershipId}/leads/import`, {
        method: "POST",
        body: JSON.stringify({ csv_content: await file.text() }),
      });
      await loadLeads();
      const firstIssue = result.errors[0];
      setNotice(
        `Imported ${result.created} leads; ${result.failed} rows skipped.` +
          (firstIssue ? ` First issue: row ${firstIssue.row} — ${firstIssue.error}` : ""),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not import the CSV file.");
    } finally {
      setSubmitting(false);
    }
  }

  async function exportCsv() {
    if (!activeDealershipId) return;
    setError("");
    try {
      const params = new URLSearchParams();
      if (statusFilter !== "all") params.set("status", statusFilter);
      if (overdueOnly) params.set("overdue_only", "true");
      const response = await fetch(
        `${API_URL}/dealerships/${activeDealershipId}/leads/export?${params.toString()}`,
        { credentials: "include", headers: { Accept: "text/csv" } },
      );
      if (!response.ok) {
        let detail = `CSV export failed (${response.status}).`;
        try {
          const body = (await response.json()) as { detail?: string };
          if (body.detail) detail = body.detail;
        } catch {
          // Use the status message when the server does not return JSON.
        }
        throw new Error(detail);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "dealerdesk-leads.csv";
      link.click();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not export the leads.");
    }
  }

  const visibleLeads = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    if (!q) return leads;
    return leads.filter(
      (lead) =>
        lead.name.toLowerCase().includes(q) ||
        lead.email.toLowerCase().includes(q) ||
        (lead.phone && lead.phone.toLowerCase().includes(q)) ||
        lead.message.toLowerCase().includes(q),
    );
  }, [leads, searchTerm]);

  const metrics = useMemo(() => {
    const total = leads.length;
    const unassigned = leads.filter((l) => !l.assigned_to_user_id && l.status !== "won" && l.status !== "lost").length;
    const testDrives = leads.filter((l) => l.status === "test_drive_scheduled" || l.test_drive_booking_id != null).length;
    const pipelineValue = leads
      .filter((l) => l.status !== "lost")
      .reduce((acc, l) => acc + (l.deal_value != null ? Number(l.deal_value) : 0), 0);
    const overdue = leads.filter(
      (lead) =>
        lead.next_follow_up_at &&
        new Date(lead.next_follow_up_at).getTime() < Date.now() &&
        lead.status !== "won" &&
        lead.status !== "lost",
    ).length;
    return { total, unassigned, testDrives, pipelineValue, overdue };
  }, [leads]);

  const formatVehicleLabel = (vehicleId: number | null) => {
    if (!vehicleId) return null;
    const v = vehicleById.get(vehicleId);
    return v ? `${v.model_year} ${v.make} ${v.model}` : `Vehicle #${vehicleId}`;
  };
  const quoteVehicle = selectedLead?.requested_vehicle_id
    ? vehicleById.get(selectedLead.requested_vehicle_id)
    : undefined;
  const quotePrice = selectedLead
    ? editDealValue !== ""
      ? Number(editDealValue)
      : Number(quoteVehicle?.price ?? 0)
    : 0;
  const quotePrincipal = Math.max(
    0,
    quotePrice - Number(editTradeInValue || 0) - Number(editDownPayment || 0),
  );
  const quoteApr = Number(editAprPercent || 0);
  const quoteTerm = Number(editLoanTermMonths || 60);
  const quoteMonthly = estimateMonthlyPayment(quotePrincipal, quoteApr, quoteTerm);

  return (
    <Shell>
      {/* Page Header */}
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="crm-page-title mt-1">Customer Leads</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            Track inquiries, assign sales reps, schedule follow-ups, and convert test drives into closed deals.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => void exportCsv()} className="crm-btn-secondary">
            <Download className="h-4 w-4" /> Export CSV
          </button>
          {canManageTeam && (
            <label className="crm-btn-secondary cursor-pointer">
              <Upload className="h-4 w-4" /> Import CSV
              <input
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                disabled={submitting}
                onChange={(event) => void importCsv(event)}
              />
            </label>
          )}
          <button
            type="button"
            onClick={() => void loadLeads()}
            className="crm-btn-secondary"
          >
            <RefreshCw className="h-4 w-4" /> Refresh
          </button>
          <button
            type="button"
            onClick={() => setShowCreateModal(true)}
            className="crm-btn-primary"
          >
            <Plus className="h-4 w-4" /> New Lead
          </button>
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div role="alert" className="mb-4 flex items-center justify-between rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          <span>{error}</span>
          <button type="button" onClick={() => setError("")} className="text-rose-500 hover:text-rose-700">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}
      {notice && (
        <div role="status" className="mb-4 flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" />
            {notice}
          </span>
          <button type="button" onClick={() => setNotice("")} className="text-emerald-600 hover:text-emerald-800">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* KPI Strip */}
      <div className="mb-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <div className="crm-kpi">
          <div className="text-xs font-medium text-slate-500">Active Leads</div>
          <div className="mt-1 text-2xl font-semibold text-slate-900">{metrics.total}</div>
          <div className="mt-1 text-xs text-slate-400">Filtered view</div>
        </div>
        <div className="crm-kpi">
          <div className="text-xs font-medium text-slate-500">Unassigned</div>
          <div className="mt-1 text-2xl font-semibold text-amber-600">{metrics.unassigned}</div>
          <div className="mt-1 text-xs text-slate-400">Awaiting rep ownership</div>
        </div>
        <div className="crm-kpi">
          <div className="text-xs font-medium text-slate-500">Test Drives</div>
          <div className="mt-1 text-2xl font-semibold text-blue-700">{metrics.testDrives}</div>
          <div className="mt-1 text-xs text-slate-400">Booked or linked</div>
        </div>
        <div className="crm-kpi">
          <div className="text-xs font-medium text-slate-500">Pipeline Value</div>
          <div className="mt-1 text-2xl font-semibold text-emerald-700">
            ${metrics.pipelineValue.toLocaleString()}
          </div>
          <div className="mt-1 text-xs text-slate-400">Open &amp; won deals</div>
        </div>
        <button
          type="button"
          onClick={() => setOverdueOnly((current) => !current)}
          aria-pressed={overdueOnly}
          className={`crm-kpi text-left transition-colors ${
            overdueOnly ? "border-rose-300 bg-rose-50" : "hover:border-rose-200"
          }`}
        >
          <div className="text-xs font-medium text-slate-500">Overdue Follow-ups</div>
          <div className="mt-1 text-2xl font-semibold text-rose-700">{metrics.overdue}</div>
          <div className="mt-1 text-xs text-slate-400">Click to filter overdue items</div>
        </button>
      </div>

      {/* Filter Bar */}
      <div className="crm-card mb-5 flex flex-col gap-3 p-3.5 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search name, email, phone, inquiry..."
            className="crm-input pl-9"
          />
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="font-medium text-slate-500">Stage:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="crm-select w-auto min-w-[160px]"
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
        <div className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white p-1">
          <button
            type="button"
            onClick={() => setViewMode("table")}
            aria-pressed={viewMode === "table"}
            className={`rounded-md p-1.5 ${viewMode === "table" ? "bg-blue-50 text-blue-700" : "text-slate-500"}`}
            title="Table view"
          >
            <List className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => setViewMode("board")}
            aria-pressed={viewMode === "board"}
            className={`rounded-md p-1.5 ${viewMode === "board" ? "bg-blue-50 text-blue-700" : "text-slate-500"}`}
            title="Pipeline board"
          >
            <LayoutGrid className="h-4 w-4" />
          </button>
        </div>
      </div>

      {canManageTeam && selectedLeadIds.length > 0 && (
        <div className="crm-card mb-4 flex flex-wrap items-center gap-2 p-3">
          <span className="mr-2 text-xs font-medium text-slate-600">
            {selectedLeadIds.length} selected
          </span>
          <select
            value={bulkStatus}
            onChange={(event) => setBulkStatus(event.target.value)}
            className="crm-select w-auto min-w-36"
            aria-label="Bulk stage update"
          >
            <option value="">Change stage…</option>
            <option value="new">New</option>
            <option value="contacted">Contacted</option>
            <option value="qualified">Qualified</option>
            <option value="follow_up">Follow-up</option>
          </select>
          <select
            value={bulkAssignee}
            onChange={(event) => setBulkAssignee(event.target.value)}
            className="crm-select w-auto min-w-40"
            aria-label="Bulk owner update"
          >
            <option value="">Change owner…</option>
            <option value="__unassign__">Unassign</option>
            {staff.map((member) => (
              <option key={member.id} value={member.id}>{member.name}</option>
            ))}
          </select>
          <button
            type="button"
            disabled={submitting}
            onClick={() => void applyBulkChanges()}
            className="crm-btn-primary min-h-9 px-3 text-xs"
          >
            {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
            Apply
          </button>
          <button
            type="button"
            onClick={() => setSelectedLeadIds([])}
            className="crm-btn-secondary min-h-9 px-3 text-xs"
          >
            Clear
          </button>
        </div>
      )}

      {viewMode === "board" && (
        <div className="flex gap-3 overflow-x-auto pb-3">
          {PIPELINE_STAGES.map((stage) => {
            const stageLeads = visibleLeads.filter((lead) => lead.status === stage);
            const stageValue = stageLeads.reduce(
              (sum, lead) => sum + Number(lead.deal_value ?? 0),
              0,
            );
            return (
              <section
                key={stage}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  const lead = leads.find((item) => item.id === draggedLeadId);
                  if (lead) void moveLeadToStage(lead, stage);
                  setDraggedLeadId(null);
                }}
                className="w-[270px] shrink-0 rounded-xl border border-slate-200 bg-slate-50 p-2.5"
                aria-label={`${STATUS_LABELS[stage]} leads`}
              >
                <header className="mb-2 flex items-center justify-between px-1">
                  <div>
                    <h2 className="text-xs font-semibold text-slate-700">{STATUS_LABELS[stage]}</h2>
                    <p className="text-[11px] text-slate-500">{formatCurrency(stageValue)}</p>
                  </div>
                  <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-slate-600">
                    {stageLeads.length}
                  </span>
                </header>
                <div className="space-y-2">
                  {stageLeads.map((lead) => (
                    <article
                      key={lead.id}
                      draggable
                      onDragStart={() => setDraggedLeadId(lead.id)}
                      onDragEnd={() => setDraggedLeadId(null)}
                      onClick={() => openLeadDrawer(lead)}
                      className={`cursor-grab rounded-lg border bg-white p-3 shadow-sm active:cursor-grabbing ${
                        draggedLeadId === lead.id ? "border-blue-300 opacity-50" : "border-slate-200"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <h3 className="truncate text-xs font-semibold text-slate-800">{lead.name}</h3>
                          <p className="truncate text-[11px] text-slate-500">{lead.email}</p>
                        </div>
                        <span className="shrink-0 text-[11px] font-semibold text-slate-700">
                          {formatCurrency(lead.deal_value)}
                        </span>
                      </div>
                      <p className="mt-2 line-clamp-2 text-[11px] text-slate-600">{lead.message}</p>
                      <div className="mt-3 flex items-center justify-between gap-2">
                        <span className="truncate text-[10px] text-slate-500">
                          {lead.assigned_to_user_id
                            ? staffById.get(lead.assigned_to_user_id)?.name ?? "Assigned"
                            : "Unassigned"}
                        </span>
                        <select
                          value={lead.status}
                          onClick={(event) => event.stopPropagation()}
                          onChange={(event) => void moveLeadToStage(lead, event.target.value as LeadStatus)}
                          aria-label={`Move ${lead.name} to stage`}
                          className="max-w-28 rounded border border-slate-200 bg-white px-1.5 py-1 text-[10px] text-slate-600"
                        >
                          {PIPELINE_STAGES.map((option) => (
                            <option key={option} value={option}>{STATUS_LABELS[option]}</option>
                          ))}
                        </select>
                      </div>
                      {lead.next_follow_up_at && (
                        <p className={`mt-2 text-[10px] ${
                          new Date(lead.next_follow_up_at).getTime() < Date.now()
                            ? "font-medium text-rose-600"
                            : "text-slate-500"
                        }`}>
                          Follow-up {new Date(lead.next_follow_up_at).toLocaleString()}
                        </p>
                      )}
                    </article>
                  ))}
                  {stageLeads.length === 0 && (
                    <p className="rounded-lg border border-dashed border-slate-200 bg-white p-4 text-center text-[11px] text-slate-400">
                      Drop a lead here
                    </p>
                  )}
                </div>
              </section>
            );
          })}
        </div>
      )}

      {/* Clean CRM Table */}
      {viewMode === "table" && <div className="crm-table-wrap">
        <table className="crm-table min-w-[960px]">
          <thead>
            <tr>
              <th>
                <input
                  type="checkbox"
                  aria-label="Select all visible leads"
                  checked={visibleLeads.length > 0 && visibleLeads.every((lead) => selectedLeadIds.includes(lead.id))}
                  onChange={(event) =>
                    setSelectedLeadIds(
                      event.target.checked ? visibleLeads.map((lead) => lead.id) : [],
                    )
                  }
                  className="accent-blue-600"
                />
              </th>
              <th>Customer</th>
              <th>Stage</th>
              <th>Interest &amp; Inquiry</th>
              <th>Deal Value</th>
              <th>Owner</th>
              <th>Follow-up / Booking</th>
              <th className="text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {visibleLeads.map((lead) => {
              const owner = lead.assigned_to_user_id ? staffById.get(lead.assigned_to_user_id) : null;
              const vehicleLabel = formatVehicleLabel(lead.requested_vehicle_id);
              const isSelected = selectedLead?.id === lead.id;

              return (
                <tr
                  key={lead.id}
                  onClick={() => openLeadDrawer(lead, "details")}
                  className={`cursor-pointer transition-colors ${isSelected ? "bg-blue-50/60" : ""}`}
                >
                  <td onClick={(event) => event.stopPropagation()}>
                    <input
                      type="checkbox"
                      aria-label={`Select ${lead.name}`}
                      checked={selectedLeadIds.includes(lead.id)}
                      onChange={(event) =>
                        setSelectedLeadIds((current) =>
                          event.target.checked
                            ? [...current, lead.id]
                            : current.filter((id) => id !== lead.id),
                        )
                      }
                      className="accent-blue-600"
                    />
                  </td>
                  {/* Customer */}
                  <td className="min-w-[230px]">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-700 border border-slate-200">
                        {getInitials(lead.name)}
                      </div>
                      <div className="min-w-0">
                        <div className="truncate font-medium text-slate-900">{lead.name}</div>
                        <div className="truncate text-xs text-slate-500">{lead.email}</div>
                        <div className="mt-0.5 text-[11px] text-slate-400">
                          {lead.phone || "No phone"} · {lead.source} · {new Date(lead.created_at).toLocaleDateString()}
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Stage */}
                  <td className="whitespace-nowrap">
                    <span className={`crm-badge ${leadStatusBadge(lead.status)}`}>
                      {STATUS_LABELS[lead.status] ?? lead.status.replaceAll("_", " ")}
                    </span>
                  </td>

                  {/* Interest & Inquiry */}
                  <td className="max-w-[280px]">
                    {vehicleLabel && (
                      <div className="mb-1 inline-flex items-center gap-1 rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-700">
                        <Car className="h-3 w-3 text-slate-500" />
                        {vehicleLabel}
                      </div>
                    )}
                    <p className="truncate text-xs text-slate-600" title={lead.message}>
                      {lead.message}
                    </p>
                    {(lead.budget != null || lead.purchase_timeline) && (
                      <div className="mt-1 flex flex-wrap gap-1.5 text-[11px] text-slate-500">
                        {lead.budget != null && (
                          <span>Budget: ${Number(lead.budget).toLocaleString()}</span>
                        )}
                        {lead.purchase_timeline && (
                          <span>· {lead.purchase_timeline.replaceAll("_", " ")}</span>
                        )}
                      </div>
                    )}
                  </td>

                  {/* Deal Value */}
                  <td className="whitespace-nowrap font-medium text-slate-900">
                    {formatCurrency(lead.deal_value)}
                  </td>

                  {/* Owner */}
                  <td className="whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                    {owner ? (
                      <div className="flex items-center gap-1.5 text-xs font-medium text-slate-700">
                        <span className="h-2 w-2 rounded-full bg-emerald-500" />
                        {owner.name}
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-400">Unassigned</span>
                        {canManageTeam && (
                          <button
                            type="button"
                            disabled={savingLeadId === lead.id}
                            onClick={() => void autoAssignLead(lead.id)}
                            className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-600 hover:bg-slate-50"
                            title="Auto-assign to least-loaded rep"
                          >
                            <Bot className="h-3 w-3 text-blue-600" /> Auto
                          </button>
                        )}
                      </div>
                    )}
                  </td>

                  {/* Follow-up / Booking */}
                  <td className="whitespace-nowrap">
                    {lead.test_drive_booking_id ? (
                      <span className="crm-badge crm-badge-info">
                        Booking #{lead.test_drive_booking_id}
                      </span>
                    ) : lead.next_follow_up_at ? (
                      <div className="flex items-center gap-1.5 text-xs text-slate-600">
                        <Clock className="h-3.5 w-3.5 text-slate-400" />
                        {new Date(lead.next_follow_up_at).toLocaleDateString()}
                      </div>
                    ) : (
                      <span className="text-xs text-slate-400">—</span>
                    )}
                  </td>

                  {/* Actions */}
                  <td className="whitespace-nowrap text-right" onClick={(e) => e.stopPropagation()}>
                    <div className="inline-flex items-center justify-end gap-1.5">
                      <button
                        type="button"
                        onClick={() => openLeadDrawer(lead, "details")}
                        className="crm-btn-secondary min-h-8 px-2.5 py-1 text-xs"
                      >
                        <SlidersHorizontal className="h-3.5 w-3.5" /> Manage
                      </button>
                      <button
                        type="button"
                        onClick={() => openLeadDrawer(lead, "timeline")}
                        className="crm-btn-secondary min-h-8 px-2 py-1 text-xs"
                        title="Activity Timeline"
                      >
                        <History className="h-3.5 w-3.5" />
                      </button>
                      {canManageTeam && (
                        <button
                          type="button"
                          disabled={savingLeadId === lead.id}
                          onClick={() => void deleteLead(lead)}
                          className="crm-btn-danger min-h-8 px-2 py-1 text-xs"
                          title="Delete lead"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {loading ? (
          <div className="p-10 text-center text-sm text-slate-500">Loading customer leads...</div>
        ) : visibleLeads.length === 0 ? (
          <div className="p-10 text-center text-sm text-slate-500">
            No leads matched the current filters.
          </div>
        ) : null}
      </div>}

      {/* Create Lead Modal */}
      {showCreateModal && (
        <div className="crm-modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="crm-modal max-w-2xl p-6" onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-center justify-between border-b border-slate-200 pb-3">
              <div className="flex items-center gap-2 text-base font-medium text-slate-900">
                <UserRound className="h-4 w-4 text-blue-600" /> Add Customer Lead
              </div>
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={createLead} className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-600">Customer Name *</label>
                  <input required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} placeholder="Jane Doe" className="crm-input" />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-600">Email Address *</label>
                  <input required type="email" maxLength={320} value={email} onChange={(e) => setEmail(e.target.value)} placeholder="jane@example.com" className="crm-input" />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-600">Phone</label>
                  <input maxLength={32} value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+1 (555) 010-2000" className="crm-input" />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-600">Budget ($)</label>
                  <input type="number" min={0} step="100" value={budget} onChange={(e) => setBudget(e.target.value)} placeholder="35000" className="crm-input" />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-600">Purchase Timeline</label>
                  <select value={purchaseTimeline} onChange={(e) => setPurchaseTimeline(e.target.value)} className="crm-select">
                    <option value="">Select timeline (optional)</option>
                    <option value="immediate">Immediate</option>
                    <option value="this_month">This Month</option>
                    <option value="1_3_months">1-3 Months</option>
                    <option value="researching">Researching</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-600">Vehicle of Interest</label>
                  <select value={requestedVehicleId} onChange={(e) => setRequestedVehicleId(e.target.value)} className="crm-select">
                    <option value="">Select vehicle (optional)</option>
                    {vehicles.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.model_year} {v.make} {v.model} ({v.stock_number})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Inquiry Details *</label>
                <textarea required maxLength={2000} value={message} onChange={(e) => setMessage(e.target.value)} placeholder="What vehicle or financing options is the customer asking about?" className="crm-textarea min-h-24" />
              </div>

              <div className="flex flex-col gap-2 rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="accent-blue-600" />
                  Customer agreed to be contacted regarding this inquiry.
                </label>
                <div className="grid gap-2 border-t border-slate-200 pt-2 sm:grid-cols-3">
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={emailConsent} onChange={(e) => setEmailConsent(e.target.checked)} className="accent-blue-600" />
                    Email permission
                  </label>
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={smsConsent} onChange={(e) => setSmsConsent(e.target.checked)} className="accent-blue-600" />
                    SMS permission
                  </label>
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={whatsappConsent} onChange={(e) => setWhatsappConsent(e.target.checked)} className="accent-blue-600" />
                    WhatsApp permission
                  </label>
                </div>
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={autoAssign} onChange={(e) => setAutoAssign(e.target.checked)} className="accent-blue-600" />
                  Auto-assign to least-loaded available sales rep.
                </label>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setShowCreateModal(false)} className="crm-btn-secondary">
                  Cancel
                </button>
                <button type="submit" disabled={submitting || !consent} className="crm-btn-primary">
                  {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                  Create Lead
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Slide-Over Lead Detail & Edit Drawer */}
      {selectedLead && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/35" onClick={() => setSelectedLead(null)}>
          <div
            className="flex h-full w-full max-w-xl flex-col bg-white shadow-2xl border-l border-slate-200"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Drawer Header */}
            <div className="flex items-start justify-between border-b border-slate-200 px-6 py-4">
              <div className="flex items-center gap-3 min-w-0">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-50 text-sm font-semibold text-blue-700 border border-blue-200">
                  {getInitials(selectedLead.name)}
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="truncate text-base font-semibold text-slate-900">
                      {selectedLead.name}
                    </h2>
                    <span className={`crm-badge ${leadStatusBadge(selectedLead.status)}`}>
                      {STATUS_LABELS[selectedLead.status] ?? selectedLead.status.replaceAll("_", " ")}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs text-slate-500">
                    Lead #{selectedLead.id} · {selectedLead.source} · Added{" "}
                    {new Date(selectedLead.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedLead(null)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Drawer Tabs */}
            <div className="flex border-b border-slate-200 px-6">
              <button
                type="button"
                onClick={() => setDrawerTab("details")}
                className={`border-b-2 px-3 py-2.5 text-xs font-medium transition-colors ${
                  drawerTab === "details"
                    ? "border-blue-600 text-blue-700"
                    : "border-transparent text-slate-500 hover:text-slate-800"
                }`}
              >
                Pipeline &amp; Details
              </button>
              <button
                type="button"
                onClick={() => setDrawerTab("timeline")}
                className={`border-b-2 px-3 py-2.5 text-xs font-medium transition-colors ${
                  drawerTab === "timeline"
                    ? "border-blue-600 text-blue-700"
                    : "border-transparent text-slate-500 hover:text-slate-800"
                }`}
              >
                Activity Timeline ({activities.length})
              </button>
            </div>

            {/* Drawer Body */}
            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
              {drawerTab === "details" ? (
                <>
                  {/* Contact & Inquiry Summary */}
                  <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-3">
                    <div className="flex flex-wrap gap-4 text-xs">
                      <span className="inline-flex items-center gap-1.5 font-medium text-slate-600">
                        <Mail className="h-3.5 w-3.5" />
                        {selectedLead.email}
                      </span>
                      <span className="inline-flex items-center gap-1.5 text-slate-600">
                        <Phone className="h-3.5 w-3.5 text-slate-400" />
                        {selectedLead.phone || "No phone provided"}
                      </span>
                    </div>

                    <div className="text-xs text-slate-700 whitespace-pre-wrap rounded-lg bg-white p-3 border border-slate-200/80">
                      {selectedLead.message}
                    </div>

                    <div className="flex flex-wrap items-center gap-2 text-[11px]">
                      {selectedLead.requested_vehicle_id && (
                        <span className="crm-badge crm-badge-info">
                          <Car className="h-3 w-3" />
                          {formatVehicleLabel(selectedLead.requested_vehicle_id)}
                        </span>
                      )}
                      {selectedLead.budget != null && (
                        <span className="crm-badge crm-badge-success">
                          Budget: ${Number(selectedLead.budget).toLocaleString()}
                        </span>
                      )}
                      {selectedLead.purchase_timeline && (
                        <span className="crm-badge crm-badge-neutral">
                          Timeline: {selectedLead.purchase_timeline.replaceAll("_", " ")}
                        </span>
                      )}
                      <span className="text-slate-500">
                        Channel permissions: email {selectedLead.email_consent ? "granted" : "not granted"},
                        SMS {selectedLead.sms_consent ? "granted" : "not granted"},
                        WhatsApp {selectedLead.whatsapp_consent ? "granted" : "not granted"}
                      </span>
                    </div>
                  </div>

                  <section
                    id="lead-followup-composer"
                    className="rounded-xl border border-slate-200 p-4"
                  >
                    <div className="mb-3 flex items-center gap-2">
                      <MessageSquare className="h-4 w-4 text-slate-500" />
                      <h3 className="text-sm font-semibold text-slate-900">Follow-up composer</h3>
                    </div>
                    <textarea
                      value={followUpMessage}
                      onChange={(event) => setFollowUpMessage(event.target.value)}
                      rows={3}
                      maxLength={2000}
                      aria-label="Follow-up message"
                      className="crm-input resize-y"
                      placeholder="Write a follow-up message..."
                    />
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        type="button"
                        disabled={!selectedLead.email_consent || !selectedLead.email || !followUpMessage.trim()}
                        onClick={() => void composeLeadFollowUp("email")}
                        className="crm-btn-secondary min-h-8 px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <Mail className="h-3.5 w-3.5" />
                        Email
                      </button>
                      <button
                        type="button"
                        disabled={!selectedLead.sms_consent || !selectedLead.phone || !followUpMessage.trim()}
                        onClick={() => void composeLeadFollowUp("sms")}
                        className="crm-btn-secondary min-h-8 px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <Send className="h-3.5 w-3.5" />
                        SMS
                      </button>
                      <button
                        type="button"
                        disabled={!selectedLead.whatsapp_consent || !selectedLead.phone || !followUpMessage.trim()}
                        onClick={() => void composeLeadFollowUp("whatsapp")}
                        className="crm-btn-secondary min-h-8 px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <MessageSquare className="h-3.5 w-3.5" />
                        WhatsApp
                      </button>
                    </div>
                    <p className="mt-2 text-[11px] text-slate-500">
                      Opens your email or messaging app; review and send there. Consent is required.
                    </p>
                    {composerMessage && (
                      <p
                        role="status"
                        className={`mt-2 text-xs ${
                          composerMessage.startsWith("Opened")
                            ? "text-emerald-700"
                            : "text-rose-700"
                        }`}
                      >
                        {composerMessage}
                      </p>
                    )}
                  </section>

                  {/* Pipeline Form */}
                  <form id="lead-edit-form" onSubmit={saveSelectedLead} className="space-y-4">
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <label className="mb-1 block text-xs font-medium text-slate-600">
                          Pipeline Stage
                        </label>
                        <select
                          value={editStatus}
                          onChange={(e) => setEditStatus(e.target.value as LeadStatus)}
                          className="crm-select"
                        >
                          {selectedLead.test_drive_booking_id || selectedLead.status === "test_drive_scheduled" ? (
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
                      </div>

                      <div>
                        <div className="mb-1 flex items-center justify-between">
                          <label className="text-xs font-medium text-slate-600">Assigned Rep</label>
                          {canManageTeam && !editAssignee && (
                            <button
                              type="button"
                              disabled={savingLeadId === selectedLead.id}
                              onClick={() => void autoAssignLead(selectedLead.id)}
                              className="inline-flex items-center gap-1 text-[11px] font-medium text-blue-600 hover:underline"
                            >
                              <Bot className="h-3 w-3" /> Auto-assign
                            </button>
                          )}
                        </div>
                        <select
                          value={editAssignee}
                          onChange={(e) => setEditAssignee(e.target.value)}
                          className="crm-select"
                        >
                          <option value="">Unassigned</option>
                          {staff.map((member) => (
                            <option key={member.id} value={member.id}>
                              {member.name}
                            </option>
                          ))}
                        </select>
                      </div>
                      {editStatus === "lost" && (
                        <div>
                          <label className="mb-1 block text-xs font-medium text-slate-600">
                            Loss reason
                          </label>
                          <select
                            required
                            value={editLostReason}
                            onChange={(event) =>
                              setEditLostReason(
                                event.target.value as NonNullable<
                                  CustomerLead["lost_reason"]
                                > | "",
                              )
                            }
                            className="crm-select"
                          >
                            <option value="">Select a reason</option>
                            <option value="price">Price</option>
                            <option value="vehicle_unavailable">Vehicle unavailable</option>
                            <option value="bought_elsewhere">Bought elsewhere</option>
                            <option value="financing">Financing</option>
                            <option value="timing">Timing</option>
                            <option value="no_response">No response</option>
                            <option value="other">Other</option>
                          </select>
                        </div>
                      )}

                      <div>
                        <label className="mb-1 block text-xs font-medium text-slate-600">
                          Next Follow-up
                        </label>
                        <input
                          type="datetime-local"
                          value={editFollowUp}
                          onChange={(e) => setEditFollowUp(e.target.value)}
                          className="crm-input"
                        />
                      </div>

                      <div>
                        <label className="mb-1 block text-xs font-medium text-slate-600">
                          Deal Value ($)
                        </label>
                        <input
                          type="number"
                          min={0}
                          step="100"
                          placeholder="Agreed price"
                          value={editDealValue}
                          onChange={(e) => setEditDealValue(e.target.value)}
                          className="crm-input"
                        />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs font-medium text-slate-600">
                          Trade-in Vehicle
                        </label>
                        <input
                          type="text"
                          maxLength={200}
                          placeholder="Year, make, model, condition"
                          value={editTradeInVehicle}
                          onChange={(event) => setEditTradeInVehicle(event.target.value)}
                          className="crm-input"
                        />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs font-medium text-slate-600">
                          Trade-in Allowance ($)
                        </label>
                        <input
                          type="number"
                          min={0}
                          step="100"
                          value={editTradeInValue}
                          onChange={(event) => setEditTradeInValue(event.target.value)}
                          className="crm-input"
                        />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs font-medium text-slate-600">
                          Down Payment ($)
                        </label>
                        <input
                          type="number"
                          min={0}
                          step="100"
                          value={editDownPayment}
                          onChange={(event) => setEditDownPayment(event.target.value)}
                          className="crm-input"
                        />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs font-medium text-slate-600">
                          APR (%)
                        </label>
                        <input
                          type="number"
                          min={0}
                          max={50}
                          step="0.01"
                          value={editAprPercent}
                          onChange={(event) => setEditAprPercent(event.target.value)}
                          className="crm-input"
                        />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs font-medium text-slate-600">
                          Term (months)
                        </label>
                        <input
                          type="number"
                          min={1}
                          max={120}
                          value={editLoanTermMonths}
                          onChange={(event) => setEditLoanTermMonths(event.target.value)}
                          className="crm-input"
                        />
                      </div>
                    </div>

                    <fieldset className="rounded-lg border border-slate-200 p-3">
                      <legend className="px-1 text-xs font-medium text-slate-600">
                        Contact permissions
                      </legend>
                      <div className="grid gap-2 text-xs text-slate-700 sm:grid-cols-3">
                        <label className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={editEmailConsent}
                            onChange={(event) => setEditEmailConsent(event.target.checked)}
                            className="accent-blue-600"
                          />
                          Email
                        </label>
                        <label className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={editSmsConsent}
                            onChange={(event) => setEditSmsConsent(event.target.checked)}
                            className="accent-blue-600"
                          />
                          SMS
                        </label>
                        <label className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={editWhatsappConsent}
                            onChange={(event) => setEditWhatsappConsent(event.target.checked)}
                            className="accent-blue-600"
                          />
                          WhatsApp
                        </label>
                      </div>
                      <p className="mt-2 text-[11px] text-slate-500">
                        Permission changes are added to the activity timeline. Save changes to apply them.
                      </p>
                    </fieldset>

                    <div>
                      <label className="mb-1 block text-xs font-medium text-slate-600">
                        Negotiation Notes
                      </label>
                      <textarea
                        rows={3}
                        placeholder="Trade-in details, financing terms, or negotiation notes..."
                        value={editDealNotes}
                        onChange={(e) => setEditDealNotes(e.target.value)}
                        className="crm-textarea"
                      />
                    </div>
                  </form>

                  <section className="print-quote rounded-xl border border-blue-100 bg-blue-50/50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h3 className="text-sm font-semibold text-slate-900">Deal Estimate</h3>
                        <p className="mt-1 text-[11px] text-slate-500">
                          {quoteVehicle
                            ? `${quoteVehicle.model_year} ${quoteVehicle.make} ${quoteVehicle.model}`
                            : "Vehicle and financing summary"}
                        </p>
                      </div>
                      <div className="print:hidden flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => window.print()}
                          className="crm-btn-secondary min-h-8 px-2.5 py-1 text-xs"
                        >
                          Print quote
                        </button>
                        <button
                          type="button"
                          disabled={savingQuote}
                          onClick={() => void saveQuoteSnapshot()}
                          className="crm-btn-secondary min-h-8 px-2.5 py-1 text-xs disabled:opacity-50"
                        >
                          {savingQuote ? "Saving..." : "Save quote"}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            const vehicleLabel = quoteVehicle
                              ? `${quoteVehicle.model_year} ${quoteVehicle.make} ${quoteVehicle.model}`
                              : "Selected vehicle";
                            setFollowUpMessage(
                              [
                                `Hi ${selectedLead.name},`,
                                "",
                                `Here is the estimate we discussed for ${vehicleLabel}:`,
                                `Sale price: ${formatCurrency(quotePrice)}`,
                                `Trade-in allowance: ${formatCurrency(Number(editTradeInValue || 0))}`,
                                `Down payment: ${formatCurrency(Number(editDownPayment || 0))}`,
                                `Estimated amount financed: ${formatCurrency(quotePrincipal)}`,
                                `APR / term: ${quoteApr}% / ${quoteTerm} months`,
                                `Estimated monthly payment: ${formatCurrency(quoteMonthly)}`,
                                "",
                                "Estimate only; excludes taxes, title, registration, dealer fees, lender approval, and other charges.",
                              ].join("\n"),
                            );
                            setComposerMessage("Estimate added to the follow-up draft.");
                            document
                              .getElementById("lead-followup-composer")
                              ?.scrollIntoView({ behavior: "smooth", block: "start" });
                          }}
                          className="crm-btn-secondary min-h-8 px-2.5 py-1 text-xs"
                        >
                          <Mail className="h-3.5 w-3.5" />
                          Draft email
                        </button>
                      </div>
                    </div>
                    {quoteSaveMessage && (
                      <p role="status" className="mt-2 text-xs text-slate-600">
                        {quoteSaveMessage}
                      </p>
                    )}
                    <dl className="mt-3 grid grid-cols-2 gap-3 text-xs sm:grid-cols-3">
                      <div><dt className="text-slate-500">Sale price</dt><dd className="mt-1 font-medium text-slate-800">{formatCurrency(quotePrice)}</dd></div>
                      <div><dt className="text-slate-500">Trade-in allowance</dt><dd className="mt-1 font-medium text-slate-800">{formatCurrency(Number(editTradeInValue || 0))}</dd></div>
                      <div><dt className="text-slate-500">Down payment</dt><dd className="mt-1 font-medium text-slate-800">{formatCurrency(Number(editDownPayment || 0))}</dd></div>
                      <div><dt className="text-slate-500">Estimated amount financed</dt><dd className="mt-1 font-medium text-slate-800">{formatCurrency(quotePrincipal)}</dd></div>
                      <div><dt className="text-slate-500">APR / term</dt><dd className="mt-1 font-medium text-slate-800">{quoteApr}% / {quoteTerm} months</dd></div>
                      <div><dt className="text-slate-500">Estimated monthly payment</dt><dd className="mt-1 text-base font-semibold text-blue-800">{formatCurrency(quoteMonthly)}</dd></div>
                    </dl>
                    {editTradeInVehicle && (
                      <p className="mt-3 text-[11px] text-slate-600">
                        Trade-in: {editTradeInVehicle}
                      </p>
                    )}
                    <p className="mt-3 text-[10px] text-slate-500">
                      Estimate only. Excludes taxes, title, registration, dealer fees, lender approval, and other charges.
                    </p>
                  </section>

                  <section className="rounded-xl border border-slate-200 bg-white p-4">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <div>
                        <h3 className="text-sm font-semibold text-slate-900">Quote history</h3>
                        <p className="mt-1 text-[11px] text-slate-500">
                          Saved quote terms remain as numbered snapshots.
                        </p>
                      </div>
                      {loadingQuotes && (
                        <span className="text-[11px] text-slate-400">Loading…</span>
                      )}
                    </div>
                    {!loadingQuotes && quotes.length === 0 ? (
                      <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-500">
                        No quote versions saved yet.
                      </p>
                    ) : (
                      <div className="space-y-2">
                        {quotes.map((quote) => (
                          <article
                            key={quote.id}
                            className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-100 p-3"
                          >
                            <div>
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="text-xs font-semibold text-slate-800">
                                  Version {quote.version}
                                </span>
                                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase text-slate-600">
                                  {quote.status}
                                </span>
                              </div>
                              <p className="mt-1 text-[11px] text-slate-500">
                                {quote.vehicle_label || "Vehicle estimate"} · {formatCurrency(quote.sale_price)}
                                {" · "}{quote.apr_percent}% / {quote.loan_term_months} months
                                {" · "}{formatCurrency(quote.estimated_monthly_payment)}/mo
                              </p>
                              <p className="mt-1 text-[10px] text-slate-400">
                                Saved {new Date(quote.created_at).toLocaleString()}
                              </p>
                            </div>
                            <div className="flex gap-1.5">
                              {quote.status === "draft" && (
                                <button
                                  type="button"
                                  disabled={updatingQuoteId !== null}
                                  onClick={() => void updateQuoteStatus(quote, "sent")}
                                  className="rounded-md border border-blue-200 px-2 py-1 text-[10px] font-semibold text-blue-700 hover:bg-blue-50 disabled:opacity-50"
                                >
                                  Mark sent
                                </button>
                              )}
                              {quote.status === "sent" && (
                                <>
                                  <button
                                    type="button"
                                    disabled={updatingQuoteId !== null}
                                    onClick={() => void updateQuoteStatus(quote, "accepted")}
                                    className="rounded-md border border-emerald-200 px-2 py-1 text-[10px] font-semibold text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
                                  >
                                    Accepted
                                  </button>
                                  <button
                                    type="button"
                                    disabled={updatingQuoteId !== null}
                                    onClick={() => void updateQuoteStatus(quote, "declined")}
                                    className="rounded-md border border-rose-200 px-2 py-1 text-[10px] font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                                  >
                                    Declined
                                  </button>
                                  <button
                                    type="button"
                                    disabled={updatingQuoteId !== null}
                                    onClick={() => void updateQuoteStatus(quote, "expired")}
                                    className="rounded-md border border-slate-200 px-2 py-1 text-[10px] font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                                  >
                                    Expired
                                  </button>
                                </>
                              )}
                            </div>
                          </article>
                        ))}
                      </div>
                    )}
                  </section>

                  {/* Test Drive Booking Link */}
                  <div className="rounded-xl border border-slate-200 p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-xs font-medium text-slate-700">
                        <Calendar className="h-4 w-4 text-slate-400" />
                        Test-Drive Booking
                      </div>
                      {selectedLead.test_drive_booking_id ? (
                        <span className="crm-badge crm-badge-success">
                          Linked to Booking #{selectedLead.test_drive_booking_id}
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400">Not linked</span>
                      )}
                    </div>

                    {!selectedLead.test_drive_booking_id && (
                      <div className="mt-3 flex items-center gap-2">
                        <input
                          type="number"
                          min={1}
                          placeholder="Enter Booking ID"
                          value={linkBookingId}
                          onChange={(e) => setLinkBookingId(e.target.value)}
                          className="crm-input text-xs"
                        />
                        <button
                          type="button"
                          disabled={!linkBookingId || savingLeadId === selectedLead.id}
                          onClick={() => void convertLead(selectedLead.id, Number(linkBookingId))}
                          className="crm-btn-secondary shrink-0 text-xs"
                        >
                          Link Booking
                        </button>
                      </div>
                    )}
                  </div>
                </>
              ) : (
                /* Activity Timeline Tab */
                <div className="space-y-4">
                  <form onSubmit={addNoteActivity} className="flex gap-2">
                    <input
                      type="text"
                      required
                      value={noteSummary}
                      onChange={(e) => setNoteSummary(e.target.value)}
                      placeholder="Log a call summary, customer preference, or follow-up note..."
                      className="crm-input flex-1"
                    />
                    <button type="submit" className="crm-btn-primary shrink-0">
                      Add Note
                    </button>
                  </form>

                  {loadingActivities ? (
                    <p className="text-xs text-slate-500">Loading activity timeline...</p>
                  ) : activities.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center text-xs text-slate-400">
                      No activity events recorded yet.
                    </div>
                  ) : (
                    <div className="space-y-2.5">
                      {activities.map((act) => (
                        <div key={act.id} className="rounded-xl border border-slate-200 bg-slate-50 p-3.5 text-xs">
                          <div className="flex items-center justify-between text-[11px] text-slate-500">
                            <span className="crm-badge crm-badge-info capitalize">
                              {act.activity_type.replaceAll("_", " ")}
                            </span>
                            <span>{new Date(act.created_at).toLocaleString()}</span>
                          </div>
                          <p className="mt-2 text-slate-800">{act.summary}</p>
                          {act.actor_user_email && (
                            <p className="mt-1 text-[11px] text-slate-400">By: {act.actor_user_email}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Drawer Footer */}
            {drawerTab === "details" && (
              <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50 px-6 py-3.5">
                {canManageTeam ? (
                  <button
                    type="button"
                    disabled={savingLeadId === selectedLead.id}
                    onClick={() => void deleteLead(selectedLead)}
                    className="crm-btn-danger text-xs"
                  >
                    <Trash2 className="h-3.5 w-3.5" /> Delete Lead
                  </button>
                ) : (
                  <span />
                )}
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setSelectedLead(null)}
                    className="crm-btn-secondary text-xs"
                  >
                    Close
                  </button>
                  <button
                    type="submit"
                    form="lead-edit-form"
                    disabled={savingLeadId === selectedLead.id}
                    className="crm-btn-primary text-xs"
                  >
                    {savingLeadId === selectedLead.id ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" /> Saving...
                      </>
                    ) : (
                      "Save Changes"
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </Shell>
  );
}
