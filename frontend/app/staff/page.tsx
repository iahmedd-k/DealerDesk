"use client";

import { useEffect, useState } from "react";
import {
  UserPlus,
  CheckCircle2,
  AlertCircle,
  X,
  Mail,
  Trash2,
  Power,
} from "lucide-react";
import Shell from "../components/Shell";
import { useAuth } from "../providers";
import { api } from "../api";
import type { StaffUser, StaffInvitation } from "../lib/types";

function getRoleBadge(role: string) {
  switch (role) {
    case "dealership_admin":
      return "crm-badge crm-badge-purple";
    case "manager":
      return "crm-badge crm-badge-info";
    case "sales_rep":
      return "crm-badge crm-badge-success";
    default:
      return "crm-badge crm-badge-neutral";
  }
}

export default function StaffPage() {
  const { user, authReady, activeDealershipId } = useAuth();
  const [staff, setStaff] = useState<StaffUser[]>([]);
  const [invitations, setInvitations] = useState<StaffInvitation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showInviteModal, setShowInviteModal] = useState(false);

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<StaffInvitation["role"]>("sales_rep");

  const isAdmin =
    user?.role === "dealership_admin" || user?.role === "dealerdesk_admin";

  useEffect(() => {
    if (!authReady || !user) return;
    if (!activeDealershipId) {
      setLoading(false);
      setError("Select a dealership workspace to manage staff.");
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError("");
    Promise.all([
      api<StaffUser[]>(`/dealerships/${activeDealershipId}/staff`),
      isAdmin
        ? api<StaffInvitation[]>(`/dealerships/${activeDealershipId}/staff/invitations`)
        : Promise.resolve([] as StaffInvitation[]),
    ])
      .then(([nextStaff, nextInvitations]) => {
        if (cancelled) return;
        setStaff(nextStaff);
        setInvitations(nextInvitations);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : "Could not load staff.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [authReady, user, activeDealershipId, isAdmin]);

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    if (!activeDealershipId || !inviteEmail.trim()) return;
    setError("");
    setNotice("");
    try {
      const created = await api<StaffInvitation>(
        `/dealerships/${activeDealershipId}/staff/invite`,
        {
          method: "POST",
          body: JSON.stringify({ email: inviteEmail.trim(), role: inviteRole }),
        },
      );
      setInvitations((current) => [created, ...current]);
      setInviteEmail("");
      setShowInviteModal(false);
      setNotice(`Invitation sent to ${created.email}.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not send invitation.");
    }
  }

  async function revokeInvitation(id: number) {
    if (!activeDealershipId) return;
    setError("");
    try {
      await api<void>(`/dealerships/${activeDealershipId}/staff/invitations/${id}`, {
        method: "DELETE",
      });
      setInvitations((current) => current.filter((item) => item.id !== id));
      setNotice("Invitation revoked.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not revoke invitation.");
    }
  }

  async function updateStaffMember(
    member: StaffUser,
    changes: { role?: StaffUser["role"]; is_active?: boolean },
  ) {
    if (!activeDealershipId) return;
    setError("");
    try {
      const updated = await api<StaffUser>(
        `/dealerships/${activeDealershipId}/staff/${member.id}`,
        { method: "PATCH", body: JSON.stringify(changes) },
      );
      setStaff((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      setNotice(`Updated ${updated.name}.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update this staff member.");
    }
  }

  async function removeStaffMember(member: StaffUser) {
    if (!activeDealershipId || !window.confirm(`Deactivate ${member.name}'s account?`)) return;
    setError("");
    try {
      await api<void>(`/dealerships/${activeDealershipId}/staff/${member.id}`, {
        method: "DELETE",
      });
      setStaff((current) =>
        current.map((item) =>
          item.id === member.id ? { ...item, is_active: false } : item,
        ),
      );
      setNotice(`${member.name} has been deactivated.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not deactivate this staff member.");
    }
  }

  async function updateAvailability(member: StaffUser, isAvailable: boolean) {
    if (!activeDealershipId) return;
    setError("");
    try {
      const updated = await api<StaffUser>(
        `/dealerships/${activeDealershipId}/staff/${member.id}/availability`,
        { method: "PATCH", body: JSON.stringify({ is_available: isAvailable }) },
      );
      setStaff((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      setNotice(
        `${member.name} is now marked ${isAvailable ? "available" : "unavailable"}.`,
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update availability.");
    }
  }

  return (
    <Shell>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-medium tracking-tight text-[#171717]">
            Team & Staff Workspace
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Manage dealership roles, lead-routing availability, and pending staff invitations
          </p>
        </div>

        {isAdmin && (
          <button
            type="button"
            onClick={() => setShowInviteModal(true)}
            className="crm-btn-primary"
          >
            <UserPlus className="h-4 w-4" />
            Invite Team Member
          </button>
        )}
      </div>

      {notice && (
        <div className="mb-5 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs font-medium text-emerald-700">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{notice}</span>
        </div>
      )}

      {error && (
        <div className="mb-5 flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-xs font-medium text-rose-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="crm-card p-12 text-center text-sm text-slate-500">
          Loading dealership staff...
        </div>
      ) : (
        <div className="space-y-6">
          <div className="crm-table-wrap">
            <table className="crm-table">
              <thead>
                <tr>
                  <th>Member</th>
                  <th>Role</th>
                  <th>Routing Availability</th>
                  <th>Account</th>
                  {isAdmin && <th className="text-right">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {staff.map((member) => {
                  const available = member.is_available ?? true;
                  return (
                    <tr key={member.id}>
                      <td>
                        <div className="font-semibold text-slate-900">{member.name}</div>
                        <div className="text-xs text-slate-500">{member.email}</div>
                      </td>
                      <td>
                        {isAdmin && member.id !== user?.id ? (
                          <select
                            value={member.role}
                            onChange={(e) =>
                              updateStaffMember(member, {
                                role: e.target.value as StaffUser["role"],
                              })
                            }
                            className="crm-select py-1 text-xs w-44"
                          >
                            <option value="sales_rep">Sales Rep</option>
                            <option value="manager">Manager</option>
                            <option value="dealership_admin">Dealership Admin</option>
                          </select>
                        ) : (
                          <span className={getRoleBadge(member.role)}>
                            {member.role.replace("_", " ")}
                          </span>
                        )}
                      </td>
                      <td>
                        <button
                          type="button"
                          onClick={() => updateAvailability(member, !available)}
                          className={`crm-badge cursor-pointer ${
                            available ? "crm-badge-success" : "crm-badge-neutral"
                          }`}
                        >
                          {available ? "Available" : "Unavailable"}
                        </button>
                      </td>
                      <td>
                        <span
                          className={`crm-badge ${
                            member.is_active ? "crm-badge-info" : "crm-badge-danger"
                          }`}
                        >
                          {member.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      {isAdmin && (
                        <td className="text-right">
                          {member.id !== user?.id && (
                            <div className="inline-flex items-center gap-1.5">
                              <button
                                type="button"
                                onClick={() =>
                                  updateStaffMember(member, { is_active: !member.is_active })
                                }
                                className="crm-btn-secondary py-1.5 px-2.5 text-xs"
                              >
                                <Power className="h-3.5 w-3.5" />
                                {member.is_active ? "Suspend" : "Activate"}
                              </button>
                              {member.is_active && (
                                <button
                                  type="button"
                                  onClick={() => removeStaffMember(member)}
                                  className="crm-btn-danger py-1.5 px-2.5 text-xs"
                                >
                                  Deactivate
                                </button>
                              )}
                            </div>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {isAdmin && (
            <div className="crm-card overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-200 flex items-center gap-2">
                <Mail className="h-4 w-4 text-blue-600" />
                <h2 className="text-sm font-medium text-[#171717]">
                  Pending Invitations ({invitations.length})
                </h2>
              </div>
              {invitations.length === 0 ? (
                <p className="p-6 text-xs text-slate-500 text-center">
                  No pending staff invitations.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="crm-table">
                    <thead>
                      <tr>
                        <th>Email</th>
                        <th>Assigned Role</th>
                        <th>Expires</th>
                        <th className="text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {invitations.map((inv, idx) => (
                        <tr key={inv.id ?? `${inv.email}-${idx}`}>
                          <td className="font-medium text-slate-900">{inv.email}</td>
                          <td>
                            <span className={getRoleBadge(inv.role)}>
                              {inv.role.replace("_", " ")}
                            </span>
                          </td>
                          <td className="text-xs text-slate-500">
                            {new Date(inv.expires_at).toLocaleDateString()}
                          </td>
                          <td className="text-right">
                            {inv.id !== null && (
                              <button
                                type="button"
                                onClick={() => revokeInvitation(inv.id as number)}
                                className="crm-btn-danger py-1.5 px-2.5 text-xs"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                                Revoke
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {showInviteModal && (
        <div className="crm-modal-overlay">
          <div className="crm-modal max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-medium text-[#171717]">Invite Team Member</h2>
                <p className="text-xs text-slate-500">
                  Send a dealership workspace invitation by email.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowInviteModal(false)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleInvite} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Work Email
                </label>
                <input
                  type="email"
                  required
                  placeholder="teammate@dealership.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="crm-input"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Role
                </label>
                <select
                  value={inviteRole}
                  onChange={(e) =>
                    setInviteRole(e.target.value as StaffInvitation["role"])
                  }
                  className="crm-select"
                >
                  <option value="sales_rep">Sales Representative</option>
                  <option value="manager">Dealership Manager</option>
                  <option value="dealership_admin">Dealership Admin</option>
                </select>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowInviteModal(false)}
                  className="crm-btn-secondary"
                >
                  Cancel
                </button>
                <button type="submit" className="crm-btn-primary">
                  Send Invitation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Shell>
  );
}
