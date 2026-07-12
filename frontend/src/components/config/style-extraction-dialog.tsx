"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { X, CheckCircle2, Loader2, Circle, Save, AlertCircle, ArrowLeft, Info } from "lucide-react";
import { getBusinessErrorMessage, getStyleExtractionPreviewUrl, getTask, saveStyleFromExtraction, type Task } from "@/lib/api";

interface StyleExtractionDialogProps {
  workspaceId: string;
  userId: string;
  taskId: string;
  onClose: () => void;
  onSaved?: () => void;
}

type StepStatus = "done" | "active" | "pending" | "error";

interface StepDef {
  key: string;
  label: string;
}

const STEPS: StepDef[] = [
  { key: "uploaded", label: "上传文件" },
  { key: "parsing", label: "解析 PPTX 结构" },
  { key: "analyzing_style", label: "分析风格特征" },
  { key: "generating_preview", label: "生成预览页面" },
  { key: "completed", label: "完成" },
];

function getStepStatuses(
  task: Task | null
): { stepStatuses: StepStatus[]; currentStep: number } {
  if (!task) {
    return {
      stepStatuses: ["active", "pending", "pending", "pending", "pending"],
      currentStep: 0,
    };
  }

  const rd = task.result_data
    ? (typeof task.result_data === "string"
        ? JSON.parse(task.result_data)
        : task.result_data)
    : {};
  const progressStep: string = rd.progress_step || "uploaded";

  if (task.status === "failed" || task.status === "cancelled") {
    const stepIdx = STEPS.findIndex((s) => s.key === progressStep);
    const idx = stepIdx >= 0 ? stepIdx : 1;
    return {
      stepStatuses: STEPS.map((_, i) =>
        i < idx ? "done" : i === idx ? "error" : "pending"
      ) as StepStatus[],
      currentStep: idx,
    };
  }

  if (task.status === "completed") {
    return {
      stepStatuses: STEPS.map(() => "done") as StepStatus[],
      currentStep: STEPS.length - 1,
    };
  }

  // In progress
  const stepIdx = STEPS.findIndex((s) => s.key === progressStep);
  const idx = stepIdx >= 0 ? stepIdx : 0;
  return {
    stepStatuses: STEPS.map((_, i) =>
      i < idx ? "done" : i === idx ? "active" : "pending"
    ) as StepStatus[],
    currentStep: idx,
  };
}

function StepIcon({ status }: { status: StepStatus }) {
  if (status === "done")
    return <CheckCircle2 size={16} className="text-green-500" />;
  if (status === "active")
    return <Loader2 size={16} className="animate-spin text-accent" />;
  if (status === "error")
    return <AlertCircle size={16} className="text-red-500" />;
  return <Circle size={16} className="text-muted-foreground/40" />;
}

