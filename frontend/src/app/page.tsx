"use client";

import { useEffect, useState, useCallback, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { KeyRound, Plus } from "lucide-react";
import { clearInviteUser, getUserId, getUserNickname, setInviteUser } from "@/lib/user";
import {
  ApiError,
  claimInvite,
  listWorkspaces,
  createWorkspace,
  deleteWorkspace,
  type Workspace,
} from "@/lib/api";
import { WorkspaceCard } from "@/components/workspace/workspace-card";
import { CreateDialog } from "@/components/workspace/create-dialog";
import { ThemeToggle } from "@/components/theme-toggle";

export default function Home() {
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [userId, setUserId] = useState<string | null>(null);
  const [nickname, setNickname] = useState<string | null>(null);
  const [inviteCode, setInviteCode] = useState("");
  const [inviteError, setInviteError] = useState("");
  const [claiming, setClaiming] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<Workspace | null>(null);

  const fetchWorkspaces = useCallback(async () => {
    const currentUserId = getUserId();
    if (!currentUserId) {
      setUserId(null);
      setNickname(null);
      setWorkspaces([]);
      setLoading(false);
      return;
    }
    setUserId(currentUserId);
    setNickname(getUserNickname());
    try {
      const data = await listWorkspaces(currentUserId);
      setWorkspaces(data);
    } catch (err) {
      if (err instanceof ApiError && err.code === 70001) {
        clearInviteUser();
        setUserId(null);
        setNickname(null);
        setWorkspaces([]);
        setInviteError("邀请码已失效，请重新输入。");
      }
      console.error("Failed to load workspaces");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWorkspaces();
  }, [fetchWorkspaces]);

  const handleCreate = async (name: string) => {
    const currentUserId = getUserId();
    if (!currentUserId) {
      throw new Error("请先输入邀请码");
    }
    try {
      await createWorkspace(currentUserId, name);
      await fetchWorkspaces();
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === 70001) {
          clearInviteUser();
          setUserId(null);
          setNickname(null);
          setInviteError("邀请码已失效，请重新输入。");
        }
        throw new Error(err.message);
      }
      throw err;
    }
  };

  const handleClaimInvite = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const code = inviteCode.trim();
    if (!code) {
      setInviteError("请输入邀请码");
      return;
    }
    setClaiming(true);
    setInviteError("");
    try {
      const data = await claimInvite(code);
      setInviteUser(data.user_id, data.nickname);
      setInviteCode("");
      setUserId(data.user_id);
      setNickname(data.nickname);
      setLoading(true);
      await fetchWorkspaces();
    } catch (err) {
      if (err instanceof ApiError) {
        setInviteError(err.message);
      } else {
        setInviteError("邀请码校验失败");
      }
    } finally {
      setClaiming(false);
      setLoading(false);
    }
  };

  const handleDelete = (id: string) => {
    const ws = workspaces.find((w) => w.id === id) ?? null;
    setDeleteTarget(ws);
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    const id = deleteTarget.id;
    setDeleteTarget(null);
    await deleteWorkspace(id);
    fetchWorkspaces();
  };

  const handleOpen = (id: string) => {
    router.push(`/workspace/${id}`);
  };

  return (
    <div className="flex flex-1 flex-col">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-border px-8 py-4">
        <div className="flex items-center gap-2.5">
          <svg viewBox="0 0 120 120" className="h-7 w-7 text-logo-primary" aria-hidden="true">
            <path d="M60,22 C82,22 100,40 100,62 C100,84 82,102 60,102 C45,102 32,94 25,82" stroke="currentColor" strokeWidth="5" fill="none" strokeLinecap="round"/>
            <path d="M60,42 C71,42 80,51 80,62 C80,73 71,82 60,82 C52,82 46,78 43,72" stroke="#C75B3A" strokeWidth="4" fill="none" strokeLinecap="round"/>
            <circle cx="60" cy="62" r="4" fill="currentColor"/>
          </svg>
          <h1 className="text-lg font-semibold text-foreground">RumiAI</h1>
          {nickname && (
            <span className="rounded-md border border-border px-2 py-1 text-xs text-muted-foreground">
              {nickname}
            </span>
          )}
        </div>
        <ThemeToggle />
      </header>

      {/* Content */}
      <main className="flex-1 px-8 py-8">
        {!userId ? (
          <div className="mx-auto flex min-h-[60vh] max-w-sm items-center">
            <form
              onSubmit={handleClaimInvite}
              className="w-full rounded-2xl border border-border bg-background p-6 shadow-2xl"
            >
              <div className="mb-5 flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent text-accent-foreground">
                  <KeyRound size={18} />
                </div>
                <h2 className="text-base font-semibold text-foreground">输入邀请码</h2>
              </div>
              <input
                value={inviteCode}
                onChange={(event) => setInviteCode(event.target.value)}
                className="w-full rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-accent"
                placeholder="邀请码"
                autoFocus
              />
              {inviteError && (
                <p className="mt-2 text-xs text-red-400">{inviteError}</p>
              )}
              <button
                type="submit"
                disabled={claiming}
                className="mt-4 flex w-full items-center justify-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-foreground transition-colors hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <KeyRound size={15} />
                {claiming ? "校验中..." : "进入"}
              </button>
            </form>
          </div>
        ) : (
          <div className="mx-auto max-w-4xl">
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-foreground">工作区</h2>
              <button
                onClick={() => setDialogOpen(true)}
                className="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-foreground transition-colors hover:bg-accent/90"
              >
                <Plus size={15} />
                新建工作区
              </button>
            </div>

            {loading ? (
              <div className="py-20 text-center text-muted-foreground">
                加载中...
              </div>
            ) : workspaces.length === 0 ? (
              <div className="flex flex-col items-center gap-4 py-20 text-muted-foreground">
                <svg viewBox="0 0 120 120" className="h-12 w-12 text-logo-primary" aria-hidden="true">
                  <path d="M60,22 C82,22 100,40 100,62 C100,84 82,102 60,102 C45,102 32,94 25,82" stroke="currentColor" strokeWidth="4" fill="none" strokeLinecap="round"/>
                  <path d="M60,42 C71,42 80,51 80,62 C80,73 71,82 60,82 C52,82 46,78 43,72" stroke="#C75B3A" strokeWidth="3" fill="none" strokeLinecap="round"/>
                  <circle cx="60" cy="62" r="4" fill="currentColor"/>
                </svg>
                <p>还没有工作区，创建一个开始吧</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {workspaces.map((workspace) => (
                  <WorkspaceCard
                    key={workspace.id}
                    workspace={workspace}
                    onOpen={handleOpen}
                    onDelete={handleDelete}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      {userId && (
        <CreateDialog
          open={dialogOpen}
          onClose={() => setDialogOpen(false)}
          onCreate={handleCreate}
        />
      )}

      {/* Delete workspace confirmation dialog */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="mx-4 w-full max-w-sm rounded-2xl border border-border bg-background p-5 shadow-2xl">
            <h3 className="text-sm font-semibold text-foreground">
              删除工作区「{deleteTarget.name}」？
            </h3>
            <div className="mt-2 space-y-1.5 text-xs text-muted-foreground">
              <p>
                工作区下的知识库和产出文件将被永久删除，
                <span className="text-red-400">此操作不可撤销</span>。
              </p>
              <p className="text-muted-foreground/80">已保存的 PPT 风格模版不受影响。</p>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setDeleteTarget(null)}
                className="rounded-lg px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground"
              >
                取消
              </button>
              <button
                onClick={confirmDelete}
                className="rounded-lg bg-red-500/20 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/30"
              >
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
