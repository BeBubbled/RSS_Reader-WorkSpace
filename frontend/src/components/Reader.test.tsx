import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import { Reader } from "./Reader";

const fetchMock = vi.fn();

const entry = {
  id: "e1", feed_id: "f1", title: "Title", url: null, author: null,
  published_at: "2026-01-01T00:00:00Z", content_html: "<p>hello</p>",
  content_text: "hello", is_read: false, is_starred: false, reading_position: 0,
};

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation((url: string) => {
    const path = url.split("?")[0];
    const listEndpoints = ["/api/folders", "/api/feeds", "/api/ai/providers", "/api/ai/models", "/api/ai/functions", "/api/ai/jobs", "/api/notifications", "/api/workflows"];
    if (listEndpoints.includes(path)) return Promise.resolve(json([]));
    if (path === "/api/entries") return Promise.resolve(json({ items: [entry], next_cursor: null }));
    if (path === "/api/entries/e1") return Promise.resolve(json(entry));
    if (path === "/api/entries/e1/artifacts") return Promise.resolve(json([]));
    if (path === "/api/settings/ai") return Promise.resolve(json({}));
    return Promise.resolve(json([]));
  });
  vi.stubGlobal("fetch", fetchMock);
});

test("shows translate and summary actions for a selected article", async () => {
  render(<QueryClientProvider client={new QueryClient()}><Reader /></QueryClientProvider>);
  expect(await screen.findByRole("button", { name: "翻译" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "AI 总结" })).toBeInTheDocument();
});

test("shows a selection checkbox on each article row", async () => {
  render(<QueryClientProvider client={new QueryClient()}><Reader /></QueryClientProvider>);
  expect(await screen.findByLabelText("选择文章")).toBeInTheDocument();
});
