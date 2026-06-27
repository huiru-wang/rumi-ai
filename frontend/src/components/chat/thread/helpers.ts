import type { ExtractedToolCall, AITurn } from "./types";

// ============================================================
// Text extraction
// ============================================================

export function extractTextContent(content: unknown): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .filter(
        (part): part is { type: "text"; text: string } =>
          typeof part === "object" &&
          part !== null &&
          part.type === "text" &&
          typeof part.text === "string",
      )
      .map((part) => part.text)
      .join("");
  }
  return "";
}

// ============================================================
// Tool call utilities
// ============================================================

export function getToolCallId(value: unknown): string {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

export function toolCallFingerprint(toolCall: ExtractedToolCall): string {
  return `${toolCall.name}:${stableStringify(toolCall.args)}`;
}

export function extractToolCalls(message: any): ExtractedToolCall[] {
  // Prefer dedicated tool_calls property
  if (Array.isArray(message.tool_calls) && message.tool_calls.length > 0) {
    return message.tool_calls
      .filter((toolCall: any) => typeof toolCall?.name === "string")
      .map((toolCall: any) => ({
        id: getToolCallId(toolCall.id),
        name: toolCall.name,
        args: toolCall.args ?? {},
      }));
  }
  // Fallback: extract from content array (useStream puts them here)
  if (Array.isArray(message.content)) {
    return message.content
      .filter(
        (part: any) =>
          typeof part === "object" &&
          part !== null &&
          (part.type === "tool_call" || part.type === "tool_use") &&
          typeof part.name === "string",
      )
      .map((part: any) => ({
        // Historical content tool_call parts may have id: ""; do not invent
        // a real-looking id because tool messages match by tool_call_id.
        id: getToolCallId(part.id),
        name: part.name,
        args: part.args ?? {},
      }));
  }
  return [];
}

// ============================================================
// Serialization
// ============================================================

export function stableStringify(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(",")}]`;
  }
  if (typeof value === "object" && value !== null) {
    return `{${Object.keys(value as Record<string, unknown>)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify((value as Record<string, unknown>)[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

export function tryParseJSONObject(rawText: string): Record<string, any> | null {
  const trimmed = rawText.trim();
  if (!trimmed.startsWith("{") || !trimmed.endsWith("}")) return null;
  try {
    const parsed = JSON.parse(trimmed);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

// ============================================================
// Message filtering
// ============================================================

export function isHiddenMessage(message: any): boolean {
  if (message?.name === "summary") return true;
  const kwargs = message?.additional_kwargs;
  if (kwargs?.message_hidden) return true;
  if (kwargs?.lc_source === "summarization") return true;
  const content = typeof message?.content === "string" ? message.content : "";
  return content.startsWith("Here is a summary of the conversation to date:");
}

export function isStreamingContent(messages: any[]): boolean {
  if (messages.length === 0) return false;
  const last = messages[messages.length - 1];
  const type = last._getType?.() || last.type;
  if (type === "ai") {
    const text = extractTextContent(last.content);
    const toolCalls = extractToolCalls(last);
    return text.length > 0 || toolCalls.length > 0;
  }
  // tool message means we're mid-turn, AI will continue
  if (type === "tool") return true;
  return false;
}

// ============================================================
// Scroll helpers
// ============================================================

export function isNearBottom(element: HTMLElement): boolean {
  return element.scrollHeight - element.scrollTop - element.clientHeight < 120;
}

// ============================================================
// Message grouping
// ============================================================

export function groupMessagesIntoTurns(messages: any[]) {
  const turns: Array<{ type: "human"; text: string; id: string } | { type: "ai-turn"; turn: AITurn }> = [];
  let currentTurn: AITurn | null = null;

  for (const msg of messages) {
    const msgType = msg._getType?.() || msg.type;

    if (msgType === "human") {
      if (currentTurn) {
        turns.push({ type: "ai-turn", turn: currentTurn });
        currentTurn = null;
      }
      turns.push({
        type: "human",
        text: typeof msg.content === "string" ? msg.content : "",
        id: msg.id ?? `human-${turns.length}`,
      });
    } else if (msgType === "ai") {
      if (!currentTurn) {
        currentTurn = { id: msg.id ?? `turn-${turns.length}`, aiMessages: [], toolMessages: [] };
      }
      currentTurn.aiMessages.push(msg);
    } else if (msgType === "tool") {
      if (!currentTurn) {
        currentTurn = { id: `turn-${turns.length}`, aiMessages: [], toolMessages: [] };
      }
      currentTurn.toolMessages.push(msg);
    }
  }

  if (currentTurn) {
    turns.push({ type: "ai-turn", turn: currentTurn });
  }

  return turns;
}

// ============================================================
// Tool result helpers
// ============================================================

export function truncateText(text: string, max = 90): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= max) return normalized;
  return `${normalized.slice(0, max - 1)}…`;
}

export function getToolArgString(args: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const value = args[key];
    if (typeof value === "string" && value.trim()) return value.trim();
    if (typeof value === "number" || typeof value === "boolean") {
      return String(value);
    }
  }
  return "";
}

export function extractToolResultText(result: unknown): string {
  if (!result) return "";
  if (typeof result === "string") return result;
  if (typeof result === "object" && result !== null) {
    const content = (result as { content?: unknown }).content;
    if (typeof content === "string") return content;
    if (Array.isArray(content)) {
      return content
        .map((part) => {
          if (typeof part === "string") return part;
          if (
            typeof part === "object" &&
            part !== null &&
            "text" in part &&
            typeof (part as { text?: unknown }).text === "string"
          ) {
            return (part as { text: string }).text;
          }
          return "";
        })
        .filter(Boolean)
        .join("\n");
    }
  }
  return "";
}
