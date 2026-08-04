import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, test, vi } from "vitest";
import { FreshRSSSettings } from "./FreshRSSSettings";

beforeEach(() => vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }))));

test("renders and accepts FreshRSS connection settings", () => {
  render(<QueryClientProvider client={new QueryClient()}><FreshRSSSettings /></QueryClientProvider>);
  fireEvent.change(screen.getByLabelText("FreshRSS URL"), { target: { value: "https://rss.example" } });
  expect(screen.getByDisplayValue("https://rss.example")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "测试连接" })).toBeInTheDocument();
});
