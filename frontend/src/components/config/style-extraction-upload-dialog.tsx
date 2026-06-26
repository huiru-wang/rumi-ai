"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Upload, X, FileUp, Loader2 } from "lucide-react";
import { submitStyleExtraction, type Task } from "@/lib/api";

interface StyleExtractionUploadDialogProps {
  workspaceId: string;
  onClose: () => void;
  onSubmitted: (task: Task) => void;
}

export function StyleExtractionUploadDialog({
  workspaceId,
  onClose,
  onSubmitted,
}: StyleExtractionUploadDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Close on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (dialogRef.current && !dialogRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [onClose]);

  // Close on Escape
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const handleFile = useCallback(
    async (file: File) => {
      if (!file.name.toLowerCase().endsWith(".pptx")) {
        setError("请选择 .pptx 文件");
        return;
      }
      setError(null);
      setUploading(true);
      try {
        const task = await submitStyleExtraction(workspaceId, file);
        onSubmitted(task);
      } catch (err) {
        setError(err instanceof Error ? err.message : "上传失败");
        setUploading(false);
      }
    },
    [workspaceId, onSubmitted]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div
        ref={dialogRef}
        className="mx-4 w-full max-w-md rounded-2xl border border-border bg-background p-5 shadow-2xl"
      >
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">
            视觉风格提取
          </h3>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground"
          >
            <X size={16} />
          </button>
        </div>

        {/* Drop zone */}
        <div
          className={`flex flex-col items-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 transition-colors ${
            dragOver
              ? "border-accent bg-accent/10"
              : "border-border/60 hover:border-accent/50"
          } ${uploading ? "pointer-events-none opacity-60" : "cursor-pointer"}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => !uploading && fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pptx"
            className="hidden"
            onChange={handleInputChange}
          />
          {uploading ? (
            <>
              <Loader2 size={32} className="animate-spin text-accent" />
              <p className="text-xs text-muted-foreground">正在上传...</p>
            </>
          ) : (
            <>
              <FileUp size={32} className="text-muted-foreground/60" />
              <div className="text-center">
                <p className="text-xs font-medium text-foreground">
                  拖拽或点击上传 PPTX 文件
                </p>
                <p className="mt-1 text-[10px] text-muted-foreground">
                  仅支持 .pptx 格式
                </p>
              </div>
            </>
          )}
        </div>

        {/* Error */}
        {error && (
          <p className="mt-3 text-xs text-red-400">{error}</p>
        )}

        <p className="mt-4 text-[12px] leading-relaxed text-muted-foreground">
          上传后将自动解析 PPTX 文件并通过AI提取视觉风格，生成可复用的风格模板。<span className="font-bold text-foreground">视觉风格提取不会完整复刻原PPT文件，而是提取关键元素、样式、布局、配色方案等关键信息。</span>
        </p>
      </div>
    </div>
  );
}
