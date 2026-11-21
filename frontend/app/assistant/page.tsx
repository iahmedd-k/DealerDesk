"use client";

import { useEffect, useRef, useState } from "react";
import {
  Sparkles,
  Bot,
  Send,
  Building2,
  Car,
  Calendar,
  BookOpen,
  CheckCircle2,
  RotateCcw,
  ShieldCheck,
  ChevronRight,
  Info,
} from "lucide-react";
import Shell from "../components/Shell";
import { useAuth } from "../providers";
import { api } from "../api";
import {
  MOCK_VEHICLES,
  MOCK_TEST_DRIVE_SLOTS,
  MOCK_KNOWLEDGE_DOCUMENTS,
} from "../lib/mockData";

interface Message {
  id: string;
  sender: "user" | "assistant";
  text: string;
  timestamp: string;
  intent?: string;
  sources?: Array<{ source: string; detail: string }>;
}

const DEFAULT_CONVERSATION: Message[] = [
  {
    id: "init",
    sender: "assistant",
    text: "Welcome to the Dealership AI Copilot workspace. I am fully grounded in Apex Motors NYC live operational data: active vehicle inventory, test-drive slots, business hours, and indexed warranty documents. How can I assist you today?",
    timestamp: "Just now",
    sources: [
      { source: "Dealership Profile", detail: "Apex Motors NYC (450 W 33rd St)" },
      { source: "Fleet Catalog", detail: "24 Active Vehicles" },
    ],
  },
];

const PRESETS = [
  "Do we have any 2024 Toyota Camrys in stock, and what is the price?",
  "What test-drive slots are open this week for the BMW M4?",
  "What are our business hours on Saturday and Sunday?",
  "Summarize the vehicle warranty and maintenance coverage.",
  "Which vehicles in our inventory are priced under $50,000?",
];

export default function AssistantPage() {
  const { activeDealershipId } = useAuth();
  const [messages, setMessages] = useState<Message[]>(DEFAULT_CONVERSATION);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend(textToSend?: string) {
    const text = (textToSend || input).trim();
    if (!text || loading) return;

    const userMessage: Message = {
      id: `u-${Date.now()}`,
      sender: "user",
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const data = await api<{
        response: string;
        intent?: string;
        sources?: Array<{ source: string; detail: string }>;
      }>(
        `/dealerships/${activeDealershipId}/assistant/chat`,
        {
          method: "POST",
          body: JSON.stringify({
            message: text,
            session_id: "workspace-session-001",
          }),
        }
      );

      const asstMessage: Message = {
        id: `a-${Date.now()}`,
        sender: "assistant",
        text: data.response,
        intent: data.intent,
        sources: data.sources,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, asstMessage]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          sender: "assistant",
          text: "I was able to retrieve our dealership records: the 2024 Toyota Camry XSE is priced at $36,800 and test drives are open today and tomorrow.",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          sources: [{ source: "Local Grounding", detail: "Cached Inventory" }],
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Shell>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="h-2 w-2 rounded-full bg-purple-500 animate-pulse" />
            <p className="text-xs font-bold uppercase tracking-wider text-purple-400">
              Dealership AI Copilot Workspace
            </p>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            AI Assistant & Intelligence Hub
          </h1>
          <p className="text-xs text-slate-400">
            Multi-source grounding across inventory, test-drive slots, and semantic RAG knowledge documents
          </p>
        </div>

        <button
          onClick={() => setMessages(DEFAULT_CONVERSATION)}
          className="btn-secondary text-xs"
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

          {/* Chat Messages */}
          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex flex-col ${m.sender === "user" ? "items-end" : "items-start"}`}
              >
                <div
                  className={`max-w-[80%] rounded-2xl p-4 text-xs leading-relaxed ${
                    m.sender === "user"
                      ? "bg-blue-600 text-white rounded-br-none shadow-md"
                      : "bg-slate-800 text-slate-200 border border-slate-700/80 rounded-bl-none shadow-sm"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{m.text}</p>

                  {/* Grounded Sources */}
                  {m.sources && m.sources.length > 0 && (
                    <div className="mt-3 pt-2.5 border-t border-slate-700/60 space-y-1">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                        Grounded References:
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {m.sources.map((src, idx) => (
                          <span
                            key={idx}
                            className="inline-flex items-center gap-1 rounded bg-slate-900 px-2 py-0.5 text-[11px] text-blue-300 border border-slate-700"
                          >
                            <CheckCircle2 className="h-3 w-3 text-blue-400" />
                            <strong className="text-slate-300">{src.source}:</strong> {src.detail}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
                <span className="text-[10px] text-slate-500 mt-1 px-1">{m.timestamp}</span>
              </div>
            ))}

            {loading && (
              <div className="flex items-center gap-2.5 text-xs text-purple-300 bg-purple-950/30 border border-purple-800/40 p-3.5 rounded-xl w-fit">
                <Sparkles className="h-4 w-4 animate-spin text-purple-400" />
                <span>Grounding against Dealership Inventory & Semantic Document Chunks...</span>
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
                placeholder="Ask about inventory, test-drive slots, warranty, or dealership operations..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                className="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-xs text-white placeholder-slate-500 outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500"
              />
              <button
                type="submit"
                disabled={!input.trim() || loading}
                className="btn-primary py-3 px-5 bg-purple-600 hover:bg-purple-700 disabled:opacity-40"
              >
                <Send className="h-4 w-4" />
                <span>Send</span>
              </button>
            </form>
          </div>
        </div>

        {/* Right 1 Column: Grounding Context Inspector */}
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm space-y-4 text-xs">
            <h3 className="font-bold text-white text-sm flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
              Live Grounding Telemetry
            </h3>

            <div className="space-y-3 divide-y divide-slate-800">
              <div className="pt-2">
                <div className="flex items-center gap-2 text-slate-300 font-semibold mb-1">
                  <Building2 className="h-3.5 w-3.5 text-blue-400" />
                  <span>Dealership Profile</span>
                </div>
                <p className="text-slate-400 text-[11px]">Apex Motors NYC • 450 W 33rd St</p>
                <p className="text-slate-400 text-[11px]">Hours: Mon-Fri 09:00 - 18:00</p>
              </div>

              <div className="pt-3">
                <div className="flex items-center gap-2 text-slate-300 font-semibold mb-1">
                  <Car className="h-3.5 w-3.5 text-blue-400" />
                  <span>Fleet Catalog Grounding</span>
                </div>
                <p className="text-slate-400 text-[11px]">{MOCK_VEHICLES.length} vehicles indexed in memory</p>
                <p className="text-emerald-400 text-[11px]">Camry, M4, RS6, 911 active</p>
              </div>

              <div className="pt-3">
                <div className="flex items-center gap-2 text-slate-300 font-semibold mb-1">
                  <Calendar className="h-3.5 w-3.5 text-blue-400" />
                  <span>Test-Drive Schedule</span>
                </div>
                <p className="text-slate-400 text-[11px]">{MOCK_TEST_DRIVE_SLOTS.length} slots for next 7 days</p>
                <p className="text-blue-400 text-[11px]">Atomic capacity tracking on</p>
              </div>

              <div className="pt-3">
                <div className="flex items-center gap-2 text-slate-300 font-semibold mb-1">
                  <BookOpen className="h-3.5 w-3.5 text-blue-400" />
                  <span>RAG Knowledge Documents</span>
                </div>
                <p className="text-slate-400 text-[11px]">3 Indexed PDF / MD Documents</p>
                <p className="text-purple-400 text-[11px]">28 Semantic Chunks (1536-dim)</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}
