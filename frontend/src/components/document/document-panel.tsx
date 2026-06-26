"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  FileText,
  Upload,
  Trash2,
  CheckCircle,
  Loader2,
  AlertCircle,
  X,
} from "lucide-react";
import {
  listDocuments,
  uploadDocument,
  deleteDocument,
  type Document,
  type DocumentStatus,
} from "@/lib/api";

interface DocumentPanelProps {
  workspaceId: string;
}

const STATUS_CONFIG = {
  uploaded: { icon: Loader2, color: "text-blue-500", label: "已上传" },
  processing: { icon: Loader2, color: "text-yellow-500", label: "处理中" },
  parsing: { icon: Loader2, color: "text-yellow-500", label: "正在解析" },
  parsed: { icon: Loader2, color: "text-yellow-500", label: "已解析，等待处理" },
  chunking: { icon: Loader2, color: "text-yellow-500", label: "正在分块" },
  indexing: { icon: Loader2, color: "text-yellow-500", label: "正在入库" },
  summarizing: { icon: Loader2, color: "text-yellow-500", label: "正在理解文档" },
  ready: { icon: CheckCircle, color: "text-green-500", label: "就绪" },
  error: { icon: AlertCircle, color: "text-destructive", label: "失败" },
} as const;

const ACTIVE_STATUSES = new Set<DocumentStatus>([
  "uploaded",
  "processing",
  "parsing",
  "parsed",
  "chunking",
  "indexing",
  "summarizing",
]);

const FILE_TYPE_LABELS: Record<string, string> = {
  pdf: "PDF",
  docx: "Docx",
  markdown: "MD",
  text: "文本",
};

export function DocumentPanel({ workspaceId }: DocumentPanelProps) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchDocuments = useCallback(async () => {
    try {
      const docs = await listDocuments(workspaceId);
      setDocuments(docs);
    } catch {
      console.error("Failed to load documents");
    }
  }, [workspaceId]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  useEffect(() => {
    if (!documents.some((doc) => ACTIVE_STATUSES.has(doc.status))) return;
    const interval = window.setInterval(fetchDocuments, 1500);
    return () => window.clearInterval(interval);
  }, [documents, fetchDocuments]);

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    console.log(`[DocPanel] uploading ${files.length} file(s)`);
    setUploading(true);
    setUploadError("");
    const errors: string[] = [];
    try {
      for (const file of Array.from(files)) {
        console.log(`[DocPanel] uploading: ${file.name} (${file.size} bytes)`);
        try {
          const result = await uploadDocument(workspaceId, file);
          console.log(`[DocPanel] uploaded: id=${result.id} status=${result.status}`);
          setDocuments((prev) => [
            result,
            ...prev.filter((doc) => doc.id !== result.id),
          ]);
        } catch (err) {
          const msg = err instanceof Error ? err.message : `上传 ${file.name} 失败`;
          errors.push(msg);
        }
      }
      if (errors.length > 0) {
        setUploadError(errors.join("；"));
        window.setTimeout(() => setUploadError(""), 5000);
      }
      await fetchDocuments();
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleDelete = async (docId: string) => {
    try {
      await deleteDocument(workspaceId, docId);
      await fetchDocuments();
    } catch {
      console.error("Delete failed");
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h3 className="text-sm font-medium text-foreground">📚 知识库</h3>
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-accent transition-colors hover:bg-accent/10 disabled:opacity-50"
        >
          {uploading ? (
            <Loader2 size={13} className="animate-spin" />
          ) : (
            <Upload size={13} />
          )}
          上传
        </button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.doc,.md,.txt"
          onChange={handleUpload}
          className="hidden"
        />
      </div>

      {/* Upload error toast */}
      {uploadError && (
        <div className="mx-3 mt-2 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2">
          <AlertCircle size={14} className="mt-0.5 shrink-0 text-red-400" />
          <p className="flex-1 text-xs leading-relaxed text-red-300">{uploadError}</p>
          <button
            onClick={() => setUploadError("")}
            className="shrink-0 text-red-400/60 hover:text-red-300"
          >
            <X size={12} />
          </button>
        </div>
      )}

      {/* Document List */}
      <div className="flex-1 overflow-y-auto p-3">
        {documents.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-12 text-center text-muted-foreground">
            <FileText size={28} strokeWidth={1} />
            <p className="text-xs">
              上传 PDF、Word 或 Markdown 文档
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-1.5">
            {documents.map((doc) => (
              <DocumentItem
                key={doc.id}
                document={doc}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface DocumentItemProps {
  document: Document;
  onDelete: (id: string) => void;
}

function DocumentItem({ document, onDelete }: DocumentItemProps) {
  const statusConfig =
    STATUS_CONFIG[document.status] ??
    STATUS_CONFIG.error;
  const StatusIcon = statusConfig.icon;
  const fileTypeLabel =
    FILE_TYPE_LABELS[document.file_type] ?? document.file_type;
  const isActive = ACTIVE_STATUSES.has(document.status);
  const detail =
    document.status === "error"
      ? document.error_message || "处理失败"
      : document.summary
        ? `${document.summary.slice(0, 40)}...`
        : statusConfig.label;

  return (
    <div className="group flex items-start gap-2.5 rounded-lg px-2.5 py-2 transition-colors hover:bg-muted/50">
      <div className="mt-0.5 flex-shrink-0">
        <FileText size={15} className="text-muted-foreground" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <p className="truncate text-xs font-medium text-foreground">
            {document.filename}
          </p>
          <StatusIcon
            size={12}
            className={`flex-shrink-0 ${statusConfig.color} ${isActive ? "animate-spin" : ""
              }`}
          />
        </div>
        <p className="mt-0.5 text-[10px] text-muted-foreground">
          {fileTypeLabel} · {detail}
        </p>
      </div>
      <button
        onClick={() => onDelete(document.id)}
        className="mt-0.5 flex-shrink-0 rounded p-1 text-muted-foreground opacity-0 transition-all hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
      >
        <Trash2 size={12} />
      </button>
    </div>
  );
}
