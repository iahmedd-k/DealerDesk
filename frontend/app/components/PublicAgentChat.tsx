"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  Bot,
  Send,
  UserPlus,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
  X,
  Minimize2,
  MessageSquare,
  ExternalLink,
} from "lucide-react";
import { API_URL } from "../api";
import FormattedMessage from "./FormattedMessage";

interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  timestamp: string;
  intent?: string;
  sources?: { document_id: number; filename: string; page_number: number | null }[];
  isStreaming?: boolean;
}

interface PublicAgentChatProps {
  dealershipId: number;
  dealershipName?: string;
  embedded?: boolean;
  defaultMinimized?: boolean;
  isVerified?: boolean;
  verifying?: boolean;
}

const QUICK_PROMPTS = [
  "What vehicles do you have available right now?",
  "Can I book a test drive this week?",
  "What are your dealership hours and location?",
  "Tell me about your warranty & coverage options.",
];

export default function PublicAgentChat({
  dealershipId,
  dealershipName = "DealerDesk Showroom",
  embedded = false,
  defaultMinimized = false,
  isVerified = true,
  verifying = false,
}: PublicAgentChatProps) {
  const [minimized, setMinimized] = useState(defaultMinimized);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [visitorId, setVisitorId] = useState("web-visitor");

  const [leadModalOpen, setLeadModalOpen] = useState(false);
  const [leadName, setLeadName] = useState("");
  const [leadEmail, setLeadEmail] = useState("");
  const [leadPhone, setLeadPhone] = useState("");
  const [leadMessage, setLeadMessage] = useState("");
  const [leadConsent, setLeadConsent] = useState(true);
  const [leadSubmitting, setLeadSubmitting] = useState(false);
  const [leadSuccess, setLeadSuccess] = useState(false);
  const [leadError, setLeadError] = useState("");

  const endRef = useRef<HTMLDivElement>(null);
  const historyStorageKey = `dealerdesk_chat_history_${dealershipId}`;

  useEffect(() => {
    if (typeof window === "undefined") return;
    const key = `dealerdesk_visitor_${dealershipId}`;
    let existing = window.localStorage.getItem(key);
    if (!existing) {
      existing = `vis-${Math.random().toString(36).slice(2, 10)}`;
      window.localStorage.setItem(key, existing);
    }
    setVisitorId(existing);

    try {
      const saved = window.localStorage.getItem(historyStorageKey);
      if (saved) {
        const parsed = JSON.parse(saved) as ChatMessage[];
        if (Array.isArray(parsed)) {
          setMessages(parsed.map((m) => ({ ...m, isStreaming: false })));
        }
      }
    } catch {
      // Ignore corrupt local history
    }
  }, [dealershipId, historyStorageKey]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const settled = messages.filter((m) => !m.isStreaming);
    try {
      window.localStorage.setItem(historyStorageKey, JSON.stringify(settled.slice(-30)));
    } catch {
      // Ignore storage quota errors
    }
  }, [messages, historyStorageKey]);

  useEffect(() => {
    if (!minimized) {
      endRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, loading, minimized]);

  function clearConversation() {
    setMessages([]);
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(historyStorageKey);
    }
  }

  async function sendMessage(presetText?: string) {
    const text = (presetText ?? input).trim();
    if (!text || loading || !isVerified) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      sender: "user",
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };
    const asstId = `a-${Date.now()}`;
    const placeholderMsg: ChatMessage = {
      id: asstId,
      sender: "assistant",
      text: "",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, placeholderMsg]);
    if (!presetText) setInput("");
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/dealerships/${dealershipId}/assistant/chat/stream`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: text,
            channel: "website",
            channel_user_id: visitorId,
            conversation_history: messages.slice(-6).map((m) => ({
              role: m.sender,
              content: m.text,
            })),
          }),
        },
      );

      if (!response.ok || !response.body) {
        throw new Error(`Unable to reach assistant (${response.status}).`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let accumulated = "";
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";

        for (const evt of events) {
          if (!evt.startsWith("data: ")) continue;
          try {
            const payload = JSON.parse(evt.slice(6));
            if (payload.type === "chunk" && payload.content) {
              accumulated += payload.content;
              setMessages((prev) =>
                prev.map((m) => (m.id === asstId ? { ...m, text: accumulated } : m)),
              );
            } else if (payload.type === "done") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === asstId
                    ? {
                        ...m,
                        text: accumulated,
                        intent: payload.intent,
                        sources: payload.sources || [],
                        isStreaming: false,
                      }
                    : m,
                ),
              );
            } else if (payload.type === "error") {
              setError(
                typeof payload.message === "string"
                  ? payload.message
                  : "Assistant encountered an error.",
              );
            }
          } catch {
            // Ignore malformed SSE chunk
          }
        }
      }

      setMessages((prev) =>
        prev.map((m) => (m.id === asstId ? { ...m, isStreaming: false } : m)),
      );
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : "Could not connect to the dealership assistant.";
      setError(msg);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === asstId
            ? {
                ...m,
                text: `Sorry, I couldn't reach the live showroom service right now. (${msg})`,
                isStreaming: false,
              }
            : m,
        ),
      );
    } finally {
      setLoading(false);
    }
  }

  async function submitLead(e: FormEvent) {
    e.preventDefault();
    if (!leadConsent) return;
    setLeadSubmitting(true);
    setLeadError("");
    try {
      const res = await fetch(`${API_URL}/dealerships/${dealershipId}/leads`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: leadName.trim(),
          email: leadEmail.trim(),
          phone: leadPhone.trim() || null,
          message:
            leadMessage.trim() ||
            messages.filter((m) => m.sender === "user").slice(-1)[0]?.text ||
            "Customer requested follow-up from website chatbot.",
          source: "website",
          consent_to_contact: true,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Failed (${res.status})`);
      }
      setLeadSuccess(true);
      setLeadModalOpen(false);
      setLeadName("");
      setLeadEmail("");
      setLeadPhone("");
      setLeadMessage("");
    } catch (err) {
      setLeadError(
        err instanceof Error ? err.message : "Could not submit your contact request.",
      );
    } finally {
      setLeadSubmitting(false);
    }
  }

  // Minimized floating support launcher (Azure / Oracle style)
  if (minimized) {
    return (
      <div className={embedded ? "fixed bottom-4 right-4 z-50" : "flex justify-end"}>
        <button
          type="button"
          onClick={() => setMinimized(false)}
          className="group inline-flex items-center gap-3 rounded-full bg-slate-900 hover:bg-slate-800 text-white px-4 py-3 shadow-xl border border-slate-700/70 transition-colors"
          aria-label={`Open ${dealershipName} AI Assistant`}
        >
          <span className="relative flex h-8 w-8 items-center justify-center rounded-full bg-blue-600">
            <MessageSquare className="h-4 w-4 text-white" />
            <span className="absolute -top-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-emerald-400 ring-2 ring-slate-900" />
          </span>
          <span className="text-left pr-1">
            <span className="block text-xs font-semibold leading-tight">
              {dealershipName} AI
            </span>
            <span className="block text-[11px] text-slate-300 leading-tight">
              {isVerified ? "Ask about inventory & test drives" : "Connect dealership"}
            </span>
          </span>
        </button>
      </div>
    );
  }

  return (
    <div
      className={`flex flex-col bg-white border border-black/[0.08] overflow-hidden ${
        embedded ? "h-screen rounded-none border-0" : "h-[540px] rounded-2xl"
      }`}
    >
      {/* Header */}
      <div className="px-4 py-3 bg-[#0f0f10] text-white flex items-center justify-between gap-2 shrink-0">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="h-8 w-8 rounded-lg bg-[#232325] border border-white/10 flex items-center justify-center shrink-0">
            <Bot className="h-4 w-4 text-white" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium truncate">{dealershipName}</p>
            <p
              className={`text-[11px] flex items-center gap-1.5 ${
                isVerified ? "text-[#a1a1a6]" : "text-amber-300"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  isVerified ? "bg-emerald-400" : "bg-amber-400"
                }`}
              />
              {verifying
                ? "Verifying dealership"
                : isVerified
                ? "Live inventory & test-drive agent"
                : "Dealership activation required"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          {isVerified && (
            <button
              type="button"
              onClick={() => {
                setLeadSuccess(false);
                setLeadError("");
                setLeadModalOpen(true);
              }}
              className="inline-flex items-center gap-1 rounded-lg bg-white/10 hover:bg-white/20 px-2.5 py-1.5 text-xs font-medium text-white transition-colors"
              title="Connect with a human sales advisor"
            >
              <UserPlus className="h-3.5 w-3.5" />
              <span>Talk to Sales</span>
            </button>
          )}
          {messages.length > 0 && isVerified && (
            <button
              type="button"
              onClick={clearConversation}
              className="rounded-lg p-1.5 text-slate-300 hover:bg-white/10 hover:text-white"
              title="Reset chat"
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </button>
          )}
          {embedded && (
            <button
              type="button"
              onClick={() => setMinimized(true)}
              className="rounded-lg p-1.5 text-slate-300 hover:bg-white/10 hover:text-white"
              title="Minimize chat"
              aria-label="Minimize chat"
            >
              <Minimize2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Unverified / Unregistered Dealership State */}
      {!verifying && !isVerified ? (
        <div className="flex-1 flex flex-col items-center justify-center p-6 text-center bg-slate-50">
          <div className="h-12 w-12 rounded-2xl bg-amber-50 border border-amber-200 text-amber-600 flex items-center justify-center mb-3">
            <AlertCircle className="h-6 w-6" />
          </div>
          <h3 className="text-sm font-medium text-[#171717]">
            Dealership Widget Not Activated
          </h3>
          <p className="text-xs text-slate-600 mt-1.5 max-w-xs leading-relaxed">
            Dealership #{dealershipId} is not active or registered yet. Dealership
            administrators should sign in to DealerDesk CRM to activate their workspace,
            or register a new dealership account first.
          </p>
          <div className="mt-5 flex flex-col sm:flex-row gap-2 w-full max-w-xs">
            <Link
              href="/login"
              target="_blank"
              className="crm-btn-primary flex-1 justify-center text-xs"
            >
              Sign in to CRM
              <ExternalLink className="h-3.5 w-3.5" />
            </Link>
            <Link
              href="/signup"
              target="_blank"
              className="crm-btn-secondary flex-1 justify-center text-xs"
            >
              Register Account
            </Link>
          </div>
        </div>
      ) : (
        <>
          {/* Banners */}
          {leadSuccess && (
            <div className="px-4 py-2 bg-emerald-50 border-b border-emerald-200 text-xs text-emerald-700 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span>Request sent to the dealership sales team</span>
            </div>
          )}
          {error && (
            <div className="px-4 py-2 bg-rose-50 border-b border-rose-200 text-xs text-rose-700 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50/70">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center px-3">
                <div className="h-11 w-11 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mb-3">
                  <Bot className="h-5 w-5" />
                </div>
                <p className="text-sm font-semibold text-slate-900">
                  Ask anything about our vehicles or test drives
                </p>
                <p className="text-xs text-slate-500 mt-1 max-w-xs">
                  I can check live stock, compare pricing, answer warranty questions, or
                  help you schedule a visit.
                </p>
                <div className="mt-4 flex flex-wrap justify-center gap-1.5">
                  {QUICK_PROMPTS.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => void sendMessage(q)}
                      className="rounded-full border border-slate-200 bg-white hover:bg-blue-50 hover:border-blue-200 px-3 py-1.5 text-[11px] font-medium text-slate-700 transition-colors"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-xs ${
                      msg.sender === "user"
                        ? "bg-blue-600 text-white"
                        : "bg-white text-slate-800 border border-slate-200 shadow-sm"
                    }`}
                  >
                    {msg.sender === "assistant" ? (
                      <FormattedMessage
                        content={msg.text || (msg.isStreaming ? "Checking showroom..." : "")}
                      />
                    ) : (
                      <p className="whitespace-pre-wrap leading-relaxed">{msg.text}</p>
                    )}

                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-2 pt-1.5 border-t border-slate-100 flex flex-wrap gap-1">
                        {msg.sources.map((src, i) => (
                          <span
                            key={i}
                            className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600"
                          >
                            {src.filename}
                            {src.page_number ? ` p.${src.page_number}` : ""}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
            <div ref={endRef} />
          </div>

          {/* Input */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void sendMessage();
            }}
            className="p-3 bg-white border-t border-slate-200 flex items-center gap-2 shrink-0"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about a vehicle, price, or test drive..."
              className="crm-input text-xs"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="crm-btn-primary px-3 py-2 shrink-0"
              aria-label="Send message"
            >
              <Send className="h-3.5 w-3.5" />
            </button>
          </form>
        </>
      )}

      {/* Lead Capture Modal */}
      {leadModalOpen && (
        <div className="crm-modal-overlay">
          <div className="crm-modal max-w-sm p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-[#171717]">Connect with Sales</h3>
              <button
                type="button"
                onClick={() => setLeadModalOpen(false)}
                className="rounded p-1 text-slate-400 hover:bg-slate-100"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            {leadError && (
              <div className="mb-3 rounded border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
                {leadError}
              </div>
            )}
            <form onSubmit={submitLead} className="space-y-2.5">
              <input
                type="text"
                required
                placeholder="Your full name"
                value={leadName}
                onChange={(e) => setLeadName(e.target.value)}
                className="crm-input text-xs"
              />
              <input
                type="email"
                required
                placeholder="Email address"
                value={leadEmail}
                onChange={(e) => setLeadEmail(e.target.value)}
                className="crm-input text-xs"
              />
              <input
                type="text"
                placeholder="Phone (optional)"
                value={leadPhone}
                onChange={(e) => setLeadPhone(e.target.value)}
                className="crm-input text-xs"
              />
              <textarea
                rows={2}
                placeholder="Which vehicle or time works best?"
                value={leadMessage}
                onChange={(e) => setLeadMessage(e.target.value)}
                className="crm-textarea text-xs"
              />
              <label className="flex items-center gap-2 text-[11px] text-slate-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={leadConsent}
                  onChange={(e) => setLeadConsent(e.target.checked)}
                  className="rounded border-slate-300 text-blue-600"
                />
                I agree to be contacted by the dealership team.
              </label>
              <div className="flex justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setLeadModalOpen(false)}
                  className="crm-btn-secondary py-1.5 px-3 text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={leadSubmitting || !leadConsent}
                  className="crm-btn-primary py-1.5 px-3 text-xs"
                >
                  {leadSubmitting ? "Sending..." : "Send Request"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
