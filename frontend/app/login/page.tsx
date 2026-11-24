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
      router.push("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to sign in.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-layout">
      <section className="auth-panel">
        <Link className="brand" href="/">Dealer<span>Desk</span></Link>
        <h1>Welcome back</h1>
        <p className="muted">Sign in to your DealerDesk account.</p>
        <form onSubmit={submit} className="form">
          {error && <div className="alert error">{error}</div>}
          <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
          <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
          <button className="button" disabled={loading}>{loading ? "Signing in..." : "Sign in"}</button>
        </form>
        <p className="auth-footer">No account? <Link href="/signup">Create one</Link></p>
      </section>
    </main>
  );
}
