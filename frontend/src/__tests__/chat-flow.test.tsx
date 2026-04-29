import { afterEach, beforeEach, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "../App";
import * as authModule from "../auth/AuthContext";
import { ChatPage, runChatRequestFlow } from "../pages/ChatPage";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createDeferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });

  return { promise, resolve };
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

it("stores generated sessions and loads real history instead of mock entries", async () => {
  localStorage.setItem(
    "travel_user",
    JSON.stringify({
      id: 1,
      username: "alex",
      email: "alex@example.com",
    })
  );
  localStorage.setItem("travel_token", "token-123");

  const user = userEvent.setup();
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/chat/async")) {
      expect(init?.method).toBe("POST");
      return jsonResponse(
        {
          task_id: "t-history",
          session_id: "s-history",
          status: "PENDING",
        },
        202
      );
    }

    if (url.endsWith("/task/t-history")) {
      return jsonResponse({
        task_id: "t-history",
        session_id: "s-history",
        status: "SUCCEEDED",
      });
    }

    if (url.endsWith("/plan/s-history")) {
      return jsonResponse({
        overview: "Saved Hangzhou plan",
        hotels: [{ name: "Lake Hotel" }],
        budget: { total: 1800 },
      });
    }

    if (url.endsWith("/plan/s-history/history?limit=5")) {
      return jsonResponse({
        session_id: "s-history",
        history: [
          {
            overview: "Saved Hangzhou plan",
            hotels: [{ name: "Lake Hotel" }],
            budget: { total: 1800 },
          },
        ],
      });
    }

    throw new Error(`Unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  await user.type(screen.getByLabelText("旅行需求"), "plan hangzhou");
  await user.click(screen.getByRole("button", { name: "发送" }));

  expect(await screen.findByText("Saved Hangzhou plan")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "历史" }));

  const historyDrawer = screen.getByLabelText("历史记录");
  expect(await within(historyDrawer).findByText("Saved Hangzhou plan")).toBeInTheDocument();
  expect(screen.queryByText("上海三日游")).not.toBeInTheDocument();
  expect(
    fetchMock.mock.calls.some(([input]) =>
      String(input).endsWith("/plan/s-history/history?limit=5")
    )
  ).toBe(true);
});

it("restores the selected historical plan into the full plan drawer", async () => {
  localStorage.setItem(
    "travel_user",
    JSON.stringify({
      id: 1,
      username: "alex",
      email: "alex@example.com",
    })
  );
  localStorage.setItem("travel_token", "token-123");
  localStorage.setItem(
    "travel_session_history_1",
    JSON.stringify([
      {
        session_id: "s-restore",
        title: "Restored trip",
        preview: "Restored Hangzhou plan",
        updated_at: "2026-04-25T09:00:00.000Z",
      },
    ])
  );

  const user = userEvent.setup();
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);

    if (url.endsWith("/plan/s-restore/history?limit=5")) {
      return jsonResponse({
        session_id: "s-restore",
        history: [
          {
            overview: "Restored Hangzhou plan",
            hotels: [{ name: "Restored Hotel" }],
            budget: { total: 2100 },
          },
        ],
      });
    }

    throw new Error(`Unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  await user.click(screen.getByRole("button", { name: "历史" }));
  await user.click(await screen.findByRole("button", { name: /Restored Hangzhou plan/ }));
  await user.click(screen.getByRole("button", { name: "查看完整方案" }));

  expect(await screen.findByText("Restored Hotel")).toBeInTheDocument();
});

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
});

