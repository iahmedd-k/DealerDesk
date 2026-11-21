"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  Car,
  Calendar,
  Sparkles,
  BookOpen,
  Users,
  ShieldAlert,
  Building2,
  LogOut,
  Layers,
} from "lucide-react";
import { ApiError, api } from "../api";
import { useAuth } from "../providers";
import type { Dealership } from "../lib/types";

interface ShellProps {
  children: React.ReactNode;
}

export default function Shell({ children }: ShellProps) {
  const {
    user,
    logout,
    activeDealershipId,
    setActiveDealershipId,
    authReady,
  } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [dealershipName, setDealershipName] = useState("");
  const [publicDealerships, setPublicDealerships] = useState<Dealership[]>([]);

  useEffect(() => {
    if (user?.role !== "customer") return;
    let cancelled = false;
    api<Dealership[]>("/dealerships/public")
      .then((items) => {
        if (cancelled) return;
        setPublicDealerships(items);
        const selected = items.find((item) => item.id === activeDealershipId);
        setDealershipName(selected?.name ?? "");
      })
      .catch((error: unknown) => {
        if (!cancelled) console.error("Could not load available dealerships.", error);
      });
    return () => {
      cancelled = true;
    };
  }, [activeDealershipId, user?.role]);

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  useEffect(() => {
    if (user?.role === "customer") return;
    if (!activeDealershipId) {
      setDealershipName("");
      return;
    }

    let cancelled = false;
    api<{ name: string }>(`/dealerships/${activeDealershipId}`)
      .then((dealership) => {
        if (!cancelled) setDealershipName(dealership.name);
      })
      .catch((error: unknown) => {
        if (!cancelled && !(error instanceof ApiError && error.statusCode === 401)) {
          console.error("Could not load the active dealership.", error);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeDealershipId, user?.role]);

  useEffect(() => {
    if (authReady && !user) router.replace("/login");
  }, [authReady, router, user]);

  if (!authReady || !user) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-300">
        {authReady ? "Redirecting to sign in..." : "Restoring your session..."}
      </main>
    );
  }

  const navSections =
    user.role === "customer"
      ? [
          {
            title: "Customer",
            links: [
              { href: "/inventory", label: "Browse Vehicles", icon: Car },
              { href: "/bookings", label: "My Test Drives", icon: Calendar },
              { href: "/assistant", label: "AI Assistant", icon: Sparkles },
            ],
          },
        ]
      : user.role === "dealerdesk_admin"
      ? [
          {
            title: "SaaS Platform Management",
            links: [
              { href: "/dealerships", label: "SaaS Control Tower", icon: Building2 },
              { href: "/audit", label: "Platform Audit Trail", icon: ShieldAlert },
              { href: "/assistant", label: "AI Copilot Workspace", icon: Sparkles },
            ],
          },
        ]
      : [
          {
            title: "Operations",
            links: [
              { href: "/", label: "Executive Dashboard", icon: LayoutDashboard },
              { href: "/inventory", label: "Vehicle Inventory", icon: Car },
              { href: "/bookings", label: "Test Drives & CRM", icon: Calendar },
              { href: "/leads", label: "Customer Leads", icon: Users },
              ...(["dealership_admin", "manager"].includes(user.role)
                ? [{ href: "/brands", label: "Multi-Brand Portfolio", icon: Layers }]
                : []),
            ],
          },
          {
            title: "Intelligence",
            links: [
              { href: "/assistant", label: "AI Copilot Workspace", icon: Sparkles },
              { href: "/knowledge", label: "Knowledge Center (RAG)", icon: BookOpen },
            ],
          },
          ...(["dealership_admin", "manager"].includes(user.role)
            ? [
                {
                  title: "Governance",
                  links: [
                    { href: "/staff", label: "Team & Staff", icon: Users },
                    { href: "/audit", label: "Security & Audit Logs", icon: ShieldAlert },
                  ],
                },
              ]
            : []),
        ];

  return (
    <div className="erp-container">
      {/* ERP Sidebar */}
      <aside className="erp-sidebar">
        {/* Dealership Brand & Logo */}
        <div className="p-5 border-b border-slate-800">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600 font-black text-white shadow-md">
              DD
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-bold text-base tracking-tight text-white">DealerDesk</span>
                <span className="rounded bg-blue-500/20 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-blue-400">
                  CRM
                </span>
              </div>
              <p className="text-[11px] text-slate-400">Automotive Operations Platform</p>
            </div>
          </Link>

          {/* Active dealership context */}
          {user?.role === "dealerdesk_admin" ? (
            <div className="mt-4 rounded-lg bg-indigo-950/40 border border-indigo-500/30 p-2.5">
              <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-indigo-400 mb-1">
                <Building2 className="h-3.5 w-3.5" />
                SaaS Scope
              </div>
              <p className="text-xs font-semibold text-slate-200">Cross-Tenant Platform</p>
              <p className="text-[10px] text-slate-400 mt-0.5">Monitoring all registered dealerships</p>
            </div>
          ) : user.role === "customer" ? (
            <div className="mt-4">
              <label htmlFor="customer-dealership" className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1 block">
                Choose a dealership
              </label>
              <select
                id="customer-dealership"
                value={activeDealershipId || ""}
                onChange={(event) => {
                  const dealershipId = Number(event.target.value);
                  if (dealershipId) setActiveDealershipId(dealershipId);
                }}
                className="w-full truncate rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-2 text-xs font-medium text-slate-200"
              >
                <option value="" disabled>Select dealership</option>
                {publicDealerships.map((dealership) => (
                  <option key={dealership.id} value={dealership.id}>{dealership.name}</option>
                ))}
              </select>
            </div>
          ) : (
            <div className="mt-4">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1 block">
                Dealership Workspace
              </span>
              <p className="truncate rounded-lg bg-slate-800/80 border border-slate-700/80 px-2.5 py-2 text-xs font-medium text-slate-200">
                {dealershipName || "Loading dealership..."}
              </p>
            </div>
          )}
        </div>

        {/* Navigation Groups */}
        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
          {navSections.map((section) => (
            <div key={section.title}>
              <p className="px-3 text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">
                {section.title}
              </p>
              <div className="space-y-1">
                {section.links.map((link) => {
                  const Icon = link.icon;
                  const isActive = pathname === link.href;
                  return (
                    <Link
                      key={link.href}
                      href={link.href}
                      className={`flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-semibold transition-all ${
                        isActive
                          ? "bg-blue-600 text-white shadow-sm"
                          : "text-slate-300 hover:bg-slate-800 hover:text-white"
                      }`}
                    >
                      <Icon className={`h-4 w-4 ${isActive ? "text-white" : "text-slate-400"}`} />
                      <span>{link.label}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* User Footer Profile & Health Status */}
        <div className="p-3 border-t border-slate-800 bg-slate-950">
          <div className="flex items-center justify-between pt-1">
            <div className="flex items-center gap-2 min-w-0">
              <div className="h-8 w-8 rounded-full bg-slate-800 flex items-center justify-center font-bold text-xs text-blue-400 border border-slate-700">
                {user?.name?.slice(0, 2).toUpperCase() || "DD"}
              </div>
              <div className="min-w-0">
                <p className="text-xs font-bold text-white truncate">{user.name}</p>
                <p className="text-[10px] text-slate-400 truncate capitalize">
                  {user?.role?.replaceAll("_", " ") || "Administrator"}
                </p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              title="Sign out"
              className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-800 rounded transition-colors"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main ERP Canvas */}
      <div className="erp-main">
        {/* Top Header Bar */}
        <header className="erp-header">
          <div className="flex items-center gap-3">
            {user?.role === "dealerdesk_admin" ? (
              <div className="flex items-center gap-2 text-xs">
                <span className="flex items-center gap-1.5 rounded-full bg-indigo-500/20 px-2.5 py-0.5 text-[11px] font-bold text-indigo-300 border border-indigo-500/30">
                  👑 DealerDesk SaaS SuperAdmin
                </span>
                <span className="text-slate-500">/</span>
                <span className="text-slate-300 font-medium capitalize">
                  {pathname === "/dealerships" ? "SaaS Control Tower" : pathname.replace("/", "")}
                </span>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <Building2 className="h-4 w-4 text-blue-400" />
                <span className="font-semibold text-slate-200">{dealershipName || "Dealership"}</span>
                <span className="text-slate-500">/</span>
                <span className="capitalize">{pathname === "/" ? "Executive Dashboard" : pathname.slice(1)}</span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-3">
            {/* Quick Copilot Launcher in Topbar */}
            <Link
              href="/assistant"
              className="flex items-center gap-2 rounded-lg bg-blue-600/10 border border-blue-500/30 px-3 py-1.5 text-xs font-semibold text-blue-400 hover:bg-blue-600 hover:text-white transition-all shadow-sm"
            >
              <Sparkles className="h-3.5 w-3.5" />
              <span>Ask AI Copilot</span>
            </Link>
          </div>
        </header>

        {/* Page Content */}
        <main className="erp-content">{children}</main>
      </div>

    </div>
  );
}
