"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Activity,
  BookOpen,
  Building2,
  Calendar,
  Car,
  Layers,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  ShieldAlert,
  Bot,
  Users,
  X,
} from "lucide-react";
import { ApiError, api } from "../api";
import { useAuth } from "../providers";
import type { Dealership } from "../lib/types";

const dealershipNameCache = new Map<number, string>();

interface ShellProps {
  children: React.ReactNode;
}

const ROUTE_TITLES: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/inventory": "Vehicle Inventory",
  "/bookings": "Test Drives & Schedule",
  "/leads": "Customer Leads",
  "/inbox": "Conversation Inbox",
  "/brands": "Brand Portfolio",
  "/operations": "Operations & Outbox",
  "/assistant": "AI Sales Copilot",
  "/knowledge": "Knowledge Base (RAG)",
  "/staff": "Team & Staff",
  "/audit": "Audit Logs",
  "/dealerships": "SaaS Control Tower",
};

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
  const [isAvailable, setIsAvailable] = useState<boolean>(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!authReady || !user || user.role !== "customer") return;
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
  }, [activeDealershipId, authReady, user]);

  useEffect(() => {
    if (!authReady || !user || user.role === "customer") return;
    if (!activeDealershipId) {
      setDealershipName("");
      return;
    }

    const cachedName = dealershipNameCache.get(activeDealershipId);
    if (cachedName) {
      setDealershipName(cachedName);
      return;
    }

    let cancelled = false;
    api<{ name: string }>(`/dealerships/${activeDealershipId}`)
      .then((dealership) => {
        dealershipNameCache.set(activeDealershipId, dealership.name);
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
  }, [activeDealershipId, authReady, user]);

  useEffect(() => {
    if (authReady && !user) router.replace("/login");
  }, [authReady, router, user]);

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  async function toggleAvailability() {
    if (!activeDealershipId || !user) return;
    try {
      const nextState = !isAvailable;
      await api(`/dealerships/${activeDealershipId}/staff/${user.id}/availability`, {
        method: "PATCH",
        body: JSON.stringify({ is_available: nextState }),
      });
      setIsAvailable(nextState);
    } catch (error) {
      console.error("Failed to update availability", error);
    }
  }

  if (!authReady || !user) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-slate-50 text-slate-600 text-sm">
        {authReady ? "Redirecting to sign in..." : "Restoring your session..."}
      </main>
    );
  }

  const isManagerOrAdmin =
    user.role === "dealership_admin" || user.role === "manager";

  const navSections =
    user.role === "customer"
      ? [
          {
            title: "Customer Portal",
            links: [
              { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
              { href: "/inventory", label: "Browse Vehicles", icon: Car },
              { href: "/bookings", label: "My Test Drives", icon: Calendar },
              { href: "/assistant", label: "AI Assistant", icon: Bot },
            ],
          },
        ]
      : user.role === "dealerdesk_admin"
      ? [
          {
            title: "Platform Governance",
            links: [
              { href: "/dealerships", label: "SaaS Control Tower", icon: Building2 },
              { href: "/audit", label: "Platform Audit Trail", icon: ShieldAlert },
              { href: "/assistant", label: "AI Copilot Workspace", icon: Bot },
            ],
          },
        ]
      : [
          {
            title: "Sales & CRM",
            links: [
              { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
              { href: "/leads", label: "Customer Leads", icon: Users },
              { href: "/inbox", label: "Conversation Inbox", icon: MessageSquare },
              { href: "/bookings", label: "Test Drives", icon: Calendar },
              { href: "/inventory", label: "Vehicle Inventory", icon: Car },
              ...(isManagerOrAdmin
                ? [{ href: "/brands", label: "Brands", icon: Layers }]
                : []),
            ],
          },
          {
            title: "AI & Knowledge",
            links: [
              { href: "/assistant", label: "AI Copilot", icon: Bot },
              { href: "/knowledge", label: "Knowledge Base", icon: BookOpen },
            ],
          },
          ...(isManagerOrAdmin
            ? [
                {
                  title: "Operations & Governance",
                  links: [
                    { href: "/operations", label: "Operations & Outbox", icon: Activity },
                    { href: "/staff", label: "Team & Staff", icon: Users },
                    { href: "/audit", label: "Audit Logs", icon: ShieldAlert },
                  ],
                },
              ]
            : []),
        ];

  const pageTitle = ROUTE_TITLES[pathname] ?? "Workspace";

  const sidebarContent = (
    <div className="flex h-full flex-col bg-[#0f0f10] text-[#ededed]">
      {/* Brand Header */}
      <div className="px-4 py-3.5 border-b border-white/[0.08]">
        <div className="flex items-center justify-between">
          <Link href="/dashboard" className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-white text-[#0f0f10] font-mono font-medium text-xs">
              DD
            </div>
            <div>
              <span className="font-medium text-sm tracking-tight text-white">
                DealerDesk
              </span>
              <p className="text-[11px] text-[#85858b]">Dealership CRM</p>
            </div>
          </Link>
          <button
            type="button"
            onClick={() => setMobileMenuOpen(false)}
            className="lg:hidden rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white"
            aria-label="Close navigation"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Workspace Context */}
        {user.role === "dealerdesk_admin" ? (
          <div className="mt-3 rounded-lg bg-slate-800/70 border border-slate-700/70 px-3 py-2">
            <div className="flex items-center gap-1.5 text-xs font-medium text-[#a1a1a6]">
              <Building2 className="h-3.5 w-3.5" />
              SaaS Scope
            </div>
            <p className="mt-0.5 text-xs font-medium text-white">Cross-Tenant Platform</p>
          </div>
        ) : user.role === "customer" ? (
          <div className="mt-3">
            <label
              htmlFor="customer-dealership"
              className="block text-xs font-medium text-[#85858b] mb-1"
            >
              Dealership
            </label>
            <select
              id="customer-dealership"
              value={activeDealershipId || ""}
              onChange={(event) => {
                const dealershipId = Number(event.target.value);
                if (dealershipId) setActiveDealershipId(dealershipId);
              }}
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-1.5 text-xs text-white"
            >
              <option value="" disabled>
                Select dealership
              </option>
              {publicDealerships.map((dealership) => (
                <option key={dealership.id} value={dealership.id}>
                  {dealership.name}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div className="mt-3 rounded-lg bg-slate-800/70 border border-slate-700/70 px-3 py-2">
            <span className="block text-xs font-medium text-[#85858b]">
              Workspace
            </span>
            <p className="mt-0.5 truncate text-xs font-semibold text-white">
              {dealershipName || "Loading dealership..."}
            </p>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
        {navSections.map((section) => (
          <div key={section.title}>
            <p className="px-2.5 text-xs font-medium text-[#85858b] mb-1.5">
              {section.title}
            </p>
            <div className="space-y-0.5">
              {section.links.map((link) => {
                const Icon = link.icon;
                const isActive = pathname === link.href;
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs font-medium transition-colors ${
                      isActive
                        ? "bg-blue-600 text-white"
                        : "text-slate-300 hover:bg-slate-800 hover:text-white"
                    }`}
                  >
                    <Icon className={`h-4 w-4 shrink-0 ${isActive ? "text-white" : "text-slate-400"}`} />
                    <span className="truncate">{link.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* User Footer */}
      <div className="p-3 border-t border-slate-800 bg-slate-950/50">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="h-8 w-8 shrink-0 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center font-semibold text-xs text-blue-300">
              {user.name.slice(0, 2).toUpperCase() || "DD"}
            </div>
            <div className="min-w-0">
              <p className="text-xs font-semibold text-white truncate">{user.name}</p>
              <p className="text-[11px] text-slate-400 truncate capitalize">
                {user.role.replaceAll("_", " ")}
              </p>
              {user.role !== "customer" && user.role !== "dealerdesk_admin" && (
                <button
                  type="button"
                  onClick={() => void toggleAvailability()}
                  className={`mt-0.5 inline-flex items-center gap-1 text-[10px] font-semibold ${
                    isAvailable ? "text-emerald-400" : "text-amber-400"
                  } hover:underline`}
                >
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      isAvailable ? "bg-emerald-400" : "bg-amber-400"
                    }`}
                  />
                  {isAvailable ? "Available for Leads" : "Unavailable"}
                </button>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={() => void handleLogout()}
            title="Sign out"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-rose-400 transition-colors"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="crm-shell">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:block w-64 shrink-0 h-screen sticky top-0 border-r border-slate-800">
        {sidebarContent}
      </aside>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div
            className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs"
            onClick={() => setMobileMenuOpen(false)}
          />
          <aside className="relative w-64 max-w-[80vw] h-full z-10 shadow-xl">
            {sidebarContent}
          </aside>
        </div>
      )}

      {/* Main Content Area */}
      <div className="crm-main">
        <header className="crm-header">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              className="lg:hidden rounded-lg p-2 text-slate-600 hover:bg-slate-100"
              aria-label="Open navigation"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div className="flex items-center gap-2 text-sm min-w-0">
              <span className="hidden sm:inline text-slate-400 font-medium truncate">
                {user.role === "dealerdesk_admin"
                  ? "Platform"
                  : dealershipName || "DealerDesk"}
              </span>
              <span className="hidden sm:inline text-slate-300">/</span>
              <span className="font-semibold text-slate-900 truncate">{pageTitle}</span>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            {user.role !== "customer" && user.role !== "dealerdesk_admin" && (
              <Link href="/inbox" className="crm-btn-secondary hidden sm:inline-flex min-h-8 text-xs py-1.5 px-3">
                <MessageSquare className="h-3.5 w-3.5 text-slate-500" />
                Inbox
              </Link>
            )}
            <Link href="/assistant" className="crm-btn-primary min-h-8 text-xs py-1.5 px-3">
              <Bot className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">AI Copilot</span>
            </Link>
          </div>
        </header>

        <main className="crm-content">{children}</main>
      </div>
    </div>
  );
}
