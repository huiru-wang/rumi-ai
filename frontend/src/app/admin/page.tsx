"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  BarChart3,
  Check,
  Clipboard,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Presentation,
  RefreshCw,
  Users,
  Volume2,
} from "lucide-react";

import { ThemeToggle } from "@/components/theme-toggle";
import { GithubLink } from "@/components/github-link";
import {
  buildTrendPolyline,
  readAdminToken,
  writeAdminToken,
} from "@/components/admin/admin-utils";
import {
  createAdminInvite,
  getAdminAccessMode,
  getAdminDashboard,
  listAdminInvites,
  listAdminUsers,
  loginAdmin,
  updateAdminAccessMode,
  updateAdminInvite,
  type AdminDashboard,
  type AdminInvite,
  type AdminTrendPoint,
  type AdminUserSummary,
} from "@/lib/api";

type AdminTab = "dashboard" | "users" | "invites";
type TrendKey = keyof Pick<
  AdminTrendPoint,
  "active_users" | "human_messages" | "documents" | "completed_ppts" | "completed_narrations"
>;

const tabs: Array<{ id: AdminTab; label: string; icon: typeof LayoutDashboard }> = [
  { id: "dashboard", label: "看板", icon: LayoutDashboard },
  { id: "users", label: "用户", icon: Users },
  { id: "invites", label: "邀请码", icon: KeyRound },
];

const trendOptions: Array<{ id: TrendKey; label: string }> = [
  { id: "active_users", label: "活跃用户" },
  { id: "human_messages", label: "用户提问" },
  { id: "documents", label: "上传文档" },
  { id: "completed_ppts", label: "完成 PPT" },
  { id: "completed_narrations", label: "完成口播稿" },
];

