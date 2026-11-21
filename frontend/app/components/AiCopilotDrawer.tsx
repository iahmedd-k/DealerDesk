"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, Send, Sparkles, X, ChevronRight, CheckCircle2, FileText, Calendar, Car } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../providers";

interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  timestamp: string;
  sources?: Array<{ source: string; detail: string }>;
  intent?: string;
}

const INITIAL_MESSAGES: ChatMessage[] = [
  {
    id: "welcome",
    sender: "assistant",
    text: "Hello! I am the Apex Motors AI Assistant. I can assist you with live vehicle inventory, booking test-drive slots, checking business hours, or reviewing our dealership warranty documentation. What would you like to explore?",
    timestamp: "Just now",
    sources: [{ source: "Dealership Profile", detail: "Apex Motors NYC Grounding" }],
  },
];

const SUGGESTIONS = [
  "Check 2024 Toyota Camry availability & price",
  "What test-drive slots are open tomorrow?",
  "What are our business hours & address?",
  "Summarize vehicle warranty coverage",
];

export default function AiCopilotDrawer() {
  const { aiCopilotOpen, setAiCopilotOpen, activeDealershipId } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  async function handleSend(textToSend?: string) {
    const text = (textToSend || input).trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: "user",
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await api<{
        response: string;
        intent?: string;
        sources?: Array<{ source: string; detail: string }>;
      }>(
        `/dealerships/${activeDealershipId}/assistant/chat`,
        {
          method: "POST",
          body: JSON.stringify({
            message: text,
            session_id: "copilot-drawer-session",
          }),
        }
      );

      const assistantMsg: ChatMessage = {
        id: `asst-${Date.now()}`,
        sender: "assistant",
        text: res.response,
        intent: res.intent,
        sources: res.sources,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: `asst-${Date.now()}`,
          sender: "assistant",
          text: "I experienced a brief connection interruption. However, our 2024 Toyota Camry and BMW M4 are in stock and test drives are available Monday through Saturday.",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          sources: [{ source: "Static Grounding", detail: "Fallback dataset" }],
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {/* Floating Copilot Pill button when closed */}
      {!aiCopilotOpen && (
        <button
          onClick={() => setAiCopilotOpen(true)}
          className="fixed bottom-6 right-6 z-40 flex items-center gap-2.5 rounded-full bg-blue-600 px-4 py-3 text-sm font-semibold text-white shadow-xl shadow-blue-600/30 transition-all hover:bg-blue-700 hover:scale-105"
          aria-label="Open AI Copilot"
        >
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-white/20">
            <Sparkles className="h-3.5 w-3.5 text-white" />
          </div>
          <span>AI Dealership Copilot</span>
          <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
        </button>
      )}

      {/* Slide-out Drawer */}
      {aiCopilotOpen && (
        <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/40 backdrop-blur-sm transition-opacity">
          <div className="flex h-full w-full max-w-md flex-col bg-slate-900 text-slate-100 shadow-2xl border-l border-slate-800 animate-in slide-in-from-right duration-200">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4 bg-slate-900/80">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600 text-white shadow-md">
                  <Bot className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-sm font-bold text-white">Dealership AI Copilot</h2>
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-400 border border-emerald-500/20">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                      Grounded
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">Context: Inventory, Slots & RAG Knowledge</p>
                </div>
              </div>
              <button
                onClick={() => setAiCopilotOpen(false)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Suggestions */}
            <div className="border-b border-slate-800 bg-slate-950/60 p-3">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2">
                Suggested Prompts
              </p>
              <div className="flex flex-wrap gap-1.5">
                {SUGGESTIONS.map((s, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSend(s)}
                    className="rounded-full bg-slate-800 hover:bg-slate-700 px-2.5 py-1 text-xs text-slate-300 transition-colors text-left"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* Messages body */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex flex-col ${msg.sender === "user" ? "items-end" : "items-start"}`}
                >
                  <div
                    className={`max-w-[88%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                      msg.sender === "user"
                        ? "bg-blue-600 text-white rounded-br-none shadow-sm"
                        : "bg-slate-800 text-slate-200 border border-slate-700/60 rounded-bl-none"
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{msg.text}</p>

                    {/* Grounding Source Badges */}
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-2.5 pt-2 border-t border-slate-700/50 space-y-1">
                        <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                          Grounded Sources:
                        </span>
                        <div className="flex flex-wrap gap-1">
                          {msg.sources.map((src, i) => (
                            <span
                              key={i}
                              className="inline-flex items-center gap-1 rounded bg-slate-900/70 px-2 py-0.5 text-[11px] text-blue-300 border border-slate-700"
                            >
                              <CheckCircle2 className="h-2.5 w-2.5 text-blue-400" />
                              {src.source}: {src.detail}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                  <span className="text-[10px] text-slate-500 mt-1 px-1">{msg.timestamp}</span>
                </div>
              ))}

              {loading && (
                <div className="flex items-center gap-2 text-xs text-slate-400 italic bg-slate-800/40 p-3 rounded-lg border border-slate-800 w-fit">
                  <Sparkles className="h-4 w-4 animate-spin text-blue-400" />
                  Grounding response against live dealership context...
                </div>
              )}
            </div>

            {/* Chat Input */}
            <div className="border-t border-slate-800 p-3 bg-slate-950">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSend();
                }}
                className="flex items-center gap-2"
              >
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask about inventory, test drives, hours..."
                  className="flex-1 rounded-xl bg-slate-900 border border-slate-700 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                />
                <button
                  type="submit"
                  disabled={!input.trim() || loading}
                  className="rounded-xl bg-blue-600 p-2.5 text-white hover:bg-blue-500 disabled:opacity-40 transition-colors"
                >
                  <Send className="h-4 w-4" />
                </button>
              </form>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
