"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { api } from "../api";
import { useAuth, User } from "../providers";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const { setSession } = useAuth();

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const tokens = await api<{ access_token: string; refresh_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      const user = await api<User>("/auth/me", {}, tokens.access_token);
      setSession(tokens.access_token, tokens.refresh_token, user);
      router.push("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to sign in.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <Link className="inline-flex items-center gap-2.5" href="/" aria-label="DealerDesk home">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-[#171717] font-mono font-medium text-xs text-white">
            DD
          </span>
          <span className="text-base font-medium tracking-tight text-[#171717]">
            DealerDesk
          </span>
        </Link>

        <h1 className="mt-7 text-2xl font-medium tracking-tight text-[#171717]">Sign in to DealerDesk</h1>
        <p className="mt-1 text-sm text-[#525252]">Access your dealership CRM workspace</p>

        <form onSubmit={submit} className="mt-6 space-y-4">
          {error && (
            <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-xs font-medium text-rose-700">
              {error}
            </div>
          )}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">Email address</label>
            <input
              className="crm-input"
              type="email"
              placeholder="name@dealership.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">Password</label>
            <input
              className="crm-input"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button className="crm-btn-primary w-full h-10" disabled={loading}>
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-slate-500">
          Don&apos;t have an account?{" "}
          <Link href="/signup" className="font-semibold text-blue-600 hover:underline">
            Create one
          </Link>
        </p>
      </section>
    </main>
  );
}
