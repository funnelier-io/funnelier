"use client";

import { useState, useMemo, useCallback } from "react";
import { useTranslations } from "next-intl";
import { useApi } from "@/lib/hooks";
import { api } from "@/lib/api-client";
import StatCard from "@/components/ui/StatCard";
import DataTable from "@/components/ui/DataTable";
import { showToast } from "@/components/ui/ToastContainer";
import type { UserResponse, UserRole, CreateUserRequest } from "@/types/auth";

const ROLES: UserRole[] = ["super_admin", "tenant_admin", "manager", "salesperson", "viewer"];

function RoleBadge({ role, t }: { role: string; t: (key: string) => string }) {
  const colors: Record<string, string> = {
    super_admin: "bg-red-100 text-red-700",
    tenant_admin: "bg-purple-100 text-purple-700",
    manager: "bg-blue-100 text-blue-700",
    salesperson: "bg-green-100 text-green-700",
    viewer: "bg-gray-100 text-gray-600",
  };
  const roleLabels: Record<string, string> = {
    super_admin: "roleSuperAdmin",
    tenant_admin: "roleTenantAdmin",
    manager: "roleManager",
    salesperson: "roleSalesperson",
    viewer: "roleViewer",
  };
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${colors[role] ?? colors.viewer}`}>
      {t(roleLabels[role] ?? "roleViewer")}
    </span>
  );
}

function StatusBadge({ user, t }: { user: UserResponse; t: (key: string) => string }) {
  if (!user.is_active) {
    return <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-red-50 text-red-600">{t("inactive")}</span>;
  }
  if (!user.is_approved) {
    return <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-600">{t("pending")}</span>;
  }
  return <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-green-50 text-green-700">{t("active")}</span>;
}

export default function UsersPage() {
  const t = useTranslations("users");
  const tc = useTranslations("common");

  const [tab, setTab] = useState<"all" | "pending">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [filterRole, setFilterRole] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showResetModal, setShowResetModal] = useState<string | null>(null);
  const [selectedUser, setSelectedUser] = useState<UserResponse | null>(null);

  // Fetch all users (include inactive)
  const { data: allUsers, isLoading, refetch } = useApi<UserResponse[]>("/auth/users?include_inactive=true");
  const { data: pendingUsers, refetch: refetchPending } = useApi<UserResponse[]>("/auth/users/pending");

  const users = allUsers ?? [];
  const pending = pendingUsers ?? [];

  const filteredUsers = useMemo(() => {
    let list = tab === "pending" ? pending : users;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (u) =>
          u.full_name.toLowerCase().includes(q) ||
          u.email.toLowerCase().includes(q) ||
          u.username.toLowerCase().includes(q)
      );
    }
    if (filterRole) {
      list = list.filter((u) => u.role === filterRole);
    }
    if (filterStatus === "active") list = list.filter((u) => u.is_active && u.is_approved);
    else if (filterStatus === "inactive") list = list.filter((u) => !u.is_active);
    else if (filterStatus === "pending") list = list.filter((u) => !u.is_approved && u.is_active);
    return list;
  }, [users, pending, tab, searchQuery, filterRole, filterStatus]);

  // KPI data
  const totalUsers = users.length;
  const activeUsers = users.filter((u) => u.is_active && u.is_approved).length;
  const pendingCount = pending.length;
  const uniqueRoles = new Set(users.map((u) => u.role)).size;

  // Actions
  const handleAction = useCallback(
    async (action: string, userId: string) => {
      try {
        const res = await api("POST", `/auth/users/${userId}/${action}`);
        if (res.ok) {
          const msgKey = action === "approve" ? "userApproved" : action === "reject" ? "userRejected" : action === "activate" ? "userActivated" : "userDeactivated";
          showToast({ type: "success", title: t(msgKey) });
          refetch();
          refetchPending();
        } else {
          showToast({ type: "error", title: t("errorAction") });
        }
      } catch {
        showToast({ type: "error", title: t("errorAction") });
      }
    },
    [t, refetch, refetchPending]
  );

  const handleRoleChange = useCallback(
    async (userId: string, newRole: string) => {
      try {
        const res = await api("PUT", `/auth/users/${userId}/role`, { role: newRole });
        if (res.ok) {
          showToast({ type: "success", title: t("roleUpdated") });
          refetch();
        } else {
          showToast({ type: "error", title: t("errorAction") });
        }
      } catch {
        showToast({ type: "error", title: t("errorAction") });
      }
    },
    [t, refetch]
  );

  const columns = [
    {
      key: "name",
      header: t("colName"),
      render: (u: UserResponse) => (
        <div>
          <div className="font-medium text-gray-900">{u.full_name || u.username}</div>
          <div className="text-xs text-gray-400">@{u.username}</div>
        </div>
      ),
    },
    {
      key: "email",
      header: t("colEmail"),
      render: (u: UserResponse) => <span className="text-sm text-gray-600">{u.email}</span>,
    },
    {
      key: "role",
      header: t("colRole"),
      render: (u: UserResponse) => (
        <select
          value={u.role}
          onChange={(e) => handleRoleChange(u.id, e.target.value)}
          className="text-xs border border-gray-200 rounded-md px-2 py-1 bg-white focus:ring-1 focus:ring-blue-300 outline-none"
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {t(`role${r.split("_").map((w) => w[0].toUpperCase() + w.slice(1)).join("")}` as Parameters<typeof t>[0])}
            </option>
          ))}
        </select>
      ),
    },
    {
      key: "status",
      header: t("colStatus"),
      render: (u: UserResponse) => <StatusBadge user={u} t={t} />,
    },
    {
      key: "last_login",
      header: t("colLastLogin"),
      render: (u: UserResponse) =>
        u.last_login ? (
          <span className="text-xs text-gray-500">
            {new Date(u.last_login).toLocaleDateString("fa-IR")} {new Date(u.last_login).toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" })}
          </span>
        ) : (
          <span className="text-xs text-gray-300">{t("never")}</span>
        ),
    },
    {
      key: "actions",
      header: t("colActions"),
      render: (u: UserResponse) => (
        <div className="flex items-center gap-1">
          {!u.is_approved && u.is_active && (
            <>
              <button
                onClick={(e) => { e.stopPropagation(); handleAction("approve", u.id); }}
                className="text-xs px-2 py-1 rounded bg-green-50 text-green-700 hover:bg-green-100 transition-colors"
              >
                {t("approve")}
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (confirm(t("confirmReject"))) handleAction("reject", u.id);
                }}
                className="text-xs px-2 py-1 rounded bg-red-50 text-red-600 hover:bg-red-100 transition-colors"
              >
                {t("reject")}
              </button>
            </>
          )}
          {u.is_approved && u.is_active && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (confirm(t("confirmDeactivate"))) handleAction("deactivate", u.id);
              }}
              className="text-xs px-2 py-1 rounded bg-amber-50 text-amber-600 hover:bg-amber-100 transition-colors"
            >
              {t("deactivate")}
            </button>
          )}
          {!u.is_active && (
            <button
              onClick={(e) => { e.stopPropagation(); handleAction("activate", u.id); }}
              className="text-xs px-2 py-1 rounded bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors"
            >
              {t("activate")}
            </button>
          )}
          <button
            onClick={(e) => { e.stopPropagation(); setShowResetModal(u.id); }}
            className="text-xs px-2 py-1 rounded bg-gray-50 text-gray-600 hover:bg-gray-100 transition-colors"
          >
            🔑
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); setSelectedUser(u); }}
            className="text-xs px-2 py-1 rounded bg-gray-50 text-gray-600 hover:bg-gray-100 transition-colors"
          >
            ✏️
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t("title")}</h1>
          <p className="text-sm text-gray-500 mt-1">{t("subtitle")}</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 transition-colors"
        >
          {t("addUser")}
        </button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard title={t("totalUsers")} value={String(totalUsers)} />
        <StatCard title={t("activeUsers")} value={String(activeUsers)} />
        <StatCard title={t("pendingApproval")} value={String(pendingCount)} />
        <StatCard title={t("roles")} value={String(uniqueRoles)} />
      </div>

      {/* Tabs */}
      <div className="flex gap-4 border-b border-gray-200">
        <button
          className={`pb-2 text-sm font-medium transition-colors ${tab === "all" ? "border-b-2 border-blue-600 text-blue-600" : "text-gray-500 hover:text-gray-700"}`}
          onClick={() => setTab("all")}
        >
          {t("tabAll")}
        </button>
        <button
          className={`pb-2 text-sm font-medium transition-colors ${tab === "pending" ? "border-b-2 border-amber-500 text-amber-600" : "text-gray-500 hover:text-gray-700"}`}
          onClick={() => setTab("pending")}
        >
          {t("tabPending", { count: pendingCount })}
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="text"
          placeholder={t("searchPlaceholder")}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-72 focus:ring-2 focus:ring-blue-200 outline-none"
        />
        <select
          value={filterRole}
          onChange={(e) => setFilterRole(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-blue-200 outline-none"
        >
          <option value="">{t("allRoles")}</option>
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {t(`role${r.split("_").map((w) => w[0].toUpperCase() + w.slice(1)).join("")}` as Parameters<typeof t>[0])}
            </option>
          ))}
        </select>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-blue-200 outline-none"
        >
          <option value="">{t("allStatuses")}</option>
          <option value="active">{t("active")}</option>
          <option value="inactive">{t("inactive")}</option>
          <option value="pending">{t("pending")}</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
        {tab === "pending" && filteredUsers.length === 0 && !isLoading ? (
          <div className="text-center py-12 text-gray-400">{t("noPending")}</div>
        ) : (
          <DataTable
            columns={columns}
            data={filteredUsers}
            isLoading={isLoading}
            emptyMessage={t("noUsers")}
          />
        )}
      </div>

      {/* Create User Modal */}
      {showCreateModal && (
        <CreateUserModal
          t={t}
          tc={tc}
          onClose={() => setShowCreateModal(false)}
          onCreated={() => { refetch(); refetchPending(); setShowCreateModal(false); }}
        />
      )}

      {/* Edit User Modal */}
      {selectedUser && (
        <EditUserModal
          t={t}
          tc={tc}
          user={selectedUser}
          onClose={() => setSelectedUser(null)}
          onUpdated={() => { refetch(); setSelectedUser(null); }}
        />
      )}

      {/* Reset Password Modal */}
      {showResetModal && (
        <ResetPasswordModal
          t={t}
          tc={tc}
          userId={showResetModal}
          onClose={() => setShowResetModal(null)}
        />
      )}
    </div>
  );
}

// ============================================================================
// Create User Modal
// ============================================================================
function CreateUserModal({
  t,
  tc,
  onClose,
  onCreated,
}: {
  t: (key: string, values?: Record<string, string | number>) => string;
  tc: (key: string) => string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form, setForm] = useState<CreateUserRequest>({
    email: "",
    username: "",
    password: "",
    full_name: "",
    role: "viewer",
  });
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await api("POST", "/auth/users", form);
      if (res.ok) {
        showToast({ type: "success", title: t("userCreated") });
        onCreated();
      } else {
        const detail = (res.data as Record<string, string>)?.detail || t("errorCreating");
        showToast({ type: "error", title: detail });
      }
    } catch {
      showToast({ type: "error", title: t("errorCreating") });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-gray-900 mb-4">{t("createUser")}</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t("fullName")}</label>
            <input
              type="text"
              value={form.full_name}
              onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
              placeholder={t("fullNamePlaceholder")}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-200 outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t("username")} *</label>
            <input
              type="text"
              required
              value={form.username}
              onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
              placeholder={t("usernamePlaceholder")}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-200 outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t("email")} *</label>
            <input
              type="email"
              required
              value={form.email}
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              placeholder={t("emailPlaceholder")}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-200 outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t("password")} *</label>
            <input
              type="password"
              required
              minLength={8}
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              placeholder={t("passwordPlaceholder")}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-200 outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t("role")}</label>
            <select
              value={form.role}
              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as UserRole }))}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-blue-200 outline-none"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {t(`role${r.split("_").map((w) => w[0].toUpperCase() + w.slice(1)).join("")}`)}
                </option>
              ))}
            </select>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 transition-colors">
              {tc("cancel")}
            </button>
            <button
              type="submit"
              disabled={saving}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {saving ? t("creatingUser") : t("createButton")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ============================================================================
// Edit User Modal
// ============================================================================
function EditUserModal({
  t,
  tc,
  user,
  onClose,
  onUpdated,
}: {
  t: (key: string, values?: Record<string, string | number>) => string;
  tc: (key: string) => string;
  user: UserResponse;
  onClose: () => void;
  onUpdated: () => void;
}) {
  const [form, setForm] = useState({
    full_name: user.full_name,
    email: user.email,
  });
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await api("PUT", `/auth/users/${user.id}`, form);
      if (res.ok) {
        showToast({ type: "success", title: t("userUpdated") });
        onUpdated();
      } else {
        const detail = (res.data as Record<string, string>)?.detail || t("errorUpdating");
        showToast({ type: "error", title: detail });
      }
    } catch {
      showToast({ type: "error", title: t("errorUpdating") });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-gray-900 mb-1">{t("editUser")}</h2>
        <p className="text-sm text-gray-400 mb-4">@{user.username}</p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t("fullName")}</label>
            <input
              type="text"
              value={form.full_name}
              onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-200 outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t("email")}</label>
            <input
              type="email"
              value={form.email}
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-200 outline-none"
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 transition-colors">
              {tc("cancel")}
            </button>
            <button
              type="submit"
              disabled={saving}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {saving ? t("savingUser") : t("saveButton")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ============================================================================
// Reset Password Modal
// ============================================================================
function ResetPasswordModal({
  t,
  tc,
  userId,
  onClose,
}: {
  t: (key: string, values?: Record<string, string | number>) => string;
  tc: (key: string) => string;
  userId: string;
  onClose: () => void;
}) {
  const [newPassword, setNewPassword] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await api("POST", `/auth/users/${userId}/reset-password`, { new_password: newPassword });
      if (res.ok) {
        showToast({ type: "success", title: t("passwordReset") });
        onClose();
      } else {
        showToast({ type: "error", title: t("errorAction") });
      }
    } catch {
      showToast({ type: "error", title: t("errorAction") });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-6" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-gray-900 mb-4">🔑 {t("resetPassword")}</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t("newPassword")}</label>
            <input
              type="password"
              required
              minLength={8}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder={t("passwordPlaceholder")}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-200 outline-none"
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 transition-colors">
              {tc("cancel")}
            </button>
            <button
              type="submit"
              disabled={saving || newPassword.length < 8}
              className="bg-red-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-red-700 disabled:opacity-50 transition-colors"
            >
              {saving ? t("resetting") : t("resetButton")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

