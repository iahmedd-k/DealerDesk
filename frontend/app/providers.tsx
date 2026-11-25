"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { ApiError, api, refreshSession } from "./api";

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
  authReady: boolean;
  activeDealershipId: number;
  setActiveDealershipId: (id: number) => void;
  setSession: (accessToken: string, refreshToken: string, user: User) => void;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [activeDealershipId, setActiveDealershipId] = useState<number>(0);

  useEffect(() => {
    function handleAuthExpired() {
      localStorage.removeItem("dealerdesk_access");
      localStorage.removeItem("dealerdesk_refresh");
      localStorage.removeItem("dealerdesk_user");
      localStorage.removeItem("dealerdesk_active_dealership");
      setAccessToken(null);
      setUser(null);
      setActiveDealershipId(0);
    }
    window.addEventListener("dealerdesk:auth-expired", handleAuthExpired);
    return () => window.removeEventListener("dealerdesk:auth-expired", handleAuthExpired);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function restoreSession() {
      localStorage.removeItem("dealerdesk_access");
      localStorage.removeItem("dealerdesk_refresh");
      const storedDealership = localStorage.getItem("dealerdesk_active_dealership");

      try {
        let restoredUser: User;
        try {
          restoredUser = await api<User>("/auth/me", {}, null);
        } catch (err) {
          if (err instanceof ApiError && err.statusCode === 401) {
            const refreshed = await refreshSession();
            if (!refreshed) throw err;
            restoredUser = await api<User>("/auth/me", {}, null);
          } else {
            throw err;
          }
        }
        if (cancelled) return;
        setUser(restoredUser);
        setAccessToken(null);
        const storedId = Number(storedDealership);
        setActiveDealershipId(
          restoredUser.dealership_id ??
            (Number.isInteger(storedId) && storedId > 0 ? storedId : 0),
        );
      } catch {
        if (cancelled) return;
        localStorage.removeItem("dealerdesk_user");
        localStorage.removeItem("dealerdesk_active_dealership");
        setAccessToken(null);
        setUser(null);
      } finally {
        if (!cancelled) setAuthReady(true);
      }
    }
    restoreSession();
    return () => {
      cancelled = true;
    };
  }, []);

  function setSession(_accessTokenValue: string, _refreshToken: string, nextUser: User) {
    localStorage.removeItem("dealerdesk_access");
    localStorage.removeItem("dealerdesk_refresh");
    if (nextUser.dealership_id) {
      localStorage.setItem("dealerdesk_active_dealership", String(nextUser.dealership_id));
      setActiveDealershipId(nextUser.dealership_id);
    } else {
      localStorage.removeItem("dealerdesk_active_dealership");
      setActiveDealershipId(0);
    }
    setAccessToken(null);
    setUser(nextUser);
    setAuthReady(true);
  }

  function handleSetActiveDealershipId(id: number) {
    if (!Number.isInteger(id) || id < 1) {
      throw new Error("A valid dealership must be selected.");
    }
    setActiveDealershipId(id);
    localStorage.setItem("dealerdesk_active_dealership", String(id));
  }

  async function logout() {
    try {
      await api<void>("/auth/logout", { method: "POST" }, accessToken);
    } catch (error) {
      console.error("The server could not revoke the current session.", error);
    }
    localStorage.removeItem("dealerdesk_access");
    localStorage.removeItem("dealerdesk_refresh");
    localStorage.removeItem("dealerdesk_user");
    localStorage.removeItem("dealerdesk_active_dealership");
    setAccessToken(null);
    setUser(null);
    setActiveDealershipId(0);
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        accessToken,
        authReady,
        activeDealershipId,
        setActiveDealershipId: handleSetActiveDealershipId,
        setSession,
        logout,
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
