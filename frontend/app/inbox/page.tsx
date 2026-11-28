"use client";

import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  Bot,
  Check,
  CheckCircle2,
  Filter,
  Globe,
  Hand,
  Mail,
  MessageCircle,
  MessageSquare,
  Phone,
  PhoneCall,
  RefreshCw,
  Search,
  Send,
  ShieldAlert,
  Sparkles,
  Tag,
  UserCheck,
  UserRound,
  X,
} from "lucide-react";
import Shell from "../components/Shell";
import { API_URL, api } from "../api";
import { useAuth } from "../providers";
import type {
  ConversationDetail,
  ConversationSummary,
  CustomerLead,
  GmailMailboxStatus,
  StaffUser,
} from "../lib/types";

function channelMeta(channel: string) {
  switch (channel) {
    case "whatsapp":
      return {
        label: "WhatsApp",
        icon: MessageCircle,
        badgeClass: "bg-emerald-50 text-emerald-700 border-emerald-200",
        dotClass: "bg-emerald-500 text-white",
      };
    case "voice":
      return {
        label: "Voice (Vapi)",
        icon: PhoneCall,
        badgeClass: "bg-violet-50 text-violet-700 border-violet-200",
        dotClass: "bg-violet-600 text-white",
      };
    case "email":
      return {
        label: "Email",
        icon: Mail,
        badgeClass: "bg-indigo-50 text-indigo-700 border-indigo-200",
        dotClass: "bg-indigo-600 text-white",
      };
    case "website":
    default:
      return {
        label: "Website",
        icon: Globe,
        badgeClass: "bg-blue-50 text-blue-700 border-blue-200",
        dotClass: "bg-blue-600 text-white",
      };
  }
}

function statusMeta(status: string, channel?: string) {
  switch (status) {
    case "handed_off":
      return {
        label: "Handoff",
        badgeClass: "bg-amber-50 text-amber-800 border-amber-200",
        dotClass: "bg-amber-500",
      };
    case "closed":
      return {
        label: "Closed",
        badgeClass: "bg-slate-100 text-slate-600 border-slate-200",
        dotClass: "bg-slate-400",
      };
    case "active":
    default:
      return {
        label: channel === "email" ? "Open" : "Active AI",
        badgeClass: "bg-emerald-50 text-emerald-700 border-emerald-200",
        dotClass: "bg-emerald-500",
      };
  }
}

function getInitials(value: string): string {
  const cleaned = value.trim();
  if (!cleaned) return "?";
  const parts = cleaned.split(/[\s@._-]+/).filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function formatShortTime(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();
  if (isToday) {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleDateString([], { day: "numeric", month: "short" });
}

function formatDateDivider(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  if (date.toDateString() === now.toDateString()) return "TODAY";
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) return "YESTERDAY";
  return date.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" }).toUpperCase();
}

function getEmailAttachments(
  value: unknown,
): { attachment_id: string; filename: string; size: number }[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is { attachment_id: string; filename: string; size: number } =>
      typeof item === "object" &&
      item !== null &&
      "attachment_id" in item &&
      typeof item.attachment_id === "string" &&
      "filename" in item &&
      typeof item.filename === "string" &&
      "size" in item &&
      typeof item.size === "number",
  );
}

