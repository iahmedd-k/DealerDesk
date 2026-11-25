"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";
import {
  Sparkles,
  Bot,
  Send,
  Building2,
  Car,
  Calendar,
  BookOpen,
  RotateCcw,
  ShieldCheck,
  ShieldAlert,
  ChevronRight,
  Info,
  CheckCircle2,
} from "lucide-react";
import Shell from "../components/Shell";
import { useAuth } from "../providers";
import FormattedMessage from "../components/FormattedMessage";
import { API_URL, api, refreshSession } from "../api";

interface Message {
  id: string;
  sender: "user" | "assistant";
  text: string;
  timestamp: string;
  intent?: string;
  suggested_actions?: string[];
  sources?: { document_id: number; filename: string; page_number: number | null }[];
  isStreaming?: boolean;
}

const PRESETS = [
  "What vehicles are available?",
  "What test-drive slots are open this week?",
  "What are our business hours and address?",
  "Summarize the indexed warranty and coverage documents.",
  "Which vehicles are priced under $50,000?",
];

export default function AssistantPage() {
  const { activeDealershipId, accessToken, user } = useAuth();
  const [dealershipName, setDealershipName] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [chatError, setChatError] = useState("");
  const [leadFormOpen, setLeadFormOpen] = useState(false);
  const [leadName, setLeadName] = useState("");
  const [leadEmail, setLeadEmail] = useState("");
  const [leadPhone, setLeadPhone] = useState("");
  const [leadMessage, setLeadMessage] = useState("");
  const [leadConsent, setLeadConsent] = useState(false);
  const [leadError, setLeadError] = useState("");
  const [leadSubmitted, setLeadSubmitted] = useState(false);
  const [submittingLead, setSubmittingLead] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!activeDealershipId) return;
    let cancelled = false;
    api<{ name: string }>(`/dealerships/${activeDealershipId}`)
      .then((dealership) => {
        if (!cancelled) setDealershipName(dealership.name);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setChatError(cause instanceof Error ? cause.message : "Could not load dealership details.");
      });
    return () => {
      cancelled = true;
    };
  }, [activeDealershipId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend(textToSend?: string) {
    const text = (textToSend || input).trim();
    if (!text || loading) return;
    if (!activeDealershipId) {
      setChatError("Select a dealership workspace before starting a conversation.");
      return;
    }

    const userMessage: Message = {
      id: `u-${Date.now()}`,
      sender: "user",
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    const asstMsgId = `a-${Date.now()}`;
    const initialAsstMessage: Message = {
      id: asstMsgId,
      sender: "assistant",
      text: "",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMessage, initialAsstMessage]);
    setInput("");
    setLoading(true);
    setChatError("");

    try {
      const requestBody = JSON.stringify({
        message: text,
        channel: "website",
        conversation_history: messages
          .slice(-6)
          .map((message) => ({
            role: message.sender,
            content: message.text,
          })),
      });
      const sendStream = () => fetch(
        `${API_URL}/dealerships/${activeDealershipId}/assistant/chat/stream`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
          },
          body: requestBody,
        },
      );
      let response = await sendStream();
      if (response.status === 401) {
        const renewed = await refreshSession();
        if (renewed) response = await sendStream();
      }

      if (!response.ok || !response.body) {
        throw new Error(`Assistant request failed (${response.status}).`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let accumulated = "";
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === "chunk" && data.content) {
                accumulated += data.content;
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === asstMsgId ? { ...m, text: accumulated } : m
                  )
                );
              } else if (data.type === "done") {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === asstMsgId
                      ? {
                          ...m,
                          text: accumulated,
                          intent: data.intent,
                          suggested_actions: data.suggested_actions,
                          sources: data.sources || [],
                          isStreaming: false,
                        }
                      : m
                  )
                );
              } else if (data.type === "error") {
                setChatError(typeof data.message === "string" ? data.message : "The assistant request failed.");
              }
            } catch (err) {
              console.error("SSE parse error", err);
            }
          }
        }
      }

      setMessages((prev) =>
        prev.map((m) => (m.id === asstMsgId ? { ...m, isStreaming: false } : m))
      );
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "The assistant request failed.";
      setChatError(message);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === asstMsgId
            ? {
                ...m,
                text: `I could not retrieve a response. ${message}`,
                isStreaming: false,
              }
            : m
        )
      );
    } finally {
      setLoading(false);
    }
  }

  function openLeadForm() {
    const latestInquiry = messages
      .filter((message) => message.sender === "user")
      .slice(-1)[0]?.text;
    setLeadName(user?.name ?? "");
    setLeadEmail(user?.email ?? "");
    setLeadMessage(latestInquiry ?? "");
    setLeadError("");
    setLeadSubmitted(false);
    setLeadFormOpen(true);
  }

  async function submitLead(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeDealershipId || !leadConsent) return;
    setSubmittingLead(true);
    setLeadError("");
    try {
      await api(`/dealerships/${activeDealershipId}/leads`, {
        method: "POST",
        body: JSON.stringify({
          name: leadName,
          email: leadEmail,
          phone: leadPhone || null,
          message: leadMessage,
          source: "assistant",
          consent_to_contact: true,
        }),
      });
      setLeadSubmitted(true);
      setLeadFormOpen(false);
      setLeadConsent(false);
    } catch (cause) {
      setLeadError(cause instanceof Error ? cause.message : "Could not submit your inquiry.");
    } finally {
      setSubmittingLead(false);
    }
  }

  return (
    <Shell>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="flex h-5 items-center gap-1.5 rounded-full bg-blue-500/20 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-blue-400 border border-blue-500/30">
              <Bot className="h-3 w-3" />
              Dealership AI Concierge
            </span>
            <span className="flex items-center gap-1 text-[11px] font-semibold text-slate-400">
              AI-assisted responses
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            {dealershipName || "Dealership"} AI Assistant
          </h1>
          <p className="text-xs text-slate-400">
            Responses are scoped to the active dealership. Verify important details with your team.
          </p>
        </div>

        {chatError && (
          <div role="alert" className="mb-4 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">
            {chatError}
          </div>
        )}

        <button
          onClick={() => setMessages([])}
          className="btn-secondary text-xs flex items-center gap-1.5"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          <span>Reset Session</span>
        </button>
      </div>

      {/* Workspace Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 h-[720px]">
        {/* Left 3 Columns: Main Chat Experience */}
        <div className="lg:col-span-3 bg-slate-900 border border-slate-800 rounded-2xl flex flex-col h-full shadow-lg overflow-hidden">
          {/* Preset Prompts Strip */}
          <div className="bg-slate-950/70 border-b border-slate-800 p-3 overflow-x-auto">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex-shrink-0">
                Suggested Prompts:
              </span>
              {PRESETS.map((p, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(p)}
                  className="rounded-full bg-slate-800/80 hover:bg-slate-700 px-3 py-1 text-xs text-slate-300 transition-colors whitespace-nowrap flex-shrink-0 border border-slate-700/60"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          {/* Chat Messages Container */}
          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex flex-col ${m.sender === "user" ? "items-end" : "items-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl p-4 text-xs leading-relaxed ${
                    m.sender === "user"
                      ? "bg-blue-600 text-white rounded-br-none shadow-md"
                      : "bg-slate-850 text-slate-200 border border-slate-700/80 rounded-bl-none shadow-sm"
                  }`}
                >
                  {m.text ? (
                    <FormattedMessage content={m.text} />
                  ) : (
                    m.isStreaming && (
                      <span className="inline-block h-3 w-1.5 bg-blue-400 animate-pulse" />
                    )
                  )}

                  {/* Suggested Quick Actions */}
                  {m.suggested_actions && m.suggested_actions.length > 0 && !m.isStreaming && (
                    <div className="mt-3 pt-2.5 border-t border-slate-700/60 space-y-1.5">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                        Suggested Actions:
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {m.suggested_actions.map((act, idx) => (
                          <button
                            key={idx}
                            onClick={() => handleSend(act)}
                            className="inline-flex items-center gap-1 rounded-lg bg-slate-800 hover:bg-slate-750 px-2.5 py-1 text-[11px] text-blue-300 border border-slate-700 transition-colors"
                          >
                            <ChevronRight className="h-3 w-3 text-blue-400" />
                            <span>{act}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {m.sources && m.sources.length > 0 && (
                    <div className="mt-3 border-t border-slate-700/60 pt-2.5 text-[10px] text-slate-400">
                      <span className="font-semibold uppercase tracking-wide">Sources</span>
                      <ul className="mt-1 space-y-1">
                        {m.sources.map((source) => (
                          <li key={`${source.document_id}-${source.page_number ?? "document"}`}>
                            {source.filename}{source.page_number ? `, page ${source.page_number}` : ""}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
                <span className="text-[10px] text-slate-500 mt-1 px-1">{m.timestamp}</span>
              </div>
            ))}

            {loading && !messages.some((m) => m.isStreaming && m.text.length > 0) && (
              <div className="flex items-center gap-2.5 text-xs text-blue-300 bg-blue-950/30 border border-blue-800/40 p-3.5 rounded-xl w-fit">
                <Sparkles className="h-4 w-4 animate-spin text-blue-400" />
                <span>Checking live dealership catalog and schedule...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Box */}
          <div className="border-t border-slate-800 p-4 bg-slate-950">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="flex items-center gap-3"
            >
              <input
                type="text"
                placeholder="Ask about vehicle inventory, test-drive booking, warranty, or dealership hours..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                className="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-xs text-white placeholder-slate-500 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              />
              <button
                type="submit"
                disabled={!input.trim() || loading}
                className="btn-primary py-3 px-5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40"
              >
                <Send className="h-4 w-4" />
                <span>Send</span>
              </button>
            </form>
          </div>
        </div>

        {/* Right 1 Column: Safety Guardrails & Dealership Scope */}
        <div className="space-y-4">
          {/* Responsible-use guidance */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm space-y-3 text-xs">
            <h3 className="font-bold text-white text-sm flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
              Before You Rely on an Answer
            </h3>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Do not enter payment or government ID details. Confirm prices, availability, and policies with dealership staff before making a commitment.
            </p>
          </div>

          {/* Dealership Context Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm space-y-3 text-xs">
            <h3 className="font-bold text-white text-sm flex items-center gap-2">
              <Building2 className="h-4 w-4 text-blue-400" />
              Dealership Context
            </h3>

            <div className="space-y-2.5 divide-y divide-slate-800 text-[11px]">
              <div className="pt-1">
                <span className="text-slate-400 block">Dealership Workspace:</span>
                <strong className="text-white">{dealershipName || "Loading..."}</strong>
              </div>

              <div className="pt-2">
                <span className="text-slate-400 block">Fleet Catalog:</span>
                <span className="text-slate-400 font-semibold">Current inventory is retrieved per request</span>
              </div>

              <div className="pt-2">
                <span className="text-slate-400 block">Test-Drive Schedule:</span>
                <span className="text-slate-400 font-semibold">Availability is checked per request</span>
              </div>

              <div className="pt-2">
                <span className="text-slate-400 block">Streaming Protocol:</span>
                <span className="font-mono text-indigo-400 text-[10px]">Server-Sent Events (SSE)</span>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5 shadow-sm">
              <h3 className="text-sm font-bold text-white">Want a dealership follow-up?</h3>
              <p className="mt-2 text-[11px] leading-relaxed text-slate-400">
                Send your inquiry to the dealership team. Your contact details are only shared after you agree.
              </p>
              {leadSubmitted ? (
                <div role="status" className="mt-3 flex items-center gap-2 text-xs text-emerald-300">
                  <CheckCircle2 className="h-4 w-4" /> Your inquiry was sent to the dealership.
                </div>
              ) : null}
              {!leadFormOpen ? (
                <button
                  type="button"
                  onClick={openLeadForm}
                  className="mt-3 w-full rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-500"
                >
                  Request a follow-up
                </button>
              ) : (
                <form onSubmit={submitLead} className="mt-3 space-y-2.5">
                  <input
                    required
                    maxLength={100}
                    value={leadName}
                    onChange={(event) => setLeadName(event.target.value)}
                    placeholder="Your name"
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
                  />
                  <input
                    required
                    type="email"
                    maxLength={320}
                    value={leadEmail}
                    onChange={(event) => setLeadEmail(event.target.value)}
                    placeholder="Email"
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
                  />
                  <input
                    maxLength={32}
                    value={leadPhone}
                    onChange={(event) => setLeadPhone(event.target.value)}
                    placeholder="Phone (optional)"
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
                  />
                  <textarea
                    required
                    maxLength={2000}
                    value={leadMessage}
                    onChange={(event) => setLeadMessage(event.target.value)}
                    placeholder="How can the dealership help?"
                    className="min-h-20 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
                  />
                  <label className="flex items-start gap-2 text-[11px] leading-relaxed text-slate-400">
                    <input
                      type="checkbox"
                      checked={leadConsent}
                      onChange={(event) => setLeadConsent(event.target.checked)}
                      className="mt-0.5 accent-blue-500"
                    />
                    I agree that this dealership may contact me about my inquiry.
                  </label>
                  {leadError ? <p role="alert" className="text-xs text-rose-300">{leadError}</p> : null}
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setLeadFormOpen(false)}
                      className="flex-1 rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-200"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={!leadConsent || submittingLead}
                      className="flex-1 rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"
                    >
                      {submittingLead ? "Sending..." : "Send inquiry"}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}
