"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
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
  Search,
  Activity,
  ChevronDown,
  UserCheck,
} from "lucide-react";
import { useAuth, User } from "../providers";
import { MOCK_DEALERSHIPS } from "../lib/mockData";
import AiCopilotDrawer from "./AiCopilotDrawer";

interface ShellProps {
  children: React.ReactNode;
}

export default function Shell({ children }: ShellProps) {
  const {
    user,
    logout,
    activeDealershipId,
    setActiveDealershipId,
    setAiCopilotOpen,
    switchRoleDemo,
  } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  const currentDealership =
    MOCK_DEALERSHIPS.find((d) => d.id === activeDealershipId) || MOCK_DEALERSHIPS[0];

  const navSections = [
    {
      title: "Operations",
      links: [
        { href: "/", label: "Dashboard", icon: LayoutDashboard },
        { href: "/inventory", label: "Vehicle Inventory", icon: Car },
        { href: "/bookings", label: "Test Drives & CRM", icon: Calendar },
      ],
    },
    {
      title: "Intelligence",
      links: [
        { href: "/assistant", label: "AI Copilot Workspace", icon: Sparkles },
        { href: "/knowledge", label: "Knowledge Center (RAG)", icon: BookOpen },
      ],
    },
    {
      title: "Governance",
      links: [
        { href: "/staff", label: "Team & Staff", icon: Users },
        { href: "/audit", label: "Security & Audit Logs", icon: ShieldAlert },
      ],
    },
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
                  ERP
                </span>
              </div>
              <p className="text-[11px] text-slate-400">Automotive Operations Platform</p>
            </div>
          </Link>

          {/* Dealership Switcher */}
          <div className="mt-4">
            <label className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1 block">
              Active Dealership Workspace
            </label>
            <div className="relative">
              <select
                value={activeDealershipId}
                onChange={(e) => setActiveDealershipId(Number(e.target.value))}
                className="w-full appearance-none rounded-lg bg-slate-800/80 border border-slate-700/80 px-2.5 py-2 text-xs font-medium text-slate-200 outline-none hover:border-slate-600 focus:border-blue-500"
              >
                {MOCK_DEALERSHIPS.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
            </div>
          </div>
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

        {/* Demo Role Switcher */}
        <div className="px-3 py-3 border-t border-slate-800/80 bg-slate-900/50">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1">
              <UserCheck className="h-3 w-3 text-blue-400" />
              Role Perspective
            </span>
          </div>
          <div className="grid grid-cols-2 gap-1 text-[11px]">
            <button
              onClick={() => switchRoleDemo("dealership_admin")}
              className={`rounded px-1.5 py-1 font-medium transition-colors ${
                user?.role === "dealership_admin"
                  ? "bg-blue-600 text-white"
                  : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              }`}
            >
              Admin
            </button>
            <button
              onClick={() => switchRoleDemo("manager")}
              className={`rounded px-1.5 py-1 font-medium transition-colors ${
                user?.role === "manager"
                  ? "bg-blue-600 text-white"
                  : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              }`}
            >
              Manager
            </button>
            <button
              onClick={() => switchRoleDemo("sales_rep")}
              className={`rounded px-1.5 py-1 font-medium transition-colors ${
                user?.role === "sales_rep"
                  ? "bg-blue-600 text-white"
                  : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              }`}
            >
              Sales Rep
            </button>
            <button
              onClick={() => switchRoleDemo("customer")}
              className={`rounded px-1.5 py-1 font-medium transition-colors ${
                user?.role === "customer"
                  ? "bg-blue-600 text-white"
                  : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              }`}
            >
              Customer
            </button>
          </div>
        </div>

        {/* User Footer Profile & Health Status */}
        <div className="p-3 border-t border-slate-800 bg-slate-950">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5 text-[11px] text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>DB Ping: 12ms</span>
            </div>
            <span className="text-[10px] text-slate-400 uppercase font-mono">v0.1.0-erp</span>
          </div>

          <div className="flex items-center justify-between pt-1">
            <div className="flex items-center gap-2 min-w-0">
              <div className="h-8 w-8 rounded-full bg-slate-800 flex items-center justify-center font-bold text-xs text-blue-400 border border-slate-700">
                {user?.name?.slice(0, 2).toUpperCase() || "DD"}
              </div>
              <div className="min-w-0">
                <p className="text-xs font-bold text-white truncate">{user?.name || "Marcus Vance"}</p>
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
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <Building2 className="h-4 w-4 text-blue-400" />
              <span className="font-semibold text-slate-200">{currentDealership.name}</span>
              <span>/</span>
              <span className="capitalize">{pathname === "/" ? "Executive Dashboard" : pathname.slice(1)}</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Quick Copilot Launcher in Topbar */}
            <button
              onClick={() => setAiCopilotOpen(true)}
              className="flex items-center gap-2 rounded-lg bg-blue-600/10 border border-blue-500/30 px-3 py-1.5 text-xs font-semibold text-blue-400 hover:bg-blue-600 hover:text-white transition-all shadow-sm"
            >
              <Sparkles className="h-3.5 w-3.5" />
              <span>Ask AI Copilot</span>
            </button>

            {/* Status indicator */}
            <div className="hidden sm:flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-400 border border-emerald-500/20">
              <Activity className="h-3 w-3" />
              <span>All Services Operational</span>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="erp-content">{children}</main>
      </div>

      {/* Embedded Global Copilot Drawer */}
      <AiCopilotDrawer />
    </div>
  );
}
