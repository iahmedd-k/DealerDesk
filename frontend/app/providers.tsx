"use client";

import { createContext, useContext, useEffect, useState } from "react";

export type User = {
  id: number;
  name: string;
  email: string;
  role: "dealership_admin" | "manager" | "sales_rep" | "customer" | "dealerdesk_admin";
  dealership_id: number | null;
};

type AuthContextValue = {
  user: User | null;
  accessToken: string | null;
  activeDealershipId: number;
  setActiveDealershipId: (id: number) => void;
  aiCopilotOpen: boolean;
  setAiCopilotOpen: (open: boolean) => void;
  setSession: (accessToken: string, refreshToken: string, user: User) => void;
  logout: () => Promise<void>;
  switchRoleDemo: (role: User["role"]) => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const DEFAULT_DEMO_USER: User = {
  id: 1,
  name: "Marcus Vance (Admin)",
  email: "marcus@apexmotors.com",
  role: "dealership_admin",
  dealership_id: 1,
};

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(DEFAULT_DEMO_USER);
  const [accessToken, setAccessToken] = useState<string | null>("demo-bearer-token");
  const [activeDealershipId, setActiveDealershipId] = useState<number>(1);
  const [aiCopilotOpen, setAiCopilotOpen] = useState<boolean>(false);

  useEffect(() => {
    try {
      const storedToken = localStorage.getItem("dealerdesk_access");
      const storedUser = localStorage.getItem("dealerdesk_user");
      const storedDealership = localStorage.getItem("dealerdesk_active_dealership");
      if (storedToken) setAccessToken(storedToken);
      if (storedUser) setUser(JSON.parse(storedUser));
      if (storedDealership) setActiveDealershipId(Number(storedDealership));
    } catch {
      // Keep default demo user
    }
  }, []);

  function setSession(accessTokenValue: string, refreshToken: string, nextUser: User) {
    try {
      localStorage.setItem("dealerdesk_access", accessTokenValue);
      localStorage.setItem("dealerdesk_refresh", refreshToken);
      localStorage.setItem("dealerdesk_user", JSON.stringify(nextUser));
      if (nextUser.dealership_id) {
        localStorage.setItem("dealerdesk_active_dealership", String(nextUser.dealership_id));
        setActiveDealershipId(nextUser.dealership_id);
      }
    } catch {}
    setAccessToken(accessTokenValue);
    setUser(nextUser);
  }

  function handleSetActiveDealershipId(id: number) {
    setActiveDealershipId(id);
    try {
      localStorage.setItem("dealerdesk_active_dealership", String(id));
    } catch {}
  }

  function switchRoleDemo(role: User["role"]) {
    let nextUser: User;
    if (role === "dealership_admin") {
      nextUser = { id: 1, name: "Marcus Vance", email: "marcus@apexmotors.com", role, dealership_id: 1 };
    } else if (role === "manager") {
      nextUser = { id: 2, name: "Sarah Jenkins", email: "sarah.j@apexmotors.com", role, dealership_id: 1 };
    } else if (role === "sales_rep") {
      nextUser = { id: 3, name: "Carlos Reyes", email: "carlos.r@apexmotors.com", role, dealership_id: 1 };
    } else if (role === "dealerdesk_admin") {
      nextUser = { id: 99, name: "DealerDesk Admin", email: "dealerdesk@demo.com", role, dealership_id: null };
    } else {
      nextUser = { id: 501, name: "Sophia Martinez", email: "customer@demo.com", role: "customer", dealership_id: null };
    }
    setUser(nextUser);
    try {
      localStorage.setItem("dealerdesk_user", JSON.stringify(nextUser));
    } catch {}
  }

  async function logout() {
    if (accessToken) {
      await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/auth/logout`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${accessToken}` },
        }
      ).catch(() => undefined);
    }
    try {
      localStorage.removeItem("dealerdesk_access");
      localStorage.removeItem("dealerdesk_refresh");
      localStorage.removeItem("dealerdesk_user");
    } catch {}
    setAccessToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        accessToken,
        activeDealershipId,
        setActiveDealershipId: handleSetActiveDealershipId,
        aiCopilotOpen,
        setAiCopilotOpen,
        setSession,
        logout,
        switchRoleDemo,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
