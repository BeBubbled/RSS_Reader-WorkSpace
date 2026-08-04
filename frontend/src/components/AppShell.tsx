import type { AppStatus, CurrentUser } from "../api/client";

type Props = { user: CurrentUser; status: AppStatus | null; onLogout: () => Promise<void> };

export function AppShell({ user, status, onLogout }: Props) {
  return <header className="app-toolbar">
    <div className="brand-mark" aria-label="RSS-AI">R</div><div className="toolbar-title">阅读</div><div className="toolbar-spacer" />
    <span className={`service-indicator ${status ? "online" : ""}`} title={status ? "服务已连接" : "正在连接服务"} />
    <span className="account-name">{user.username}</span><button className="text-button" onClick={() => void onLogout()}>退出</button>
  </header>;
}
