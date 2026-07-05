"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { X, Check, ArrowLeft, Trash2, Loader2, ChevronLeft, ChevronRight } from "lucide-react";
import { deletePptStyle, fetchFileContent, getPptStylePreviewUrl, type PptStyleInfo } from "@/lib/api";
import {
  getPptStyleCategoryGroups,
  normalizePptStyleCategory,
  type PptStyleCategoryId,
} from "./style-categories";
import { prepareStylePreviewHtml } from "./style-preview-html";

interface StylePickerDialogProps {
  selectedId: string;
  styles: PptStyleInfo[];
  onSelect: (styleId: string) => void;
  onClose: () => void;
  onDelete?: (style: PptStyleInfo) => void;
}

export function StylePickerDialog({
  selectedId,
  styles,
  onSelect,
  onClose,
  onDelete,
}: StylePickerDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const previewIframeRef = useRef<HTMLIFrameElement>(null);
  const [previewStyle, setPreviewStyle] = useState<PptStyleInfo | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewHtml, setPreviewHtml] = useState("");
  const [previewError, setPreviewError] = useState("");
  const [previewSlideIndex, setPreviewSlideIndex] = useState(0);
  const [previewSlideTotal, setPreviewSlideTotal] = useState(1);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [activeCategory, setActiveCategory] = useState<PptStyleCategoryId | null>(null);

  const closePreview = useCallback(() => {
    setPreviewStyle(null);
    setPreviewLoading(false);
    setPreviewHtml("");
    setPreviewError("");
    setPreviewSlideIndex(0);
    setPreviewSlideTotal(1);
  }, []);

  const navigatePreview = useCallback((index: number) => {
    const next = Math.max(0, Math.min(index, previewSlideTotal - 1));
    setPreviewSlideIndex(next);
    previewIframeRef.current?.contentWindow?.postMessage(
      { type: "style-preview:navigate", index: next },
      "*"
    );
  }, [previewSlideTotal]);

  // Close on Escape only — priority: delete confirm → preview → dialog
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (confirmDeleteId) {
          setConfirmDeleteId(null);
        } else if (previewStyle) {
          closePreview();
        } else {
          onClose();
        }
      } else if (previewStyle && !confirmDeleteId) {
        if (e.key === "ArrowLeft" || e.key === "PageUp") {
          e.preventDefault();
          navigatePreview(previewSlideIndex - 1);
        } else if (e.key === "ArrowRight" || e.key === "PageDown" || e.key === " ") {
          e.preventDefault();
          navigatePreview(previewSlideIndex + 1);
        }
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose, previewStyle, confirmDeleteId, closePreview, navigatePreview, previewSlideIndex]);

  useEffect(() => {
    if (!previewStyle) return;

    let cancelled = false;

    fetchFileContent(getPptStylePreviewUrl(previewStyle.id))
      .then((html) => {
        if (cancelled) return;
        setPreviewHtml(prepareStylePreviewHtml(html));
      })
      .catch((err) => {
        if (cancelled) return;
        console.error("[StylePicker] failed to load style preview:", err);
        setPreviewError("预览加载失败");
      })
      .finally(() => {
        if (!cancelled) setPreviewLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [previewStyle]);

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const data = event.data as { type?: string; index?: number; total?: number } | null;
      if (!data || data.type !== "style-preview-state") return;
      const total = Math.max(Number(data.total) || 1, 1);
      const index = Math.max(0, Math.min(Number(data.index) || 0, total - 1));
      setPreviewSlideTotal(total);
      setPreviewSlideIndex(index);
    };

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  const categoryGroups = getPptStyleCategoryGroups(styles);
  const selectedStyle = styles.find((style) => style.id === selectedId);
  const selectedCategory = selectedStyle
    ? normalizePptStyleCategory(selectedStyle.category)
    : "business";
  const currentCategory = activeCategory ?? selectedCategory;
  const activeGroup = categoryGroups.find((group) => group.id === currentCategory) ?? categoryGroups[0];

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
    setPreviewHtml("");
    setPreviewError("");
    setPreviewSlideIndex(0);
    setPreviewSlideTotal(1);
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
                onClick={closePreview}
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
            onClick={previewStyle ? closePreview : onClose}
            className="rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground"
          >
            <X size={16} />
          </button>
        </div>

        {/* Content: picker grid or preview iframe */}
        {previewStyle ? (
          <div className="relative flex flex-1 flex-col items-center justify-center overflow-hidden bg-muted/30 p-6">
            {/* Loading overlay */}
            {previewLoading && (
              <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80">
                <Loader2 size={28} className="animate-spin text-muted-foreground" />
              </div>
            )}
            <div className="relative aspect-video w-full max-w-[min(100%,calc((85vh-150px)*16/9))] overflow-hidden rounded-lg border border-border bg-background shadow-lg">
              {previewError ? (
                <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
                  {previewError}
                </div>
              ) : previewHtml ? (
                <iframe
                  ref={previewIframeRef}
                  srcDoc={previewHtml}
                  title={`${previewStyle.name} 全屏预览`}
                  sandbox="allow-scripts allow-same-origin"
                  className={`h-full w-full border-0 transition-opacity duration-300 ${previewLoading ? "opacity-0" : "opacity-100"}`}
                  onLoad={() => navigatePreview(previewSlideIndex)}
                />
              ) : null}
            </div>
            <div className="mt-4 flex items-center gap-3 rounded-full border border-border bg-background/90 px-3 py-2 shadow-lg">
              <button
                onClick={() => navigatePreview(previewSlideIndex - 1)}
                disabled={previewSlideIndex <= 0 || previewLoading || !!previewError}
                className="flex h-8 w-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-35"
                title="上一页"
              >
                <ChevronLeft size={16} />
              </button>
              <span className="min-w-16 text-center font-mono text-xs text-muted-foreground">
                {previewSlideIndex + 1} / {previewSlideTotal}
              </span>
              <button
                onClick={() => navigatePreview(previewSlideIndex + 1)}
                disabled={previewSlideIndex >= previewSlideTotal - 1 || previewLoading || !!previewError}
                className="flex h-8 w-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-35"
                title="下一页"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        ) : (
          <div className="grid min-h-0 flex-1 grid-cols-[220px_1fr] overflow-hidden">
            <div className="border-r border-border bg-muted/20 p-3">
              <div className="space-y-1">
                {categoryGroups.map((group) => {
                  const isActive = group.id === currentCategory;
                  return (
                    <button
                      key={group.id}
                      onClick={() => setActiveCategory(group.id)}
                      className={`w-full rounded-lg px-3 py-2.5 text-left transition-colors ${
                        isActive
                          ? "bg-accent/15 text-accent"
                          : "text-muted-foreground hover:bg-muted hover:text-foreground"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-xs font-medium">{group.label}</span>
                        <span className="rounded-full bg-background/70 px-1.5 py-0.5 text-[10px] text-muted-foreground">
                          {group.styles.length}
                        </span>
                      </div>
                      <p className="mt-1 line-clamp-2 text-[10px] leading-snug opacity-80">
                        {group.description}
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="min-h-0 overflow-y-auto p-5">
              <div className="mb-4 flex items-end justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-foreground">
                    {activeGroup.label}
                  </h3>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {activeGroup.description}
                  </p>
                </div>
              </div>

              {activeGroup.styles.length === 0 ? (
                <div className="flex h-[360px] items-center justify-center rounded-xl border border-dashed border-border bg-muted/20">
                  <p className="text-xs text-muted-foreground">
                    该分类下暂时没有系统模板
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-3 xl:grid-cols-3">
                  {activeGroup.styles.map((style) => {
                    const isSelected = style.id === selectedId;
                    const isCustom = normalizePptStyleCategory(style.category) === "custom";
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
                          className="relative block aspect-[16/9] w-full cursor-pointer overflow-hidden bg-muted"
                        >
                          <iframe
                            src={getPptStylePreviewUrl(style.id, true)}
                            title={style.name}
                            className="pointer-events-none h-full w-full border-0"
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
                              预览模板
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
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
