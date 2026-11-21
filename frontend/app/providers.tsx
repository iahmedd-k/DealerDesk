"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { ApiError, api } from "./api";

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
      const storedToken = localStorage.getItem("dealerdesk_access");
      const storedDealership = localStorage.getItem("dealerdesk_active_dealership");
      if (!storedToken) {
        setAuthReady(true);
        return;
      }

      setAccessToken(storedToken);
      try {
        const restoredUser = await api<User>("/auth/me", {}, storedToken);
        if (cancelled) return;
        setUser(restoredUser);
        const storedId = Number(storedDealership);
        setActiveDealershipId(
          restoredUser.dealership_id ??
            (Number.isInteger(storedId) && storedId > 0 ? storedId : 0),
        );
      } catch (error) {
        if (cancelled) return;
        localStorage.removeItem("dealerdesk_access");
        localStorage.removeItem("dealerdesk_refresh");
        localStorage.removeItem("dealerdesk_user");
        localStorage.removeItem("dealerdesk_active_dealership");
        setAccessToken(null);
        setUser(null);
        if (!(error instanceof ApiError && error.statusCode === 401)) {
          console.error("Could not restore the DealerDesk session.", error);
        }
      } finally {
        if (!cancelled) setAuthReady(true);
      }
    }
    restoreSession();
    return () => {
      cancelled = true;
    };
  }, []);

  function setSession(accessTokenValue: string, refreshToken: string, nextUser: User) {
    localStorage.setItem("dealerdesk_access", accessTokenValue);
    localStorage.setItem("dealerdesk_refresh", refreshToken);
    if (nextUser.dealership_id) {
      localStorage.setItem("dealerdesk_active_dealership", String(nextUser.dealership_id));
      setActiveDealershipId(nextUser.dealership_id);
    } else {
      localStorage.removeItem("dealerdesk_active_dealership");
      setActiveDealershipId(0);
    }
    setAccessToken(accessTokenValue);
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
    if (accessToken) {
      try {
        await api<void>(
          "/auth/logout",
          {
          method: "POST",
          },
          accessToken,
        );
      } catch (error) {
        console.error("The server could not revoke the current session.", error);
      }
    }
    localStorage.removeItem("dealerdesk_access");
    localStorage.removeItem("dealerdesk_refresh");
    localStorage.removeItem("dealerdesk_user");
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
