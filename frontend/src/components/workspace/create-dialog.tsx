"use client";

import { useState } from "react";
import { Plus, X } from "lucide-react";

interface CreateDialogProps {
  open: boolean;
  onClose: () => void;
  onCreate: (name: string) => Promise<void>;
}

export function CreateDialog({ open, onClose, onCreate }: CreateDialogProps) {
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    setSubmitting(true);
    setError("");
    try {
      await onCreate(trimmed);
      setName("");
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-border bg-background p-6 shadow-2xl">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">
            新建工作区
          </h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-muted-foreground hover:text-foreground"
          >
            <X size={18} />
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <input
            autoFocus
            value={name}
            onChange={(event) => {
              setName(event.target.value);
              setError("");
            }}
            placeholder="例如：Q3 产品规划"
            className="w-full rounded-lg border border-border bg-muted px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
          {error && (
            <p className="mt-2 text-xs text-destructive">{error}</p>
          )}
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setError("");
                onClose();
              }}
              disabled={submitting}
              className="rounded-lg px-4 py-2 text-sm text-muted-foreground hover:text-foreground"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={!name.trim() || submitting}
              className="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-foreground transition-colors hover:bg-accent/90 disabled:opacity-40"
            >
              <Plus size={15} />
              {submitting ? "创建中..." : "创建"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