it("creates a chat task and opens the full plan drawer", async () => {
  localStorage.setItem(
    "travel_user",
    JSON.stringify({
      id: 1,
      username: "alex",
      email: "alex@example.com",
    })
  );
  localStorage.setItem("travel_token", "token-123");

  const user = userEvent.setup();
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/chat/async")) {
      expect(init?.method).toBe("POST");
      return jsonResponse(
        {
          task_id: "t-1",
          session_id: "s-1",
          status: "PENDING",
        },
        202
      );
    }

    if (url.endsWith("/task/t-1")) {
      return jsonResponse({
        task_id: "t-1",
        session_id: "s-1",
        status: "SUCCEEDED",
      });
    }

    if (url.endsWith("/plan/s-1")) {
      return jsonResponse({
        overview: "杭州两日游",
        transport: [{ name: "高铁", price: 180 }],
        hotels: [{ name: "西湖附近酒店", price: 520 }],
        itinerary: [{ day: 1, title: "西湖与湖滨" }],
        budget: { total: 2200 },
        notes: ["提前预约热门景点"],
      });
    }

    throw new Error(`Unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  await user.type(screen.getByLabelText("旅行需求"), "帮我规划杭州两日游");
  await user.click(screen.getByRole("button", { name: "发送" }));

  expect(await screen.findByText("杭州两日游")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "查看完整方案" }));

  expect(await screen.findByText("交通推荐")).toBeInTheDocument();
  expect(screen.getByText("西湖附近酒店")).toBeInTheDocument();
});

it("asks for login when submitting without a token", async () => {
  const onLoginRequired = vi.fn();
  const useAuthSpy = vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: {
      id: 1,
      username: "alex",
      email: "alex@example.com",
    },
    token: null,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  });

  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  const user = userEvent.setup();

  render(<ChatPage onLoginRequired={onLoginRequired} />);

  await user.type(screen.getByLabelText("旅行需求"), "帮我规划杭州两日游");
  await user.click(screen.getByRole("button", { name: "发送" }));

  expect(onLoginRequired).toHaveBeenCalledTimes(1);
  expect(fetchMock).not.toHaveBeenCalled();

  useAuthSpy.mockRestore();
});

it("lets a signed-in user edit travel preferences", async () => {
  localStorage.setItem(
    "travel_user",
    JSON.stringify({
      id: 1,
      username: "alex",
      email: "alex@example.com",
    })
  );
  localStorage.setItem("travel_token", "token-123");

  const user = userEvent.setup();
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/preferences") && init?.method !== "PUT") {
      return jsonResponse({
        preferences: {
          budget: { max: 1800 },
          hotel_preferences: { stars: 4, near: "西湖" },
          transport_preferences: { mode: "train" },
          attraction_preferences: { theme: "family" },
          pace_preference: "relaxed",
          must_visit_places: ["西湖"],
          excluded_places: [],
          notes: ["少走路"],
        },
      });
    }

    if (url.endsWith("/preferences") && init?.method === "PUT") {
      expect(init.body).toContain('"max":2200');
      expect(init.body).toContain('"near":"外滩"');
      return jsonResponse({ preferences: JSON.parse(String(init.body)) });
    }

    throw new Error(`Unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  await user.click(screen.getAllByRole("button", { name: "偏好设置" })[0]);
  expect(await screen.findByDisplayValue("1800")).toBeInTheDocument();

  await user.clear(screen.getByLabelText("预算上限"));
  await user.type(screen.getByLabelText("预算上限"), "2200");
  await user.clear(screen.getByLabelText("酒店位置偏好"));
  await user.type(screen.getByLabelText("酒店位置偏好"), "外滩");
  await user.click(screen.getByRole("button", { name: "保存偏好" }));

  expect(await screen.findByText("偏好已保存")).toBeInTheDocument();
  expect(
    fetchMock.mock.calls.some(
      ([input, init]) => String(input).endsWith("/preferences") && init?.method === "PUT"
    )
  ).toBe(true);
});

