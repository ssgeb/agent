import { useCallback, useRef, useState } from "react";
import {
  createBookingRecord,
  createChatTask,
  getAuthUserId,
  getPlan,
  getTask,
  rememberSession,
  type ChatTask,
  type TravelPlan,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { BookingDrawer } from "../components/BookingDrawer";
import { ChatComposer } from "../components/ChatComposer";
import { HistoryDrawer } from "../components/HistoryDrawer";
import { MessageList, type ChatMessage } from "../components/MessageList";
import { PlanDrawer } from "../components/PlanDrawer";
import { PreferencesDrawer } from "../components/PreferencesDrawer";

interface ChatPageProps {
  onLogout?: () => void;
  onLoginRequired?: () => void;
}

function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : "请求失败，请稍后再试";
}

function createMessageId(prefix: string) {
  return `${prefix}-${globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`}`;
}

export interface ChatRequestFlowDeps {
  token: string;
  requestId: number;
  getCurrentRequestId: () => number;
  createChatTask: (message: string, token: string) => Promise<ChatTaskLike>;
  getTask: (taskId: string, token: string) => Promise<ChatTaskLike>;
  getPlan: typeof getPlan;
  onAssistantMessage: (text: string) => void;
  onPlan: (plan: TravelPlan, sessionId: string) => void;
}

type ChatTaskLike = Omit<ChatTask, "status"> & { status: string };

const POLL_INTERVAL_MS = 2000;
const MAX_POLL_ATTEMPTS = 150;

export async function runChatRequestFlow(
  message: string,
  deps: ChatRequestFlowDeps
): Promise<void> {
  const task = await deps.createChatTask(message, deps.token);
  if (deps.requestId !== deps.getCurrentRequestId()) {
    return;
  }

  let taskState = await deps.getTask(task.task_id, deps.token);
  if (deps.requestId !== deps.getCurrentRequestId()) {
    return;
  }

  let attempts = 0;
  while (
    taskState.status !== "SUCCEEDED" &&
    taskState.status !== "WAITING_INPUT" &&
    taskState.status !== "FAILED" &&
    taskState.status !== "CANCELED" &&
    attempts < MAX_POLL_ATTEMPTS
  ) {
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
    if (deps.requestId !== deps.getCurrentRequestId()) {
      return;
    }
    taskState = await deps.getTask(task.task_id, deps.token);
    if (deps.requestId !== deps.getCurrentRequestId()) {
      return;
    }
    attempts++;
  }

  if (taskState.status === "FAILED" || taskState.status === "CANCELED") {
    deps.onAssistantMessage("方案生成失败，请稍后重试。");
    return;
  }

  if (taskState.status === "SUCCEEDED" || taskState.status === "WAITING_INPUT") {
    const nextPlan = await deps.getPlan(taskState.session_id, deps.token);
    if (deps.requestId !== deps.getCurrentRequestId()) {
      return;
    }

    deps.onPlan(nextPlan, taskState.session_id);
    deps.onAssistantMessage(nextPlan.overview ?? "方案已生成");
    return;
  }

  deps.onAssistantMessage("方案生成超时，请稍后重试。");
}

export function ChatPage({ onLogout, onLoginRequired }: ChatPageProps) {
  const { user, logout, token } = useAuth();
  const [composerValue, setComposerValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [bookingLoading, setBookingLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [plan, setPlan] = useState<TravelPlan | null>(null);
  const [planOpen, setPlanOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [preferencesOpen, setPreferencesOpen] = useState(false);
  const [bookingsOpen, setBookingsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const inFlightRef = useRef(false);
  const requestIdRef = useRef(0);

  const handleLogout = useCallback(() => {
    onLogout?.();
    logout();
  }, [logout, onLogout]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const appendAssistantMessage = useCallback((text: string) => {
    setMessages((current) => [
      ...current,
      {
        id: createMessageId("assistant"),
        role: "assistant",
        text,
      },
    ]);
  }, []);

  const updateStatusMessage = useCallback((text: string) => {
    setMessages((current) => {
      const lastMessage = current[current.length - 1];
      if (lastMessage && lastMessage.role === "status") {
        const updatedMessages = [...current];
        updatedMessages[updatedMessages.length - 1] = {
          ...lastMessage,
          text,
        };
        return updatedMessages;
      }
      return current;
    });
  }, []);

  const createFakeBooking = useCallback(
    async (bookingType: "hotel" | "transport") => {
      if (!token) {
        onLoginRequired?.();
        return;
      }
      if (!currentSessionId || !plan) {
        setError("请先生成方案后再模拟预订");
        return;
      }

      const sourceItems = bookingType === "hotel" ? plan.hotels ?? [] : plan.transport ?? [];
      const selectedItem = sourceItems[0];
      if (!selectedItem) {
        setError(`当前方案没有可预订的${bookingType === "hotel" ? "酒店" : "交通"}项`);
        return;
      }

      const itemName = String(selectedItem.name ?? selectedItem.title ?? `${bookingType}预订`);
      const rawAmount = selectedItem.price;
      const parsedAmount =
        typeof rawAmount === "number"
          ? rawAmount
          : typeof rawAmount === "string"
            ? Number(rawAmount)
            : undefined;

      setBookingLoading(true);
      clearError();

      try {
        const created = await createBookingRecord(
          {
            session_id: currentSessionId,
            booking_type: bookingType,
            item_name: itemName,
            amount: Number.isFinite(parsedAmount ?? NaN) ? parsedAmount : undefined,
            currency: "CNY",
            status: "CREATED",
            payload: {
              source: "fake_booking",
              plan_overview: plan.overview ?? null,
              selected_item: selectedItem,
            },
          },
          token
        );

        appendAssistantMessage(
          `已创建模拟预订：${created.booking_type} · ${created.item_name} · ${created.currency} ${created.amount ?? "未填写"}`
        );
      } catch (bookingError) {
        const message = getErrorMessage(bookingError);
        setError(message);
        appendAssistantMessage(`模拟预订失败：${message}`);
      } finally {
        setBookingLoading(false);
      }
    },
    [appendAssistantMessage, clearError, currentSessionId, onLoginRequired, plan, token]
  );

  const handleSubmit = useCallback(async () => {
    const message = composerValue.trim();
    if (!message) {
      return;
    }

    if (!token) {
      onLoginRequired?.();
      return;
    }

    if (inFlightRef.current) {
      return;
    }

    clearError();
    const requestId = ++requestIdRef.current;
    inFlightRef.current = true;
    setIsLoading(true);

    const userMessage: ChatMessage = {
      id: createMessageId("user"),
      role: "user",
      text: message,
    };
    const statusMessage: ChatMessage = {
      id: createMessageId("status"),
      role: "status",
      text: "正在分析你的旅行需求...",
    };

    setMessages((current) => [...current, userMessage, statusMessage]);
    setComposerValue("");
    setPlan(null);
    setPlanOpen(false);

    try {
      await runChatRequestFlow(message, {
        token,
        requestId,
        getCurrentRequestId: () => requestIdRef.current,
        createChatTask,
        getTask,
        getPlan,
        onPlan: (planData, sessionId) => {
          setPlan(planData);
          setCurrentSessionId(sessionId);
          if (user) {
            rememberSession(getAuthUserId(user), {
              session_id: sessionId,
              title: planData.overview,
              preview: planData.overview ?? message,
              latest_plan: planData,
            });
          }
        },
        onAssistantMessage: (text) => {
          if (text.includes("正在生成") || text.includes("准备中")) {
            updateStatusMessage(text);
          } else {
            appendAssistantMessage(text);
          }
        },
      });
    } catch (submitError) {
      if (requestId === requestIdRef.current) {
        const messageText = getErrorMessage(submitError);
        setError(messageText);
        appendAssistantMessage(`生成失败：${messageText}`);
      }
    } finally {
      if (requestId === requestIdRef.current) {
        inFlightRef.current = false;
        setIsLoading(false);
      }
    }
  }, [
    appendAssistantMessage,
    clearError,
    composerValue,
    onLoginRequired,
    token,
    updateStatusMessage,
    user,
  ]);

  const handleNewConversation = useCallback(() => {
    setMessages([]);
    setPlan(null);
    setPlanOpen(false);
    setComposerValue("");
    setCurrentSessionId(null);
    clearError();
  }, [clearError]);

  const handleOpenHistory = useCallback(() => {
    if (!token) {
      onLoginRequired?.();
      return;
    }
    setHistoryOpen(true);
  }, [onLoginRequired, token]);

  const handleOpenPreferences = useCallback(() => {
    if (!token) {
      onLoginRequired?.();
      return;
    }
    setPreferencesOpen(true);
  }, [onLoginRequired, token]);

  const handleOpenBookings = useCallback(() => {
    if (!token) {
      onLoginRequired?.();
      return;
    }
    setBookingsOpen(true);
  }, [onLoginRequired, token]);

  const handleHistorySelect = useCallback((sessionId: string, selectedPlan: TravelPlan) => {
    setCurrentSessionId(sessionId);
    setPlan(selectedPlan);
    setMessages([
      {
        id: createMessageId("assistant"),
        role: "assistant",
        text: selectedPlan.overview ?? "已恢复历史方案",
      },
    ]);
    setPlanOpen(false);
    setHistoryOpen(false);
  }, []);

  return (
    <div className="chat-page">
      {error && (
        <div className="error-banner" role="alert">
          <span>{error}</span>
          <button className="icon-button" onClick={() => setError(null)} aria-label="关闭错误提示" type="button">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      <aside className="chat-sidebar" aria-label="侧边导航">
        <div className="sidebar-brand">旅行</div>
        <button className="sidebar-primary-action" type="button" onClick={handleNewConversation}>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 5v14M5 12h14" />
          </svg>
          新建对话
        </button>
        <button className="sidebar-link" type="button" onClick={handleOpenHistory}>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
            <path d="M3 3v5h5M12 7v6l4 2" />
          </svg>
          最近对话
        </button>
        <button className="sidebar-link" type="button" onClick={handleOpenHistory}>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 19V5a2 2 0 0 1 2-2h9l5 5v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z" />
            <path d="M14 3v6h6" />
          </svg>
          我的方案
        </button>
        <button className="sidebar-link" type="button" onClick={handleOpenPreferences}>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" />
            <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.6-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1A2 2 0 1 1 7.1 4l.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.6V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" />
          </svg>
          偏好设置
        </button>
        <button className="sidebar-link" type="button" onClick={handleOpenBookings}>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M5 7h14v10H5z" />
            <path d="M5 11h14M9 7v10" />
          </svg>
          预订记录
        </button>
        <div className="sidebar-spacer" />
        <div className="sidebar-account">
          <div className="account-avatar" aria-hidden="true">
            {user?.username?.slice(0, 1).toUpperCase() ?? "旅"}
          </div>
          {user ? (
            <>
              <span>{user.username}</span>
              <button className="sidebar-account-action" type="button" onClick={handleLogout}>
                退出
              </button>
            </>
          ) : (
            <>
              <span>未登录</span>
              <button className="sidebar-account-action" type="button" onClick={onLoginRequired}>
                登录
              </button>
            </>
          )}
        </div>
      </aside>

      <div className="chat-workspace">
        <header className="chat-topbar">
          <button className="model-selector" type="button">
            Travel-Agent 旅行规划助手
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="m6 9 6 6 6-6" />
            </svg>
          </button>
          <div className="chat-topbar-actions">
            <button className="topbar-link" type="button" onClick={handleOpenHistory}>
              历史
            </button>
            <button className="topbar-link" type="button" onClick={handleOpenPreferences}>
              偏好设置
            </button>
            <button className="topbar-link" type="button" onClick={handleOpenBookings}>
              预订记录
            </button>
            {user ? (
              <button className="topbar-link" type="button" onClick={handleLogout}>
                退出登录
              </button>
            ) : (
              <button className="topbar-link" type="button" onClick={onLoginRequired}>
                登录
              </button>
            )}
          </div>
        </header>

        <main className="chat-main">
          <MessageList messages={messages} />
          {plan && (
            <div className="plan-launcher">
              <button className="primary-button" type="button" onClick={() => setPlanOpen(true)}>
                查看完整方案
              </button>
            </div>
          )}
          <div className="composer-shell">
            <ChatComposer value={composerValue} loading={isLoading} onChange={setComposerValue} onSubmit={handleSubmit} />
          </div>
        </main>
      </div>

      <PlanDrawer
        open={planOpen}
        plan={plan}
        onClose={() => setPlanOpen(false)}
        onBookHotel={() => createFakeBooking("hotel")}
        onBookTransport={() => createFakeBooking("transport")}
        onOpenBookings={() => setBookingsOpen(true)}
        bookingLoading={bookingLoading}
      />
      <PreferencesDrawer open={preferencesOpen} onClose={() => setPreferencesOpen(false)} />
      <HistoryDrawer open={historyOpen} onClose={() => setHistoryOpen(false)} onSelect={handleHistorySelect} />
      <BookingDrawer open={bookingsOpen} onClose={() => setBookingsOpen(false)} />
    </div>
  );
}
