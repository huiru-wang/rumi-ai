"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Package,
  Loader2,
  CheckCircle,
  Download,
  Presentation,
  FileText,
  Mic,
  MoreHorizontal,
  Trash2,
  AlertCircle,
  ChevronRight,
  Play,
  Eye,
  Palette,
  Ban,
} from "lucide-react";
import { listTasks, deleteTask, downloadTaskFile, type Task, type PptStyleInfo, type VoiceInfo } from "@/lib/api";

interface TaskPanelProps {
  workspaceId: string;
  styles: PptStyleInfo[];
  voices: VoiceInfo[];
  onNarrate?: (taskId: string, title: string) => void;
  onPlayNarration?: (narrationTask: Task, pptTask: Task) => void;
  onPreview?: (task: Task) => void;
  onViewStyleExtraction?: (task: Task) => void;
}

const TYPE_CONFIG: Record<
  string,
  { icon: typeof Presentation; label: string }
> = {
  ppt: { icon: Presentation, label: "PPT" },
  report: { icon: FileText, label: "报告" },
  narration: { icon: Mic, label: "口播稿" },
  ppt_style_extraction: { icon: Palette, label: "风格提取" },
};

const STATUS_CONFIG = {
  generating: {
    icon: Loader2,
    color: "text-yellow-500",
    label: "生成中",
    animate: true,
  },
  completed: {
    icon: CheckCircle,
    color: "text-green-500",
    label: "已完成",
    animate: false,
  },
  failed: {
    icon: Package,
    color: "text-red-500",
    label: "失败",
    animate: false,
  },
  cancelled: {
    icon: Ban,
    color: "text-muted-foreground",
    label: "已取消",
    animate: false,
  },
  narrating: {
    icon: Loader2,
    color: "text-yellow-500",
    label: "文本生成中",
    animate: true,
  },
  tts_generating: {
    icon: Loader2,
    color: "text-blue-500",
    label: "音频生成中",
    animate: true,
  },
  tts_failed: {
    icon: AlertCircle,
    color: "text-orange-500",
    label: "音频失败",
    animate: false,
  },
} as const;

