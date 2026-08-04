import type { AppStatus, CurrentUser } from "../api/client";

type Props = {
  user: CurrentUser;
  status: AppStatus | null;
  onLogout: () => Promise<void>;
};

const upcomingPages = ["Reader", "AI Functions", "AI Engines", "Workflows", "Jobs", "Settings"];

export function AppShell({ user, status, onLogout }: Props) {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <header className="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <div><span className="font-semibold">RSS-AI</span><span className="ml-3 text-sm text-slate-400">Phase 2</span></div>
        <div className="flex items-center gap-4 text-sm"><span>{user.username}</span><button className="text-cyan-400" onClick={() => void onLogout()}>退出登录</button></div>
      </header>
      <section className="mx-auto max-w-5xl p-6">
        <p className="text-sm font-medium uppercase tracking-[0.18em] text-cyan-400">Reader ready</p>
        <h1 className="mt-2 text-3xl font-semibold">RSS-AI 阅读器</h1>
        <p className="mt-3 max-w-2xl text-slate-400">连接 FreshRSS 并同步文章后，可使用键盘完成阅读。</p>
        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          <article className="rounded-xl border border-slate-800 bg-slate-900 p-5"><h2 className="font-medium">服务状态</h2><p className="mt-2 text-sm text-slate-400">{status ? `API: ${status.status}` : "正在检查 API…"}</p></article>
          <article className="rounded-xl border border-slate-800 bg-slate-900 p-5"><h2 className="font-medium">后续模块</h2><ul className="mt-2 grid grid-cols-2 gap-2 text-sm text-slate-400">{upcomingPages.map((page) => <li key={page}>{page}</li>)}</ul></article>
        </div>
      </section>
    </main>
  );
}