export default function ConversationInboxPage() {
  const { activeDealershipId, authReady, user } = useAuth();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [selected, setSelected] = useState<ConversationDetail | null>(null);
  const [staff, setStaff] = useState<StaffUser[]>([]);
  const [leads, setLeads] = useState<CustomerLead[]>([]);
  const [channelFilter, setChannelFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [showChannelFilters, setShowChannelFilters] = useState(false);
  const [search, setSearch] = useState("");
  const [threadSearchOpen, setThreadSearchOpen] = useState(false);
  const [threadSearch, setThreadSearch] = useState("");
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [replyText, setReplyText] = useState("");
  const [handoffReason, setHandoffReason] = useState("");
  const [assigneeId, setAssigneeId] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [mailboxStatus, setMailboxStatus] = useState<GmailMailboxStatus | null>(null);
  const [emailSyncing, setEmailSyncing] = useState(false);
  const [autoSyncRequested, setAutoSyncRequested] = useState(false);

  const canManageTeam = user?.role === "dealership_admin" || user?.role === "manager";

  const loadConversations = useCallback(async (quiet = false) => {
    if (!authReady || !user) return;
    if (!activeDealershipId) {
      setLoadingList(false);
      return;
    }
    if (!quiet) setLoadingList(true);
    setError("");
    try {
      const params = new URLSearchParams({ page: "1", page_size: "100" });
      if (channelFilter !== "all") params.set("channel", channelFilter);
      if (statusFilter !== "all") params.set("status", statusFilter);
      if (search.trim()) params.set("search", search.trim());

      const [items, team, leadRows] = await Promise.all([
        api<ConversationSummary[]>(
          `/dealerships/${activeDealershipId}/conversations?${params.toString()}`,
        ),
        canManageTeam
          ? api<StaffUser[]>(`/dealerships/${activeDealershipId}/staff`)
          : Promise.resolve(
              user
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
        api<CustomerLead[]>(`/dealerships/${activeDealershipId}/leads?limit=200`).catch(
          () => [] as CustomerLead[],
        ),
      ]);
      setConversations(items);
      setStaff(team);
      setLeads(leadRows);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load conversations.");
    } finally {
      if (!quiet) setLoadingList(false);
    }
  }, [activeDealershipId, authReady, canManageTeam, channelFilter, search, statusFilter, user]);

  const syncEmail = useCallback(async () => {
    if (!activeDealershipId || !mailboxStatus?.connected) return;
    setEmailSyncing(true);
    setError("");
    try {
      const result = await api<{ threads: number; messages: number }>(
        `/dealerships/${activeDealershipId}/email-mailbox/sync`,
        { method: "POST" },
      );
      setNotice(
        result.messages
          ? `Synced ${result.messages} new email message${result.messages === 1 ? "" : "s"}.`
          : "Email is up to date.",
      );
      await loadConversations();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not sync email.");
    } finally {
      setEmailSyncing(false);
    }
  }, [activeDealershipId, loadConversations, mailboxStatus?.connected]);

  useEffect(() => {
    void loadConversations();
  }, [loadConversations]);

  useEffect(() => {
    if (!authReady || !user || !activeDealershipId) return;
    let timer: ReturnType<typeof setTimeout>;
    let cancelled = false;
    const poll = async () => {
      if (document.visibilityState === "visible") {
        await loadConversations(true);
      }
      if (!cancelled) timer = setTimeout(poll, 15_000);
    };
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        clearTimeout(timer);
        timer = setTimeout(poll, 1_000);
      }
    };
    timer = setTimeout(poll, 15_000);
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      cancelled = true;
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [activeDealershipId, authReady, loadConversations, user]);

  useEffect(() => {
    if (!authReady || !user || !activeDealershipId) return;
    let cancelled = false;
    api<GmailMailboxStatus>(`/dealerships/${activeDealershipId}/email-mailbox`)
      .then((status) => {
        if (!cancelled) setMailboxStatus(status);
      })
      .catch((cause) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Could not load email status.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activeDealershipId, authReady, user]);

  useEffect(() => {
    if (!authReady || !user || !activeDealershipId) return;
    let cancelled = false;
    const timer = setInterval(() => {
      if (document.visibilityState !== "visible") return;
      api<GmailMailboxStatus>(`/dealerships/${activeDealershipId}/email-mailbox`)
        .then((status) => {
          if (!cancelled) setMailboxStatus(status);
        })
        .catch((cause) => {
          if (!cancelled) {
            setError(cause instanceof Error ? cause.message : "Could not refresh email status.");
          }
        });
    }, 60_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [activeDealershipId, authReady, user]);

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    if (query.get("gmail_connected") === "1") {
      setNotice("Gmail connected. Syncing the shared inbox…");
      setAutoSyncRequested(true);
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  useEffect(() => {
    if (!autoSyncRequested || !mailboxStatus?.connected) return;
    setAutoSyncRequested(false);
    void syncEmail();
  }, [autoSyncRequested, mailboxStatus?.connected, syncEmail]);

  const leadByConversationId = useMemo(() => {
    const map = new Map<number, CustomerLead>();
    leads.forEach((lead) => {
      if (lead.conversation_id) {
        map.set(lead.conversation_id, lead);
      }
    });
    return map;
  }, [leads]);

  const handoffCount = useMemo(
    () => conversations.filter((c) => c.status === "handed_off").length,
    [conversations],
  );

  async function selectConversation(convId: number) {
    if (!activeDealershipId) return;
    setLoadingDetail(true);
    setError("");
    setThreadSearch("");
    try {
      const detail = await api<ConversationDetail>(
        `/dealerships/${activeDealershipId}/conversations/${convId}`,
      );
      setSelected(detail);
      setAssigneeId(detail.assigned_to_user_id ? String(detail.assigned_to_user_id) : "");
      setHandoffReason(detail.handoff_reason || "");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load transcript.");
    } finally {
      setLoadingDetail(false);
    }
  }

  async function updateStatus(
    nextStatus: "active" | "handed_off" | "closed",
    overrideAssigneeId?: string,
  ) {
    if (!activeDealershipId || !selected) return;
    const targetAssignee = overrideAssigneeId !== undefined ? overrideAssigneeId : assigneeId;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const updated = await api<ConversationDetail>(
        `/dealerships/${activeDealershipId}/conversations/${selected.id}/status`,
        {
          method: "PATCH",
          body: JSON.stringify({
            status: nextStatus,
            assigned_to_user_id: targetAssignee ? Number(targetAssignee) : null,
            handoff_reason: handoffReason.trim() || null,
          }),
        },
      );
      setSelected(updated);
      setConversations((prev) =>
        prev.map((item) => (item.id === updated.id ? { ...item, ...updated } : item)),
      );
      setNotice(`Conversation updated (${statusMeta(nextStatus).label}).`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update conversation.");
    } finally {
      setBusy(false);
    }
  }

  async function sendReply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeDealershipId || !selected || !replyText.trim()) return;
    setBusy(true);
    setError("");
    try {
      const created = await api<ConversationDetail["messages"][number]>(
        `/dealerships/${activeDealershipId}/conversations/${selected.id}/messages`,
        {
          method: "POST",
          body: JSON.stringify({ content: replyText.trim() }),
        },
      );
      setSelected((prev) =>
        prev
          ? {
              ...prev,
              messages: [...prev.messages, created],
              last_message_preview: created.content,
              message_count: prev.message_count + 1,
            }
          : prev,
      );
      setConversations((prev) =>
        prev.map((c) =>
          c.id === selected.id
            ? { ...c, last_message_preview: created.content, message_count: c.message_count + 1 }
            : c,
        ),
      );
      setReplyText("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not send reply.");
    } finally {
      setBusy(false);
    }
  }

  async function redactMessage(messageId: number) {
    if (!activeDealershipId || !selected) return;
    setBusy(true);
    setError("");
    try {
      const updated = await api<ConversationDetail["messages"][number]>(
        `/dealerships/${activeDealershipId}/conversations/${selected.id}/messages/${messageId}/redact`,
        { method: "POST", body: JSON.stringify({ reason: "Redacted by staff" }) },
      );
      setSelected((prev) =>
        prev
          ? {
              ...prev,
              messages: prev.messages.map((m) => (m.id === messageId ? updated : m)),
            }
          : prev,
      );
      setNotice("Message redacted.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not redact message.");
    } finally {
      setBusy(false);
    }
  }

  const selectedLead = useMemo(() => {
    if (!selected) return null;
    return (
      leadByConversationId.get(selected.id) ??
      leads.find(
        (l) =>
          l.email.toLowerCase() === selected.channel_user_id.toLowerCase() ||
          (l.phone && l.phone === selected.channel_user_id),
      ) ??
      null
    );
  }, [leadByConversationId, leads, selected]);

  const canReplyOnSelectedChannel =
    selected?.channel === "whatsapp" ||
    (selected?.channel === "email" && mailboxStatus?.connected === true);
  const replyUnavailableMessage =
    selected?.channel === "email"
      ? mailboxStatus?.connected
        ? ""
        : "Connect the shared Gmail mailbox in Settings to reply to email."
      : selected?.channel === "whatsapp"
        ? ""
        : "Replies are not available for this channel yet.";

  const filteredMessages = useMemo(() => {
    if (!selected) return [];
    const q = threadSearch.trim().toLowerCase();
    if (!q) return selected.messages;
    return selected.messages.filter((m) => m.content.toLowerCase().includes(q));
  }, [selected, threadSearch]);

  useEffect(() => {
    if (!activeDealershipId || !selected?.id) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const refreshSelectedConversation = async () => {
      if (document.visibilityState === "visible") {
        try {
          const detail = await api<ConversationDetail>(
            `/dealerships/${activeDealershipId}/conversations/${selected.id}`,
          );
          if (!cancelled) {
            setSelected((current) => current?.id === detail.id ? detail : current);
          }
        } catch (cause) {
          if (!cancelled) {
            setError(cause instanceof Error ? cause.message : "Could not refresh transcript.");
          }
        }
      }
      if (!cancelled) timer = setTimeout(refreshSelectedConversation, 15_000);
    };
    timer = setTimeout(refreshSelectedConversation, 15_000);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [activeDealershipId, selected?.id]);

  const selectedChannel = selected ? channelMeta(selected.channel) : null;
  const selectedStatus = selected ? statusMeta(selected.status, selected.channel) : null;
  const selectedDisplayName =
    selectedLead?.name || selected?.channel_user_id || "";

  return (
    <Shell>
      {/* Top Page Bar */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-100 text-violet-700">
            <MessageSquare className="h-4 w-4" />
          </div>
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-slate-900">
              Conversations
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {mailboxStatus?.connected ? (
            <button
              type="button"
              onClick={() => void syncEmail()}
              disabled={emailSyncing}
              className="crm-btn-secondary min-h-9 px-3 text-xs"
            >
              <Mail className="h-3.5 w-3.5" />
              {emailSyncing ? "Syncing…" : "Sync email"}
            </button>
          ) : mailboxStatus?.connected === false && canManageTeam ? (
            <Link href="/settings" className="crm-btn-secondary min-h-9 px-3 text-xs">
              <Mail className="h-3.5 w-3.5" />
              Connect email
            </Link>
          ) : null}
          <button
            type="button"
            onClick={() => void loadConversations()}
            className="crm-btn-secondary min-h-9 px-3 text-xs"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </button>
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div role="alert" className="mb-3 flex items-center justify-between rounded-xl border border-rose-200 bg-rose-50 px-4 py-2.5 text-xs text-rose-700">
          <span>{error}</span>
          <button type="button" onClick={() => setError("")}>
            <X className="h-4 w-4" />
          </button>
        </div>
      )}
      {notice && (
        <div role="status" className="mb-3 flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-xs text-emerald-700">
          <span className="flex items-center gap-1.5">
            <CheckCircle2 className="h-4 w-4" />
            {notice}
          </span>
          <button type="button" onClick={() => setNotice("")}>
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* 3-Column Reference-Style Inbox Shell */}
      <div className="grid grid-cols-1 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm lg:grid-cols-12 lg:min-h-[680px]">
        {/* LEFT COLUMN: My Inbox List */}
        <div className="flex flex-col border-b border-slate-200 lg:col-span-4 lg:border-b-0 lg:border-r xl:col-span-3">
          {/* Inbox Header */}
          <div className="flex items-center justify-between px-4 pt-4 pb-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-900">My Inbox</span>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
                {conversations.length}
              </span>
            </div>
            <button
              type="button"
              onClick={() => setShowChannelFilters((v) => !v)}
              className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors ${
                showChannelFilters || channelFilter !== "all"
                  ? "border-violet-300 bg-violet-50 text-violet-700"
                  : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
              }`}
            >
              <Filter className="h-3.5 w-3.5" /> Filter
            </button>
          </div>

          {/* Search Input */}
          <div className="px-4 pb-2.5">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search in your inbox"
                className="w-full rounded-xl border border-slate-200 bg-slate-50/60 py-2 pl-8 pr-3 text-xs text-slate-900 placeholder:text-slate-400 focus:border-violet-400 focus:bg-white focus:outline-none"
              />
            </div>

            {showChannelFilters && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {[
                  { id: "all", label: "All Channels" },
                  { id: "website", label: "Website" },
                  { id: "whatsapp", label: "WhatsApp" },
                  { id: "voice", label: "Voice" },
                  { id: "email", label: "Email" },
                ].map((ch) => (
                  <button
                    key={ch.id}
                    type="button"
                    onClick={() => setChannelFilter(ch.id)}
                    className={`rounded-lg px-2.5 py-1 text-[11px] font-medium border transition-colors ${
                      channelFilter === ch.id
                        ? "border-violet-300 bg-violet-50 text-violet-700"
                        : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    {ch.label}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Filter Pills Row (All | Handoffs | Active AI | Closed) */}
          <div className="flex flex-wrap items-center gap-1.5 border-b border-slate-100 px-4 pb-3">
            <button
              type="button"
              onClick={() => setStatusFilter("all")}
              className={`shrink-0 rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
                statusFilter === "all"
                  ? "bg-violet-100 text-violet-800"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              All
            </button>
            <button
              type="button"
              onClick={() => setStatusFilter("handed_off")}
              className={`inline-flex shrink-0 items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
                statusFilter === "handed_off"
                  ? "bg-violet-100 text-violet-800"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              Handoffs
              {handoffCount > 0 && (
                <span className="rounded-full bg-rose-100 px-1.5 py-0.2 text-[10px] font-semibold text-rose-700">
                  {handoffCount}
                </span>
              )}
            </button>
            <button
              type="button"
              onClick={() => setStatusFilter("active")}
              className={`shrink-0 rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
                statusFilter === "active"
                  ? "bg-violet-100 text-violet-800"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              Active AI
            </button>
            <button
              type="button"
              onClick={() => setStatusFilter("closed")}
              className={`shrink-0 rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
                statusFilter === "closed"
                  ? "bg-violet-100 text-violet-800"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              Closed
            </button>
          </div>

          {/* Conversation Cards */}
          <div className="flex-1 overflow-y-auto p-2.5 space-y-1.5 max-h-[600px]">
            {loadingList ? (
              <div className="p-8 text-center text-xs text-slate-400">Loading inbox...</div>
            ) : conversations.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">
                No conversations match your filters.
              </div>
            ) : (
              conversations.map((conv) => {
                const ch = channelMeta(conv.channel);
                const st = statusMeta(conv.status, conv.channel);
                const ChannelIcon = ch.icon;
                const isSelected = selected?.id === conv.id;
                const matchedLead = leadByConversationId.get(conv.id);
                const displayName = matchedLead?.name || conv.channel_user_id;
                const preview =
                  conv.channel === "email"
                    ? conv.email_subject || conv.last_message_preview || "Email conversation"
                    : conv.last_message_preview || "No messages yet";

                return (
                  <button
                    key={conv.id}
                    type="button"
                    onClick={() => void selectConversation(conv.id)}
                    className={`w-full rounded-xl border p-3 text-left transition-all ${
                      isSelected
                        ? "border-violet-300 bg-violet-50/40 shadow-sm"
                        : "border-transparent hover:border-slate-200 hover:bg-slate-50/70"
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      {/* Avatar with Corner Channel Badge */}
                      <div className="relative shrink-0">
                        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-50 text-xs font-semibold text-indigo-700 border border-indigo-100">
                          {getInitials(displayName)}
                        </div>
                        <span
                          className={`absolute -bottom-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full ring-2 ring-white ${ch.dotClass}`}
                          title={ch.label}
                        >
                          <ChannelIcon className="h-2.5 w-2.5" />
                        </span>
                      </div>

                      {/* Card Body */}
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate text-xs font-semibold text-slate-900">
                            {displayName}
                          </span>
                          <span className="shrink-0 text-[10px] text-slate-400">
                            {formatShortTime(conv.updated_at)}
                          </span>
                        </div>

                        <div className="mt-0.5 flex items-center justify-between gap-2">
                          <p className="flex items-center gap-1 truncate text-xs text-slate-500">
                            <ArrowUpRight className="h-3 w-3 shrink-0 text-amber-500" />
                            <span className="truncate">
                              {preview}
                            </span>
                          </p>
                          <span className="shrink-0 rounded-full bg-amber-100 px-1.5 py-0.2 text-[10px] font-semibold text-amber-800">
                            {conv.message_count}
                          </span>
                        </div>

                        {/* Tags + Assignee Footer */}
                        <div className="mt-2 flex items-center justify-between gap-1.5">
                          <div className="flex flex-wrap items-center gap-1">
                            <span className={`rounded-md border px-1.5 py-0.5 text-[10px] font-medium ${st.badgeClass}`}>
                              {st.label}
                            </span>
                            {matchedLead && (
                              <span className="rounded-md border border-teal-200 bg-teal-50 px-1.5 py-0.5 text-[10px] font-medium text-teal-700">
                                Lead #{matchedLead.id}
                              </span>
                            )}
                          </div>

                          {conv.assigned_to_name ? (
                            <span
                              className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-200 text-[9px] font-semibold text-slate-700"
                              title={`Assigned to ${conv.assigned_to_name}`}
                            >
                              {getInitials(conv.assigned_to_name)}
                            </span>
                          ) : (
                            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-100 text-slate-400">
                              <UserRound className="h-3 w-3" />
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* CENTER COLUMN: Active Conversation Thread */}
        <div className="flex flex-col border-b border-slate-200 bg-white lg:col-span-5 lg:border-b-0 lg:border-r xl:col-span-6">
          {!selected ? (
            <div className="flex flex-1 flex-col items-center justify-center p-10 text-center text-slate-400">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-50 text-violet-600">
                <MessageSquare className="h-6 w-6" />
              </div>
              <p className="text-sm font-semibold text-slate-800">Select a conversation</p>
              <p className="mt-1 max-w-xs text-xs text-slate-500">
                Pick a customer thread from the inbox to inspect messages, take over from AI, or reply directly.
              </p>
            </div>
          ) : loadingDetail ? (
            <div className="flex flex-1 items-center justify-center p-10 text-xs text-slate-400">
              Loading conversation...
            </div>
          ) : (
            <>
              {/* Thread Top Header */}
              <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3.5">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="relative shrink-0">
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-50 text-xs font-semibold text-indigo-700 border border-indigo-100">
                      {getInitials(selectedDisplayName)}
                    </div>
                    {selectedChannel && (
                      <span
                        className={`absolute -bottom-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full ring-2 ring-white ${selectedChannel.dotClass}`}
                      >
                        <selectedChannel.icon className="h-2.5 w-2.5" />
                      </span>
                    )}
                  </div>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-slate-900">
                      {selectedDisplayName}
                    </div>
                    <div className="flex items-center gap-1.5 text-[11px] text-slate-500 truncate">
                      {selected.status === "handed_off" ? (
                        <span className="inline-flex items-center gap-1 font-medium text-amber-600">
                          <ShieldAlert className="h-3 w-3" />
                          {selected.handoff_reason || "Handoff / Callback requested"}
                        </span>
                      ) : (
                        <span>
                          {selected.channel === "email"
                            ? `${selected.email_subject || "Email"} · Email · Conv #${selected.id}`
                            : `${selectedChannel?.label} · Conv #${selected.id}`}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Quick Icon Action Bar (Reference Style) */}
                <div className="flex items-center gap-1.5">
                  <span
                    className={`mr-1 h-2.5 w-2.5 rounded-full ${selectedStatus?.dotClass}`}
                    title={selectedStatus?.label}
                  />
                  <button
                    type="button"
                    onClick={() => setThreadSearchOpen((v) => !v)}
                    className={`rounded-lg p-1.5 transition-colors ${
                      threadSearchOpen
                        ? "bg-violet-100 text-violet-700"
                        : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
                    }`}
                    title="Search in conversation"
                  >
                    <Search className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    disabled={busy || selected.status === "active"}
                    onClick={() => void updateStatus("active")}
                    className="rounded-lg p-1.5 text-slate-500 hover:bg-emerald-50 hover:text-emerald-700 disabled:opacity-40"
                    title="Resume AI Assistant"
                  >
                    <Bot className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    disabled={busy || selected.status === "handed_off"}
                    onClick={() => void updateStatus("handed_off")}
                    className="rounded-lg p-1.5 text-slate-500 hover:bg-amber-50 hover:text-amber-700 disabled:opacity-40"
                    title="Request Human Handoff"
                  >
                    <Hand className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    disabled={busy || selected.status === "closed"}
                    onClick={() => void updateStatus("closed")}
                    className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800 disabled:opacity-40"
                    title="Close Conversation"
                  >
                    <CheckCircle2 className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {/* Collapsible In-Thread Search Bar */}
              {threadSearchOpen && (
                <div className="border-b border-slate-100 bg-slate-50/60 px-5 py-2.5">
                  <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-1.5">
                    <Search className="h-3.5 w-3.5 text-slate-400" />
                    <input
                      type="text"
                      value={threadSearch}
                      onChange={(e) => setThreadSearch(e.target.value)}
                      placeholder="Search messages in this thread..."
                      className="flex-1 bg-transparent text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none"
                    />
                    {threadSearch && (
                      <span className="text-[11px] text-slate-400">
                        {filteredMessages.length} found
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => {
                        setThreadSearch("");
                        setThreadSearchOpen(false);
                      }}
                      className="text-slate-400 hover:text-slate-700"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              )}

              {/* Message Feed */}
              <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4 max-h-[450px] bg-white">
                {filteredMessages.length === 0 ? (
                  <p className="py-12 text-center text-xs text-slate-400">
                    {threadSearch ? "No matching messages." : "No messages recorded."}
                  </p>
                ) : (
                  filteredMessages.map((msg, idx) => {
                    const prev = idx > 0 ? filteredMessages[idx - 1] : null;
                    const showDateDivider =
                      !prev ||
                      new Date(prev.created_at).toDateString() !==
                        new Date(msg.created_at).toDateString();

                    const isCustomer = msg.sender_type === "customer";
                    const isStaff = msg.sender_type === "staff";
                    const isSystem = msg.sender_type === "system";

                    return (
                      <div key={msg.id} className="space-y-2">
                        {showDateDivider && (
                          <div className="my-2 text-center text-[10px] font-medium tracking-wider text-slate-400">
                            {formatDateDivider(msg.created_at)}
                          </div>
                        )}

                        {isSystem ? (
                          <div className="text-center text-[11px] italic text-slate-400">
                            {msg.content} · {new Date(msg.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                          </div>
                        ) : (
                          <div className={`flex flex-col ${isCustomer ? "items-start" : "items-end"}`}>
                            <div
                              className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-xs leading-relaxed whitespace-pre-wrap ${
                                isCustomer
                                  ? "rounded-tl-sm bg-slate-100 text-slate-900"
                                  : isStaff
                                  ? "rounded-tr-sm bg-[#ede9fe] text-slate-900 border border-violet-200/70"
                                  : "rounded-tr-sm bg-[#f3f0ff] text-slate-800 border border-violet-100"
                              }`}
                            >
                              {msg.content}
                              {getEmailAttachments(msg.channel_metadata?.attachments).map(
                                (attachment) => (
                                  <a
                                    key={attachment.attachment_id}
                                    href={`${API_URL}/dealerships/${activeDealershipId}/email-mailbox/attachments/${msg.id}/${encodeURIComponent(attachment.attachment_id)}`}
                                    download={attachment.filename}
                                    className="mt-2 block rounded-lg border border-slate-200 bg-white/80 px-2.5 py-2 text-[11px] font-medium text-violet-700 hover:bg-violet-50"
                                  >
                                    {attachment.filename} ·{" "}
                                    {Math.max(1, Math.round(attachment.size / 1024))} KB
                                  </a>
                                ),
                              )}
                            </div>

                            <div className="mt-1 flex items-center gap-1.5 px-1 text-[10px] text-slate-400">
                              <span>
                                {isCustomer ? "Customer" : isStaff ? "Staff" : "AI Assistant"}
                              </span>
                              <span>·</span>
                              <span>
                                {new Date(msg.created_at).toLocaleTimeString([], {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}
                              </span>
                              {isStaff &&
                                typeof msg.channel_metadata?.provider_status === "string" && (
                                  <>
                                    <span>·</span>
                                    <span className="capitalize">
                                      {msg.channel_metadata.provider_status}
                                    </span>
                                  </>
                                )}
                              {canManageTeam && msg.content !== "[REDACTED BY STAFF]" && (
                                <button
                                  type="button"
                                  disabled={busy}
                                  onClick={() => void redactMessage(msg.id)}
                                  className="ml-1 font-medium text-rose-500 hover:underline"
                                >
                                  Redact
                                </button>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>

              {/* Bottom Reference-Style Composer */}
              <div className="border-t border-slate-100 bg-white px-4 pt-2.5 pb-3.5">
                <div className="mb-2 flex items-center justify-between text-[11px]">
                  <div className="flex items-center gap-2 text-slate-500">
                    <span className="inline-flex items-center gap-1 font-medium text-slate-700">
                      <UserCheck className="h-3.5 w-3.5 text-violet-600" />
                      Staff Reply
                    </span>
                    <span className="text-slate-300">·</span>
                    <span>
                      {selected.channel === "whatsapp"
                        ? "Sends via Twilio"
                        : selected.channel === "email"
                          ? "Sends via Gmail"
                          : "External reply unavailable"}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => void updateStatus(selected.status === "handed_off" ? "active" : "handed_off")}
                    className="inline-flex items-center gap-1 font-medium text-violet-700 hover:underline"
                  >
                    <Sparkles className="h-3.5 w-3.5" />
                    {selected.status === "handed_off" ? "Resume AI" : "Take Over"}
                  </button>
                </div>

                {canReplyOnSelectedChannel ? (
                  <form
                    onSubmit={sendReply}
                    className="flex items-center gap-2 rounded-xl border-2 border-violet-400 bg-white px-3 py-2 focus-within:border-violet-600"
                  >
                    {selectedChannel && (
                      <span
                        className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-md ${selectedChannel.dotClass}`}
                      >
                        <selectedChannel.icon className="h-3.5 w-3.5" />
                      </span>
                    )}
                    <input
                      type="text"
                      value={replyText}
                      onChange={(e) => setReplyText(e.target.value)}
                      placeholder={`Reply on ${selectedChannel?.label || "channel"}...`}
                      disabled={busy}
                      className="flex-1 bg-transparent text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none"
                    />
                    <button
                      type="submit"
                      disabled={busy || !replyText.trim()}
                      className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-violet-600 text-white transition-colors hover:bg-violet-700 disabled:opacity-40"
                      title="Send reply"
                    >
                      <Send className="h-3.5 w-3.5" />
                    </button>
                  </form>
                ) : (
                  <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                    {replyUnavailableMessage}
                    {selected.channel === "email" && (
                      <Link href="/settings" className="ml-1 font-medium text-violet-700 hover:underline">
                        Open Settings
                      </Link>
                    )}
                  </p>
                )}
              </div>
            </>
          )}
        </div>

        {/* RIGHT COLUMN: Contact & Lead Details Panel */}
        <div className="flex flex-col bg-slate-50/40 p-4 lg:col-span-3">
          {!selected ? (
            <div className="flex flex-1 flex-col items-center justify-center p-6 text-center text-xs text-slate-400">
              <UserRound className="mb-2 h-8 w-8 text-slate-300" />
              Contact &amp; lead metadata will appear here.
            </div>
          ) : (
            <div className="space-y-3">
              {/* Centered Profile Header */}
              <div className="flex flex-col items-center text-center pt-1 pb-2">
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-violet-100 text-base font-semibold text-violet-700 border border-violet-200">
                  {getInitials(selectedDisplayName)}
                </div>
                <h3 className="mt-2.5 text-sm font-semibold text-slate-900 truncate max-w-full">
                  {selectedDisplayName}
                </h3>
                <p className="text-[11px] text-slate-400">
                  ID: {selected.id} · {selectedChannel?.label}
                </p>

                {/* Status / Channel Tags */}
                <div className="mt-2.5 flex flex-wrap items-center justify-center gap-1.5">
                  {selectedStatus && (
                    <span className={`rounded-md border px-2 py-0.5 text-[11px] font-medium ${selectedStatus.badgeClass}`}>
                      {selectedStatus.label}
                    </span>
                  )}
                  {selectedLead && (
                    <span className="rounded-md border border-teal-200 bg-teal-50 px-2 py-0.5 text-[11px] font-medium text-teal-700">
                      Lead #{selectedLead.id}
                    </span>
                  )}
                </div>
              </div>

              {/* Bordered Detail Rows (Reference Style) */}
              <div className="space-y-2 text-xs">
                <div className="flex items-center gap-2.5 rounded-xl border border-slate-200 bg-white px-3 py-2.5">
                  <UserRound className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                  <span className="text-slate-400">Name:</span>
                  <span className="truncate font-medium text-slate-800">
                    {selectedLead?.name || "Guest Visitor"}
                  </span>
                </div>

                <div className="flex items-center gap-2.5 rounded-xl border border-slate-200 bg-white px-3 py-2.5">
                  <Phone className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                  <span className="text-slate-400">Phone:</span>
                  <span className="truncate font-medium text-slate-800">
                    {selectedLead?.phone || (selected.channel !== "website" ? selected.channel_user_id : "—")}
                  </span>
                </div>

                <div className="flex items-center gap-2.5 rounded-xl border border-slate-200 bg-white px-3 py-2.5">
                  <Mail className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                  <span className="text-slate-400">Email:</span>
                  <span className="truncate font-medium text-slate-800">
                    {selectedLead?.email || "—"}
                  </span>
                </div>

                <div className="flex items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2.5">
                  <div className="flex items-center gap-2.5">
                    <Tag className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                    <span className="text-slate-400">Source:</span>
                  </div>
                  {selectedChannel && (
                    <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium ${selectedChannel.badgeClass}`}>
                      <selectedChannel.icon className="h-3 w-3" />
                      {selectedChannel.label}
                    </span>
                  )}
                </div>

                {/* Assigned Rep Selector */}
                <div className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 space-y-1.5">
                  <label className="block text-[11px] font-medium text-slate-400">
                    Assigned Rep
                  </label>
                  <select
                    value={assigneeId}
                    onChange={(e) => {
                      const nextVal = e.target.value;
                      setAssigneeId(nextVal);
                      void updateStatus(selected.status as "active" | "handed_off" | "closed", nextVal);
                    }}
                    disabled={busy}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs text-slate-800 focus:border-violet-400 focus:outline-none"
                  >
                    <option value="">Unassigned</option>
                    {staff.map((member) => (
                      <option key={member.id} value={member.id}>
                        {member.name} ({member.role})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Handoff Reason / Note */}
                <div className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 space-y-1.5">
                  <label className="block text-[11px] font-medium text-slate-400">
                    Handoff / Callback Note
                  </label>
                  <div className="flex items-center gap-1.5">
                    <input
                      type="text"
                      value={handoffReason}
                      onChange={(e) => setHandoffReason(e.target.value)}
                      placeholder="Click to add note..."
                      className="flex-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs text-slate-800 placeholder:text-slate-400 focus:border-violet-400 focus:outline-none"
                    />
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void updateStatus(selected.status as "active" | "handed_off" | "closed")}
                      className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                      title="Save note"
                    >
                      <Check className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>

                {selectedLead && (
                  <div className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 space-y-1 text-[11px] text-slate-600">
                    <div className="font-medium text-slate-700">Matched Lead Details</div>
                    <div>Stage: <span className="font-medium capitalize">{selectedLead.status.replaceAll("_", " ")}</span></div>
                    {selectedLead.budget != null && (
                      <div>Budget: <span className="font-medium">${Number(selectedLead.budget).toLocaleString()}</span></div>
                    )}
                    {selectedLead.purchase_timeline && (
                      <div>Timeline: <span className="font-medium">{selectedLead.purchase_timeline.replaceAll("_", " ")}</span></div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </Shell>
  );
}