export function TaskPanel({ workspaceId, styles, voices, onNarrate, onPlayNarration, onPreview, onViewStyleExtraction }: TaskPanelProps) {
  const [tasks, setTasks] = useState<Task[]>([]);

  const fetchTasks = useCallback(async () => {
    try {
      const data = await listTasks(workspaceId);
      setTasks(data);
    } catch {
      console.error("Failed to load tasks");
    }
  }, [workspaceId]);

  useEffect(() => {
    fetchTasks();
    const interval = setInterval(fetchTasks, 5000);
    return () => clearInterval(interval);
  }, [fetchTasks]);

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center border-b border-border px-4 py-3">
        <h3 className="text-sm font-medium text-foreground">📦 产出</h3>
      </div>

      {/* Task List */}
      <div className="flex-1 overflow-y-auto p-3">
        {tasks.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-12 text-center text-muted-foreground">
            <Package size={28} strokeWidth={1} />
            <p className="text-xs">
              产出的文件会显示在这里
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-1.5">
            {tasks.map((task) => (
              <TaskItemGroup
                key={task.id}
                task={task}
                workspaceId={workspaceId}
                styles={styles}
                voices={voices}
                onDeleted={fetchTasks}
                onNarrate={onNarrate}
                onPlayNarration={onPlayNarration}
                onPreview={onPreview}
                onViewStyleExtraction={onViewStyleExtraction}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface TaskItemGroupProps {
  task: Task;
  workspaceId: string;
  styles: PptStyleInfo[];
  voices: VoiceInfo[];
  onDeleted: () => void;
  onNarrate?: (taskId: string, title: string) => void;
  onPlayNarration?: (narrationTask: Task, pptTask: Task) => void;
  onPreview?: (task: Task) => void;
  onViewStyleExtraction?: (task: Task) => void;
}

function TaskItemGroup({ task, workspaceId, styles, voices, onDeleted, onNarrate, onPlayNarration, onPreview, onViewStyleExtraction }: TaskItemGroupProps) {
  const [expanded, setExpanded] = useState(true);
  const prevChildCount = useRef(task.children?.length ?? 0);

  // Auto-expand when new children appear
  const childCount = task.children?.length ?? 0;
  if (childCount > prevChildCount.current) {
    prevChildCount.current = childCount;
    if (!expanded) setExpanded(true);
  }

  const hasChildren = childCount > 0;

  return (
    <div>
      <TaskItem
        task={task}
        workspaceId={workspaceId}
        styles={styles}
        voices={voices}
        onDeleted={onDeleted}
        onNarrate={onNarrate}
        onPreview={onPreview}
        onViewStyleExtraction={onViewStyleExtraction}
        canExpand={hasChildren}
        expanded={expanded}
        onToggleExpand={() => setExpanded(!expanded)}
      />
      {/* Render children (e.g. narration tasks) */}
      {hasChildren && expanded && (
        <div className="ml-5 mt-0.5 flex flex-col gap-0.5 border-l border-border/50 pl-2">
          {task.children!.map((child) => (
            <TaskItem
              key={child.id}
              task={child}
              workspaceId={workspaceId}
              styles={styles}
              voices={voices}
              onDeleted={onDeleted}
              onPlayNarration={onPlayNarration}
              parentTask={task}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface TaskItemProps {
  task: Task;
  workspaceId: string;
  styles: PptStyleInfo[];
  voices: VoiceInfo[];
  onDeleted: () => void;
  onNarrate?: (taskId: string, title: string) => void;
  onPlayNarration?: (narrationTask: Task, pptTask: Task) => void;
  onPreview?: (task: Task) => void;
  onViewStyleExtraction?: (task: Task) => void;
  parentTask?: Task;
  canExpand?: boolean;
  expanded?: boolean;
  onToggleExpand?: () => void;
}

function TaskItem({ task, workspaceId, styles, voices, onDeleted, onNarrate, onPlayNarration, onPreview, onViewStyleExtraction, parentTask, canExpand, expanded, onToggleExpand }: TaskItemProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const typeConfig = TYPE_CONFIG[task.type] ?? {
    icon: Package,
    label: task.type,
  };
  const statusKey = task.status as keyof typeof STATUS_CONFIG;
  const statusConfig = STATUS_CONFIG[statusKey] ?? STATUS_CONFIG.generating;
  const TypeIcon = typeConfig.icon;
  const StatusIcon = statusConfig.icon;

  const resultData = task.result_data
    ? JSON.parse(task.result_data)
    : null;

  let statusLabel: string = statusConfig.label;
  if (task.status === "tts_generating" && resultData) {
    const progress = resultData.tts_progress || 0;
    const total = resultData.slides?.length || "?";
    statusLabel = `音频生成中 ${progress}/${total}`;
  }
  if (task.type === "ppt_style_extraction" && task.status === "generating" && resultData?.progress_step) {
    const STEP_LABELS: Record<string, string> = {
      parsing: "解析中",
      analyzing_style: "分析风格",
      generating_preview: "生成预览",
    };
    statusLabel = STEP_LABELS[resultData.progress_step] || "生成中";
  }

  const hasDownload = task.status === "completed" && resultData?.file_path;
  const isPptCompleted = task.type === "ppt" && task.status === "completed";
  const canPlay = task.type === "narration" && task.status === "completed" && !!onPlayNarration && !!parentTask;
  const canPreview = task.type === "ppt" && task.status === "completed" && !!onPreview;
  const canViewStyleExtraction = task.type === "ppt_style_extraction" && !!onViewStyleExtraction;

  // Derive style/voice name for subtitle
  const pptStyleName = task.type === "ppt" && resultData
    ? resultData.ppt_style_name
      || styles.find((s) => s.id === resultData.ppt_style || s.name_en === resultData.ppt_style)?.name
      || resultData.ppt_style
      || ""
    : "";
  const voiceName = task.type === "narration" && resultData?.voice_name
    ? resultData.voice_name
    : task.type === "narration" && resultData?.voice_id
      ? voices.find((v) => v.id === resultData.voice_id)?.name || resultData.voice_id
      : "";

  const handlePlay = () => {
    if (canPlay) onPlayNarration!(task, parentTask!);
  };

  const handleDownload = async () => {
    if (resultData?.file_path) {
      try {
        await downloadTaskFile(task.id, resultData.filename || "download");
      } catch (err) {
        console.error("Download failed:", err);
      }
    }
    setMenuOpen(false);
  };

  const handleNarrate = () => {
    setMenuOpen(false);
    onNarrate?.(task.id, task.title || "PPT");
  };

  const handleDelete = async () => {
    setConfirmDelete(false);
    try {
      await deleteTask(workspaceId, task.id);
      onDeleted();
    } catch {
      console.error("Failed to delete task");
    }
  };

  useEffect(() => {
    if (!menuOpen) return;
    const handleClick = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [menuOpen]);

  return (
    <>
      <div
        className={`group flex items-start gap-2.5 rounded-lg px-2.5 py-2 transition-colors hover:bg-muted/50 ${canExpand ? "cursor-pointer" : ""}`}
        onClick={canExpand ? onToggleExpand : undefined}
      >
        {/* Left icon: always show type icon, chevron below for expandable */}
        <div className="mt-1 flex flex-shrink-0 flex-col items-center gap-0.5">
          <TypeIcon size={15} className="text-accent/70" />
          {canExpand && (
            <ChevronRight
              size={10}
              className={`text-muted-foreground/50 transition-transform duration-150 ${expanded ? "rotate-90" : ""}`}
            />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <p className="truncate text-xs font-medium text-foreground">
              {task.title ?? typeConfig.label}
            </p>
            <StatusIcon
              size={12}
              className={`flex-shrink-0 ${statusConfig.color} ${
                statusConfig.animate ? "animate-spin" : ""
              }`}
            />
          </div>
          <p className="mt-0.5 text-[10px] text-muted-foreground">
            {typeConfig.label} · {statusLabel}
            {pptStyleName && ` · （${pptStyleName}）`}
            {voiceName && `（${voiceName}）`}
          </p>
          {task.status === "tts_failed" && resultData?.tts_error && (
            <p className="mt-0.5 text-[10px] text-orange-400">
              {resultData.tts_error}
            </p>
          )}
        </div>
        {/* Play button for completed narration */}
        {canPlay && (
          <button
            onClick={(e) => { e.stopPropagation(); handlePlay(); }}
            className="mt-0.5 flex-shrink-0 rounded p-1 text-accent/70 opacity-0 transition-all hover:text-accent group-hover:opacity-100"
            title="播放 PPT"
          >
            <Play size={13} />
          </button>
        )}
        {/* Preview button for completed PPT */}
        {canPreview && (
          <button
            onClick={(e) => { e.stopPropagation(); onPreview!(task); }}
            className="mt-0.5 flex-shrink-0 rounded p-1 text-accent/70 opacity-0 transition-all hover:text-accent group-hover:opacity-100"
            title="预览 PPT"
          >
            <Eye size={13} />
          </button>
        )}
        {/* View button for style extraction */}
        {canViewStyleExtraction && (
          <button
            onClick={(e) => { e.stopPropagation(); onViewStyleExtraction!(task); }}
            className="mt-0.5 flex-shrink-0 rounded p-1 text-accent/70 opacity-0 transition-all hover:text-accent group-hover:opacity-100"
            title="查看风格提取"
          >
            <Eye size={13} />
          </button>
        )}
        {/* More menu */}
        <div className="relative mt-0.5" ref={menuRef}>
          <button
            onClick={(e) => { e.stopPropagation(); setMenuOpen(!menuOpen); }}
            className="flex-shrink-0 rounded p-1 text-muted-foreground opacity-0 transition-all hover:text-foreground group-hover:opacity-100"
            title="更多操作"
          >
            <MoreHorizontal size={12} />
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-full z-50 mt-1 w-36 rounded-lg border border-border bg-muted py-1 shadow-xl">
              {hasDownload && (
                <button
                  onClick={(e) => { e.stopPropagation(); handleDownload(); }}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-foreground hover:bg-muted/50"
                >
                  <Download size={12} />
                  下载
                </button>
              )}
              {isPptCompleted && onNarrate && (
                <button
                  onClick={(e) => { e.stopPropagation(); handleNarrate(); }}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-foreground hover:bg-muted/50"
                >
                  <Mic size={12} />
                  生成口播稿
                </button>
              )}
              <button
                onClick={(e) => { e.stopPropagation(); setMenuOpen(false); setConfirmDelete(true); }}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-red-400 hover:bg-muted/50"
              >
                <Trash2 size={12} />
                删除
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Delete confirmation dialog */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="mx-4 w-full max-w-sm rounded-2xl border border-border bg-background p-5 shadow-2xl">
            <h3 className="text-sm font-semibold text-foreground">
              {task.type === "ppt" ? "删除PPT及全部关联产出？" : "确认删除？"}
            </h3>
            <p className="mt-2 text-xs text-muted-foreground">
              {task.type === "ppt"
                ? `将同时删除该PPT关联的口播稿和音频文件，此操作不可撤销。`
                : `将删除「${task.title ?? typeConfig.label}」及其文件，此操作不可撤销。`}
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setConfirmDelete(false)}
                className="rounded-lg px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground"
              >
                取消
              </button>
              <button
                onClick={handleDelete}
                className="rounded-lg bg-red-500/20 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/30"
              >
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

