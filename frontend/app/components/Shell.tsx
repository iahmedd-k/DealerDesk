"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Activity,
  BookOpen,
  Bell,
  Building2,
  Calendar,
  Car,
  Layers,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  Settings,
  ShieldAlert,
  Bot,
  UserRound,
  Users,
  Wrench,
  X,
} from "lucide-react";
import { ApiError, api } from "../api";
import { useAuth } from "../providers";
import type { Dealership, InAppNotification } from "../lib/types";
import DealerDeskLogo from "./DealerDeskLogo";

const dealershipNameCache = new Map<number, string>();

interface ShellProps {
  children: React.ReactNode;
}

const ROUTE_TITLES: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/inventory": "Inventory",
  "/bookings": "Test drives",
  "/service": "Service & warranty",
  "/leads": "Leads",
  "/inbox": "Inbox",
  "/brands": "Brands",
  "/operations": "Operations",
  "/assistant": "Sales assistant",
  "/knowledge": "Knowledge base",
  "/staff": "Team",
  "/audit": "Audit log",
  "/dealerships": "Dealerships",
  "/profile": "Profile",
  "/settings": "Settings",
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
  const [notifications, setNotifications] = useState<InAppNotification[]>([]);
  const [notificationsError, setNotificationsError] = useState(false);
  const [notificationPanelOpen, setNotificationPanelOpen] = useState(false);

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (user && typeof user.is_available === "boolean") {
      setIsAvailable(user.is_available);
    }
  }, [user]);

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
    if (
      !authReady ||
      !user ||
      user.role === "customer" ||
      user.role === "dealerdesk_admin" ||
      !activeDealershipId
    ) {
      setNotifications([]);
      return;
    }

    let cancelled = false;
    const loadNotifications = async () => {
      try {
        const items = await api<InAppNotification[]>(
          `/dealerships/${activeDealershipId}/notifications/center`,
        );
        if (!cancelled) {
          setNotifications(items);
          setNotificationsError(false);
        }
      } catch {
        if (!cancelled) {
          setNotificationsError(true);
        }
      }
    };

    void loadNotifications();
    const intervalId = window.setInterval(() => {
      if (document.visibilityState === "visible") void loadNotifications();
    }, 30_000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
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

  const roleNavSections =
    user.role === "customer"
      ? [
          {
            title: "Your dealership",
            links: [
              { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
              { href: "/inventory", label: "Inventory", icon: Car },
              { href: "/bookings", label: "My test drives", icon: Calendar },
              { href: "/assistant", label: "Showroom assistant", icon: Bot },
            ],
          },
        ]
      : user.role === "dealerdesk_admin"
      ? [
          {
            title: "Platform",
            links: [
              { href: "/dealerships", label: "Dealerships", icon: Building2 },
              { href: "/audit", label: "Audit log", icon: ShieldAlert },
              { href: "/assistant", label: "Assistant", icon: Bot },
            ],
          },
        ]
      : [
          {
            title: "Sales",
            links: [
              { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
              { href: "/leads", label: "Leads", icon: Users },
              { href: "/inbox", label: "Inbox", icon: MessageSquare },
              { href: "/bookings", label: "Test Drives", icon: Calendar },
              { href: "/service", label: "Service & warranty", icon: Wrench },
              { href: "/inventory", label: "Inventory", icon: Car },
              ...(isManagerOrAdmin
                ? [{ href: "/brands", label: "Brands", icon: Layers }]
                : []),
            ],
          },
          {
            title: "Resources",
            links: [
              { href: "/assistant", label: "Sales assistant", icon: Bot },
              { href: "/knowledge", label: "Knowledge Base", icon: BookOpen },
            ],
          },
          ...(isManagerOrAdmin
            ? [
                {
                  title: "Administration",
                  links: [
                    { href: "/operations", label: "Operations", icon: Activity },
                    { href: "/staff", label: "Team", icon: Users },
                    { href: "/audit", label: "Audit log", icon: ShieldAlert },
                  ],
                },
              ]
            : []),
        ];
  const navSections = roleNavSections;

  const pageTitle = ROUTE_TITLES[pathname] ?? "Workspace";

  const sidebarContent = (
    <div className="crm-sidebar flex h-full flex-col justify-between overflow-hidden">
      {/* Brand Header */}
      <div className="border-b border-slate-200/80 px-3.5 py-2.5 shrink-0">
        <div className="flex items-center justify-between">
          <Link href="/dashboard" className="flex items-center gap-2">
            <DealerDeskLogo variant="light" subtitle="Dealership CRM" size="sm" />
          </Link>
          <button
            type="button"
            onClick={() => setMobileMenuOpen(false)}
            className="rounded-lg p-1 text-slate-500 hover:bg-slate-100 lg:hidden"
            aria-label="Close navigation"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Workspace Context */}
        {user.role === "dealerdesk_admin" ? (
          <div className="crm-sidebar-context mt-2.5 rounded-lg px-2.5 py-1.5">
            <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-500">
              <Building2 className="h-3 w-3" aria-hidden="true" />
              Platform scope
            </div>
            <p className="mt-0.5 text-xs font-medium text-slate-900">All dealerships</p>
          </div>
        ) : user.role === "customer" ? (
          <div className="mt-2.5">
            <label
              htmlFor="customer-dealership"
              className="mb-1 block text-[11px] font-medium text-slate-600"
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
              className="crm-select w-full py-1.5 text-xs"
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
          <div className="crm-sidebar-context mt-2.5 rounded-lg px-2.5 py-1.5">
            <span className="block text-[10px] font-medium text-slate-500">
              Workspace
            </span>
            <p className="truncate text-xs font-medium text-slate-900">
              {dealershipName || "Loading dealership..."}
            </p>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav aria-label="Main navigation" className="flex-1 space-y-3 px-2.5 py-2.5 overflow-y-auto lg:overflow-hidden">
        {navSections.map((section) => (
          <div key={section.title}>
            <p className="mb-1 px-2 text-[10px] font-medium uppercase tracking-[0.12em] text-slate-400">
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
                    className={`relative flex items-center gap-2 rounded-md px-2.5 py-2 text-[13px] font-medium transition-colors ${
                      isActive
                        ? "bg-slate-900 text-white"
                        : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                    }`}
                    aria-current={isActive ? "page" : undefined}
                  >
                    {isActive && (
                      <span className="absolute -left-2.5 h-5 w-1 rounded-r-full bg-blue-500" />
                    )}
                    <Icon className={`h-3.5 w-3.5 shrink-0 ${isActive ? "text-white" : "text-slate-500"}`} aria-hidden="true" />
                    <span className="truncate">{link.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* User Footer */}
      <div className="border-t border-slate-200/80 px-3 py-2.5 shrink-0">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2.5 min-w-0">
            <Link
              href="/profile"
              aria-label="Open profile"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-700 hover:bg-slate-200"
            >
              {user.name.trim().slice(0, 2).toUpperCase() || "DD"}
            </Link>
            <div className="min-w-0">
              <Link href="/profile" className="block truncate text-xs font-semibold text-slate-900 hover:underline">
                {user.name}
              </Link>
              <p className="truncate text-[11px] capitalize text-slate-500">
                {user.role.replaceAll("_", " ")}
              </p>
              {user.role !== "customer" && user.role !== "dealerdesk_admin" && (
                <button
                  type="button"
                  onClick={() => void toggleAvailability()}
                  className={`mt-0.5 inline-flex items-center gap-1 text-[11px] font-semibold ${
                    isAvailable ? "text-emerald-700" : "text-amber-700"
                  } hover:underline`}
                >
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      isAvailable ? "bg-emerald-600" : "bg-amber-600"
                    }`}
                  />
                  {isAvailable ? "Available for Leads" : "Unavailable"}
                </button>
              )}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <Link
              href="/settings"
              title="Settings"
              aria-label="Settings"
              className="rounded-md p-1.5 text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
            >
              <Settings className="h-4 w-4" aria-hidden="true" />
            </Link>
            <button
              type="button"
              onClick={() => void handleLogout()}
              title="Sign out"
              aria-label="Sign out"
              className="rounded-md p-1.5 text-slate-500 transition-colors hover:bg-rose-50 hover:text-rose-700"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="crm-shell">
      {/* Desktop Sidebar */}
      <aside className="crm-sidebar sticky top-0 hidden h-screen w-64 shrink-0 border-r border-slate-200 lg:block">
        {sidebarContent}
      </aside>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div
            className="fixed inset-0 bg-black/45"
            onClick={() => setMobileMenuOpen(false)}
          />
          <aside className="crm-sidebar relative z-10 h-full w-64 max-w-[80vw] border-r border-slate-200 shadow-xl">
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
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setNotificationPanelOpen((open) => !open)}
                  aria-label={`Notifications${notifications.length ? ` (${notifications.length})` : ""}`}
                  aria-expanded={notificationPanelOpen}
                  aria-controls="notification-center"
                  className="relative rounded-lg p-2 text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
                >
                  <Bell className="h-4 w-4" aria-hidden="true" />
                  {notifications.length > 0 && (
                    <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-semibold leading-none text-white">
                      {notifications.length > 9 ? "9+" : notifications.length}
                    </span>
                  )}
                </button>
                {notificationPanelOpen && (
                  <section
                    id="notification-center"
                    aria-label="Notification center"
                    className="absolute right-0 z-40 mt-2 w-80 max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl"
                  >
                    <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
                      <h2 className="text-sm font-semibold text-slate-900">Notifications</h2>
                      <span className="text-xs text-slate-500">
                        {notifications.length} active
                      </span>
                    </div>
                    <div className="max-h-96 overflow-y-auto">
                      {notificationsError ? (
                        <p className="px-4 py-6 text-center text-sm text-rose-700">
                          Notifications could not be loaded.
                        </p>
                      ) : notifications.length === 0 ? (
                        <p className="px-4 py-6 text-center text-sm text-slate-500">
                          You&apos;re all caught up.
                        </p>
                      ) : (
                        notifications.map((notification) => (
                          <Link
                            key={notification.id}
                            href={notification.href}
                            onClick={() => setNotificationPanelOpen(false)}
                            className="block border-b border-slate-100 px-4 py-3 transition-colors last:border-b-0 hover:bg-slate-50"
                          >
                            <span className="flex items-center gap-2">
                              <span
                                className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                                  notification.severity === "urgent"
                                    ? "bg-rose-600"
                                    : notification.severity === "high"
                                      ? "bg-amber-500"
                                      : "bg-slate-400"
                                }`}
                              />
                              <span className="truncate text-sm font-medium text-slate-900">
                                {notification.title}
                              </span>
                            </span>
                            <span className="mt-1 block pl-3.5 text-xs text-slate-600">
                              {notification.message}
                            </span>
                            <time
                              className="mt-1 block pl-3.5 text-[11px] text-slate-400"
                              dateTime={notification.created_at}
                            >
                              {new Date(notification.created_at).toLocaleString()}
                            </time>
                          </Link>
                        ))
                      )}
                    </div>
                  </section>
                )}
              </div>
            )}
            {user.role !== "customer" && user.role !== "dealerdesk_admin" && (
              <Link href="/inbox" className="crm-btn-secondary hidden sm:inline-flex min-h-8 text-xs py-1.5 px-3">
                <MessageSquare className="h-3.5 w-3.5 text-slate-500" />
                Inbox
              </Link>
            )}
            <Link href="/assistant" className="crm-btn-primary min-h-8 text-xs py-1.5 px-3">
              <Bot className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Assistant</span>
            </Link>
          </div>
        </header>

        <main className="crm-content">{children}</main>
        <nav className="crm-mobile-nav lg:hidden" aria-label="Mobile navigation">
          <Link href="/dashboard" data-active={pathname === "/dashboard"}>
            <LayoutDashboard className="h-5 w-5" />
            <span>Overview</span>
          </Link>
          <Link href="/leads" data-active={pathname === "/leads"}>
            <Users className="h-5 w-5" />
            <span>Leads</span>
          </Link>
          <Link href="/inbox" data-active={pathname === "/inbox"}>
            <MessageSquare className="h-5 w-5" />
            <span>Inbox</span>
          </Link>
          <Link href="/bookings" data-active={pathname === "/bookings"}>
            <Calendar className="h-5 w-5" />
            <span>Bookings</span>
          </Link>
        </nav>
      </div>
    </div>
  );
}
