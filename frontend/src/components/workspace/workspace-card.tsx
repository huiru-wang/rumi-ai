"use client";

import { Loader2, Trash2, MessageSquare } from "lucide-react";
import type { Workspace } from "@/lib/api";

interface WorkspaceCardProps {
  workspace: Workspace;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
  deleting?: boolean;
}

export function WorkspaceCard({
  workspace,
  onOpen,
  onDelete,
  deleting = false,
}: WorkspaceCardProps) {
  const createdDate = new Date(workspace.created_at).toLocaleDateString(
    "zh-CN",
    { month: "short", day: "numeric" }
  );

  return (
    <div
      className={`group relative flex flex-col gap-3 rounded-xl border border-border bg-muted/50 p-5 transition-all ${
        deleting
          ? "cursor-wait opacity-80"
          : "cursor-pointer hover:border-accent/40 hover:bg-muted"
      }`}
      onClick={() => {
        if (!deleting) onOpen(workspace.id);
      }}
      aria-busy={deleting}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/15 text-accent">
            {deleting ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <MessageSquare size={18} />
            )}
          </div>
          <h3 className="text-base font-medium text-foreground">
            {workspace.name}
          </h3>
        </div>
        <button
          onClick={(event) => {
            event.stopPropagation();
            if (deleting) return;
            onDelete(workspace.id);
          }}
          disabled={deleting}
          className="rounded-md p-1.5 text-muted-foreground opacity-0 transition-all hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100 disabled:cursor-wait disabled:opacity-40"
          title={deleting ? "正在删除" : "删除工作区"}
        >
          <Trash2 size={15} />
        </button>
      </div>
      <p className="text-xs text-muted-foreground">
        {deleting ? "正在删除工作区..." : `创建于 ${createdDate}`}
      </p>
      {deleting && (
        <div className="absolute inset-0 rounded-xl bg-background/35" aria-hidden="true" />
      )}
    </div>
  );
}
