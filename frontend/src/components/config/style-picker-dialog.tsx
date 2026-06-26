"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { X, Check, ArrowLeft, Trash2, Loader2 } from "lucide-react";
import { deletePptStyle, type PptStyleInfo } from "@/lib/api";

interface StylePickerDialogProps {
  selectedId: string;
  styles: PptStyleInfo[];
  onSelect: (styleId: string) => void;
  onClose: () => void;
  onDelete?: (style: PptStyleInfo) => void;
}

const CATEGORY_LABELS: Record<string, string> = {
  dark: "深色主题",
  light: "浅色主题",
  custom: "我的主题",
};

export function StylePickerDialog({
  selectedId,
  styles,
  onSelect,
  onClose,
  onDelete,
}: StylePickerDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [previewStyle, setPreviewStyle] = useState<PptStyleInfo | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Close on Escape only — priority: delete confirm → preview → dialog
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (confirmDeleteId) {
          setConfirmDeleteId(null);
        } else if (previewStyle) {
          setPreviewStyle(null);
          setPreviewLoading(false);
        } else {
          onClose();
        }
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose, previewStyle, confirmDeleteId]);

  const categories = ["dark", "light", "custom"] as const;

  const apiBase = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

  const getPreviewUrl = (style: PptStyleInfo) =>
    `${apiBase}/api/ppt-style-preview/${style.preview_path}`;

  const handleDelete = async (style: PptStyleInfo) => {
    console.log("[StylePicker] deleting style:", style.id, style.name);
    setDeleting(true);
    try {
      await deletePptStyle(style.id);
      console.log("[StylePicker] style deleted successfully");
      if (style.id === selectedId) {
        onSelect("");
      }
      onDelete?.(style);
    } catch (err) {
      console.error("[StylePicker] failed to delete style:", err);
    } finally {
      setDeleting(false);
      setConfirmDeleteId(null);
    }
  };

  const handlePreview = useCallback((style: PptStyleInfo) => {
    setPreviewLoading(true);
    setPreviewStyle(style);
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div
        ref={dialogRef}
        className="relative mx-4 flex h-[85vh] w-full max-w-5xl flex-col rounded-2xl border border-border bg-background shadow-2xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          {previewStyle ? (
            <div className="flex items-center gap-3">
              <button
                onClick={() => setPreviewStyle(null)}
                className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
              >
                <ArrowLeft size={14} />
                返回
              </button>
              <div className="h-4 w-px bg-border" />
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold text-foreground">
                  {previewStyle.name}
                </h2>
                <span className="text-xs text-muted-foreground">
                  {previewStyle.name_en}
                </span>
              </div>
            </div>
          ) : (
            <h2 className="text-sm font-semibold text-foreground">
              PPT 视觉风格
            </h2>
          )}
          <button
            onClick={previewStyle ? () => setPreviewStyle(null) : onClose}
            className="rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground"
          >
            <X size={16} />
          </button>
        </div>

        {/* Content: picker grid or preview iframe */}
        {previewStyle ? (
          <div className="relative flex-1 overflow-hidden">
            {/* Loading overlay */}
            {previewLoading && (
              <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80">
                <Loader2 size={28} className="animate-spin text-muted-foreground" />
              </div>
            )}
            <iframe
              src={getPreviewUrl(previewStyle)}
              title={`${previewStyle.name} 全屏预览`}
              className={`h-full w-full border-0 transition-opacity duration-300 ${previewLoading ? "opacity-0" : "opacity-100"}`}
              onLoad={() => setPreviewLoading(false)}
            />
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto p-5">
            {categories.map((cat) => {
              const catStyles = styles.filter((s) => s.category === cat);
              if (catStyles.length === 0) return null;
              return (
                <div key={cat} className="mb-5 last:mb-0">
                  <h3 className="mb-2.5 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    {CATEGORY_LABELS[cat]}
                  </h3>
                  <div className="grid grid-cols-3 gap-2.5">
                    {catStyles.map((style) => {
                      const isSelected = style.id === selectedId;
                      const isCustom = style.category === "custom";
                      return (
                        <div
                          key={style.id}
                          className={`group relative flex flex-col overflow-hidden rounded-xl border text-left transition-all ${
                            isSelected
                              ? "border-accent ring-1 ring-accent"
                              : "border-border hover:border-accent/50"
                          }`}
                        >
                          <button
                            onClick={() => onSelect(style.id)}
                            className="relative block aspect-[16/10] w-full cursor-pointer overflow-hidden bg-muted"
                          >
                            <iframe
                              src={`${getPreviewUrl(style)}?thumb=1`}
                              title={style.name}
                              className="h-full w-full border-0 pointer-events-none"
                              loading="lazy"
                              tabIndex={-1}
                            />
                            {isSelected && (
                              <div className="absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded-full bg-accent">
                                <Check size={12} className="text-background" />
                              </div>
                            )}
                          </button>
                          <div className="flex items-center justify-between px-3 py-2">
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-xs font-medium text-foreground">
                                {style.name}
                              </p>
                              <p className="mt-0.5 truncate text-[10px] leading-tight text-muted-foreground">
                                {style.description}
                              </p>
                            </div>
                            <div className="ml-2 flex shrink-0 items-center gap-1">
                              {isCustom && (
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setConfirmDeleteId(style.id);
                                  }}
                                  className="rounded-md p-1.5 text-muted-foreground/60 transition-colors hover:bg-red-500/15 hover:text-red-400"
                                  title="删除"
                                >
                                  <Trash2 size={12} />
                                </button>
                              )}
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handlePreview(style);
                                }}
                                className="rounded-md bg-accent/15 px-2.5 py-1 text-[10px] font-medium text-accent transition-colors hover:bg-accent/25"
                              >
                                预览模版
                              </button>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Delete confirmation dialog */}
      {confirmDeleteId && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="mx-4 w-full max-w-sm rounded-2xl border border-border bg-background p-5 shadow-2xl">
            <h3 className="text-sm font-semibold text-foreground">
              确认删除该主题？
            </h3>
            <p className="mt-2 text-xs text-muted-foreground">
              删除后无法恢复，关联的预览文件也会一并清除。
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setConfirmDeleteId(null)}
                disabled={deleting}
                className="rounded-lg px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground"
              >
                取消
              </button>
              <button
                onClick={() => {
                  const style = styles.find((s) => s.id === confirmDeleteId);
                  if (style) handleDelete(style);
                }}
                disabled={deleting}
                className="rounded-lg bg-red-500/20 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/30 disabled:opacity-50"
              >
                {deleting ? "删除中..." : "确认删除"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
