export type CurrentUser = { username: string };
export type AppStatus = { status: string; user: string };
export type Folder = { id: string; name: string };
export type Feed = { id: string; title: string; folder_id: string | null; site_url: string | null };
export type Entry = { id: string; feed_id: string; title: string; url: string | null; author: string | null; published_at: string; content_html: string; content_text: string | null; is_read: boolean; is_starred: boolean; reading_position: number };
export type EntryList = { items: Entry[]; next_cursor: string | null };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Request failed (${response.status})`);
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
};
