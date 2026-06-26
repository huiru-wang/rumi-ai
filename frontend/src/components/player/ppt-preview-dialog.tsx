"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { X, Save, Check, Loader2, AlertCircle, Pencil } from "lucide-react";
import { fetchFileContent, getFileViewUrl, saveTaskFile, type Task, type PptStyleInfo } from "@/lib/api";

// Script injected into iframe: handles edit mode sync + HTML export for save
const EDIT_MODE_MONITOR_SCRIPT = `
(function() {
  var lastEditable = false;

  // Monitor E key inside iframe and report mode change to parent
  document.addEventListener('keydown', function(e) {
    if (e.key === 'e' || e.key === 'E') {
      setTimeout(function() {
        var editable = document.body.contentEditable === 'true' || document.body.isContentEditable;
        if (editable !== lastEditable) {
          lastEditable = editable;
          window.parent.postMessage({ type: 'ppt-edit-mode-change', editable: editable }, '*');
        }
      }, 100);
    }
  });

  // Listen for commands from parent
  window.addEventListener('message', function(e) {
    if (!e.data || !e.data.type) return;

    // Toggle edit mode from parent button
    if (e.data.type === 'toggle-edit-mode') {
      document.body.contentEditable = e.data.editable ? 'true' : 'false';
      lastEditable = e.data.editable;
      window.parent.postMessage({ type: 'ppt-edit-mode-change', editable: e.data.editable }, '*');
    }

    // Export current HTML for save
    if (e.data.type === 'get-html') {
      var html = '<!DOCTYPE html>\\n' + document.documentElement.outerHTML;
      window.parent.postMessage({ type: 'ppt-html-response', html: html }, '*');
    }
  });
})();
`;

type SaveState = "idle" | "saving" | "saved" | "error";

interface PPTPreviewDialogProps {
  workspaceId: string;
  pptTask: Task;
  styles: PptStyleInfo[];
  onClose: () => void;
}

