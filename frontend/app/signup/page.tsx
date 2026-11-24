"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { api } from "../api";

export default function SignupPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api("/auth/signup", { method: "POST", body: JSON.stringify({ name, email, password }) });
      router.push("/login");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to create account.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-layout">
      <section className="auth-panel">
        <Link className="brand" href="/">Dealer<span>Desk</span></Link>
        <h1>Create account</h1>
        <p className="muted">Create a customer account to book test drives.</p>
        <form onSubmit={submit} className="form">
          {error && <div className="alert error">{error}</div>}
          <label>Name<input value={name} onChange={(e) => setName(e.target.value)} required /></label>
          <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
          <label>Password<input type="password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
          <button className="button" disabled={loading}>{loading ? "Creating..." : "Create account"}</button>
        </form>
        <p className="auth-footer">Already have an account? <Link href="/login">Sign in</Link></p>
      </section>
    </main>
  );
}