it("creates a fake booking and loads it from booking history", async () => {
  localStorage.setItem(
    "travel_user",
    JSON.stringify({
      id: 1,
      username: "alex",
      email: "alex@example.com",
    })
  );
  localStorage.setItem("travel_token", "token-123");

  const user = userEvent.setup();
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/chat/async")) {
      return jsonResponse(
        {
          task_id: "t-booking",
          session_id: "s-booking",
          status: "PENDING",
        },
        202
      );
    }

    if (url.endsWith("/task/t-booking")) {
      return jsonResponse({
        task_id: "t-booking",
        session_id: "s-booking",
        status: "SUCCEEDED",
      });
    }

    if (url.endsWith("/plan/s-booking")) {
      return jsonResponse({
        overview: "杭州两日游",
        transport: [{ name: "高铁", price: 180 }],
        hotels: [{ name: "西湖景观酒店", price: 680 }],
        itinerary: [{ title: "西湖一日游" }],
        budget: { total: 2200 },
        notes: ["提前预约热门景点"],
      });
    }

    if (url.endsWith("/bookings") && init?.method === "POST") {
      expect(init.body).toContain('"booking_type":"hotel"');
      expect(init.body).toContain('"item_name":"西湖景观酒店"');
      return jsonResponse(
        {
          booking_id: "b-booking",
          user_id: "u-1",
          session_id: "s-booking",
          booking_type: "hotel",
          item_name: "西湖景观酒店",
          amount: 680,
          currency: "CNY",
          status: "CREATED",
          payload: {
            source: "fake_booking",
          },
          created_at: "2026-04-28T10:00:00.000Z",
          updated_at: "2026-04-28T10:00:00.000Z",
        },
        201
      );
    }

    if (url.endsWith("/bookings?limit=50")) {
      return jsonResponse({
        bookings: [
          {
            booking_id: "b-booking",
            user_id: "u-1",
            session_id: "s-booking",
            booking_type: "hotel",
            item_name: "西湖景观酒店",
            amount: 680,
            currency: "CNY",
            status: "CREATED",
            payload: { source: "fake_booking" },
            created_at: "2026-04-28T10:00:00.000Z",
            updated_at: "2026-04-28T10:00:00.000Z",
          },
        ],
      });
    }

    throw new Error(`Unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  await user.type(screen.getByLabelText("旅行需求"), "帮我规划杭州两日游");
  await user.click(screen.getByRole("button", { name: "发送" }));
  expect(await screen.findByText("杭州两日游")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "查看完整方案" }));
  await user.click(await screen.findByRole("button", { name: "模拟预订酒店" }));

  expect(await screen.findByText(/已创建模拟预订/)).toBeInTheDocument();

  const planDrawer = screen.getByLabelText("完整行程方案");
  await user.click(within(planDrawer).getByRole("button", { name: "预订记录" }));
  const bookingDrawer = screen.getByLabelText("预订记录");
  expect(await within(bookingDrawer).findByText("hotel · 西湖景观酒店")).toBeInTheDocument();
});

it("only creates one chat job when the form is submitted twice before the first request resolves", async () => {
  localStorage.setItem(
    "travel_user",
    JSON.stringify({
      id: 1,
      username: "alex",
      email: "alex@example.com",
    })
  );
  localStorage.setItem("travel_token", "token-123");

  const pendingChat = createDeferred<Response>();
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/chat/async")) {
      expect(init?.method).toBe("POST");
      return pendingChat.promise;
    }

    throw new Error(`Unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  const textarea = screen.getByLabelText("旅行需求");
  const form = textarea.closest("form");

  expect(form).not.toBeNull();

  await userEvent.type(textarea, "帮我规划杭州两日游");
  form?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  form?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));

  expect(
    fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/chat/async"))
  ).toHaveLength(1);
});

