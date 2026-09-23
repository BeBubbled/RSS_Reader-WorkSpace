import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, Entry, type AIArtifact, type AIJob } from "../api/client";
import { FreshRSSSettings } from "./FreshRSSSettings";
import { AISettings } from "./AISettings";

type Pane = "sources" | "articles" | "reader";
type IconName = "chevron" | "star" | "more" | "search" | "inbox" | "feed";

function Icon({ name }: { name: IconName }) {
  const shapes: Record<IconName, ReactNode> = {
    chevron: <path d="m9 18 6-6-6-6" />, star: <path d="m12 3.8 2.55 5.16 5.7.83-4.13 4.02.98 5.68L12 16.78l-5.1 2.69.98-5.68-4.13-4.02 5.7-.83L12 3.8Z" />,
    more: <><circle cx="5" cy="12" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /></>, search: <><circle cx="11" cy="11" r="5.8" /><path d="m16 16 4 4" /></>,
    inbox: <><path d="M4 5.5h16v13H4z" /><path d="M4 12h4l1.7 2.4h4.6L16 12h4" /></>, feed: <><circle cx="6" cy="18" r="1.5" /><path d="M4.5 11.5a7.9 7.9 0 0 1 8 8M4.5 5a14.4 14.4 0 0 1 14.5 14.5" /></>
  };
  return <svg className="icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{shapes[name]}</svg>;
}
function articleDate(value: string) { const date = new Date(value); return Number.isNaN(date.valueOf()) ? "" : new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric" }).format(date); }

export function Reader() {
  const [pane, setPane] = useState<Pane>("articles"); const [source, setSource] = useState<{ kind: "feed" | "folder"; id: string }>(); const [selected, setSelected] = useState<string>();
  const reader = useRef<HTMLElement>(null); const scrollTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined); const queryClient = useQueryClient();
  const folders = useQuery({ queryKey: ["folders"], queryFn: api.getFolders }); const feeds = useQuery({ queryKey: ["feeds"], queryFn: api.getFeeds });
  const entries = useQuery({ queryKey: ["entries", source], queryFn: () => api.getEntries(source) }); const article = useQuery({ queryKey: ["entry", selected], queryFn: () => api.getEntry(selected!), enabled: !!selected });
  const [activeJob, setActiveJob] = useState<{ id: string; kind: "translate" | "summary" | "digest" } | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);
  const [digestResult, setDigestResult] = useState<{ content: string; jobId: string } | null>(null);
  const [multiSelect, setMultiSelect] = useState<Set<string>>(new Set());
  const autoHandled = useRef<Set<string>>(new Set());
  const artifacts = useQuery({ queryKey: ["artifacts", selected], queryFn: () => api.getArtifacts(selected!), enabled: !!selected });
  const aiSettings = useQuery({ queryKey: ["ai-settings"], queryFn: api.getAISettings });
  const activeJobState = useQuery({ queryKey: ["ai-job", activeJob?.id], queryFn: () => api.getAIJob(activeJob!.id), enabled: !!activeJob?.id, refetchInterval: (query) => (query.state.data?.status === "queued" || query.state.data?.status === "running" ? 1500 : false) });
  const sourceItems = [...(Array.isArray(folders.data) ? folders.data : []).map((x) => ({ kind: "folder" as const, id: x.id, label: x.name })), ...(Array.isArray(feeds.data) ? feeds.data : []).map((x) => ({ kind: "feed" as const, id: x.id, label: x.title }))];
  const entryItems = Array.isArray(entries.data?.items) ? entries.data.items : [];
  useEffect(() => { setSelected(entryItems[0]?.id); }, [source?.id, entryItems.map((x) => x.id).join(",")]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if ((event.target as HTMLElement)?.matches("input,textarea,select,[contenteditable=true]") || event.altKey || event.ctrlKey || event.metaKey) return;
      const panes: Pane[] = ["sources", "articles", "reader"];
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") { event.preventDefault(); setPane((current) => panes[Math.max(0, Math.min(2, panes.indexOf(current) + (event.key === "ArrowLeft" ? -1 : 1)))]); return; }
      if (pane === "reader" && reader.current && [" ", "PageDown", "PageUp", "Home", "End"].includes(event.key)) { event.preventDefault(); const el = reader.current; if (event.key === "Home") el.scrollTop = 0; else if (event.key === "End") el.scrollTop = el.scrollHeight; else el.scrollBy({ top: (event.key === "PageUp" || (event.key === " " && event.shiftKey) ? -1 : 1) * el.clientHeight, behavior: "smooth" }); return; }
      const list = pane === "sources" ? sourceItems : entryItems;
      if ((event.key === "ArrowDown" || event.key === "ArrowUp") && list.length) { event.preventDefault(); const current = pane === "sources" ? source?.id : selected; const next = list[(Math.max(0, list.findIndex((item) => item.id === current)) + (event.key === "ArrowDown" ? 1 : -1) + list.length) % list.length]; if (pane === "sources") setSource(next as typeof source); else setSelected(next.id); }
    }; window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey);
  }, [pane, sourceItems, entryItems, source, selected]);
  useEffect(() => { if (article.data && reader.current) reader.current.scrollTop = article.data.reading_position * (reader.current.scrollHeight - reader.current.clientHeight); }, [article.data?.id]);
  async function updateEntry(id: string, state: Partial<Pick<Entry, "is_read" | "is_starred">>) { await api.patchState(id, state); await queryClient.invalidateQueries({ queryKey: ["entries"] }); await queryClient.invalidateQueries({ queryKey: ["entry", id] }); }
  async function runAI(kind: "translate" | "summary") { if (!selected) return; setAiError(null); try { const { job_id } = kind === "translate" ? await api.translateEntry(selected) : await api.summarizeEntry(selected); setActiveJob({ id: job_id, kind }); } catch (error) { setAiError(error instanceof Error ? error.message : "AI 任务提交失败"); } }
  async function runDigest() { const ids = [...multiSelect]; if (!ids.length) return; setAiError(null); try { const { job_id } = await api.digest({ entry_ids: ids }); setActiveJob({ id: job_id, kind: "digest" }); setMultiSelect(new Set()); } catch (error) { setAiError(error instanceof Error ? error.message : "简报生成失败"); } }
  function toggleMulti(id: string) { setMultiSelect((prev) => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next; }); }
  useEffect(() => { const job = activeJobState.data; if (!job) return; if (job.status === "succeeded") { if (activeJob?.kind === "digest") { void api.getJobArtifacts(activeJob.id).then((items) => { const summary = items.find((a) => a.artifact_type.includes("summary")); if (summary?.content_markdown) setDigestResult({ content: summary.content_markdown, jobId: activeJob.id }); }).catch(() => {}); } else { void queryClient.invalidateQueries({ queryKey: ["artifacts", selected] }); } setActiveJob(null); } else if (job.status === "failed") { setActiveJob(null); setAiError(parseJobError(job)); } }, [activeJobState.data, activeJob, selected, queryClient]);
  useEffect(() => { if (!article.data || !aiSettings.data) return; const entryId = article.data.id; const existing = artifacts.data ?? []; const has = (type: string) => existing.some((a) => a.artifact_type === type); const trigger = (kind: "translate" | "summary") => { const key = `${entryId}:${kind}`; if (autoHandled.current.has(key)) return; autoHandled.current.add(key); (kind === "translate" ? api.translateEntry(entryId) : api.summarizeEntry(entryId)).then(({ job_id }) => setActiveJob({ id: job_id, kind })).catch(() => setAiError(null)); }; if (aiSettings.data.auto_translate && !has("single_article_translation")) trigger("translate"); if (aiSettings.data.auto_summary && !has("single_article_summary")) trigger("summary"); }, [article.data?.id, aiSettings.data, artifacts.data]);
  function onScroll() { const el = reader.current; if (!article.data || !el) return; clearTimeout(scrollTimer.current); const ratio = el.scrollHeight > el.clientHeight ? el.scrollTop / (el.scrollHeight - el.clientHeight) : 0; scrollTimer.current = setTimeout(() => void api.savePosition(article.data!.id, ratio), 350); }
  return <div className="reader-grid">
    <aside className={`sources-pane ${pane === "sources" ? "active" : ""}`}><div className="pane-toolbar"><span>资料库</span><button className="icon-button" aria-label="搜索"><Icon name="search" /></button></div>
      <button className={`source-row ${!source ? "selected" : ""}`} onClick={() => { setSource(undefined); setPane("articles"); }}><Icon name="inbox" /><span>全部文章</span><small>{entryItems.length || ""}</small></button>
      {folders.data?.length ? <p className="pane-label">文件夹</p> : null}{Array.isArray(folders.data) && folders.data.map((folder) => <button key={folder.id} className={`source-row ${source?.id === folder.id ? "selected" : ""}`} onClick={() => { setSource({ kind: "folder", id: folder.id }); setPane("articles"); }}><span className="folder-dot" /><span>{folder.name}</span></button>)}
      <p className="pane-label">订阅源</p>{Array.isArray(feeds.data) && feeds.data.map((feed) => <button key={feed.id} className={`source-row ${source?.id === feed.id ? "selected" : ""}`} onClick={() => { setSource({ kind: "feed", id: feed.id }); setPane("articles"); }}><Icon name="feed" /><span>{feed.title}</span></button>)}
      {!sourceItems.length && <div className="empty-source"><Icon name="feed" /><p>还没有订阅源</p><small>在“连接与同步”中添加 FreshRSS。</small></div>}<details className="settings-panel"><summary>连接与同步</summary><FreshRSSSettings /></details><details className="settings-panel ai-panel"><summary>AI 设置与任务</summary><AISettings /></details>
    </aside>
    <section className={`articles-pane ${pane === "articles" ? "active" : ""}`}><div className="pane-toolbar">{multiSelect.size > 0 ? <><div><strong>已选 {multiSelect.size} 篇</strong><small>生成一篇中文简报</small></div><button className="toolbar-action" onClick={() => void runDigest()}>生成简报</button><button className="toolbar-action" onClick={() => setMultiSelect(new Set())}>清除</button></> : <><div><strong>{source ? sourceItems.find((item) => item.id === source.id)?.label : "全部文章"}</strong><small>{entryItems.length} 篇</small></div><button className="icon-button" aria-label="更多选项"><Icon name="more" /></button></>}</div><div className="article-list">{entryItems.map((item) => <div key={item.id} className={`article-row-wrap ${selected === item.id ? "selected" : ""}`}><input type="checkbox" className="article-check" aria-label="选择文章" checked={multiSelect.has(item.id)} onChange={() => toggleMulti(item.id)} /><button className={`article-row ${item.is_read ? "read" : ""}`} onClick={() => { setSelected(item.id); setPane("reader"); if (!item.is_read) void updateEntry(item.id, { is_read: true }); }}><div className="article-row-meta"><span>{feeds.data?.find((feed) => feed.id === item.feed_id)?.title ?? "订阅"}</span><time>{articleDate(item.published_at)}</time></div><strong>{item.title}</strong><p>{item.content_text?.replace(/\s+/g, " ").slice(0, 120) || "打开文章以继续阅读。"}</p></button></div>)}{!entryItems.length && <div className="empty-list"><Icon name="inbox" /><h2>这里还没有文章</h2><p>同步 FreshRSS 后，新文章会出现在这里。</p></div>}</div></section>
    <article ref={reader} onScroll={onScroll} className={`reading-pane ${pane === "reader" ? "active" : ""}`}>{article.data ? <><ReaderArticle item={article.data} onToggleStar={() => void updateEntry(article.data!.id, { is_starred: !article.data!.is_starred })} onMarkUnread={() => void updateEntry(article.data!.id, { is_read: false })} /><AIReaderPanel artifacts={artifacts.data} job={activeJobState.data} error={aiError} onTranslate={() => void runAI("translate")} onSummarize={() => void runAI("summary")} />{digestResult && <div className="ai-reader-panel digest-panel"><div className="ai-reader-actions"><strong>简报</strong><button type="button" onClick={() => setDigestResult(null)}>关闭</button></div><section className="ai-block"><div className="ai-block-content">{digestResult.content}</div></section></div>}</> : <div className="empty-reader"><Icon name="inbox" /><h1>选择一篇文章</h1><p>选择文章后，可在下方使用翻译与 AI 总结。</p></div>}</article>
  </div>;
}
function ReaderArticle({ item, onToggleStar, onMarkUnread }: { item: Entry; onToggleStar: () => void; onMarkUnread: () => void }) { return <><div className="reader-toolbar"><button className={`icon-button ${item.is_starred ? "starred" : ""}`} aria-label="收藏" onClick={onToggleStar}><Icon name="star" /></button><button className="reader-source" onClick={onMarkUnread}>{item.is_read ? "标为未读" : "未读"}</button><span /><button className="icon-button" aria-label="更多文章选项"><Icon name="more" /></button></div><div className="reading-content"><p className="eyebrow">{item.author || "RSS 阅读"} <span>·</span> {articleDate(item.published_at)}</p><h1>{item.title}</h1>{item.url && <a className="original-link" href={item.url} target="_blank" rel="noreferrer">在原网站打开 <Icon name="chevron" /></a>}<div className="article-body" dangerouslySetInnerHTML={{ __html: item.content_html }} /></div></> }

