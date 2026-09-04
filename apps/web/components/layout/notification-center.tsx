"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Bell,
  BellOff,
  Check,
  CheckCheck,
  Clock,
  Loader2,
  Lock,
  RefreshCw,
  SearchCheck,
  ShieldAlert,
  XCircle,
  Ban,
  Inbox,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  fetchNotifications,
  fetchUnreadCount,
  markAllNotificationsRead,
  markNotificationRead,
  type NotificationItem,
} from "@/lib/api";

/** Relative, locale-aware time label (e.g. "just now", "14m ago", "2d ago"). */
function timeLabel(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diffMs = Date.now() - then;
  const sec = Math.floor(diffMs / 1000);
  if (sec < 45) return "just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day}d ago`;
  return new Date(iso).toLocaleDateString();
}

function typeIcon(type: string) {
  switch (type) {
    case "ACTION_REQUEST_PENDING":
      return { Icon: Clock, tone: "text-amber-600 dark:text-amber-400" };
    case "ACTION_REQUEST_APPROVED":
      return { Icon: Check, tone: "text-emerald-600 dark:text-emerald-400" };
    case "ACTION_REQUEST_REJECTED":
      return { Icon: XCircle, tone: "text-red-600 dark:text-red-400" };
    case "ACTION_REQUEST_CANCELLED":
      return { Icon: Ban, tone: "text-muted-foreground" };
    case "INVESTIGATION_COMPLETED":
      return { Icon: SearchCheck, tone: "text-blue-600 dark:text-blue-400" };
    case "INVESTIGATION_FAILED":
      return { Icon: ShieldAlert, tone: "text-red-600 dark:text-red-400" };
    case "PERIOD_BLOCKED":
      return { Icon: Lock, tone: "text-amber-600 dark:text-amber-400" };
    case "PERIOD_CLOSED":
      return { Icon: Lock, tone: "text-emerald-600 dark:text-emerald-400" };
    default:
      return { Icon: Bell, tone: "text-muted-foreground" };
  }
}

/** Maps a notification target to its detail route; falls back to the workspace. */
function targetHref(type: string | null, id: string | null): string | null {
  if (!type || !id) return null;
  switch (type) {
    case "action_request":
      return `/action-requests/${id}`;
    case "investigation":
      return `/investigations/${id}`;
    case "period":
      return `/periods/${id}`;
    default:
      return null;
  }
}

interface NotificationCenterProps {
  className?: string;
}

