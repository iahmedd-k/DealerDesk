"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";
import {
  Bot,
  Send,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  X,
  UserPlus,
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
  const { activeDealershipId, authReady, user } = useAuth();
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
    if (!authReady || !user || !activeDealershipId) return;
    let cancelled = false;
    api<{ name: string }>(`/dealerships/${activeDealershipId}`)
      .then((dealership) => {
        if (!cancelled) setDealershipName(dealership.name);
      })
      .catch((cause: unknown) => {
        if (!cancelled)
          setChatError(
            cause instanceof Error ? cause.message : "Could not load dealership details.",
          );
      });
    return () => {
      cancelled = true;
    };
  }, [authReady, user, activeDealershipId]);

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
        conversation_history: messages.slice(-6).map((message) => ({
          role: message.sender,
          content: message.text,
        })),
      });
      const sendStream = () =>
        fetch(`${API_URL}/dealerships/${activeDealershipId}/assistant/chat/stream`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: requestBody,
        });

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
                  prev.map((m) => (m.id === asstMsgId ? { ...m, text: accumulated } : m)),
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
                      : m,
                  ),
                );
              } else if (data.type === "error") {
                setChatError(
                  typeof data.message === "string"
                    ? data.message
                    : "The assistant request failed.",
                );
              }
            } catch (err) {
              console.error("SSE parse error", err);
            }
          }
        }
      }

      setMessages((prev) =>
        prev.map((m) => (m.id === asstMsgId ? { ...m, isStreaming: false } : m)),
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
            : m,
        ),
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
    } catch (cause) {
      setLeadError(cause instanceof Error ? cause.message : "Could not submit follow-up request.");
    } finally {
      setSubmittingLead(false);
    }
  }

  return (
    <Shell>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-medium tracking-tight text-[#171717]">
            {dealershipName ? `${dealershipName} Assistant` : "Dealership AI Copilot"}
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Grounded in live dealership inventory, test-drive slots, and RAG knowledge documents
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={openLeadForm}
            className="crm-btn-secondary"
          >
            <UserPlus className="h-4 w-4" />
            Request Sales Follow-up
          </button>
          <button
            type="button"
            onClick={() => setMessages([])}
            className="crm-btn-secondary"
          >
            <RotateCcw className="h-4 w-4" />
            Clear Chat
          </button>
        </div>
      </div>

      {leadSubmitted && (
        <div className="mb-5 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs font-medium text-emerald-700">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>Follow-up request logged in the dealership lead pipeline.</span>
        </div>
      )}

      {chatError && (
        <div className="mb-5 flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-xs font-medium text-rose-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{chatError}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Main Chat Panel */}
        <div className="lg:col-span-3 crm-card flex flex-col h-[640px] overflow-hidden">
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center max-w-md mx-auto">
                <div className="h-12 w-12 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mb-3">
                  <Bot className="h-6 w-6" />
                </div>
                <h2 className="text-base font-medium text-[#171717]">
                  Ask about inventory, availability, or policies
                </h2>
                <p className="text-xs text-slate-500 mt-1">
                  Responses stream directly from your dealership&apos;s live vehicle catalog,
                  test-drive slots, and indexed PDF/Markdown knowledge base.
                </p>
              </div>
            ) : (
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${msg.sender === "user"
                      ? "bg-blue-600 text-white"
                      : "bg-slate-100 text-slate-900 border border-slate-200"
                      }`}
                  >
                    <div className="flex items-center gap-2 mb-1 text-[11px] opacity-75">
                      {msg.sender === "assistant" && <Bot className="h-3.5 w-3.5" />}
                      <span className="font-semibold">
                        {msg.sender === "user" ? "You" : "DealerDesk AI"}
                      </span>
                      <span>· {msg.timestamp}</span>
                      {msg.intent && (
                        <span className="rounded bg-white/80 px-1.5 py-0.5 text-[10px] font-semibold text-slate-700">
                          {msg.intent}
                        </span>
                      )}
                    </div>

                    {msg.sender === "assistant" ? (
                      <FormattedMessage content={msg.text || (msg.isStreaming ? "Thinking..." : "")} />
                    ) : (
                      <p className="whitespace-pre-wrap">{msg.text}</p>
                    )}

                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-slate-200/80 flex flex-wrap gap-1.5">
                        {msg.sources.map((src, i) => (
                          <span
                            key={i}
                            className="rounded bg-white px-2 py-0.5 text-[11px] text-slate-600 border border-slate-200"
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
            <div ref={messagesEndRef} />
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              void handleSend();
            }}
            className="border-t border-slate-200 bg-slate-50 p-3 flex items-center gap-2"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about available vehicles, pricing, warranty docs, or open slots..."
              className="crm-input bg-white"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="crm-btn-primary shrink-0"
            >
              <Send className="h-4 w-4" />
              Send
            </button>
          </form>
        </div>

        {/* Presets Sidebar */}
        <div className="crm-card p-5 space-y-4 h-fit">
          <div>
            <h2 className="text-sm font-medium text-[#171717]">Quick Prompts</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Test grounded retrieval and slot awareness
            </p>
          </div>
          <div className="space-y-2">
            {PRESETS.map((preset) => (
              <button
                key={preset}
                type="button"
                disabled={loading}
                onClick={() => void handleSend(preset)}
                className="w-full text-left rounded-lg border border-slate-200 bg-slate-50 hover:bg-slate-100 px-3 py-2 text-xs font-medium text-slate-700 transition-colors"
              >
                {preset}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Lead Follow-up Modal */}
      {leadFormOpen && (
        <div className="crm-modal-overlay">
          <div className="crm-modal max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-medium text-[#171717]">Request Sales Follow-up</h2>
              <button
                type="button"
                onClick={() => setLeadFormOpen(false)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {leadError && (
              <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
                {leadError}
              </div>
            )}

            <form onSubmit={submitLead} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Name
                </label>
                <input
                  type="text"
                  required
                  value={leadName}
                  onChange={(e) => setLeadName(e.target.value)}
                  className="crm-input"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Email
                </label>
                <input
                  type="email"
                  required
                  value={leadEmail}
                  onChange={(e) => setLeadEmail(e.target.value)}
                  className="crm-input"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Phone (Optional)
                </label>
                <input
                  type="text"
                  value={leadPhone}
                  onChange={(e) => setLeadPhone(e.target.value)}
                  className="crm-input"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Notes
                </label>
                <textarea
                  rows={3}
                  required
                  value={leadMessage}
                  onChange={(e) => setLeadMessage(e.target.value)}
                  className="crm-textarea"
                />
              </div>
              <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={leadConsent}
                  onChange={(e) => setLeadConsent(e.target.checked)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                />
                I consent to dealership sales contact regarding this inquiry.
              </label>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setLeadFormOpen(false)}
                  className="crm-btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingLead || !leadConsent}
                  className="crm-btn-primary"
                >
                  {submittingLead ? "Submitting..." : "Submit Request"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Shell>
  );
}
