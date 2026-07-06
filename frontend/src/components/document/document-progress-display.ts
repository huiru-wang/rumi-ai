import type { Document } from "@/lib/api";

function clampPercent(value: unknown): number {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) return 0;
  return Math.max(0, Math.min(100, Math.round(numeric)));
}

export function keepDocumentProgressMonotonic<T extends Pick<Document, "id" | "status" | "progress">>(
  documents: T[],
  maxPercentById: Map<string, number>,
): T[] {
  return documents.map((doc) => {
    if (!doc.progress) return doc;
    const incoming = doc.status === "ready" ? 100 : clampPercent(doc.progress.percent);
    const previous = maxPercentById.get(doc.id) ?? 0;
    const displayPercent = Math.max(previous, incoming);
    maxPercentById.set(doc.id, displayPercent);
    if (displayPercent === doc.progress.percent) return doc;
    return {
      ...doc,
      progress: {
        ...doc.progress,
        percent: displayPercent,
      },
    };
  });
}
