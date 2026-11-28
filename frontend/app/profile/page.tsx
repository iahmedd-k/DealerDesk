"use client";

import { FormEvent, useEffect, useState } from "react";
import { Check, CircleUserRound, Mail, ShieldCheck } from "lucide-react";
import { api } from "../api";
import Shell from "../components/Shell";
import { useAuth, User } from "../providers";

const ROLE_LABELS: Record<User["role"], string> = {
  dealership_admin: "Dealership administrator",
  manager: "Manager",
  sales_rep: "Sales representative",
  customer: "Customer",
  dealerdesk_admin: "Platform administrator",
};

export default function ProfilePage() {
  const { user, updateUser } = useAuth();
  const [name, setName] = useState(user?.name ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    setName(user?.name ?? "");
  }, [user?.name]);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user) return;

    const updatedName = name.trim();
    if (!updatedName) {
      setError("Enter your name before saving.");
      return;
    }

    setBusy(true);
    setError("");
    setNotice("");
    try {
      const updatedUser = await api<User>("/auth/me", {
        method: "PATCH",
        body: JSON.stringify({ name: updatedName }),
      });
      updateUser(updatedUser);
      setName(updatedUser.name);
      setNotice("Profile changes saved.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save your profile.");
    } finally {
      setBusy(false);
    }
  }

  if (!user) {
    return (
      <Shell>
        <p className="text-sm text-slate-500">Loading profile…</p>
      </Shell>
    );
  }

  const initials = user.name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
  const workspace =
    user.role === "dealerdesk_admin"
      ? "DealerDesk platform"
      : user.role === "customer"
        ? "Customer account"
        : "Dealership workspace";

  return (
    <Shell>
      <div className="mx-auto max-w-5xl">
        <header className="mb-6">
          <h1 className="crm-page-title">Your profile</h1>
          <p className="mt-1 text-sm text-slate-500">
            Manage the name and account details shown across DealerDesk.
          </p>
        </header>

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.35fr)_minmax(260px,0.65fr)]">
          <section className="crm-card overflow-hidden">
            <div className="flex items-center gap-3 border-b border-slate-200 px-5 py-4">
              <CircleUserRound className="h-5 w-5 text-slate-500" aria-hidden="true" />
              <div>
                <h2 className="text-sm font-semibold text-slate-900">Personal details</h2>
                <p className="mt-0.5 text-xs text-slate-500">
                  Keep your account information up to date.
                </p>
              </div>
            </div>

            <form onSubmit={saveProfile}>
              <div className="grid gap-5 p-5 sm:grid-cols-2 sm:p-6">
                <label className="block sm:col-span-2">
                  <span className="mb-1.5 block text-xs font-medium text-slate-700">
                    Full name
                  </span>
                  <input
                    className="crm-input"
                    autoComplete="name"
                    maxLength={100}
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    required
                  />
                </label>

                <label className="block sm:col-span-2">
                  <span className="mb-1.5 block text-xs font-medium text-slate-700">
                    Sign-in email
                  </span>
                  <input
                    className="crm-input bg-slate-50 text-slate-500"
                    type="email"
                    value={user.email}
                    readOnly
                    aria-describedby="profile-email-help"
                  />
                  <span id="profile-email-help" className="mt-1.5 block text-xs text-slate-500">
                    This address is used to sign in and receive account notices.
                  </span>
                </label>
              </div>

              {(error || notice) && (
                <div className="px-5 pb-4 sm:px-6" aria-live="polite">
                  {error ? (
                    <p role="alert" className="text-sm text-rose-700">{error}</p>
                  ) : (
                    <p role="status" className="flex items-center gap-1.5 text-sm text-emerald-700">
                      <Check className="h-4 w-4" aria-hidden="true" />
                      {notice}
                    </p>
                  )}
                </div>
              )}

              <footer className="flex justify-end border-t border-slate-200 bg-slate-50/70 px-5 py-3.5 sm:px-6">
                <button
                  className="crm-btn-primary"
                  type="submit"
                  disabled={busy || name.trim() === user.name}
                >
                  {busy ? "Saving…" : "Save changes"}
                </button>
              </footer>
            </form>
          </section>

          <aside className="space-y-5">
            <section className="crm-card p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-slate-900 text-sm font-semibold text-white">
                  {initials || "DD"}
                </div>
                <div className="min-w-0">
                  <h2 className="truncate text-sm font-semibold text-slate-900">{user.name}</h2>
                  <p className="mt-0.5 truncate text-xs text-slate-500">{user.email}</p>
                </div>
              </div>
              <div className="mt-5 border-t border-slate-200 pt-4">
                <div className="flex items-start gap-2.5">
                  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />
                  <div>
                    <p className="text-xs font-medium text-slate-900">Account role</p>
                    <p className="mt-1 text-xs text-slate-500">{ROLE_LABELS[user.role]}</p>
                  </div>
                </div>
                <div className="mt-4 flex items-start gap-2.5">
                  <Mail className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />
                  <div>
                    <p className="text-xs font-medium text-slate-900">Workspace</p>
                    <p className="mt-1 text-xs text-slate-500">{workspace}</p>
                  </div>
                </div>
              </div>
            </section>
          </aside>
        </div>
      </div>
    </Shell>
  );
}
