"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Bot,
  Calendar,
  Car,
  Code2,
  Inbox,
  ShieldCheck,
} from "lucide-react";
import { API_URL } from "./api";
import PublicAgentChat from "./components/PublicAgentChat";
import type { Dealership, Vehicle } from "./lib/types";

export default function LandingPage() {
  const [dealerships, setDealerships] = useState<Dealership[]>([]);
  const [selectedId, setSelectedId] = useState<number>(1);
  const [publicVehicles, setPublicVehicles] = useState<Vehicle[]>([]);
  const [origin, setOrigin] = useState("https://your-dealerdesk-domain.com");

  useEffect(() => {
    if (typeof window !== "undefined") {
      setOrigin(window.location.origin);
    }
    fetch(`${API_URL}/dealerships/public`)
      .then((res) => (res.ok ? res.json() : []))
      .then((items: Dealership[]) => {
        if (Array.isArray(items) && items.length > 0) {
          setDealerships(items);
          setSelectedId(items[0].id);
        }
      })
      .catch(() => {
        // Fallback to default dealership #1 if backend is offline
      });
  }, []);

  useEffect(() => {
    fetch(`${API_URL}/dealerships/${selectedId}/vehicles/public`)
      .then((res) => (res.ok ? res.json() : []))
      .then((items: Vehicle[]) => {
        if (Array.isArray(items)) setPublicVehicles(items.slice(0, 3));
      })
      .catch(() => setPublicVehicles([]));
  }, [selectedId]);

  const activeDealership = dealerships.find((d) => d.id === selectedId);
  const embedSnippet = `<iframe
  src="${origin}/embed/${selectedId}"
  title="Dealership AI Assistant"
  style="width:100%;max-width:420px;height:580px;border:0;border-radius:16px;box-shadow:0 12px 32px rgba(15,23,42,0.16);"
  allow="clipboard-write"
></iframe>`;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Top Public Navbar */}
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600 font-bold text-sm text-white">
              DD
            </span>
            <span className="text-lg font-medium tracking-tight text-[#171717]">
              Dealer<span className="text-blue-600">Desk</span>
            </span>
          </Link>

          <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-slate-600">
            <a href="#features" className="hover:text-slate-900">
              Platform
            </a>
            <a href="#live-agent" className="hover:text-slate-900">
              Live AI Agent
            </a>
            <a href="#embed" className="hover:text-slate-900">
              Website Embed
            </a>
          </nav>

          <div className="flex items-center gap-2.5">
            <Link href="/login" className="crm-btn-secondary">
              CRM Sign In
            </Link>
            <Link href="/dashboard" className="crm-btn-primary">
              Open CRM
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </header>

      {/* Hero + Live Agentic Chatbot */}
      <section id="live-agent" className="mx-auto max-w-7xl px-4 sm:px-6 py-12 lg:py-16">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
          <div className="lg:col-span-6 space-y-6">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
              <Bot className="h-3.5 w-3.5" />
              Multi-Tenant Automotive AI &amp; CRM
            </span>

            <h1 className="text-3xl sm:text-5xl font-medium tracking-tight text-[#171717] leading-tight">
              Turn every dealership website visitor into a booked test drive.
            </h1>

            <p className="text-base text-slate-600 leading-relaxed">
              DealerDesk gives automotive dealerships a 24/7 AI sales agent grounded in
              live vehicle inventory, test-drive slots, and warranty documents—plus a
              dedicated CRM for leads, multi-channel inbox handoff, and operations.
            </p>

            <div className="flex flex-wrap items-center gap-3">
              <Link href="/signup" className="crm-btn-primary px-5 py-2.5 text-sm">
                Create Account
              </Link>
              <Link
                href={`/embed/${selectedId}`}
                className="crm-btn-secondary px-5 py-2.5 text-sm"
              >
                Preview Embed Widget
              </Link>
            </div>

            {dealerships.length > 1 && (
              <div className="pt-2 max-w-xs">
                <label className="block text-xs font-semibold text-slate-600 mb-1">
                  Demo Showroom Tenant
                </label>
                <select
                  value={selectedId}
                  onChange={(e) => setSelectedId(Number(e.target.value))}
                  className="crm-select"
                >
                  {dealerships.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          <div className="lg:col-span-6">
            <PublicAgentChat
              dealershipId={selectedId}
              dealershipName={activeDealership?.name || "DealerDesk Showroom"}
            />
          </div>
        </div>
      </section>

      {/* Public Inventory Snapshot */}
      {publicVehicles.length > 0 && (
        <section className="border-t border-slate-200 bg-white py-12">
          <div className="mx-auto max-w-7xl px-4 sm:px-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-xl font-medium text-[#171717] tabular-nums">
                  Live Showroom Inventory ({activeDealership?.name || "Demo Dealership"})
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Publicly available units the AI agent can recommend and schedule right now
                </p>
              </div>
              <Link href="/login" className="text-xs font-semibold text-blue-600 hover:underline">
                Manage in CRM →
              </Link>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {publicVehicles.map((v) => (
                <div key={v.id} className="crm-card p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-medium text-[#171717]">
                        {v.model_year} {v.make} {v.model}
                      </p>
                      <p className="text-xs text-slate-500">{v.variant || "Standard trim"}</p>
                    </div>
                    <span className="text-sm font-medium text-[#171717]">
                      ${Number(v.price).toLocaleString()}
                    </span>
                  </div>
                  <div className="mt-3 flex items-center justify-between text-xs">
                    <span className="crm-badge crm-badge-success">Available</span>
                    <span className="font-mono text-slate-500">#{v.stock_number}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Features Grid */}
      <section id="features" className="border-t border-slate-200 py-14">
        <div className="mx-auto max-w-7xl px-4 sm:px-6">
          <div className="max-w-2xl mb-10">
            <h2 className="text-2xl font-medium text-[#171717] tabular-nums">
              Built as two clean layers: Customer Agent + Dealer CRM
            </h2>
            <p className="text-sm text-slate-600 mt-2">
              Keep your public website fast and unauthenticated while your sales team works
              inside an isolated, role-based CRM.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            <div className="crm-card p-5">
              <Bot className="h-5 w-5 text-blue-600 mb-3" />
              <h3 className="text-sm font-medium text-[#171717]">Agentic Sales Chat</h3>
              <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                Streams grounded answers from live vehicle stock, slot availability, and
                uploaded PDF/Markdown dealership docs.
              </p>
            </div>
            <div className="crm-card p-5">
              <Inbox className="h-5 w-5 text-blue-600 mb-3" />
              <h3 className="text-sm font-medium text-[#171717]">Multi-Channel Handoff</h3>
              <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                Website, WhatsApp, and Voice conversations route into one unified CRM inbox
                with instant human takeover.
              </p>
            </div>
            <div className="crm-card p-5">
              <Calendar className="h-5 w-5 text-blue-600 mb-3" />
              <h3 className="text-sm font-medium text-[#171717]">Test-Drive Engine</h3>
              <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                Automated slot generation, capacity tracking, reminders, and self-service
                reschedule/cancel flows.
              </p>
            </div>
            <div className="crm-card p-5">
              <ShieldCheck className="h-5 w-5 text-blue-600 mb-3" />
              <h3 className="text-sm font-medium text-[#171717]">Multi-Tenant Isolation</h3>
              <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                Every dealership gets isolated inventory, staff permissions, audit trails,
                and an embeddable chat widget.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Embed on Any Dealership Website */}
      <section id="embed" className="border-t border-slate-200 bg-white py-14">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
          <div className="lg:col-span-5 space-y-3">
            <div className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-blue-600">
              <Code2 className="h-4 w-4" />
              Drop-In Website Integration
            </div>
            <h2 className="text-2xl font-medium text-[#171717] tabular-nums">
              Already have a dealership website? Embed in 1 line.
            </h2>
            <p className="text-sm text-slate-600 leading-relaxed">
              Dealerships keep their existing WordPress, Dealer.com, or custom site. Just
              paste the scoped iframe snippet—zero CSS conflicts, zero CORS setup, and
              all leads flow directly into their DealerDesk CRM.
            </p>
            <div className="pt-2">
              <Link href={`/embed/${selectedId}`} className="crm-btn-secondary">
                Open Standalone Embed View
              </Link>
            </div>
          </div>

          <div className="lg:col-span-7">
            <pre className="rounded-xl bg-slate-900 text-slate-100 p-5 text-xs overflow-x-auto border border-slate-800">
              {embedSnippet}
            </pre>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-200 py-8 text-center text-xs text-slate-500">
        <div className="mx-auto max-w-7xl px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span className="flex items-center gap-1.5 font-medium text-slate-700">
            <Car className="h-4 w-4 text-blue-600" />
            DealerDesk Automotive CRM
          </span>
          <span>Public Showroom &amp; Agentic Chat · Isolated from Internal CRM</span>
        </div>
      </footer>
    </div>
  );
}
