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
import DealerDeskLogo from "./components/DealerDeskLogo";
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
  style="width:100%;max-width:420px;height:580px;border:0;border-radius:16px;box-shadow:0 8px 24px rgba(0,0,0,0.06);"
  allow="clipboard-write"
></iframe>`;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Top Public Navbar */}
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
          <Link href="/" className="shrink-0">
            <DealerDeskLogo variant="light" />
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

          <div className="flex shrink-0 items-center gap-3 sm:gap-4">
            <Link href="/login" className="whitespace-nowrap text-sm font-medium text-slate-600 hover:text-slate-900">
              Sign in
            </Link>
            <Link href="/dashboard" className="crm-btn-primary min-h-9 whitespace-nowrap px-3 py-2 text-sm">
              Open CRM
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </header>

      {/* Hero and live showroom assistant */}
      <section id="live-agent" className="mx-auto max-w-7xl px-4 sm:px-6 py-12 lg:py-16">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
          <div className="lg:col-span-6 space-y-6">
            <span className="inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-sm font-semibold text-blue-700">
              <Bot className="h-4 w-4" />
              AI-powered dealership sales
            </span>

            <h1 className="max-w-xl text-4xl sm:text-6xl font-semibold tracking-tight text-[#171717] leading-[1.02]">
              Sell more. Follow up faster.
            </h1>

            <p className="max-w-xl text-lg text-slate-600 leading-relaxed">
              Turn website questions into qualified leads and test-drive bookings, with every
              conversation connected to your dealership CRM.
            </p>

            <div className="flex flex-wrap items-center gap-3">
              <Link href="/signup" className="crm-btn-primary px-5 py-2.5 text-sm">
                Create account
              </Link>
              <Link
                href={`/embed/${selectedId}`}
                className="crm-btn-secondary px-5 py-2.5 text-sm"
              >
                Preview assistant
              </Link>
            </div>

            {dealerships.length > 1 && (
              <div className="pt-2 max-w-xs">
                <label className="block text-xs font-semibold text-slate-600 mb-1">
                  Demo showroom
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
                  Available vehicles
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  {activeDealership?.name || "Demo Dealership"} showroom inventory
                </p>
              </div>
              <Link href="/login" className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:underline">
                Manage in CRM
                <ArrowRight className="h-3 w-3" />
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
            <h2 className="text-2xl font-medium text-[#171717]">
              A showroom assistant and a dealership workspace
            </h2>
            <p className="text-sm text-slate-600 mt-2">
              The public assistant handles inventory questions and test-drive requests. The
              CRM brings lead follow-up, conversations, and dealership operations together.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            <div className="crm-card p-5">
              <Bot className="h-5 w-5 text-slate-500 mb-3" />
              <h3 className="text-sm font-medium text-[#171717]">Website sales assistant</h3>
              <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                Streams grounded answers from live vehicle stock, slot availability, and
                uploaded PDF/Markdown dealership docs.
              </p>
            </div>
            <div className="crm-card p-5">
              <Inbox className="h-5 w-5 text-slate-500 mb-3" />
              <h3 className="text-sm font-medium text-[#171717]">Conversation handoff</h3>
              <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                Website, WhatsApp, and voice conversations appear in one inbox so staff can
                take over when needed.
              </p>
            </div>
            <div className="crm-card p-5">
              <Calendar className="h-5 w-5 text-slate-500 mb-3" />
              <h3 className="text-sm font-medium text-[#171717]">Test-drive scheduling</h3>
              <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                Automated slot generation, capacity tracking, reminders, and self-service
                reschedule/cancel flows.
              </p>
            </div>
            <div className="crm-card p-5">
              <ShieldCheck className="h-5 w-5 text-slate-500 mb-3" />
              <h3 className="text-sm font-medium text-[#171717]">Dealership workspaces</h3>
              <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                Inventory, staff access, and records stay within each dealership workspace.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Embed on Any Dealership Website */}
      <section id="embed" className="border-t border-slate-200 bg-white py-14">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
          <div className="lg:col-span-5 space-y-3">
            <div className="inline-flex items-center gap-2 text-sm font-medium text-slate-600">
              <Code2 className="h-4 w-4 text-slate-500" />
              Website integration
            </div>
            <h2 className="text-2xl font-medium text-[#171717]">
              Add the assistant to your dealership website
            </h2>
            <p className="text-sm text-slate-600 leading-relaxed">
              Copy the iframe snippet into your existing site. Each widget is scoped to its
              dealership, and conversations appear in the DealerDesk inbox.
            </p>
            <div className="pt-2">
              <Link href={`/embed/${selectedId}`} className="crm-btn-secondary">
                Preview assistant
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
            <Car className="h-4 w-4 text-slate-500" />
            DealerDesk Automotive CRM
          </span>
          <span>Public showroom and sales assistant</span>
        </div>
      </footer>
    </div>
  );
}