export function PPTPreviewDialog({ workspaceId, pptTask, styles, onClose }: PPTPreviewDialogProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pptHtml, setPptHtml] = useState("");
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [saveError, setSaveError] = useState("");
  const [isEditMode, setIsEditMode] = useState(false);

  const iframeRef = useRef<HTMLIFrameElement>(null);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const htmlResponseResolver = useRef<((html: string) => void) | null>(null);

  // Derive style name from task result_data
  const resultData = pptTask.result_data ? JSON.parse(pptTask.result_data) : null;
  const styleId = resultData?.ppt_style || "";
  const styleName = resultData?.ppt_style_name
    || styles.find((s) => s.id === styleId || s.name_en === styleId)?.name
    || styleId;
  const pptTitle = pptTask.title || "未命名 PPT";

  // Load PPT HTML
  useEffect(() => {
    let cancelled = false;

    const init = async () => {
      try {
        const result = JSON.parse(pptTask.result_data || "{}");
        if (!result.file_path) {
          throw new Error("PPT 文件路径缺失");
        }

        const fileUrl = getFileViewUrl(result.file_path);
        const html = await fetchFileContent(fileUrl);
        if (cancelled) return;

        // Inject edit mode monitor script before </body> with markers for stripping on save
        const injectedHtml = html.replace(
          "</body>",
          `<!--PPT_PREVIEW_MONITOR_START--><script>${EDIT_MODE_MONITOR_SCRIPT}</script><!--PPT_PREVIEW_MONITOR_END--></body>`
        );
        setPptHtml(injectedHtml);
        setIsLoading(false);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "加载失败");
          setIsLoading(false);
        }
      }
    };

    init();
    return () => {
      cancelled = true;
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    };
  }, [pptTask]);

  // ESC to close
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  // Listen for messages from iframe: edit mode changes + HTML response for save
  useEffect(() => {
    const handleMessage = (e: MessageEvent) => {
      if (e.data?.type === "ppt-edit-mode-change") {
        setIsEditMode(e.data.editable);
      }
      if (e.data?.type === "ppt-html-response" && htmlResponseResolver.current) {
        htmlResponseResolver.current(e.data.html);
        htmlResponseResolver.current = null;
      }
    };
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  // Toggle edit mode: send command to iframe and update local state
  const handleToggleEdit = useCallback(() => {
    const newMode = !isEditMode;
    iframeRef.current?.contentWindow?.postMessage(
      { type: "toggle-edit-mode", editable: newMode },
      "*"
    );
    setIsEditMode(newMode);
  }, [isEditMode]);

  // Save handler: close edit mode first, then request HTML and upload
  const handleSave = useCallback(async () => {
    const iframe = iframeRef.current;
    if (!iframe?.contentWindow) {
      setSaveState("error");
      setSaveError("无法访问预览内容");
      return;
    }

    setSaveState("saving");
    setSaveError("");

    try {
      // Close edit mode first to remove contenteditable from saved HTML
      iframe.contentWindow.postMessage({ type: "toggle-edit-mode", editable: false }, "*");
      setIsEditMode(false);

      // Request current HTML from iframe via postMessage
      const htmlPromise = new Promise<string>((resolve) => {
        htmlResponseResolver.current = resolve;
      });
      iframe.contentWindow.postMessage({ type: "get-html" }, "*");

      // Wait for response with timeout
      const timeoutPromise = new Promise<string>((_, reject) =>
        setTimeout(() => reject(new Error("获取内容超时")), 5000)
      );
      const fullHtml = await Promise.race([htmlPromise, timeoutPromise]);

      // Strip our injected monitor script (between markers) before saving
      const cleanHtml = fullHtml.replace(
        /<!--PPT_PREVIEW_MONITOR_START-->[\s\S]*?<!--PPT_PREVIEW_MONITOR_END-->/,
        ""
      );

      await saveTaskFile(workspaceId, pptTask.id, cleanHtml);
      setSaveState("saved");
      saveTimeoutRef.current = setTimeout(() => setSaveState("idle"), 2000);
    } catch (err) {
      setSaveState("error");
      setSaveError(err instanceof Error ? err.message : "保存失败");
    }
  }, [workspaceId, pptTask.id]);

  // Error state
  if (error) {
    return (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/80"
        onClick={onClose}
      >
        <div
          className="mx-4 w-full max-w-md rounded-2xl border border-border bg-background p-6 text-center"
          onClick={(e) => e.stopPropagation()}
        >
          <AlertCircle size={32} className="mx-auto text-red-400" />
          <p className="mt-3 text-sm text-foreground">加载失败</p>
          <p className="mt-1 text-xs text-muted-foreground">{error}</p>
          <button
            onClick={onClose}
            className="mt-4 rounded-lg bg-accent/20 px-4 py-1.5 text-xs text-accent hover:bg-accent/30"
          >
            关闭
          </button>
        </div>
      </div>
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80">
        <div className="flex flex-col items-center gap-2 text-muted-foreground">
          <Loader2 size={28} className="animate-spin" />
          <p className="text-xs">加载 PPT 预览...</p>
        </div>
      </div>
    );
  }

  // Save button content
  const SaveButtonContent = () => {
    switch (saveState) {
      case "saving":
        return (
          <>
            <Loader2 size={13} className="animate-spin" />
            保存中...
          </>
        );
      case "saved":
        return (
          <>
            <Check size={13} />
            已保存
          </>
        );
      case "error":
        return (
          <>
            <AlertCircle size={13} />
            保存失败
          </>
        );
      default:
        return (
          <>
            <Save size={13} />
            保存
          </>
        );
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col bg-background"
      onClick={(e) => {
        // Only close if clicking the backdrop (outside the main content area)
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/* Close button - floating top right */}
      <button
        onClick={onClose}
        className="absolute right-4 top-4 z-10 rounded-lg bg-background/80 p-2 text-muted-foreground backdrop-blur-sm transition-colors hover:text-foreground"
        title="关闭 (ESC)"
      >
        <X size={18} />
      </button>

      {/* PPT iframe area - fills all space except bottom bar */}
      <div className="min-h-0 flex-1">
        {pptHtml && (
          <iframe
            ref={iframeRef}
            srcDoc={pptHtml}
            className="h-full w-full border-0"
            title="PPT Preview"
            sandbox="allow-scripts allow-same-origin"
          />
        )}
      </div>

      {/* Bottom bar */}
      <div className="flex shrink-0 items-center justify-between border-t border-border bg-background px-5 py-3">
        {/* Left: hints */}
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 text-[10px]">←</kbd>
            <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 text-[10px]">→</kbd>
            翻页
          </span>
        </div>

        {/* Center: title + style name */}
        <div className="flex items-center gap-2 text-sm text-foreground">
          <span className="font-medium">{pptTitle}</span>
          {styleName && (
            <span className="text-xs text-muted-foreground">（{styleName}）</span>
          )}
        </div>

        {/* Right: edit/save button + error message */}
        <div className="flex items-center gap-2">
          {saveState === "error" && saveError && (
            <span className="text-xs text-red-400">{saveError}</span>
          )}
          {/* Combined edit/save button */}
          {!isEditMode ? (
            <button
              onClick={handleToggleEdit}
              className="flex items-center gap-1.5 rounded-lg bg-muted px-3 py-2 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted/80 hover:text-foreground"
              title="开启编辑模式"
            >
              <Pencil size={13} />
              开启编辑模式
            </button>
          ) : (
            <button
              onClick={handleSave}
              disabled={saveState === "saving"}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                saveState === "saved"
                  ? "bg-green-500/20 text-green-400"
                  : saveState === "error"
                    ? "bg-red-500/20 text-red-400 hover:bg-red-500/30"
                    : "bg-accent/20 text-accent hover:bg-accent/30"
              } disabled:opacity-50`}
            >
              <SaveButtonContent />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