export function NotificationCenter({ className }: NotificationCenterProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState<number | null>(null);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const fetchingRef = useRef(false);

  const refreshUnread = useCallback(async () => {
    try {
      setUnread(await fetchUnreadCount());
    } catch {
      // Non-fatal: the bell simply shows no badge when the count is unknown.
    }
  }, []);

  const loadFeed = useCallback(async () => {
    if (fetchingRef.current) return;
    fetchingRef.current = true;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchNotifications(30, 0);
      setItems(data.items);
      setTotal(data.total);
      setUnread(data.unread_count);
    } catch {
      setError("Could not load notifications. Please retry.");
    } finally {
      setLoading(false);
      fetchingRef.current = false;
    }
  }, []);

  // Poll the unread count while the page is open (lightweight).
  useEffect(() => {
    refreshUnread();
    const interval = window.setInterval(refreshUnread, 30_000);
    return () => window.clearInterval(interval);
  }, [refreshUnread]);

  // Load the feed when the panel opens and close on outside click / Escape.
  useEffect(() => {
    if (!open) return;
    loadFeed();

    const handleOutside = (event: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", handleOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [open, loadFeed]);

  const handleItemClick = async (item: NotificationItem) => {
    const href = targetHref(item.target_type, item.target_id);
    if (!item.is_read) {
      // Optimistically reflect read state, confirmed by the backend call.
      const prev = items;
      setItems((list) =>
        list.map((n) => (n.id === item.id ? { ...n, is_read: true } : n))
      );
      setUnread((u) => (u === null ? u : Math.max(0, u - 1)));
      try {
        await markNotificationRead(item.id);
      } catch {
        // Revert on failure so the UI never lies about read state.
        setItems(prev);
        setUnread(await fetchUnreadCount().catch(() => null));
      }
    }
    setOpen(false);
    if (href) router.push(href);
  };

  const handleMarkAll = async () => {
    if (acting) return;
    setActing(true);
    try {
      const updated = await markAllNotificationsRead();
      if (updated > 0) {
        setItems((list) => list.map((n) => ({ ...n, is_read: true })));
        setUnread(0);
      }
    } catch {
      setError("Could not mark notifications as read. Please retry.");
    } finally {
      setActing(false);
    }
  };

  const unreadBadge =
    unread !== null && unread > 0 ? (
      <span className="absolute -top-0.5 -right-0.5 flex items-center justify-center min-w-[16px] h-4 px-1 rounded-full bg-error text-white text-[10px] font-semibold ring-2 ring-card leading-none">
        {unread > 99 ? "99+" : unread}
      </span>
    ) : null;

  return (
    <div className={cn("relative", className)} ref={panelRef}>
      <button
        onClick={() => {
          if (open) {
            setOpen(false);
          } else {
            setOpen(true);
          }
        }}
        className="relative p-2 text-muted-foreground hover:text-foreground rounded-full hover:bg-surface-muted transition-colors focus-ring"
        aria-haspopup="true"
        aria-expanded={open}
        aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}
      >
        <Bell className="w-[18px] h-[18px]" />
        {unreadBadge}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-[380px] max-w-[calc(100vw-2rem)] rounded-md shadow-lg bg-card border border-border overflow-hidden z-50 animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="px-4 py-3 border-b border-border flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-foreground">Notifications</p>
              {unread !== null && unread > 0 && (
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  {unread} unread
                </p>
              )}
            </div>
            <button
              onClick={handleMarkAll}
              disabled={acting || !unread}
              className="flex items-center gap-1.5 text-[12px] font-medium text-primary hover:underline disabled:opacity-40 disabled:cursor-not-allowed focus-ring rounded px-1.5 py-1"
            >
              {acting ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <CheckCheck className="w-3.5 h-3.5" />
              )}
              Mark all read
            </button>
          </div>

          <div className="max-h-[360px] overflow-y-auto">
            {loading && items.length === 0 ? (
              <div className="p-4 space-y-3">
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 animate-pulse"
                  >
                    <div className="w-8 h-8 rounded-full bg-surface-muted" />
                    <div className="flex-1 space-y-1.5 pt-1">
                      <div className="h-3 w-3/4 rounded bg-surface-muted" />
                      <div className="h-2.5 w-1/2 rounded bg-surface-muted" />
                    </div>
                  </div>
                ))}
              </div>
            ) : error ? (
              <div className="p-6 text-center">
                <BellOff className="w-6 h-6 mx-auto text-muted-foreground/60" />
                <p className="mt-2 text-[13px] text-muted-foreground">{error}</p>
                <button
                  onClick={loadFeed}
                  className="mt-3 inline-flex items-center gap-1.5 text-[12px] font-medium text-primary hover:underline focus-ring rounded px-2 py-1"
                >
                  <RefreshCw className="w-3 h-3" /> Retry
                </button>
              </div>
            ) : items.length === 0 ? (
              <div className="p-8 text-center">
                <Inbox className="w-6 h-6 mx-auto text-muted-foreground/60" />
                <p className="mt-2 text-[13px] font-medium text-foreground">
                  No notifications
                </p>
                <p className="mt-0.5 text-[12px] text-muted-foreground">
                  Updates about investigations, action requests and period
                  closures will appear here.
                </p>
              </div>
            ) : (
              <ul role="list" className="divide-y divide-border-subtle">
                {items.map((item) => {
                  const { Icon, tone } = typeIcon(item.type);
                  const href = targetHref(item.target_type, item.target_id);
                  return (
                    <li key={item.id}>
                      <button
                        onClick={() => handleItemClick(item)}
                        className={cn(
                          "w-full text-left px-4 py-3 flex items-start gap-3 transition-colors focus-ring",
                          item.is_read
                            ? "hover:bg-surface-muted/60"
                            : "bg-primary/[0.04] hover:bg-primary/[0.08]"
                        )}
                      >
                        <span
                          className={cn(
                            "mt-0.5 flex items-center justify-center w-8 h-8 rounded-full bg-surface-muted shrink-0",
                            tone
                          )}
                        >
                          <Icon className="w-4 h-4" />
                        </span>
                        <span className="flex-1 min-w-0">
                          <span className="flex items-center justify-between gap-2">
                            <span
                              className={cn(
                                "text-[13px] truncate",
                                item.is_read
                                  ? "text-foreground"
                                  : "font-semibold text-foreground"
                              )}
                            >
                              {item.title}
                            </span>
                            {!item.is_read && (
                              <span className="w-2 h-2 rounded-full bg-primary shrink-0" />
                            )}
                          </span>
                          <span className="block text-[12px] text-muted-foreground mt-0.5 leading-snug">
                            {item.message}
                          </span>
                          <span className="block text-[11px] text-muted-foreground/70 mt-1">
                            {timeLabel(item.created_at)}
                            {href ? " · Open" : ""}
                          </span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {total > items.length && (
            <div className="px-4 py-2 border-t border-border text-center">
              <p className="text-[11px] text-muted-foreground">
                Showing {items.length} of {total}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
