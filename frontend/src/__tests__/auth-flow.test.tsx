import { afterEach, beforeEach, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "../App";

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

it("logs in and shows the chat empty state", async () => {
  const user = userEvent.setup();
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);

    if (url.endsWith("/auth/login")) {
      return new Response(
        JSON.stringify({
          access_token: "token-123",
          token_type: "bearer",
          user: {
            id: 1,
            username: "alex",
            email: "alex@example.com",
          },
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    throw new Error(`Unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  expect(screen.getByText("你好，我是旅行规划助手")).toBeInTheDocument();
  await user.click(screen.getAllByRole("button", { name: "登录" })[0]);

  await user.type(screen.getByLabelText("账号"), "alex");
  await user.type(screen.getByLabelText("密码"), "secret");
  await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "登录" }));

  expect(await screen.findByText("你好，我是旅行规划助手")).toBeInTheDocument();
  expect(screen.getByText("alex")).toBeInTheDocument();
});