it("ignores a stale response when a newer request has taken over", async () => {
  const currentRequestIds = { value: 1 };
  const assistantMessages: string[] = [];
  const plans: Array<{ overview?: string }> = [];

  const firstCreate = createDeferred<{ task_id: string; session_id: string; status: string }>();
  const secondCreate = createDeferred<{ task_id: string; session_id: string; status: string }>();
  const firstTask = createDeferred<{ task_id: string; session_id: string; status: string }>();
  const secondTask = createDeferred<{ task_id: string; session_id: string; status: string }>();
  const firstPlan = createDeferred<{ overview: string }>();
  const secondPlan = createDeferred<{ overview: string }>();

  const createChatTaskMock = vi.fn((message: string) => {
    if (message === "旧请求") {
      return firstCreate.promise;
    }

    if (message === "新请求") {
      return secondCreate.promise;
    }

    throw new Error(`Unexpected message: ${message}`);
  });

  const getTaskMock = vi.fn((taskId: string) => {
    if (taskId === "t-old") {
      return firstTask.promise;
    }

    if (taskId === "t-new") {
      return secondTask.promise;
    }

    throw new Error(`Unexpected task: ${taskId}`);
  });

  const getPlanMock = vi.fn((sessionId: string) => {
    if (sessionId === "s-old") {
      return firstPlan.promise;
    }

    if (sessionId === "s-new") {
      return secondPlan.promise;
    }

    throw new Error(`Unexpected session: ${sessionId}`);
  });

  const firstRun = runChatRequestFlow("旧请求", {
    token: "token-123",
    requestId: 1,
    getCurrentRequestId: () => currentRequestIds.value,
    createChatTask: createChatTaskMock,
    getTask: getTaskMock,
    getPlan: getPlanMock,
    onAssistantMessage: (text) => assistantMessages.push(text),
    onPlan: (plan) => plans.push(plan),
  });

  currentRequestIds.value = 2;

  const secondRun = runChatRequestFlow("新请求", {
    token: "token-123",
    requestId: 2,
    getCurrentRequestId: () => currentRequestIds.value,
    createChatTask: createChatTaskMock,
    getTask: getTaskMock,
    getPlan: getPlanMock,
    onAssistantMessage: (text) => assistantMessages.push(text),
    onPlan: (plan) => plans.push(plan),
  });

  secondCreate.resolve(
    {
      task_id: "t-new",
      session_id: "s-new",
      status: "PENDING",
    }
  );
  secondTask.resolve(
    {
      task_id: "t-new",
      session_id: "s-new",
      status: "SUCCEEDED",
    }
  );
  secondPlan.resolve(
    {
      overview: "新方案",
    }
  );

  firstCreate.resolve(
    {
      task_id: "t-old",
      session_id: "s-old",
      status: "PENDING",
    }
  );
  firstTask.resolve(
    {
      task_id: "t-old",
      session_id: "s-old",
      status: "SUCCEEDED",
    }
  );
  firstPlan.resolve(
    {
      overview: "旧方案",
    }
  );

  await Promise.all([secondRun, firstRun]);

  expect(assistantMessages).toEqual(["新方案"]);
  expect(plans).toHaveLength(1);
  expect(plans[0]?.overview).toBe("新方案");
});

it("shows an empty budget state when the budget object has no values", async () => {
  localStorage.setItem(
    "travel_user",
    JSON.stringify({
      id: 1,
      username: "alex",
      email: "alex@example.com",
    })
  );
  localStorage.setItem("travel_token", "token-123");

  const user = userEvent.setup();
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/chat/async")) {
      expect(init?.method).toBe("POST");
      return jsonResponse(
        {
          task_id: "t-1",
          session_id: "s-1",
          status: "PENDING",
        },
        202
      );
    }

    if (url.endsWith("/task/t-1")) {
      return jsonResponse({
        task_id: "t-1",
        session_id: "s-1",
        status: "SUCCEEDED",
      });
    }

    if (url.endsWith("/plan/s-1")) {
      return jsonResponse({
        overview: "杭州两日游",
        transport: [{ name: "高铁", price: 180 }],
        hotels: [{ name: "西湖附近酒店", price: 520 }],
        itinerary: [{ day: 1, title: "西湖与湖滨" }],
        budget: {},
        notes: ["提前预约热门景点"],
      });
    }

    throw new Error(`Unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  await user.type(screen.getByLabelText("旅行需求"), "帮我规划杭州两日游");
  await user.click(screen.getByRole("button", { name: "发送" }));

  expect(await screen.findByText("杭州两日游")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "查看完整方案" }));

  const budgetSection = screen.getByRole("heading", { name: "预算估算" }).closest("section");
  expect(budgetSection).not.toBeNull();
  expect(within(budgetSection as HTMLElement).getByText("暂无内容")).toBeInTheDocument();
});
