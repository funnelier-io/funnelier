"use client";

import { create } from "zustand";
import { apiGet, apiPost, apiDelete } from "@/lib/api-client";
import type {
  Notification,
  NotificationListResponse,
  UnreadCountResponse,
} from "@/types/notifications";

interface NotificationStore {
  notifications: Notification[];
  unreadCount: number;
  total: number;
  isOpen: boolean;
  isLoading: boolean;

  setOpen: (open: boolean) => void;
  toggle: () => void;

  fetchNotifications: () => Promise<void>;
  fetchUnreadCount: () => Promise<void>;

  markRead: (id: string) => Promise<void>;
  markAllRead: () => Promise<void>;
  deleteNotification: (id: string) => Promise<void>;

  addNotification: (n: Notification) => void;
}

export const useNotificationStore = create<NotificationStore>((set, get) => ({
  notifications: [],
  unreadCount: 0,
  total: 0,
  isOpen: false,
  isLoading: false,

  setOpen: (open) => {
    set({ isOpen: open });
    if (open) {
      get().fetchNotifications();
    }
  },

  toggle: () => {
    const open = !get().isOpen;
    set({ isOpen: open });
    if (open) {
      get().fetchNotifications();
    }
  },

  fetchNotifications: async () => {
    set({ isLoading: true });
    try {
      const res = await apiGet<NotificationListResponse>(
        "/notifications?limit=30"
      );
      if (res.ok) {
        set({
          notifications: res.data.items,
          total: res.data.total,
          unreadCount: res.data.unread_count,
        });
      }
    } catch {
      // ignore
    } finally {
      set({ isLoading: false });
    }
  },

  fetchUnreadCount: async () => {
    try {
      const res = await apiGet<UnreadCountResponse>(
        "/notifications/unread-count"
      );
      if (res.ok) {
        set({ unreadCount: res.data.unread_count });
      }
    } catch {
      // ignore
    }
  },

  markRead: async (id) => {
    try {
      const res = await apiPost(`/notifications/${id}/read`);
      if (res.ok) {
        set((state) => ({
          notifications: state.notifications.map((n) =>
            n.id === id ? { ...n, is_read: true, read_at: new Date().toISOString() } : n
          ),
          unreadCount: Math.max(0, state.unreadCount - 1),
        }));
      }
    } catch {
      // ignore
    }
  },

  markAllRead: async () => {
    try {
      const res = await apiPost("/notifications/read-all");
      if (res.ok) {
        set((state) => ({
          notifications: state.notifications.map((n) => ({
            ...n,
            is_read: true,
            read_at: n.read_at ?? new Date().toISOString(),
          })),
          unreadCount: 0,
        }));
      }
    } catch {
      // ignore
    }
  },

  deleteNotification: async (id) => {
    try {
      const res = await apiDelete(`/notifications/${id}`);
      if (res.ok || res.status === 204) {
        const wasUnread = get().notifications.find((n) => n.id === id && !n.is_read);
        set((state) => ({
          notifications: state.notifications.filter((n) => n.id !== id),
          total: state.total - 1,
          unreadCount: wasUnread ? Math.max(0, state.unreadCount - 1) : state.unreadCount,
        }));
      }
    } catch {
      // ignore
    }
  },

  addNotification: (n) => {
    set((state) => ({
      notifications: [n, ...state.notifications].slice(0, 30),
      total: state.total + 1,
      unreadCount: state.unreadCount + 1,
    }));
  },
}));

