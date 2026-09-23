export type CurrentUser = { username: string };
export type AppStatus = { status: string; user: string };
export type Folder = { id: string; name: string };
export type Feed = { id: string; title: string; folder_id: string | null; site_url: string | null };
export type Entry = { id: string; feed_id: string; title: string; url: string | null; author: string | null; published_at: string; content_html: string; content_text: string | null; is_read: boolean; is_starred: boolean; reading_position: number };
export type EntryList = { items: Entry[]; next_cursor: string | null };
export type FreshRSSConnection = { id: string; base_url: string; username: string; sync_interval: number; last_sync_at: string | null; status: string; last_error: string | null };
export type AIProvider = { id: string; name: string; provider_type: string; base_url: string | null; enabled: boolean; health_status: string; timeout_seconds: number; concurrency_limit: number };
export type AIModel = { id: string; provider_id: string; model_key: string; display_name: string; capabilities_json: string[]; enabled: boolean };
export type AIFunction = { id: string; name: string; function_key: string; capability: string; prompt_version: number; enabled: boolean };
export type AIJob = { id: string; status: string; progress: number; estimated_cost: number; error_json: string | null; provider_id?: string | null; model_id?: string | null };
export type Notification = { id: string; title: string; body: string; is_read: boolean };
export type AIArtifact = { id: string; artifact_type: string; language: string | null; content_markdown: string | null; content_json: string | null };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    const detail = payload?.detail;
    throw new Error(typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  getCurrentUser: () => request<CurrentUser>("/api/auth/me"),
  login: (username: string, password: string) =>
    request<CurrentUser>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password })
    }),
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),
  getStatus: () => request<AppStatus>("/api/app/status")
  ,getFolders: () => request<Folder[]>("/api/folders")
  ,getFeeds: () => request<Feed[]>("/api/feeds")
  ,getEntries: (source?: { kind: "feed" | "folder"; id: string }) => request<EntryList>(`/api/entries${source ? `?${source.kind}_id=${source.id}` : ""}`)
  ,getEntry: (id: string) => request<Entry>(`/api/entries/${id}`)
  ,patchState: (id: string, body: Partial<Pick<Entry, "is_read" | "is_starred">>) => request<Entry>(`/api/entries/${id}/state`, { method: "PATCH", body: JSON.stringify(body) })
  ,savePosition: (id: string, scroll_ratio: number) => request<Entry>(`/api/entries/${id}/reading-position`, { method: "PATCH", body: JSON.stringify({ scroll_ratio }) })
  ,getFreshRSSStatus: () => request<FreshRSSConnection[]>("/api/freshrss/status")
  ,testFreshRSS: (body: { base_url: string; username: string; api_password: string; sync_interval: number }) => request<{ status: string; subscription_count?: number }>("/api/freshrss/test", { method: "POST", body: JSON.stringify(body) })
  ,createFreshRSS: (body: { base_url: string; username: string; api_password: string; sync_interval: number }) => request<FreshRSSConnection>("/api/freshrss/connections", { method: "POST", body: JSON.stringify(body) })
  ,syncFreshRSS: (connectionId?: string) => request<unknown[]>(`/api/freshrss/sync${connectionId ? `?connection_id=${connectionId}` : ""}`, { method: "POST" })
  ,importOpml: (content: string) => request<{ folders: number; feeds: number }>("/api/opml/import", { method: "POST", headers: { "Content-Type": "application/xml" }, body: content })
  ,exportOpml: () => fetch("/api/opml/export", { credentials: "include" }).then(async (response) => { if (!response.ok) throw new Error("OPML export failed"); return response.text(); })
  ,getAISettings: () => request<Record<string, boolean | number>>("/api/settings/ai")
  ,saveAISettings: (body: Record<string, boolean | number>) => request<Record<string, boolean | number>>("/api/settings/ai", { method: "PUT", body: JSON.stringify(body) })
  ,getProviders: () => request<AIProvider[]>("/api/ai/providers")
  ,createProvider: (body: { name: string; provider_type: string; base_url?: string; api_key?: string; enabled?: boolean; concurrency_limit?: number }) => request<AIProvider>("/api/ai/providers", { method: "POST", body: JSON.stringify(body) })
  ,testProvider: (id: string) => request<AIProvider>(`/api/ai/providers/${id}/test`, { method: "POST" })
  ,getModels: () => request<AIModel[]>("/api/ai/models")
  ,createModel: (body: { provider_id: string; model_key: string; display_name: string; capabilities_json: string[]; cost_config_json?: Record<string, number>; enabled?: boolean }) => request<{ id: string }>("/api/ai/models", { method: "POST", body: JSON.stringify(body) })
  ,getAIFunctions: () => request<AIFunction[]>("/api/ai/functions")
  ,getAIJobs: () => request<AIJob[]>("/api/ai/jobs")
  ,getNotifications: () => request<Notification[]>("/api/notifications")
  ,getWorkflows: () => request<{ id: string; name: string; enabled: boolean; schedule_config_json: Record<string, unknown> }[]>("/api/workflows")
  ,summarizeEntry: (id: string) => request<{ job_id: string }>(`/api/entries/${id}/summarize`, { method: "POST" })
  ,translateEntry: (id: string) => request<{ job_id: string }>(`/api/entries/${id}/translate`, { method: "POST" })
  ,getArtifacts: (id: string) => request<AIArtifact[]>(`/api/entries/${id}/artifacts`)
  ,getAIJob: (id: string) => request<AIJob>(`/api/ai/jobs/${id}`)
  ,getJobArtifacts: (id: string) => request<AIArtifact[]>(`/api/ai/jobs/${id}/artifacts`)
  ,digest: (body: { entry_ids?: string[]; feed_id?: string; folder_id?: string; limit?: number; workflow_name?: string }) => request<{ job_id: string; article_count?: number }>("/api/ai/digests", { method: "POST", body: JSON.stringify(body) })
};
