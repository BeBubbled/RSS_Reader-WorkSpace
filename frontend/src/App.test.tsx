import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import App from "./App";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

test("shows the login page when session restoration is unauthorized", async () => {
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Authentication required" }), { status: 401 }));
  render(<QueryClientProvider client={new QueryClient()}><App /></QueryClientProvider>);
  expect(await screen.findByRole("heading", { name: "登录阅读器" })).toBeInTheDocument();
});

test("shows the application shell for an authenticated user", async () => {
  fetchMock
    .mockResolvedValueOnce(new Response(JSON.stringify({ username: "admin" }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ status: "phase-0", user: "admin" }), { status: 200 }));
  render(<QueryClientProvider client={new QueryClient()}><App /></QueryClientProvider>);
  expect(await screen.findByText("资料库")).toBeInTheDocument();
});
