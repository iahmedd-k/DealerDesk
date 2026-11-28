"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  KeyRound,
  Mail,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import { api } from "../api";
import Shell from "../components/Shell";
import type { Dealership, GmailMailboxStatus } from "../lib/types";
import { useAuth } from "../providers";

export default function SettingsPage() {
  const { user, logout, activeDealershipId } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [mailbox, setMailbox] = useState<GmailMailboxStatus | null>(null);
  const [mailboxLoading, setMailboxLoading] = useState(false);
  const [mailboxBusy, setMailboxBusy] = useState(false);
  const [mailboxError, setMailboxError] = useState("");
  const [mailboxNotice, setMailboxNotice] = useState("");
  const [whatsappNumber, setWhatsappNumber] = useState("");
  const [whatsappLoading, setWhatsappLoading] = useState(false);
  const [whatsappBusy, setWhatsappBusy] = useState(false);
  const [whatsappError, setWhatsappError] = useState("");
  const [whatsappNotice, setWhatsappNotice] = useState("");

  const canManageMailbox =
    user?.role === "dealership_admin" || user?.role === "manager";
  const canManageWhatsapp = user?.role === "dealership_admin";

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    if (query.get("gmail_error")) {
      setMailboxError("Google could not connect the mailbox. Please try again.");
    }
  }, []);

  useEffect(() => {
    if (!canManageMailbox || !activeDealershipId) return;
    let cancelled = false;
    setMailboxLoading(true);
    api<GmailMailboxStatus>(`/dealerships/${activeDealershipId}/email-mailbox`)
      .then((status) => {
        if (!cancelled) setMailbox(status);
      })
      .catch((cause) => {
        if (!cancelled) {
          setMailboxError(
            cause instanceof Error ? cause.message : "Could not load mailbox status.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setMailboxLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeDealershipId, canManageMailbox]);

  useEffect(() => {
    if (!canManageWhatsapp || !activeDealershipId) return;
    let cancelled = false;
    setWhatsappLoading(true);
    api<Dealership>(`/dealerships/${activeDealershipId}`)
      .then((dealership) => {
        if (!cancelled) setWhatsappNumber(dealership.whatsapp_number || "");
      })
      .catch((cause) => {
        if (!cancelled) {
          setWhatsappError(
            cause instanceof Error ? cause.message : "Could not load WhatsApp settings.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setWhatsappLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeDealershipId, canManageWhatsapp]);

  async function saveWhatsappNumber(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeDealershipId) return;
    setWhatsappBusy(true);
    setWhatsappError("");
    setWhatsappNotice("");
    try {
      const saved = await api<Dealership>(`/dealerships/${activeDealershipId}`, {
        method: "PATCH",
        body: JSON.stringify({
          whatsapp_number: whatsappNumber.trim() || null,
        }),
      });
      setWhatsappNumber(saved.whatsapp_number || "");
      setWhatsappNotice(
        saved.whatsapp_number
          ? "WhatsApp number saved. Inbound messages will route to this dealership."
          : "WhatsApp routing has been disabled for this dealership.",
      );
    } catch (cause) {
      setWhatsappError(
        cause instanceof Error ? cause.message : "Could not save WhatsApp settings.",
      );
    } finally {
      setWhatsappBusy(false);
    }
  }

  async function connectMailbox() {
    if (!activeDealershipId) return;
    setMailboxBusy(true);
    setMailboxError("");
    try {
      const result = await api<{ authorization_url: string }>(
        `/dealerships/${activeDealershipId}/email-mailbox/connect`,
        { method: "POST" },
      );
      window.location.assign(result.authorization_url);
    } catch (cause) {
      setMailboxError(
        cause instanceof Error ? cause.message : "Could not start Google authorization.",
      );
      setMailboxBusy(false);
    }
  }

  async function disconnectMailbox() {
    if (!activeDealershipId) return;
    if (!window.confirm("Disconnect this shared Gmail mailbox from DealerDesk?")) return;
    setMailboxBusy(true);
    setMailboxError("");
    setMailboxNotice("");
    try {
      await api<void>(`/dealerships/${activeDealershipId}/email-mailbox`, {
        method: "DELETE",
      });
      setMailbox({ connected: false, email: null, last_synced_at: null });
      setMailboxNotice("The shared mailbox has been disconnected.");
    } catch (cause) {
      setMailboxError(
        cause instanceof Error ? cause.message : "Could not disconnect the mailbox.",
      );
    } finally {
      setMailboxBusy(false);
    }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (newPassword !== confirmPassword) {
      setError("The new password and confirmation do not match.");
      return;
    }

    setBusy(true);
    setError("");
    try {
      await api("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      await logout();
      window.location.assign("/login?password_changed=1");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update your password.");
      setBusy(false);
    }
  }

  const canManageWorkspace =
    user?.role === "dealership_admin" || user?.role === "manager";

  return (
    <Shell>
      <div className="mx-auto max-w-4xl">
        <header className="mb-6">
          <h1 className="crm-page-title">Settings</h1>
          <p className="mt-1 text-sm text-slate-500">
            Review account security and the workspace options available to you.
          </p>
        </header>

        <div className="space-y-5">
          {canManageWhatsapp && (
            <section className="crm-card overflow-hidden">
              <div className="border-b border-slate-200 px-5 py-4">
                <h2 className="text-sm font-semibold text-slate-900">WhatsApp routing</h2>
                <p className="mt-0.5 text-xs text-slate-500">
                  Map this dealership&apos;s Twilio WhatsApp destination number to its inbox.
                </p>
              </div>
              <form onSubmit={saveWhatsappNumber} className="space-y-3 p-5 sm:p-6">
                <label className="block max-w-md">
                  <span className="mb-1.5 block text-xs font-medium text-slate-700">
                    WhatsApp number (E.164)
                  </span>
                  <input
                    className="crm-input"
                    type="tel"
                    inputMode="tel"
                    autoComplete="tel"
                    placeholder="+14155550123"
                    value={whatsappNumber}
                    onChange={(event) => setWhatsappNumber(event.target.value)}
                    disabled={whatsappLoading || whatsappBusy}
                  />
                </label>
                <p className="text-xs text-slate-500">
                  Configure Twilio to send inbound webhooks to DealerDesk and use this number as the
                  destination. Leave blank to disable routing.
                </p>
                <div className="flex items-center justify-between gap-3">
                  <div aria-live="polite">
                    {whatsappError ? (
                      <p role="alert" className="text-sm text-rose-700">{whatsappError}</p>
                    ) : whatsappNotice ? (
                      <p role="status" className="text-sm text-emerald-700">{whatsappNotice}</p>
                    ) : null}
                  </div>
                  <button
                    className="crm-btn-primary shrink-0"
                    type="submit"
                    disabled={whatsappLoading || whatsappBusy || !activeDealershipId}
                  >
                    {whatsappBusy ? "Saving…" : "Save number"}
                  </button>
                </div>
              </form>
            </section>
          )}

          {canManageMailbox && (
            <section className="crm-card overflow-hidden">
              <div className="flex items-center gap-3 border-b border-slate-200 px-5 py-4">
                <Mail className="h-5 w-5 text-slate-500" aria-hidden="true" />
                <div>
                  <h2 className="text-sm font-semibold text-slate-900">Shared Gmail inbox</h2>
                  <p className="mt-0.5 text-xs text-slate-500">
                    Bring dealership email into the CRM Inbox and reply from this address.
                  </p>
                </div>
              </div>

              <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
                <div className="min-w-0">
                  {mailboxLoading ? (
                    <p className="text-sm text-slate-500">Checking mailbox connection…</p>
                  ) : mailbox?.connected ? (
                    <>
                      <p className="flex items-center gap-2 text-sm font-medium text-slate-900">
                        <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden="true" />
                        Connected
                      </p>
                      <p className="mt-1 truncate text-xs text-slate-500">{mailbox.email}</p>
                      {mailbox.last_synced_at && (
                        <p className="mt-1 text-[11px] text-slate-400">
                          Last synced{" "}
                          {new Date(mailbox.last_synced_at).toLocaleString()}
                        </p>
                      )}
                      {mailbox.last_sync_error && (
                        <p role="status" className="mt-1 text-xs text-amber-700">
                          Automatic sync is retrying after {mailbox.last_sync_error}.
                        </p>
                      )}
                    </>
                  ) : (
                    <>
                      <p className="text-sm font-medium text-slate-900">No mailbox connected</p>
                      <p className="mt-1 text-xs text-slate-500">
                        Connect a shared Google Workspace account such as sales@yourdealership.com.
                      </p>
                    </>
                  )}
                </div>
                {mailbox?.connected ? (
                  <button
                    className="crm-btn-secondary shrink-0"
                    type="button"
                    onClick={() => void disconnectMailbox()}
                    disabled={mailboxBusy || mailboxLoading}
                  >
                    {mailboxBusy ? "Disconnecting…" : "Disconnect"}
                  </button>
                ) : (
                  <button
                    className="crm-btn-primary shrink-0"
                    type="button"
                    onClick={() => void connectMailbox()}
                    disabled={mailboxBusy || mailboxLoading || !activeDealershipId}
                  >
                    {mailboxBusy ? "Connecting…" : "Connect Google Workspace"}
                  </button>
                )}
              </div>

              {(mailboxError || mailboxNotice) && (
                <div className="border-t border-slate-200 px-5 py-3 sm:px-6" aria-live="polite">
                  {mailboxError ? (
                    <p role="alert" className="text-sm text-rose-700">{mailboxError}</p>
                  ) : (
                    <p role="status" className="text-sm text-emerald-700">{mailboxNotice}</p>
                  )}
                </div>
              )}
            </section>
          )}

          <section className="crm-card overflow-hidden">
            <div className="flex items-center gap-3 border-b border-slate-200 px-5 py-4">
              <KeyRound className="h-5 w-5 text-slate-500" aria-hidden="true" />
              <div>
                <h2 className="text-sm font-semibold text-slate-900">Change password</h2>
                <p className="mt-0.5 text-xs text-slate-500">
                  Choose a new password for your DealerDesk account.
                </p>
              </div>
            </div>

            <form onSubmit={changePassword}>
              <div className="grid gap-4 p-5 sm:max-w-2xl sm:grid-cols-2 sm:p-6">
                <label className="block sm:col-span-2">
                  <span className="mb-1.5 block text-xs font-medium text-slate-700">
                    Current password
                  </span>
                  <input
                    className="crm-input"
                    type="password"
                    autoComplete="current-password"
                    minLength={8}
                    maxLength={128}
                    value={currentPassword}
                    onChange={(event) => setCurrentPassword(event.target.value)}
                    required
                  />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-xs font-medium text-slate-700">
                    New password
                  </span>
                  <input
                    className="crm-input"
                    type="password"
                    autoComplete="new-password"
                    minLength={8}
                    maxLength={128}
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                    required
                  />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-xs font-medium text-slate-700">
                    Confirm new password
                  </span>
                  <input
                    className="crm-input"
                    type="password"
                    autoComplete="new-password"
                    minLength={8}
                    maxLength={128}
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    required
                  />
                </label>
              </div>

              {error && (
                <p role="alert" className="px-5 pb-4 text-sm text-rose-700 sm:px-6">
                  {error}
                </p>
              )}

              <footer className="flex flex-col gap-3 border-t border-slate-200 bg-slate-50/70 px-5 py-3.5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
                <p className="text-xs text-slate-500">
                  You&apos;ll be asked to sign in again after the change.
                </p>
                <button className="crm-btn-primary" type="submit" disabled={busy}>
                  {busy ? "Updating…" : "Update password"}
                </button>
              </footer>
            </form>
          </section>

          {canManageWorkspace && (
            <section className="crm-card flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
              <div className="flex items-start gap-3">
                <SlidersHorizontal className="mt-0.5 h-5 w-5 shrink-0 text-slate-500" aria-hidden="true" />
                <div>
                  <h2 className="text-sm font-semibold text-slate-900">Workspace configuration</h2>
                  <p className="mt-1 max-w-xl text-xs leading-5 text-slate-500">
                    Manage test-drive hours and scheduling rules for your dealership.
                  </p>
                </div>
              </div>
              <Link href="/operations" className="crm-btn-secondary shrink-0">
                Open operations
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
            </section>
          )}

          <section className="flex items-start gap-3 rounded-lg border border-slate-200 bg-white px-5 py-4">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" aria-hidden="true" />
            <p className="text-xs leading-5 text-slate-600">
              Password changes require your current password and revoke existing sessions.
              Account details can be reviewed on your{" "}
              <Link href="/profile" className="font-medium text-blue-700 hover:underline">
                profile
              </Link>
              .
            </p>
          </section>
        </div>
      </div>
    </Shell>
  );
}
