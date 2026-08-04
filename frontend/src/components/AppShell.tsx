import type { AppStatus, CurrentUser } from "../api/client";

type Props = {
  user: CurrentUser;
  status: AppStatus | null;
  onLogout: () => Promise<void>;
};

export function AppShell({ user, status, onLogout }: Props) {
  return (
    <header className="bg-slate-950 text-slate-100">
      <header className="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <div><span className="font-semibold">RSS-AI</span><span className="ml-3 text-sm text-slate-400">Phase 2</span></div>
        <div className="flex items-center gap-4 text-sm"><span>{user.username}</span><button className="text-cyan-400" onClick={() => void onLogout()}>退出登录</button></div>
      </header>
      <div className="flex items-center justify-between border-b border-slate-800 px-6 py-2 text-xs text-slate-400"><span>三栏阅读器</span><span>{status ? `API: ${status.status}` : "正在检查 API…"}</span></div>
    </header>
  );
}