function formatTime(value: string | null): string {
  if (!value) return "暂无";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export default function AdminPage() {
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [tab, setTab] = useState<AdminTab>("dashboard");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setToken(readAdminToken(window.sessionStorage));
      setReady(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const handleAuthenticated = (value: string) => {
    writeAdminToken(window.sessionStorage, value);
    setToken(value);
  };

  const logout = () => {
    writeAdminToken(window.sessionStorage, null);
    setToken(null);
  };

  if (!ready) return <div className="min-h-screen bg-background" />;
  if (!token) return <AdminLogin onAuthenticated={handleAuthenticated} />;

  return (
    <div className="min-h-screen bg-background pb-24 text-foreground md:pb-8">
      <header className="sticky top-0 z-20 border-b border-border bg-background/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 md:px-6">
          <div>
            <p className="text-xs text-muted-foreground">RumiAI</p>
            <h1 className="text-lg font-semibold">管理后台</h1>
          </div>
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <GithubLink />
            <button
              onClick={logout}
              className="flex min-h-11 items-center gap-2 rounded-lg px-3 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <LogOut size={16} />
              <span className="hidden sm:inline">退出</span>
            </button>
          </div>
        </div>
        <nav className="mx-auto hidden max-w-6xl gap-2 px-6 pb-3 md:flex">
          {tabs.map((item) => (
            <TabButton key={item.id} item={item} active={tab === item.id} onClick={() => setTab(item.id)} />
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-5 md:px-6 md:py-7">
        {tab === "dashboard" && <DashboardPanel token={token} />}
        {tab === "users" && <UsersPanel token={token} onUnauthorized={logout} />}
        {tab === "invites" && <InvitesPanel token={token} onUnauthorized={logout} />}
      </main>

      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-3 border-t border-border bg-background/95 px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-2 backdrop-blur md:hidden">
        {tabs.map((item) => (
          <TabButton key={item.id} item={item} active={tab === item.id} onClick={() => setTab(item.id)} mobile />
        ))}
      </nav>
    </div>
  );
}

function TabButton({ item, active, onClick, mobile = false }: {
  item: (typeof tabs)[number]; active: boolean; onClick: () => void; mobile?: boolean;
}) {
  const Icon = item.icon;
  return (
    <button
      onClick={onClick}
      className={`${mobile ? "flex-col gap-1 py-2 text-xs" : "gap-2 px-4 py-2 text-sm"} flex min-h-11 items-center justify-center rounded-lg transition-colors ${active ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}
    >
      <Icon size={mobile ? 19 : 16} />
      {item.label}
    </button>
  );
}

function AdminLogin({ onAuthenticated }: { onAuthenticated: (token: string) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await loginAdmin(username.trim(), password);
      onAuthenticated(result.token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <form onSubmit={submit} className="w-full max-w-sm rounded-2xl border border-border bg-background p-6 shadow-2xl">
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-accent-foreground"><KeyRound size={19} /></div>
            <div><p className="text-xs text-muted-foreground">RumiAI</p><h1 className="font-semibold">管理后台</h1></div>
          </div>
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <GithubLink />
          </div>
        </div>
        <label className="mb-4 block text-sm">账号
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" className="mt-2 min-h-11 w-full rounded-lg border border-border bg-muted/40 px-3 outline-none focus:border-accent" />
        </label>
        <label className="block text-sm">密码
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" className="mt-2 min-h-11 w-full rounded-lg border border-border bg-muted/40 px-3 outline-none focus:border-accent" />
        </label>
        {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
        <button disabled={loading || !username || !password} className="mt-5 min-h-11 w-full rounded-lg bg-accent px-4 text-sm font-medium text-accent-foreground disabled:opacity-50">
          {loading ? "登录中..." : "登录"}
        </button>
      </form>
    </div>
  );
}

function DashboardPanel({ token }: { token: string }) {
  const [days, setDays] = useState<7 | 30>(7);
  const [data, setData] = useState<AdminDashboard | null>(null);
  const [error, setError] = useState("");
  const [trendKey, setTrendKey] = useState<TrendKey>("active_users");
  const load = useCallback(async () => {
    setError("");
    try { setData(await getAdminDashboard(token, days)); }
    catch (err) { setError(err instanceof Error ? err.message : "看板加载失败"); }
  }, [days, token]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (!data && !error) return <Loading />;
  if (!data) return <ErrorState message={error} retry={load} />;
  const kpis = [
    ["总用户", data.kpis.total_users, Users],
    ["今日活跃", data.kpis.active_today, BarChart3],
    ["7 日活跃", data.kpis.active_7d, RefreshCw],
    ["核心转化率", `${data.kpis.core_conversion_rate}%`, Presentation],
    [`近 ${days} 天 PPT`, data.kpis.completed_ppts, Presentation],
    [`近 ${days} 天口播稿`, data.kpis.completed_narrations, Volume2],
  ] as const;
  return (
    <div className="space-y-6">
      <SectionTitle title="使用概览" action={<RangeSwitch days={days} setDays={setDays} />} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
        {kpis.map(([label, value, Icon]) => <MetricCard key={label} label={label} value={value} icon={Icon} />)}
      </div>
      <section className="rounded-2xl border border-border p-4 md:p-5">
        <h2 className="font-medium">使用趋势</h2>
        <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
          {trendOptions.map((option) => <button key={option.id} onClick={() => setTrendKey(option.id)} className={`min-h-10 shrink-0 rounded-full px-3 text-xs ${trendKey === option.id ? "bg-accent text-accent-foreground" : "bg-muted text-muted-foreground"}`}>{option.label}</button>)}
        </div>
        <TrendChart data={data.trends} metric={trendKey} />
      </section>
    </div>
  );
}

function TrendChart({ data, metric }: { data: AdminTrendPoint[]; metric: TrendKey }) {
  const values = data.map((item) => item[metric]);
  const max = Math.max(...values, 0);
  return <div className="mt-5"><div className="h-44 w-full"><svg viewBox="0 0 600 160" className="h-full w-full overflow-visible" role="img" aria-label="使用趋势图"><line x1="0" y1="145" x2="600" y2="145" stroke="var(--border)" /><polyline points={buildTrendPolyline(values, 600, 135)} transform="translate(0 10)" fill="none" stroke="var(--accent)" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" /></svg></div><div className="flex justify-between text-[11px] text-muted-foreground"><span>{data[0]?.date.slice(5)}</span><span>峰值 {max}</span><span>{data.at(-1)?.date.slice(5)}</span></div></div>;
}

function UsersPanel({ token, onUnauthorized }: { token: string; onUnauthorized: () => void }) {
  const [users, setUsers] = useState<AdminUserSummary[]>([]);
  const [keyword, setKeyword] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try { const result = await listAdminUsers(token, { page, keyword: search }); setUsers(result.items); setTotal(result.total); setError(""); }
    catch (err) { const message = err instanceof Error ? err.message : "用户加载失败"; setError(message); if (message.includes("登录")) onUnauthorized(); }
  }, [onUnauthorized, page, search, token]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  const submit = (event: FormEvent) => { event.preventDefault(); setPage(1); setSearch(keyword.trim()); };
  return <div className="space-y-4"><SectionTitle title="用户使用情况" subtitle={`共 ${total} 位用户`} /><form onSubmit={submit} className="flex gap-2"><input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="搜索昵称或用户 ID" className="min-h-11 min-w-0 flex-1 rounded-lg border border-border bg-muted/40 px-3 text-sm outline-none focus:border-accent" /><button className="min-h-11 rounded-lg bg-accent px-4 text-sm text-accent-foreground">搜索</button></form>{error && <ErrorState message={error} retry={load} />}
    <div className="grid gap-3 lg:grid-cols-2">{users.map((user) => <article key={user.user_id} className="rounded-xl border border-border p-4"><div className="flex items-start justify-between gap-3"><div><div className="flex items-center gap-2"><h3 className="font-medium">{user.nickname}</h3><span className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">{user.source === "open" ? "开放访问" : "邀请码"}</span></div><p className="mt-1 break-all text-xs text-muted-foreground">{user.user_id}</p></div><span className={`shrink-0 rounded-full px-2 py-1 text-xs ${user.enabled ? "bg-emerald-500/10 text-emerald-500" : "bg-red-500/10 text-red-400"}`}>{user.enabled ? "可用" : "停用"}</span></div><p className="mt-3 text-xs text-muted-foreground">最近活跃：{formatTime(user.last_active_at)}</p><div className="mt-4 grid grid-cols-3 gap-2 text-center">{[["工作区", user.workspace_count], ["文档", user.document_count], ["提问", user.message_count], ["PPT", user.ppt_count], ["口播稿", user.narration_count], ["分享", user.share_count]].map(([label, value]) => <div key={label} className="rounded-lg bg-muted p-2"><p className="font-medium">{value}</p><p className="text-[11px] text-muted-foreground">{label}</p></div>)}</div></article>)}</div><Pagination page={page} total={total} setPage={setPage} /></div>;
}

function InvitesPanel({ token, onUnauthorized }: { token: string; onUnauthorized: () => void }) {
  const [items, setItems] = useState<AdminInvite[]>([]);
  const [nickname, setNickname] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [generatedCode, setGeneratedCode] = useState("");
  const [copied, setCopied] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [inviteRequired, setInviteRequired] = useState<boolean | null>(null);
  const [modeSaving, setModeSaving] = useState(false);
  const load = useCallback(async () => { try { const [result, mode] = await Promise.all([listAdminInvites(token, page), getAdminAccessMode(token)]); setItems(result.items); setTotal(result.total); setInviteRequired(mode.invite_required); setError(""); } catch (err) { const message = err instanceof Error ? err.message : "邀请码加载失败"; setError(message); if (message.includes("登录")) onUnauthorized(); } }, [onUnauthorized, page, token]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  const create = async (event: FormEvent) => { event.preventDefault(); setSubmitting(true); setError(""); try { const result = await createAdminInvite(token, nickname.trim(), expiresAt ? new Date(expiresAt).toISOString() : null); setGeneratedCode(result.code); setNickname(""); setExpiresAt(""); setPage(1); await load(); } catch (err) { setError(err instanceof Error ? err.message : "生成失败"); } finally { setSubmitting(false); } };
  const toggle = async (invite: AdminInvite) => { try { await updateAdminInvite(token, invite.id, !invite.enabled); await load(); } catch (err) { setError(err instanceof Error ? err.message : "操作失败"); } };
  const toggleAccessMode = async () => { if (inviteRequired === null) return; const nextRequired = !inviteRequired; if (!nextRequired && !window.confirm("关闭后，任何访客都可以直接进入并使用全部功能。确认关闭邀请码模式吗？")) return; setModeSaving(true); setError(""); try { const mode = await updateAdminAccessMode(token, nextRequired); setInviteRequired(mode.invite_required); } catch (err) { setError(err instanceof Error ? err.message : "访问模式更新失败"); } finally { setModeSaving(false); } };
  const copy = async () => { await navigator.clipboard.writeText(generatedCode); setCopied(true); window.setTimeout(() => setCopied(false), 1500); };
  return <div className="space-y-5"><SectionTitle title="邀请码管理" subtitle={`共生成 ${total} 个邀请码`} /><section className="flex items-center justify-between gap-4 rounded-2xl border border-border p-4"><div><h3 className="text-sm font-medium">邀请码模式</h3><p className="mt-1 text-xs leading-5 text-muted-foreground">{inviteRequired === false ? "已关闭，访客可直接进入并使用全部功能。" : "已开启，用户必须输入有效邀请码。"}</p></div><button type="button" role="switch" aria-checked={inviteRequired === true} disabled={inviteRequired === null || modeSaving} onClick={toggleAccessMode} className={`relative h-7 w-12 shrink-0 rounded-full transition-colors disabled:opacity-50 ${inviteRequired === true ? "bg-emerald-500" : "bg-muted"}`}><span className={`absolute top-1 h-5 w-5 rounded-full bg-white shadow transition-transform ${inviteRequired === true ? "translate-x-6" : "translate-x-1"}`} /></button></section><form onSubmit={create} className="grid gap-3 rounded-2xl border border-border p-4 md:grid-cols-[1fr_220px_auto] md:items-end"><label className="text-sm">用户昵称<input required value={nickname} onChange={(e) => setNickname(e.target.value)} placeholder="例如：张老师" className="mt-2 min-h-11 w-full rounded-lg border border-border bg-muted/40 px-3 outline-none focus:border-accent" /></label><label className="text-sm">过期时间（可选）<input type="datetime-local" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} className="mt-2 min-h-11 w-full rounded-lg border border-border bg-muted/40 px-3 outline-none focus:border-accent" /></label><button disabled={submitting || !nickname.trim()} className="min-h-11 rounded-lg bg-accent px-4 text-sm font-medium text-accent-foreground disabled:opacity-50">{submitting ? "生成中..." : "生成邀请码"}</button></form>
    {generatedCode && <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4"><div className="flex items-center gap-2 text-sm text-emerald-500"><Check size={16} />邀请码已生成，可立即使用</div><div className="mt-3 flex flex-col gap-2 sm:flex-row"><code className="min-w-0 flex-1 overflow-x-auto rounded-lg bg-background px-3 py-3 text-base font-semibold">{generatedCode}</code><button onClick={copy} className="flex min-h-11 items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 text-sm"><Clipboard size={16} />{copied ? "已复制" : "复制"}</button></div><p className="mt-2 text-xs text-muted-foreground">完整邀请码仅在此处显示，请复制后发送给用户。</p></div>}
    {error && <ErrorState message={error} retry={load} />}<div className="grid gap-3 lg:grid-cols-2">{items.map((invite) => <article key={invite.id} className="rounded-xl border border-border p-4"><div className="flex items-start justify-between gap-3"><div><h3 className="font-medium">{invite.nickname}</h3><code className="mt-1 block text-xs text-muted-foreground">{invite.code_masked}</code></div><button onClick={() => toggle(invite)} className={`min-h-10 shrink-0 rounded-lg px-3 text-xs ${invite.enabled ? "bg-red-500/10 text-red-400" : "bg-emerald-500/10 text-emerald-500"}`}>{invite.enabled ? "停用" : "启用"}</button></div><div className="mt-4 grid grid-cols-2 gap-2 text-xs text-muted-foreground"><span>状态：{invite.claimed_at ? "已激活" : "未使用"}</span><span>使用次数：{invite.claim_count}</span><span>生成：{formatTime(invite.created_at)}</span><span>最近使用：{formatTime(invite.last_claimed_at)}</span></div></article>)}</div><Pagination page={page} total={total} setPage={setPage} /></div>;
}

function MetricCard({ label, value, icon: Icon }: { label: string; value: string | number; icon: typeof Users }) { return <div className="rounded-xl border border-border p-4"><div className="flex items-center justify-between text-muted-foreground"><span className="text-xs">{label}</span><Icon size={16} /></div><p className="mt-3 text-2xl font-semibold md:text-3xl">{value}</p></div>; }
function SectionTitle({ title, subtitle, action }: { title: string; subtitle?: string; action?: React.ReactNode }) { return <div className="flex items-end justify-between gap-3"><div><h2 className="text-lg font-semibold">{title}</h2>{subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}</div>{action}</div>; }
function RangeSwitch({ days, setDays }: { days: 7 | 30; setDays: (days: 7 | 30) => void }) { return <div className="flex rounded-lg bg-muted p-1">{([7, 30] as const).map((value) => <button key={value} onClick={() => setDays(value)} className={`min-h-9 rounded-md px-3 text-xs ${days === value ? "bg-background text-foreground shadow-sm" : "text-muted-foreground"}`}>{value} 天</button>)}</div>; }
function Pagination({ page, total, setPage }: { page: number; total: number; setPage: (page: number) => void }) { const pages = Math.ceil(total / 20); if (pages <= 1) return null; return <div className="flex items-center justify-center gap-3 pt-2"><button disabled={page <= 1} onClick={() => setPage(page - 1)} className="min-h-10 rounded-lg border border-border px-4 text-sm disabled:opacity-40">上一页</button><span className="text-sm text-muted-foreground">{page} / {pages}</span><button disabled={page >= pages} onClick={() => setPage(page + 1)} className="min-h-10 rounded-lg border border-border px-4 text-sm disabled:opacity-40">下一页</button></div>; }
function Loading() { return <div className="flex min-h-60 items-center justify-center text-sm text-muted-foreground"><RefreshCw className="mr-2 animate-spin" size={16} />加载中...</div>; }
function ErrorState({ message, retry }: { message: string; retry: () => void | Promise<void> }) { return <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400"><p>{message}</p><button onClick={() => void retry()} className="mt-3 min-h-10 rounded-lg border border-red-500/30 px-3">重新加载</button></div>; }
