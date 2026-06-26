"use client";

import { Trash2, MessageSquare } from "lucide-react";
import type { Workspace } from "@/lib/api";

interface WorkspaceCardProps {
  workspace: Workspace;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
}

export function WorkspaceCard({
  workspace,
  onOpen,
  onDelete,
}: WorkspaceCardProps) {
  const createdDate = new Date(workspace.created_at).toLocaleDateString(
    "zh-CN",
    { month: "short", day: "numeric" }
  );

  return (
    <div
      className="group relative flex flex-col gap-3 rounded-xl border border-border bg-muted/50 p-5 transition-all hover:border-accent/40 hover:bg-muted cursor-pointer"
      onClick={() => onOpen(workspace.id)}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/15 text-accent">
            <MessageSquare size={18} />
          </div>
          <h3 className="text-base font-medium text-foreground">
            {workspace.name}
          </h3>
        </div>
        <button
          onClick={(event) => {
            event.stopPropagation();
            onDelete(workspace.id);
          }}
          className="rounded-md p-1.5 text-muted-foreground opacity-0 transition-all hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
          title="删除工作区"
        >
          <Trash2 size={15} />
        </button>
      </div>
      <p className="text-xs text-muted-foreground">创建于 {createdDate}</p>
    </div>
  );
}
