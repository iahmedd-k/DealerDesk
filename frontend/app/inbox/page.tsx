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
      return {
        label: "WhatsApp",
        icon: MessageCircle,
        className: "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30",
      };
    case "voice":
      return {
        label: "Voice (Vapi)",
        icon: PhoneCall,
        className: "bg-purple-500/15 text-purple-300 border border-purple-500/30",
      };
    case "website":
    default:
      return {
        label: "Website",
        icon: Globe,
        className: "bg-blue-500/15 text-blue-300 border border-blue-500/30",
      };
  }
}

function statusBadge(status: string) {
  switch (status) {
    case "handed_off":
      return {
        label: "Handoff / Callback",
        className: "bg-amber-500/20 text-amber-300 border border-amber-500/30",
      };
    case "closed":
      return {
        label: "Closed",
        className: "bg-slate-500/20 text-slate-300 border border-slate-500/30",
      };
    case "active":
    default:
      return {
        label: "Active AI",
        className: "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30",
      };
  }
}

export default function ConversationInboxPage() {
  const { activeDealershipId, user } = useAuth();
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
  }, [activeDealershipId, canManageTeam, channelFilter, search, statusFilter, user]);

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
      setNotice(`Conversation marked as '${nextStatus}'.`);
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
          <p className="mb-1 text-xs font-bold uppercase tracking-wider text-blue-300">
            Multi-Channel Communications
          </p>
          <h1 className="text-2xl font-bold text-white">
            Conversation Inbox &amp; Handoff Queue
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Inspect Website, WhatsApp, and Voice (Vapi) transcripts, manage human handoffs, and reply to customers.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadConversations()}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800"
        >
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
      </div>

      {error ? (
        <div role="alert" className="mb-4 rounded-lg border border-rose-700 bg-rose-950/40 p-3 text-sm text-rose-200">
          {error}
        </div>
      ) : null}
      {notice ? (
        <div role="status" className="mb-4 flex items-center gap-2 rounded-lg border border-emerald-700 bg-emerald-950/40 p-3 text-sm text-emerald-200">
          <CheckCircle2 className="h-4 w-4" />
          {notice}
        </div>
      ) : null}

      {/* Filters Toolbar */}
      <div className="mb-5 flex flex-col gap-3 rounded-xl border border-slate-800 bg-slate-900/60 p-4 md:flex-row md:items-center md:justify-between">
        <div className="relative w-full md:w-72">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search phone, email, or session..."
            className="w-full rounded-lg border border-slate-700 bg-slate-950 py-2 pl-9 pr-3 text-xs text-white outline-none focus:border-blue-500"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-slate-400">Channel:</span>
          <select
            value={channelFilter}
            onChange={(e) => setChannelFilter(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-slate-200"
          >
            <option value="all">All Channels</option>
            <option value="website">Website</option>
            <option value="whatsapp">WhatsApp</option>
            <option value="voice">Voice (Vapi)</option>
          </select>

          <span className="ml-2 text-slate-400">Queue:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-slate-200"
          >
            <option value="all">All Conversations</option>
            <option value="handed_off">Handoff / Callback Queue</option>
            <option value="active">Active AI</option>
            <option value="closed">Closed</option>
          </select>
        </div>
      </div>

      {/* Split Inbox View */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        {/* Left Pane: Conversation List */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 lg:col-span-5">
          <div className="border-b border-slate-800 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Conversations ({conversations.length})
          </div>
          {loadingList ? (
            <div className="p-6 text-center text-xs text-slate-400">Loading conversations...</div>
          ) : conversations.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-400">
              No conversations match the selected filters.
            </div>
          ) : (
            <div className="max-h-[620px] divide-y divide-slate-800/80 overflow-y-auto">
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
                    className={`w-full p-4 text-left transition hover:bg-slate-800/60 ${
                      isSelected ? "bg-slate-800/80 border-l-2 border-blue-500" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${ch.className}`}>
                        <ChannelIcon className="h-3 w-3" /> {ch.label}
                      </span>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${st.className}`}>
                        {st.label}
                      </span>
                    </div>
                    <div className="mt-2 font-mono text-xs font-semibold text-white truncate">
                      {conv.channel_user_id}
                    </div>
                    {conv.last_message_preview ? (
                      <p className="mt-1 line-clamp-2 text-xs text-slate-400">
                        {conv.last_message_preview}
                      </p>
                    ) : null}
                    <div className="mt-2 flex items-center justify-between text-[10px] text-slate-500">
                      <span>
                        {conv.message_count} messages
                        {conv.assigned_to_name ? ` · Assigned: ${conv.assigned_to_name}` : ""}
                      </span>
                      <span>{new Date(conv.updated_at).toLocaleString()}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Pane: Transcript & Handoff Controls */}
        <div className="flex flex-col rounded-xl border border-slate-800 bg-slate-900/50 lg:col-span-7">
          {!selected ? (
            <div className="flex h-96 flex-col items-center justify-center p-8 text-center text-slate-400">
              <MessageSquare className="mb-3 h-8 w-8 text-slate-600" />
              <p className="text-sm font-medium text-slate-300">Select a conversation</p>
              <p className="mt-1 text-xs text-slate-500">
                View full Website, WhatsApp, or Voice transcripts and manage human handoffs.
              </p>
            </div>
          ) : loadingDetail ? (
            <div className="p-8 text-center text-xs text-slate-400">Loading transcript...</div>
          ) : (
            <>
              {/* Header & Handoff Controls */}
              <div className="border-b border-slate-800 p-4 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-bold text-white">
                        {selected.channel_user_id}
                      </span>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${statusBadge(selected.status).className}`}>
                        {statusBadge(selected.status).label}
                      </span>
                    </div>
                    <p className="mt-0.5 text-[11px] text-slate-400">
                      Conversation #{selected.id} · Channel: {selected.channel}
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-1.5">
                    <button
                      type="button"
                      disabled={busy || selected.status === "handed_off"}
                      onClick={() => void updateStatus("handed_off")}
                      className="rounded-lg border border-amber-500/40 bg-amber-500/15 px-2.5 py-1.5 text-xs font-semibold text-amber-200 hover:bg-amber-500/25 disabled:opacity-50"
                    >
                      Handoff / Callback
                    </button>
                    <button
                      type="button"
                      disabled={busy || selected.status === "active"}
                      onClick={() => void updateStatus("active")}
                      className="rounded-lg border border-emerald-500/40 bg-emerald-500/15 px-2.5 py-1.5 text-xs font-semibold text-emerald-200 hover:bg-emerald-500/25 disabled:opacity-50"
                    >
                      Resume AI
                    </button>
                    <button
                      type="button"
                      disabled={busy || selected.status === "closed"}
                      onClick={() => void updateStatus("closed")}
                      className="rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-700 disabled:opacity-50"
                    >
                      Close
                    </button>
                  </div>
                </div>

                {/* Staff Assignment & Handoff Reason */}
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <select
                    value={assigneeId}
                    onChange={(e) => setAssigneeId(e.target.value)}
                    className="rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-white"
                  >
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
                    className="rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-white"
                  />
                </div>
              </div>

              {/* Transcript Messages */}
              <div className="flex-1 space-y-3 overflow-y-auto p-4 max-h-[400px]">
                {selected.messages.length === 0 ? (
                  <p className="text-center text-xs text-slate-500">No messages recorded in this transcript.</p>
                ) : (
                  selected.messages.map((msg) => {
                    const isCustomer = msg.sender_type === "customer";
                    const isStaff = msg.sender_type === "staff";
                    const isSystem = msg.sender_type === "system";
                    if (isSystem) {
                      return (
                        <div key={msg.id} className="text-center text-[11px] italic text-slate-500">
                          {msg.content} · {new Date(msg.created_at).toLocaleTimeString()}
                        </div>
                      );
                    }
                    return (
                      <div
                        key={msg.id}
                        className={`flex flex-col ${isCustomer ? "items-start" : "items-end"}`}
                      >
                        <div className="mb-1 flex items-center gap-1.5 text-[10px] text-slate-400">
                          {isCustomer ? (
                            <UserRound className="h-3 w-3 text-slate-400" />
                          ) : isStaff ? (
                            <UserCheck className="h-3 w-3 text-amber-300" />
                          ) : (
                            <Bot className="h-3 w-3 text-blue-400" />
                          )}
                          <span className="uppercase font-semibold">{msg.sender_type}</span>
                          <span>· {new Date(msg.created_at).toLocaleTimeString()}</span>
                          {canManageTeam && msg.content !== "[REDACTED BY STAFF]" ? (
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => void redactMessage(msg.id)}
                              className="ml-1 text-[10px] text-rose-400 hover:text-rose-300 underline"
                            >
                              Redact
                            </button>
                          ) : null}
                        </div>
                        <div
                          className={`max-w-[85%] rounded-xl px-3.5 py-2 text-xs leading-relaxed whitespace-pre-wrap ${
                            isCustomer
                              ? "bg-slate-800 text-slate-100"
                              : isStaff
                              ? "bg-amber-600/25 border border-amber-500/30 text-amber-100"
                              : "bg-blue-600/25 border border-blue-500/30 text-blue-100"
                          }`}
                        >
                          {msg.content}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              {/* Staff Reply Box */}
              <form onSubmit={sendReply} className="border-t border-slate-800 p-3 flex gap-2">
                <input
                  type="text"
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder="Write a staff reply or callback note..."
                  disabled={busy}
                  className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white outline-none focus:border-blue-500"
                />
                <button
                  type="submit"
                  disabled={busy || !replyText.trim()}
                  className="btn-primary inline-flex items-center gap-1.5 text-xs disabled:opacity-50"
                >
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
