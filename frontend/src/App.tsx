import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "./api/client";
import { AppShell } from "./components/AppShell";
import { LoginPage } from "./components/LoginPage";
import { useAuthStore } from "./stores/auth";
import { Reader } from "./components/Reader";

export default function App() {
  const { user, isLoading, setUser, setLoading } = useAuthStore();
  const status = useQuery({ queryKey: ["app-status"], queryFn: api.getStatus, enabled: Boolean(user) });

  useEffect(() => {
    let active = true;
    api.getCurrentUser()
      .then((currentUser) => active && setUser(currentUser))
      .catch(() => active && setUser(null))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [setLoading, setUser]);

  async function login(username: string, password: string) {
    setUser(await api.login(username, password));
  }

  async function logout() {
    await api.logout();
    setUser(null);
  }

  if (isLoading) {
    return <main className="grid min-h-screen place-items-center bg-slate-950 text-slate-300">正在恢复会话…</main>;
  }
  if (!user) return <LoginPage onSubmit={login} />;
  return <><AppShell user={user} status={status.data ?? null} onLogout={logout} /><Reader /></>;
}
