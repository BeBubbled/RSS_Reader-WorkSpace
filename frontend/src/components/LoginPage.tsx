import { FormEvent, useState } from "react";

type Props = {
  onSubmit: (username: string, password: string) => Promise<void>;
};

export function LoginPage({ onSubmit }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(username, password);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "登录失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-slate-950 p-6 text-slate-100">
      <form className="w-full max-w-sm space-y-5 rounded-2xl border border-slate-700 bg-slate-900 p-8 shadow-2xl" onSubmit={submit}>
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.22em] text-cyan-400">RSS-AI</p>
          <h1 className="mt-2 text-2xl font-semibold">登录阅读器</h1>
          <p className="mt-2 text-sm text-slate-400">使用管理员账号继续。</p>
        </div>
        <label className="block text-sm">
          用户名
          <input aria-label="用户名" autoComplete="username" className="mt-1 w-full rounded-md border border-slate-600 bg-slate-800 px-3 py-2" value={username} onChange={(event) => setUsername(event.target.value)} required />
        </label>
        <label className="block text-sm">
          密码
          <input aria-label="密码" autoComplete="current-password" type="password" className="mt-1 w-full rounded-md border border-slate-600 bg-slate-800 px-3 py-2" value={password} onChange={(event) => setPassword(event.target.value)} required />
        </label>
        {error && <p role="alert" className="text-sm text-rose-400">{error}</p>}
        <button className="w-full rounded-md bg-cyan-500 px-3 py-2 font-medium text-slate-950 disabled:opacity-60" disabled={submitting} type="submit">
          {submitting ? "正在登录…" : "登录"}
        </button>
      </form>
    </main>
  );
}
