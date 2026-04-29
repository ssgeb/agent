import { useEffect, useState } from "react";
import {
  getAuthUserId,
  getPlanHistory,
  listSessions,
  readSessionHistory,
  type HistorySession,
  type TravelPlan,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";

interface HistoryDrawerProps {
  open: boolean;
  onClose: () => void;
  onSelect: (sessionId: string, plan: TravelPlan) => void;
}

function getTitle(session: HistorySession): string {
  return session.title || session.preview || session.session_id;
}

function getDate(session: HistorySession): string {
  const rawDate = session.updated_at || session.created_at;
  if (!rawDate) {
    return "刚刚";
  }

  const date = new Date(rawDate);
  if (Number.isNaN(date.getTime())) {
    return "刚刚";
  }

  return date.toLocaleDateString("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function unwrapHistoryPlan(item: unknown): TravelPlan | undefined {
  if (!item || typeof item !== "object") {
    return undefined;
  }

  const maybeSnapshot = item as { plan?: unknown };
  if (maybeSnapshot.plan && typeof maybeSnapshot.plan === "object") {
    return maybeSnapshot.plan as TravelPlan;
  }

  return item as TravelPlan;
}

export function HistoryDrawer({ open, onClose, onSelect }: HistoryDrawerProps) {
  const { token, user } = useAuth();
  const [sessions, setSessions] = useState<HistorySession[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open || !token || !user) {
      return;
    }

    let cancelled = false;

    const loadHistory = async () => {
      setLoading(true);
      setError("");

      try {
        const storedSessions = readSessionHistory(getAuthUserId(user));
        const remoteSessions = await listSessions(token, 20)
          .then((response) => response.sessions)
          .catch(() => []);
        const mergedSessions = [...storedSessions];
        for (const remoteSession of remoteSessions) {
          if (!mergedSessions.some((session) => session.session_id === remoteSession.session_id)) {
            mergedSessions.push(remoteSession);
          }
        }
        const hydrated = await Promise.all(
          mergedSessions.map(async (session) => {
            try {
              const response = await getPlanHistory(session.session_id, token, 5);
              const latestPlan = unwrapHistoryPlan(response.history[response.history.length - 1]);
              return {
                ...session,
                title: latestPlan?.overview ?? session.title,
                preview: latestPlan?.overview ?? session.preview,
                latest_plan: latestPlan ?? session.latest_plan,
              };
            } catch {
              return session;
            }
          })
        );

        if (!cancelled) {
          setSessions(hydrated.filter((session) => session.latest_plan));
        }
      } catch {
        if (!cancelled) {
          setError("加载历史记录失败");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadHistory();

    return () => {
      cancelled = true;
    };
  }, [open, token, user]);

  return (
    <aside className={`history-drawer ${open ? "open" : ""}`} aria-label="历史记录">
      <div className="drawer-header">
        <h2>历史记录</h2>
        <button className="secondary-button" type="button" onClick={onClose}>
          关闭
        </button>
      </div>
      <div className="history-list">
        {loading ? (
          <div className="loading-state">
            <span className="loading-spinner" aria-hidden="true" />
            <span>加载中...</span>
          </div>
        ) : error ? (
          <div className="error-state">
            <p>{error}</p>
          </div>
        ) : sessions.length === 0 ? (
          <div className="empty-state">
            <p>暂无历史记录</p>
          </div>
        ) : (
          sessions.map((session) => (
            <button
              key={session.session_id}
              className="history-item"
              type="button"
              onClick={() => {
                if (session.latest_plan) {
                  onSelect(session.session_id, session.latest_plan);
                }
              }}
            >
              <span className="history-item-title">{getTitle(session)}</span>
              <span className="history-item-date">{getDate(session)}</span>
            </button>
          ))
        )}
      </div>
    </aside>
  );
}
