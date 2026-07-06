import type { Document } from "@/lib/api";

interface UploadingDocumentInput {
  id: string;
  workspaceId: string;
  filename: string;
}

function getFileType(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase();
  if (ext === "pdf") return "pdf";
  if (ext === "doc" || ext === "docx") return "docx";
  if (ext === "md" || ext === "markdown") return "markdown";
  if (ext === "txt") return "text";
  return ext || "file";
}

export function createUploadingDocument({
  id,
  workspaceId,
  filename,
}: UploadingDocumentInput): Document {
  const now = new Date().toISOString();
  return {
    id,
    workspace_id: workspaceId,
    filename,
    file_type: getFileType(filename),
    summary: null,
    status: "uploaded",
    error_message: null,
    progress: {
      stage: "uploading",
      stage_label: "上传中",
      percent: 0,
      message: "上传中...",
      current: 0,
      total: 0,
      updated_at: now,
    },
    created_at: now,
    updated_at: now,
  };
}

export function replaceUploadingDocument(
  documents: Document[],
  uploadingId: string,
  uploaded: Document,
): Document[] {
  return documents.map((doc) => (doc.id === uploadingId ? uploaded : doc));
}

export function markUploadFailed(
  documents: Document[],
  uploadingId: string,
  message: string,
): Document[] {
  return documents.map((doc) =>
    doc.id === uploadingId
      ? {
          ...doc,
          status: "error",
          error_message: message,
          progress: undefined,
          updated_at: new Date().toISOString(),
        }
      : doc,
  );
}