function parseJobError(job: AIJob): string { if (!job.error_json) return "AI 任务失败"; try { const parsed = JSON.parse(job.error_json) as { message?: string }; return parsed.message ?? "AI 任务失败"; } catch { return job.error_json; } }

function AIReaderPanel({ artifacts, job, error, onTranslate, onSummarize }: { artifacts: AIArtifact[] | undefined; job: AIJob | undefined; error: string | null; onTranslate: () => void; onSummarize: () => void; }) {
  const translation = artifacts?.find((a) => a.artifact_type === "single_article_translation");
  const summary = artifacts?.find((a) => a.artifact_type === "single_article_summary");
  const busy = job?.status === "queued" || job?.status === "running";
  return <div className="ai-reader-panel"><div className="ai-reader-actions"><button type="button" onClick={onTranslate} disabled={busy}>{translation ? "重新翻译" : "翻译"}</button><button type="button" onClick={onSummarize} disabled={busy}>{summary ? "重新总结" : "AI 总结"}</button>{busy && <span className="ai-status" role="status">处理中 {job?.progress ?? 0}%…</span>}</div>{error && <p className="ai-error" role="alert">{error}</p>}{translation && <section className="ai-block"><h3>翻译</h3><div className="ai-block-content">{translation.content_markdown}</div></section>}{summary && <section className="ai-block"><h3>AI 总结</h3><div className="ai-block-content">{summary.content_markdown}</div></section>}{!translation && !summary && !busy && !error && <p className="ai-hint">点击“翻译”或“AI 总结”处理当前文章。</p>}</div>;
}
