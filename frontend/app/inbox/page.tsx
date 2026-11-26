"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";
import {
  Bot,
  CheckCircle2,
  Globe,
  MessageCircle,
  MessageSquare,
  PhoneCall,
  RefreshCw,
  Search,
  Send,
  UserCheck,
  UserRound,
} from "lucide-react";
import Shell from "../components/Shell";
import { api } from "../api";
import { useAuth } from "../providers";
import type {
  ConversationDetail,
  ConversationSummary,
  StaffUser,
} from "../lib/types";

function channelBadge(channel: string) {
  switch (channel) {
    case "whatsapp":
      return { label: "WhatsApp", icon: MessageCircle, className: "crm-badge-success" };
    case "voice":
      return { label: "Voice (Vapi)", icon: PhoneCall, className: "crm-badge-purple" };
    case "website":
    default:
      return { label: "Website", icon: Globe, className: "crm-badge-info" };
  }
}

function statusBadge(status: string) {
  switch (status) {
    case "handed_off":
      return { label: "Handoff / Callback", className: "crm-badge-warning" };
    case "closed":
      return { label: "Closed", className: "crm-badge-neutral" };
    case "active":
    default:
      return { label: "Active AI", className: "crm-badge-success" };
  }
}

export default function ConversationInboxPage() {
  const { activeDealershipId, authReady, user } = useAuth();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [selected, setSelected] = useState<ConversationDetail | null>(null);
  const [staff, setStaff] = useState<StaffUser[]>([]);
  const [channelFilter, setChannelFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [replyText, setReplyText] = useState("");
  const [handoffReason, setHandoffReason] = useState("");
  const [assigneeId, setAssigneeId] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const canManageTeam = user?.role === "dealership_admin" || user?.role === "manager";

  const loadConversations = useCallback(async () => {
    if (!authReady || !user) return;
    if (!activeDealershipId) {
      setLoadingList(false);
      return;
    }
    setLoadingList(true);
    setError("");
    try {
      const params = new URLSearchParams({ page: "1", page_size: "50" });
      if (channelFilter !== "all") params.set("channel", channelFilter);
      if (statusFilter !== "all") params.set("status", statusFilter);
      if (search.trim()) params.set("search", search.trim());

      const [items, team] = await Promise.all([
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
      ]);
      setConversations(items);
      setStaff(team);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load conversations.");
    } finally {
      setLoadingList(false);
    }
  }, [activeDealershipId, authReady, canManageTeam, channelFilter, search, statusFilter, user]);

  useEffect(() => {
    void loadConversations();
  }, [loadConversations]);

  async function selectConversation(convId: number) {
    if (!activeDealershipId) return;
    setLoadingDetail(true);
    setError("");
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

  async function updateStatus(nextStatus: "active" | "handed_off" | "closed") {
    if (!activeDealershipId || !selected) return;
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
            assigned_to_user_id: assigneeId ? Number(assigneeId) : null,
            handoff_reason: handoffReason.trim() || null,
          }),
        },
      );
      setSelected(updated);
      setConversations((prev) =>
        prev.map((item) => (item.id === updated.id ? { ...item, ...updated } : item)),
      );
      setNotice(`Conversation marked as '${nextStatus.replaceAll("_", " ")}'.`);
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
        prev ? { ...prev, messages: [...prev.messages, created] } : prev,
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

  return (
    <Shell>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="mt-1 text-2xl font-medium text-[#171717] tabular-nums">
            Conversation Inbox &amp; Handoff Queue
          </h1>
          <p className="mt-0.5 text-sm text-slate-500">
            Review Website, WhatsApp, and Voice (Vapi) transcripts, manage human handoffs, and redact sensitive PII.
          </p>
        </div>
        <button type="button" onClick={() => void loadConversations()} className="crm-btn-secondary">
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
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

      {/* Filter Toolbar */}
      <div className="crm-card mb-5 p-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="relative w-full md:w-80">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search phone, email, or session..."
            className="crm-input pl-9"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2.5 text-xs">
          <span className="font-medium text-slate-500">Channel:</span>
          <select value={channelFilter} onChange={(e) => setChannelFilter(e.target.value)} className="crm-select w-auto">
            <option value="all">All Channels</option>
            <option value="website">Website</option>
            <option value="whatsapp">WhatsApp</option>
            <option value="voice">Voice (Vapi)</option>
          </select>

          <span className="font-medium text-slate-500 ml-1">Queue:</span>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="crm-select w-auto">
            <option value="all">All Conversations</option>
            <option value="handed_off">Handoff / Callback Queue</option>
            <option value="active">Active AI</option>
            <option value="closed">Closed</option>
          </select>
        </div>
      </div>

      {/* Split-Pane Inbox */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        {/* Conversation List */}
        <div className="crm-card overflow-hidden lg:col-span-5">
          <div className="border-b border-slate-200 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Conversations ({conversations.length})
          </div>
          {loadingList ? (
            <div className="p-6 text-center text-xs text-slate-500">Loading conversations...</div>
          ) : conversations.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-500">
              No conversations match the selected filters.
            </div>
          ) : (
            <div className="max-h-[620px] divide-y divide-slate-100 overflow-y-auto">
              {conversations.map((conv) => {
                const ch = channelBadge(conv.channel);
                const st = statusBadge(conv.status);
                const ChannelIcon = ch.icon;
                const isSelected = selected?.id === conv.id;
                return (
                  <button
                    key={conv.id}
                    type="button"
                    onClick={() => void selectConversation(conv.id)}
                    className={`w-full p-4 text-left transition hover:bg-slate-50 ${
                      isSelected ? "bg-blue-50/60 border-l-2 border-blue-600" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className={`crm-badge ${ch.className}`}>
                        <ChannelIcon className="h-3 w-3" /> {ch.label}
                      </span>
                      <span className={`crm-badge ${st.className}`}>{st.label}</span>
                    </div>
                    <div className="mt-2 font-mono text-xs font-semibold text-slate-900 truncate">
                      {conv.channel_user_id}
                    </div>
                    {conv.last_message_preview && (
                      <p className="mt-1 line-clamp-2 text-xs text-slate-600">
                        {conv.last_message_preview}
                      </p>
                    )}
                    <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
                      <span>
                        {conv.message_count} messages
                        {conv.assigned_to_name ? ` · ${conv.assigned_to_name}` : ""}
                      </span>
                      <span>{new Date(conv.updated_at).toLocaleString()}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Transcript Viewer */}
        <div className="crm-card flex flex-col overflow-hidden lg:col-span-7">
          {!selected ? (
            <div className="flex h-96 flex-col items-center justify-center p-8 text-center text-slate-500">
              <MessageSquare className="mb-3 h-8 w-8 text-slate-300" />
              <p className="text-sm font-semibold text-slate-700">Select a conversation</p>
              <p className="mt-1 text-xs text-slate-500">
                Inspect transcripts, assign staff, or trigger human handoffs.
              </p>
            </div>
          ) : loadingDetail ? (
            <div className="p-8 text-center text-xs text-slate-500">Loading transcript...</div>
          ) : (
            <>
              <div className="border-b border-slate-200 bg-slate-50/70 p-4 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-medium text-[#171717]">
                        {selected.channel_user_id}
                      </span>
                      <span className={`crm-badge ${statusBadge(selected.status).className}`}>
                        {statusBadge(selected.status).label}
                      </span>
                    </div>
                    <p className="mt-0.5 text-xs text-slate-500">
                      Conversation #{selected.id} · {selected.channel}
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-1.5">
                    <button
                      type="button"
                      disabled={busy || selected.status === "handed_off"}
                      onClick={() => void updateStatus("handed_off")}
                      className="crm-btn-secondary min-h-8 px-2.5 text-xs border-amber-300 text-amber-800 bg-amber-50 hover:bg-amber-100"
                    >
                      Handoff / Callback
                    </button>
                    <button
                      type="button"
                      disabled={busy || selected.status === "active"}
                      onClick={() => void updateStatus("active")}
                      className="crm-btn-secondary min-h-8 px-2.5 text-xs border-emerald-300 text-emerald-800 bg-emerald-50 hover:bg-emerald-100"
                    >
                      Resume AI
                    </button>
                    <button
                      type="button"
                      disabled={busy || selected.status === "closed"}
                      onClick={() => void updateStatus("closed")}
                      className="crm-btn-secondary min-h-8 px-2.5 text-xs"
                    >
                      Close
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <select value={assigneeId} onChange={(e) => setAssigneeId(e.target.value)} className="crm-select text-xs">
                    <option value="">Unassigned</option>
                    {staff.map((member) => (
                      <option key={member.id} value={member.id}>
                        {member.name} ({member.role})
                      </option>
                    ))}
                  </select>
                  <input
                    type="text"
                    value={handoffReason}
                    onChange={(e) => setHandoffReason(e.target.value)}
                    placeholder="Handoff / callback reason (optional)"
                    className="crm-input text-xs"
                  />
                </div>
              </div>

              <div className="flex-1 space-y-3 overflow-y-auto p-4 max-h-[400px] bg-white">
                {selected.messages.length === 0 ? (
                  <p className="text-center text-xs text-slate-400">No messages recorded.</p>
                ) : (
                  selected.messages.map((msg) => {
                    const isCustomer = msg.sender_type === "customer";
                    const isStaff = msg.sender_type === "staff";
                    const isSystem = msg.sender_type === "system";
                    if (isSystem) {
                      return (
                        <div key={msg.id} className="text-center text-[11px] italic text-slate-400">
                          {msg.content} · {new Date(msg.created_at).toLocaleTimeString()}
                        </div>
                      );
                    }
                    return (
                      <div key={msg.id} className={`flex flex-col ${isCustomer ? "items-start" : "items-end"}`}>
                        <div className="mb-1 flex items-center gap-1.5 text-[11px] text-slate-400">
                          {isCustomer ? (
                            <UserRound className="h-3 w-3" />
                          ) : isStaff ? (
                            <UserCheck className="h-3 w-3 text-amber-600" />
                          ) : (
                            <Bot className="h-3 w-3 text-blue-600" />
                          )}
                          <span className="uppercase font-semibold">{msg.sender_type}</span>
                          <span>· {new Date(msg.created_at).toLocaleTimeString()}</span>
                          {canManageTeam && msg.content !== "[REDACTED BY STAFF]" && (
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => void redactMessage(msg.id)}
                              className="ml-1 text-[11px] font-medium text-rose-600 hover:underline"
                            >
                              Redact
                            </button>
                          )}
                        </div>
                        <div
                          className={`max-w-[85%] rounded-xl px-3.5 py-2.5 text-xs leading-relaxed whitespace-pre-wrap ${
                            isCustomer
                              ? "bg-slate-100 text-slate-900 border border-slate-200"
                              : isStaff
                              ? "bg-amber-50 text-amber-950 border border-amber-200"
                              : "bg-blue-600 text-white"
                          }`}
                        >
                          {msg.content}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              <form onSubmit={sendReply} className="border-t border-slate-200 bg-slate-50 p-3 flex gap-2">
                <input
                  type="text"
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder="Write a staff reply or callback note..."
                  disabled={busy}
                  className="crm-input flex-1"
                />
                <button type="submit" disabled={busy || !replyText.trim()} className="crm-btn-primary">
                  <Send className="h-3.5 w-3.5" /> Send
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </Shell>
  );
}