export function StyleExtractionDialog({
  workspaceId,
  userId,
  taskId,
  onClose,
  onSaved,
}: StyleExtractionDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [task, setTask] = useState<Task | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);

  // Poll task
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const data = await getTask(workspaceId, taskId);
        if (!cancelled) setTask(data);
        // Stop polling when terminal
        if (
          data.status === "completed" ||
          data.status === "failed" ||
          data.status === "cancelled"
        ) {
          return true;
        }
      } catch {
        // ignore
      }
      return false;
    };

    poll();
    const interval = setInterval(async () => {
      const done = await poll();
      if (done) clearInterval(interval);
    }, 2000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [workspaceId, taskId]);

  // Close handlers
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (dialogRef.current && !dialogRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [onClose]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (previewOpen) {
        setPreviewOpen(false);
      } else {
        onClose();
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose, previewOpen]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setSaveError(null);
    try {
      await saveStyleFromExtraction(taskId, userId);
      setSaved(true);
      onSaved?.();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }, [taskId, userId, onSaved]);

  const { stepStatuses } = getStepStatuses(task);

  const rd = task?.result_data
    ? (typeof task.result_data === "string"
        ? JSON.parse(task.result_data)
        : task.result_data)
    : null;

  const styleName = rd?.style_name as string | undefined;
  const shortDescription = rd?.description as string | undefined;
  const parseSummary = rd?.parse_summary as
    | { slide_count?: number; background_image_count?: number }
    | undefined;
  const slideCount = parseSummary?.slide_count;
  const estimatedMinutes = slideCount
    ? Math.ceil((120 + slideCount * 20) / 60)
    : null;
  const alreadySaved = !!rd?.saved_style_id;
  const isCompleted = task?.status === "completed";
  const isFailed = task?.status === "failed" || task?.status === "cancelled";
  const errorMessage = getBusinessErrorMessage(rd?.error, "视觉风格提取失败，请稍后重试。");
  const previewUrl = isCompleted ? getStyleExtractionPreviewUrl(taskId) : null;

  const openPreview = useCallback(() => {
    if (!previewUrl) return;
    setPreviewLoading(true);
    setPreviewOpen(true);
  }, [previewUrl]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div
        ref={dialogRef}
        className={`mx-4 flex max-h-[85vh] w-full flex-col rounded-2xl border border-border bg-background shadow-2xl ${
          previewOpen ? "h-[85vh] max-w-5xl" : "max-w-lg"
        }`}
      >
        {/* Header */}
        <div className="flex shrink-0 flex-col border-b border-border px-5 py-3.5">
          <div className="flex items-center justify-between">
            {previewOpen ? (
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setPreviewOpen(false)}
                  className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
                >
                  <ArrowLeft size={14} />
                  返回
                </button>
                <div className="h-4 w-px bg-border" />
                <div>
                  <h3 className="text-sm font-semibold text-foreground">
                    {styleName || "风格预览"}
                  </h3>
                  {shortDescription && (
                    <p className="mt-0.5 max-w-xl truncate text-[11px] text-muted-foreground">
                      {shortDescription}
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-1.5">
                <h3 className="text-sm font-semibold text-foreground">
                  视觉风格提取
                </h3>
                <div className="group relative flex" tabIndex={0}>
                  <Info size={14} className="text-muted-foreground" />
                  <div
                    role="tooltip"
                    className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 hidden w-72 -translate-x-1/2 rounded-md border border-border bg-popover px-3 py-2 text-[11px] font-normal leading-relaxed text-popover-foreground shadow-lg group-hover:block group-focus:block"
                  >
                    视觉风格提取不会完整复刻原PPT文件，而是提取关键元素、样式、布局、配色方案等关键信息。
                  </div>
                </div>
              </div>
            )}
            <button
              onClick={previewOpen ? () => setPreviewOpen(false) : onClose}
              className="rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground"
            >
              <X size={16} />
            </button>
          </div>
          {!previewOpen && !isCompleted && !isFailed && (
            <p className="mt-1.5 text-[11px] text-muted-foreground">
              {estimatedMinutes
                ? `共 ${slideCount} 页，预计需要 ${estimatedMinutes} 分钟完成。`
                : "正在解析文件并估算完成时间。"}
              可关闭窗口，任务已在「产出」中，随时可查看进度。
            </p>
          )}
        </div>

        {/* Content */}
        {previewOpen && previewUrl ? (
          <div className="relative flex flex-1 items-center justify-center overflow-hidden bg-muted/30 p-6">
            {previewLoading && (
              <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80">
                <Loader2 size={28} className="animate-spin text-muted-foreground" />
              </div>
            )}
            <div className="relative aspect-video w-full max-w-[min(100%,calc((85vh-150px)*16/9))] overflow-hidden rounded-lg border border-border bg-background shadow-lg">
              <iframe
                src={previewUrl}
                title={`${styleName || "风格"} 全屏预览`}
                sandbox="allow-scripts allow-same-origin"
                className={`h-full w-full border-0 transition-opacity duration-300 ${previewLoading ? "opacity-0" : "opacity-100"}`}
                onLoad={() => setPreviewLoading(false)}
              />
            </div>
          </div>
        ) : (
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          <div className="flex flex-col gap-2.5">
            {STEPS.map((step, i) => (
              <div key={step.key} className="flex flex-col">
                <div className="flex items-center gap-2.5">
                  <StepIcon status={stepStatuses[i]} />
                  <span
                    className={`text-xs ${
                      stepStatuses[i] === "done"
                        ? "text-foreground"
                        : stepStatuses[i] === "active"
                          ? "font-medium text-foreground"
                          : stepStatuses[i] === "error"
                            ? "text-red-400"
                            : "text-muted-foreground/60"
                    }`}
                  >
                    {step.label}
                  </span>
                </div>

                {/* 错误信息内联在失败步骤下 */}
                {stepStatuses[i] === "error" && isFailed && rd?.error && (
                  <div className="ml-6 mt-1.5 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2">
                    <p className="text-[11px] text-red-400">{errorMessage}</p>
                  </div>
                )}

                {step.key === "parsing" && parseSummary && (
                  <p className="ml-6 mt-1 text-[11px] text-muted-foreground">
                    {parseSummary.slide_count ?? 0} 页 · {parseSummary.background_image_count ?? 0} 张背景图片
                  </p>
                )}

                {/* 分析风格特征完成后，内联显示风格名称+描述 */}
                {step.key === "analyzing_style" && stepStatuses[i] === "done" && styleName && (
                  <div className="ml-6 mt-1.5 rounded-lg bg-muted/30 px-3 py-2">
                    <p className="text-xs font-medium text-foreground">
                      风格：{styleName}
                    </p>
                    {shortDescription && (
                      <p className="mt-0.5 text-[11px] text-muted-foreground">
                        {shortDescription}
                      </p>
                    )}
                  </div>
                )}

                {/* 生成预览页面完成后，内联显示预览 iframe */}
                {step.key === "generating_preview" && stepStatuses[i] === "done" && previewUrl && (
                  <div className="ml-6 mt-1.5 overflow-hidden rounded-xl border border-border">
                    <div className="flex items-center justify-between border-b border-border bg-muted/20 px-3 py-2">
                      <span className="text-[11px] text-muted-foreground">
                        HTML 预览
                      </span>
                      <button
                        onClick={openPreview}
                        className="rounded-md bg-accent/15 px-2.5 py-1 text-[10px] font-medium text-accent transition-colors hover:bg-accent/25"
                      >
                        预览
                      </button>
                    </div>
                    <div className="h-64">
                      <iframe
                        src={previewUrl}
                        title="风格预览"
                        className="pointer-events-none h-full w-full border-0"
                        tabIndex={-1}
                      />
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
        )}

        {/* Footer */}
        {!previewOpen && (
        <div className="flex shrink-0 items-center justify-end border-t border-border px-5 py-3">
          {saveError && (
            <p className="mr-auto text-[10px] text-red-400">{saveError}</p>
          )}
          {saved || alreadySaved ? (
            <div className="flex items-center gap-1.5 text-xs text-green-500">
              <CheckCircle2 size={14} />
              已保存
            </div>
          ) : (
            <button
              onClick={handleSave}
              disabled={!isCompleted || saving}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                isCompleted && !saving
                  ? "bg-accent/20 text-accent hover:bg-accent/30"
                  : "cursor-not-allowed bg-muted text-muted-foreground/50"
              }`}
            >
              {saving ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <Save size={12} />
              )}
              保存为新的风格模板
            </button>
          )}
        </div>
        )}
      </div>
    </div>
  );
}
