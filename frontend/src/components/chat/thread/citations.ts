import type { CitationEntry } from "./types";

const REF_MARKER_PATTERN = /\[ref:([^\]]+)\]|\{\{ref:([^}]+)\}\}/g;
const CITE_HREF_PREFIX = "#__cite__";

function isPageField(value: string): boolean {
  return value === "-" || /^第\d+(?:-\d+)?页$/.test(value);
}

function formatCitationDetail(parts: string[]): string {
  if (parts.length === 0) return "来源位置未标注";

  const isStructured = parts.length >= 2 || isPageField(parts[0]);
  return isStructured ? parts.join("｜") : parts[0];
}

function parseCitationPayload(payload: string): CitationEntry | null {
  const parts = payload
    .split("|")
    .map((part) => part.trim())
    .filter(Boolean);
  const docName = parts.shift();
  if (!docName) return null;

  return {
    docName,
    detail: formatCitationDetail(parts),
  };
}

export function replaceCitationMarkers(text: string): {
  text: string;
  citations: CitationEntry[];
} {
  const citations: CitationEntry[] = [];
  const replaced = text.replace(REF_MARKER_PATTERN, (marker, squareRef, braceRef) => {
    const entry = parseCitationPayload(squareRef || braceRef || "");
    if (!entry) return marker;
    citations.push(entry);
    return `[⟦${citations.length}⟧](${CITE_HREF_PREFIX}${citations.length})`;
  });

  return { text: replaced, citations };
}

export { CITE_HREF_PREFIX };
