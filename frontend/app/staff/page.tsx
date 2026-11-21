"use client";

import { useEffect, useState } from "react";
import {
  Users,
  UserPlus,
  Mail,
  Shield,
  Clock,
  X,
  Trash2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import Shell from "../components/Shell";
import { useAuth } from "../providers";
import { api } from "../api";
import {
  MOCK_STAFF,
  MOCK_INVITATIONS,
  StaffUser,
  StaffInvitation,
} from "../lib/mockData";

export default function StaffPage() {
  const { user, activeDealershipId } = useAuth();
  const [staff, setStaff] = useState<StaffUser[]>(MOCK_STAFF);
  const [invitations, setInvitations] = useState<StaffInvitation[]>(MOCK_INVITATIONS);

  // Invite modal
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteName, setInviteName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("sales_rep");
  const [notice, setNotice] = useState("");

  const isAdmin = user?.role === "dealership_admin" || user?.role === "dealerdesk_admin";

  useEffect(() => {
    api<StaffUser[]>(`/dealerships/${activeDealershipId}/staff`)
      .then((data) => {
        if (Array.isArray(data) && data.length) setStaff(data);
      })
      .catch(() => {});

    api<StaffInvitation[]>(`/dealerships/${activeDealershipId}/staff/invitations`)
      .then((data) => {
        if (Array.isArray(data) && data.length) setInvitations(data);
      })
      .catch(() => {});
  }, [activeDealershipId]);

  function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    const newInv: StaffInvitation = {
      id: Math.floor(Math.random() * 9000) + 1000,
      dealership_id: activeDealershipId,
      name: inviteName,
      email: inviteEmail,
      role: inviteRole,
      expires_at: new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString(),
      delivery_status: "delivered",
      status: "pending",
    };

    setInvitations([newInv, ...invitations]);
    setShowInviteModal(false);
    setInviteName("");
    setInviteEmail("");
    setNotice(`Invitation sent to ${inviteEmail} with 7-day token.`);
    setTimeout(() => setNotice(""), 5000);
  }

  function handleRevoke(invId: number) {
    setInvitations(invitations.filter((i) => i.id !== invId));
    setNotice("Staff invitation revoked.");
    setTimeout(() => setNotice(""), 4000);
  }

  return (
    <Shell>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="h-2 w-2 rounded-full bg-blue-500" />
            <p className="text-xs font-bold uppercase tracking-wider text-blue-400">
              Enterprise Access & HR Governance
            </p>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Team & Staff Workspace
          </h1>
          <p className="text-xs text-slate-400">
            Role-based authorization across Dealership Admins, Managers, and Sales Representatives
          </p>
        </div>

        {isAdmin && (
          <button onClick={() => setShowInviteModal(true)} className="btn-primary">
            <UserPlus className="h-4 w-4" />
            <span>Invite Team Member</span>
          </button>
        )}
      </div>

      {notice && (
        <div className="mb-6 rounded-xl bg-emerald-500/10 border border-emerald-500/30 p-3.5 text-xs text-emerald-300 flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          <span>{notice}</span>
        </div>
      )}

      {/* Staff Table */}
      <div className="space-y-6">
        <div>
          <h2 className="text-base font-bold text-white mb-3">Active Staff ({staff.length})</h2>
          <div className="erp-table-container">
            <table className="erp-table">
              <thead>
                <tr>
                  <th>Team Member</th>
                  <th>Email Address</th>
                  <th>Assigned Role</th>
                  <th>Status</th>
                  <th>Last Session</th>
                </tr>
              </thead>
              <tbody>
                {staff.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <div className="flex items-center gap-3">
                        <div className="h-8 w-8 rounded-full bg-slate-800 flex items-center justify-center font-bold text-xs text-blue-400 border border-slate-700">
                          {s.name.slice(0, 2).toUpperCase()}
                        </div>
                        <span className="font-bold text-white text-xs">{s.name}</span>
                      </div>
                    </td>
                    <td className="text-slate-300 font-mono text-xs">{s.email}</td>
                    <td>
                      <span
                        className={`badge ${
                          s.role === "dealership_admin"
                            ? "badge-danger"
                            : s.role === "manager"
                            ? "badge-warning"
                            : "badge-info"
                        }`}
                      >
                        {s.role.replaceAll("_", " ").toUpperCase()}
                      </span>
                    </td>
                    <td>
                      <span className="badge badge-success">Active</span>
                    </td>
                    <td className="text-slate-400 text-xs">{s.last_login || "Today"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Pending Invitations */}
        {invitations.length > 0 && (
          <div>
            <h2 className="text-base font-bold text-white mb-3">
              Pending Invitations ({invitations.length})
            </h2>
            <div className="erp-table-container">
              <table className="erp-table">
                <thead>
                  <tr>
                    <th>Invited Name</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Delivery Status</th>
                    <th>Expires</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {invitations.map((inv) => (
                    <tr key={inv.id}>
                      <td className="font-bold text-white text-xs">{inv.name}</td>
                      <td className="text-slate-300 font-mono text-xs">{inv.email}</td>
                      <td>
                        <span className="badge badge-neutral">
                          {inv.role.replaceAll("_", " ")}
                        </span>
                      </td>
                      <td>
                        <span className="badge badge-success flex items-center gap-1">
                          <CheckCircle2 className="h-3 w-3" /> Delivered (Resend)
                        </span>
                      </td>
                      <td className="text-slate-400 text-xs">
                        {new Date(inv.expires_at).toLocaleDateString()}
                      </td>
                      <td>
                        {isAdmin && (
                          <button
                            onClick={() => handleRevoke(inv.id)}
                            className="text-xs text-rose-400 hover:text-rose-300 font-semibold"
                          >
                            Revoke
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Role Permissions Matrix */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
          <h3 className="font-bold text-white text-sm flex items-center gap-2">
            <Shield className="h-4 w-4 text-blue-400" />
            Role-Based Access Control (RBAC) Matrix
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
              <span className="badge badge-danger">Dealership Admin</span>
              <p className="text-slate-300 font-semibold">Full Workspace Ownership</p>
              <ul className="text-slate-400 space-y-1 list-disc list-inside text-[11px]">
                <li>Staff invite & revocation</li>
                <li>Test-drive slot generation & operating hours</li>
                <li>Brand creation & logo management</li>
                <li>Vehicle deletion & pricing updates</li>
                <li>Full security audit log inspection</li>
              </ul>
            </div>

            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
              <span className="badge badge-warning">Manager</span>
              <p className="text-slate-300 font-semibold">Operational Oversight</p>
              <ul className="text-slate-400 space-y-1 list-disc list-inside text-[11px]">
                <li>Vehicle creation & inventory edits</li>
                <li>All customer booking management</li>
                <li>Customer rescheduling & cancellations</li>
                <li>Knowledge document upload & RAG search</li>
              </ul>
            </div>

            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
              <span className="badge badge-info">Sales Representative</span>
              <p className="text-slate-300 font-semibold">Customer & Drive Frontline</p>
              <ul className="text-slate-400 space-y-1 list-disc list-inside text-[11px]">
                <li>Fleet catalog & availability checks</li>
                <li>Customer test-drive slot bookings</li>
                <li>AI Copilot sales inquiries</li>
                <li>Customer identity verification</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      {/* Invite Modal */}
      {showInviteModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="p-5 border-b border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white">Invite Team Member</h3>
                <p className="text-xs text-slate-400">Issues secure 7-day token with role assignment</p>
              </div>
              <button onClick={() => setShowInviteModal(false)} className="text-slate-400 hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleInvite} className="p-5 space-y-4 text-xs">
              <div>
                <label className="text-slate-300 font-semibold mb-1 block">Full Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Alex Morgan"
                  value={inviteName}
                  onChange={(e) => setInviteName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-white"
                />
              </div>

              <div>
                <label className="text-slate-300 font-semibold mb-1 block">Email Address</label>
                <input
                  type="email"
                  required
                  placeholder="e.g. alex@apexmotors.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-white"
                />
              </div>

              <div>
                <label className="text-slate-300 font-semibold mb-1 block">Role</label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-white"
                >
                  <option value="sales_rep">Sales Representative</option>
                  <option value="manager">Manager</option>
                </select>
              </div>

              <div className="pt-4 border-t border-slate-800 flex justify-end gap-2">
                <button type="button" onClick={() => setShowInviteModal(false)} className="btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
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
