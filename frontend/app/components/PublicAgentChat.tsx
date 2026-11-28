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
  Calendar,
} from "lucide-react";
import { API_URL } from "../api";
import FormattedMessage from "./FormattedMessage";

interface SlotOption {
  slot_id?: number;
  id?: number;
  vehicle_id?: number;
  vehicle_name?: string;
  starts_at: string;
  ends_at?: string;
  remaining_capacity?: number;
}

interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  timestamp: string;
  intent?: string;
  slots?: SlotOption[];
  sources?: { document_id: number; filename: string; page_number: number | null }[];
  isStreaming?: boolean;
}

interface PendingBookingState {
  slotId: number;
  step: "awaiting_name" | "awaiting_email" | "awaiting_phone" | "awaiting_otp";
  customerName?: string;
  destination?: string;
  customerPhone?: string;
  holdToken?: string;
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
  "Show open test-drive slots",
  "What are your dealership hours and location?",
  "Tell me about your warranty and coverage options",
];

function extractSlotIdFromText(text: string): number | null {
  const m =
    text.match(/\bslot\s*#?(\d+)\b/i) ||
    text.match(/\b(?:book|reserve|select)\s+(?:slot\s*)?#?(\d+)\b/i);
  if (!m) return null;
  const id = Number(m[1]);
  return Number.isInteger(id) && id > 0 ? id : null;
}

function extractEmailAndName(text: string): { email: string; name?: string } | null {
  const emailMatch = text.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i);
  if (!emailMatch) return null;
  const email = emailMatch[0].trim();
  const remainder = text.replace(email, "").replace(/[,;-]+/g, " ").trim();
  return { email, name: remainder || undefined };
}

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
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [pendingBooking, setPendingBooking] = useState<PendingBookingState | null>(null);

  // Lead Capture Modal
  const [leadModalOpen, setLeadModalOpen] = useState(false);
  const [leadName, setLeadName] = useState("");
  const [leadEmail, setLeadEmail] = useState("");
  const [leadPhone, setLeadPhone] = useState("");
  const [leadMessage, setLeadMessage] = useState("");
  const [leadConsent, setLeadConsent] = useState(true);
  const [leadSubmitting, setLeadSubmitting] = useState(false);
  const [leadSuccess, setLeadSuccess] = useState(false);
  const [leadError, setLeadError] = useState("");

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const historyStorageKey = `dealerdesk_chat_history_${dealershipId}`;
  const convStorageKey = `dealerdesk_conv_${dealershipId}`;

  useEffect(() => {
    if (typeof window === "undefined") return;
    const key = `dealerdesk_visitor_${dealershipId}`;
    let existing = window.localStorage.getItem(key);
    if (!existing) {
      existing = `vis-${Math.random().toString(36).slice(2, 10)}`;
      window.localStorage.setItem(key, existing);
    }
    setVisitorId(existing);

    const savedConv = Number(window.localStorage.getItem(convStorageKey));
    if (Number.isInteger(savedConv) && savedConv > 0) {
      setConversationId(savedConv);
    }

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
  }, [dealershipId, historyStorageKey, convStorageKey]);

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
    if (!minimized && messages.length > 0 && scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
    }
  }, [messages, loading, minimized]);

  function clearConversation() {
    setMessages([]);
    setConversationId(null);
    setPendingBooking(null);
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(historyStorageKey);
      window.localStorage.removeItem(convStorageKey);
    }
  }

  function appendAssistantText(text: string, slots?: SlotOption[]) {
    const nowTime = new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
    setMessages((prev) => [
      ...prev,
      {
        id: `a-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        sender: "assistant",
        text,
        timestamp: nowTime,
        slots,
      },
    ]);
  }

  function startInlineBooking(slotId: number) {
    setPendingBooking({ slotId, step: "awaiting_name" });
    appendAssistantText(
      `To reserve **Slot #${slotId}**, what is your **full name**? (Type \`cancel\` anytime to stop.)`,
    );
  }

  async function handleInlineBookingStep(text: string) {
    if (!pendingBooking) return;
    const nowTime = new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });

    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, sender: "user", text, timestamp: nowTime },
    ]);
    setInput("");

    if (text.toLowerCase() === "cancel") {
      setPendingBooking(null);
      appendAssistantText("Booking cancelled. Ask me anytime if you want to pick another slot.");
      return;
    }

    if (pendingBooking.step === "awaiting_name") {
      const cleanName = text.trim();
      if (cleanName.length < 2) {
        appendAssistantText("Please enter your **full name** (at least 2 characters), or type `cancel`.");
        return;
      }
      setPendingBooking({
        ...pendingBooking,
        step: "awaiting_email",
        customerName: cleanName,
      });
      appendAssistantText(`Thanks, **${cleanName}**. What is your **email address**?`);
      return;
    }

    if (pendingBooking.step === "awaiting_email") {
      const parsed = extractEmailAndName(text);
      if (!parsed) {
        appendAssistantText(
          "Please enter a valid **email address** (for example: `jane@example.com`), or type `cancel`.",
        );
        return;
      }
      setPendingBooking({
        ...pendingBooking,
        step: "awaiting_phone",
        destination: parsed.email,
      });
      appendAssistantText(
        `Got it (**${parsed.email}**). What is your **phone number**?`,
      );
      return;
    }

    if (pendingBooking.step === "awaiting_phone") {
      const cleanPhone = text.trim();
      if (cleanPhone.replace(/\D/g, "").length < 7) {
        appendAssistantText(
          "Please enter a valid **phone number** (at least 7 digits), or type `cancel`.",
        );
        return;
      }

      setLoading(true);
      try {
        const res = await fetch(
          `${API_URL}/dealerships/${dealershipId}/sales-agent/verification/initiate`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              slot_id: pendingBooking.slotId,
              destination: pendingBooking.destination,
              channel: "website",
              customer_name: pendingBooking.customerName || null,
              customer_phone: cleanPhone,
              conversation_id: conversationId,
            }),
          },
        );
        const body = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(body.detail || `Could not hold slot (${res.status}).`);
        }
        setPendingBooking({
          ...pendingBooking,
          step: "awaiting_otp",
          customerPhone: cleanPhone,
          holdToken: body.hold_token,
        });
        appendAssistantText(
          `I have held **Slot #${pendingBooking.slotId}** for 10 minutes and sent a **6-digit verification code** to **${pendingBooking.destination}**. Please check your email and reply with the 6-digit code to confirm.`,
        );
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Could not hold this slot.";
        appendAssistantText(`Unable to reserve Slot #${pendingBooking.slotId}: ${msg}`);
        setPendingBooking(null);
      } finally {
        setLoading(false);
      }
      return;
    }

    if (pendingBooking.step === "awaiting_otp") {
      const codeMatch = text.match(/\b(\d{6})\b/);
      if (!codeMatch) {
        appendAssistantText(
          "Please reply with the **6-digit numeric verification code** sent to your email (or type `cancel`).",
        );
        return;
      }

      setLoading(true);
      try {
        const res = await fetch(
          `${API_URL}/dealerships/${dealershipId}/sales-agent/verification/confirm`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              hold_token: pendingBooking.holdToken,
              code: codeMatch[1],
              destination: pendingBooking.destination,
              channel: "website",
              customer_name: pendingBooking.customerName || null,
              customer_phone: pendingBooking.customerPhone || null,
              notes: pendingBooking.customerPhone
                ? `Customer phone: ${pendingBooking.customerPhone}`
                : null,
              confirmed: true,
              conversation_id: conversationId,
            }),
          },
        );
        const body = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(body.detail || `Verification failed (${res.status}).`);
        }
        setPendingBooking(null);
        appendAssistantText(
          `**Booking #${body.booking_id} confirmed** for **${body.vehicle_name}** (Slot #${body.slot_id}, ${new Date(body.starts_at).toLocaleString()}).`,
        );
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Invalid verification code.";
        appendAssistantText(`${msg} Please try entering the 6-digit code again, or type \`cancel\`.`);
      } finally {
        setLoading(false);
      }
    }
  }

  async function sendMessage(presetText?: string) {
    const text = (presetText ?? input).trim();
    if (!text || loading || !isVerified) return;

    if (pendingBooking) {
      await handleInlineBookingStep(text);
      return;
    }

    const nowTime = new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });

    const requestedSlotId = extractSlotIdFromText(text);
    if (requestedSlotId !== null) {
      setMessages((prev) => [
        ...prev,
        { id: `u-${Date.now()}`, sender: "user", text, timestamp: nowTime },
      ]);
      if (!presetText) setInput("");
      startInlineBooking(requestedSlotId);
      return;
    }

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      sender: "user",
      text,
      timestamp: nowTime,
    };
    const asstId = `a-${Date.now()}`;
    const placeholderMsg: ChatMessage = {
      id: asstId,
      sender: "assistant",
      text: "",
      timestamp: nowTime,
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, placeholderMsg]);
    if (!presetText) setInput("");
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/dealerships/${dealershipId}/sales-agent/chat/stream`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: text,
            conversation_id: conversationId,
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
              if (payload.conversation_id) {
                setConversationId(payload.conversation_id);
                if (typeof window !== "undefined") {
                  window.localStorage.setItem(convStorageKey, String(payload.conversation_id));
                }
              }
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === asstId
                    ? {
                        ...m,
                        text: accumulated,
                        intent: payload.intent,
                        slots: Array.isArray(payload.available_slots)
                          ? payload.available_slots
                          : [],
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
      const res = await fetch(`${API_URL}/dealerships/${dealershipId}/sales-agent/leads`, {
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
          conversation_id: conversationId,
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

  if (minimized) {
    return (
      <div className={embedded ? "fixed bottom-4 right-4 z-50" : "flex justify-end"}>
        <button
          type="button"
          onClick={() => setMinimized(false)}
          className="group inline-flex items-center gap-3 rounded-full bg-[#0f0f10] hover:bg-[#19191b] text-white px-4 py-3 shadow-xl border border-white/10 transition-colors"
          aria-label={`Open ${dealershipName} Assistant`}
        >
          <span className="relative flex h-8 w-8 items-center justify-center rounded-full bg-blue-700">
            <MessageSquare className="h-4 w-4 text-white" />
            <span className="absolute -top-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-emerald-400 ring-2 ring-[#0f0f10]" />
          </span>
          <span className="text-left pr-1">
            <span className="block text-xs font-medium leading-tight">
              {dealershipName}
            </span>
            <span className="block text-[11px] text-[#a1a1a6] leading-tight">
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
              className="rounded-lg p-1.5 text-[#a1a1a6] hover:bg-white/10 hover:text-white"
              title="Reset chat"
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </button>
          )}
          {embedded && (
            <button
              type="button"
              onClick={() => setMinimized(true)}
              className="rounded-lg p-1.5 text-[#a1a1a6] hover:bg-white/10 hover:text-white"
              title="Minimize chat"
              aria-label="Minimize chat"
            >
              <Minimize2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {!verifying && !isVerified ? (
        <div className="flex-1 flex flex-col items-center justify-center p-6 text-center bg-[#fafafa]">
          <div className="h-12 w-12 rounded-2xl bg-amber-50 border border-amber-200 text-amber-600 flex items-center justify-center mb-3">
            <AlertCircle className="h-6 w-6" />
          </div>
          <h3 className="text-sm font-medium text-[#171717]">
            Dealership Widget Not Activated
          </h3>
          <p className="text-xs text-[#525252] mt-1.5 max-w-xs leading-relaxed">
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
          {leadSuccess && (
            <div className="px-4 py-2 bg-emerald-50 border-b border-emerald-200 text-xs text-emerald-700 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span>Request sent to the dealership sales team</span>
            </div>
          )}
          {error && (
            <div className="px-4 py-2 bg-red-50 border-b border-red-200 text-xs text-red-700 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Messages */}
          <div
            ref={scrollContainerRef}
            className="flex-1 overflow-y-auto p-4 space-y-3 bg-[#fafafa]"
          >
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center px-3">
                <div className="h-11 w-11 rounded-xl bg-white border border-black/[0.08] text-[#171717] flex items-center justify-center mb-3">
                  <Bot className="h-5 w-5" />
                </div>
                <p className="text-sm font-medium text-[#171717]">
                  Ask anything about our vehicles or test drives
                </p>
                <p className="text-xs text-[#525252] mt-1 max-w-xs">
                  Check live stock, compare pricing, ask warranty questions, or reserve a
                  test-drive slot
                </p>
                <div className="mt-4 flex flex-wrap justify-center gap-1.5">
                  {QUICK_PROMPTS.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => void sendMessage(q)}
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-[#171717] shadow-sm transition-colors hover:border-blue-200 hover:bg-blue-50"
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
                    className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                      msg.sender === "user"
                        ? "bg-[#171717] text-white"
                        : "bg-white text-[#171717] border border-black/[0.08]"
                    }`}
                  >
                    {msg.sender === "assistant" ? (
                      msg.isStreaming ? (
                        <div className="flex items-center gap-2 text-xs text-slate-500" aria-label="Assistant is typing">
                          <span>Checking the showroom</span>
                          <span className="flex gap-1" aria-hidden="true">
                            <span className="h-1 w-1 animate-bounce rounded-full bg-slate-400" />
                            <span className="h-1 w-1 animate-bounce rounded-full bg-slate-400 [animation-delay:120ms]" />
                            <span className="h-1 w-1 animate-bounce rounded-full bg-slate-400 [animation-delay:240ms]" />
                          </span>
                        </div>
                      ) : (
                        <FormattedMessage content={msg.text} />
                      )
                    ) : (
                      <p className="whitespace-pre-wrap leading-relaxed">{msg.text}</p>
                    )}

                    {/* Clickable Inline Slot Buttons */}
                    {msg.sender === "assistant" && msg.slots && msg.slots.length > 0 && (
                      <div className="mt-2.5 pt-2 border-t border-black/[0.06] flex flex-wrap gap-1.5">
                        {msg.slots.slice(0, 4).map((slot, idx) => {
                          const sid = slot.slot_id ?? slot.id;
                          if (!sid) return null;
                          return (
                            <button
                              key={`${sid}-${idx}`}
                              type="button"
                              onClick={() => startInlineBooking(sid)}
                              className="inline-flex items-center gap-1 rounded-md border border-blue-200 bg-blue-50 hover:bg-blue-100 px-2.5 py-1 text-[11px] font-medium text-blue-800 transition-colors tabular-nums"
                            >
                              <Calendar className="h-3 w-3" />
                              Book Slot #{sid}
                            </button>
                          );
                        })}
                      </div>
                    )}

                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-2 pt-1.5 border-t border-black/[0.06] flex flex-wrap gap-1">
                        {msg.sources.map((src, i) => (
                          <span
                            key={i}
                            className="rounded bg-[#f4f4f5] px-1.5 py-0.5 text-[10px] text-[#525252]"
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
          </div>

          {/* Input */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void sendMessage();
            }}
            className="p-3 bg-white border-t border-black/[0.08] flex items-center gap-2 shrink-0"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                pendingBooking?.step === "awaiting_name"
                  ? "Enter your full name"
                  : pendingBooking?.step === "awaiting_email"
                  ? "Enter your email (e.g. jane@example.com)"
                  : pendingBooking?.step === "awaiting_phone"
                  ? "Enter your phone number"
                  : pendingBooking?.step === "awaiting_otp"
                  ? "Enter the 6-digit verification code"
                  : "Ask about a vehicle, or type slot #7 to book"
              }
              className="crm-input min-h-10 text-sm"
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
                className="rounded p-1 text-[#737373] hover:bg-[#f4f4f5]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            {leadError && (
              <div className="mb-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
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
              <label className="flex items-center gap-2 text-[11px] text-[#525252] cursor-pointer">
                <input
                  type="checkbox"
                  checked={leadConsent}
                  onChange={(e) => setLeadConsent(e.target.checked)}
                  className="rounded border-black/20 text-blue-700"
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
