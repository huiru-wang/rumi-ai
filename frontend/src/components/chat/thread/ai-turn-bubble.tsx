"use client";

import { memo } from "react";
import type { AITurn, ExtractedToolCall, RenderItem } from "./types";
import {
  extractTextContent,
  extractToolCalls,
  getToolCallId,
  toolCallFingerprint,
} from "./helpers";
import { MarkdownWithCitations } from "./markdown-renderer";
import { ReasoningBlock, MessageActions } from "./message-actions";
import { ToolCallCard } from "./tool-call-card";

// ============================================================
// AITurnBubble
// ============================================================

export const AITurnBubble = memo(function AITurnBubble({
  turn,
  toolResults,
}: {
  turn: AITurn;
  toolResults?: Map<string, any>;
}) {
  const effectiveToolMessages = turn.toolMessages;

  // --- Step 1: Collect all tool calls to build the result map ---
  const allToolCallsRaw: ExtractedToolCall[] = [];
  for (const aiMsg of turn.aiMessages) {
    allToolCallsRaw.push(...extractToolCalls(aiMsg));
  }

  // Deduplicate: history can contain the same tool call twice (top-level
  // tool_calls with a real id + content array with id: ""). Keep the real-id
  // version so tool_call_id result matching works correctly.
  const realIdFingerprints = new Set(
    allToolCallsRaw.filter((tc) => tc.id).map((tc) => toolCallFingerprint(tc)),
  );
  const seenIds = new Set<string>();
  const seenFallbackFingerprints = new Set<string>();
  const deduplicatedToolCalls = allToolCallsRaw.filter((tc) => {
    const fingerprint = toolCallFingerprint(tc);
    if (tc.id) {
      if (seenIds.has(tc.id)) return false;
      seenIds.add(tc.id);
      return true;
    }
    if (realIdFingerprints.has(fingerprint)) return false;
    if (seenFallbackFingerprints.has(fingerprint)) return false;
    seenFallbackFingerprints.add(fingerprint);
    return true;
  });

  // --- Step 2: Build tool result map ---
  const toolResultMap = new Map<string, any>();
  const hasRealIds = deduplicatedToolCalls.some((tc) => tc.id && tc.id.length > 0);

  if (hasRealIds) {
    for (const toolMsg of effectiveToolMessages) {
      const callId = toolMsg.tool_call_id;
      if (callId) toolResultMap.set(callId, toolMsg);
    }
  } else {
    // Positional matching when IDs are missing
    deduplicatedToolCalls.forEach((tc, i) => {
      if (!tc.id) tc.id = `pos-${i}`;
      if (i < effectiveToolMessages.length) {
        toolResultMap.set(tc.id, effectiveToolMessages[i]);
      }
    });
  }

  // Build a lookup by fingerprint for deduplication during ordered traversal
  const dedupedByFingerprint = new Map<string, ExtractedToolCall>();
  for (const tc of deduplicatedToolCalls) {
    dedupedByFingerprint.set(toolCallFingerprint(tc), tc);
  }

  // --- Step 3: Build ordered render items ---
  const renderItems: RenderItem[] = [];
  const seenRenderIds = new Set<string>();
  let textIndex = 0;
  let allText = "";

  for (const aiMsg of turn.aiMessages) {
    // Reasoning (thinking blocks) always come first within a message
    const reasoning = aiMsg.additional_kwargs?.reasoning_content as string | undefined;
    if (reasoning) {
      renderItems.push({ kind: "reasoning", key: `reasoning-${renderItems.length}`, text: reasoning });
    }

    if (Array.isArray(aiMsg.content)) {
      // Traverse content parts in order to preserve interleaving
      for (const part of aiMsg.content as Array<Record<string, unknown>>) {
        if (part.type === "text" && typeof part.text === "string" && (part.text as string).trim()) {
          const text = part.text as string;
          const key = `text-${textIndex++}`;
          renderItems.push({ kind: "text", key, text });
          allText += (allText ? "\n\n" : "") + text;
        } else if (part.type === "tool_call" || part.type === "tool_use") {
          const partFingerprint = toolCallFingerprint({
            id: getToolCallId(part.id as string),
            name: (part.name as string) || "",
            args: (part.args as Record<string, unknown>) ?? {},
          });
          const canonicalTc = dedupedByFingerprint.get(partFingerprint);
          if (!canonicalTc) continue;

          const renderId = canonicalTc.id || partFingerprint;
          if (seenRenderIds.has(renderId)) continue;
          seenRenderIds.add(renderId);

          renderItems.push({
            kind: "toolcall",
            key: `tc-${renderId}`,
            tc: canonicalTc,
            result: toolResultMap.get(canonicalTc.id || "") ?? toolResults?.get(canonicalTc.id || ""),
          });
        }
      }
    } else {
      // Fallback: plain string content
      const text = extractTextContent(aiMsg.content);
      if (text.trim()) {
        const key = `text-${textIndex++}`;
        renderItems.push({ kind: "text", key, text });
        allText += (allText ? "\n\n" : "") + text;
      }
      // Also emit any top-level tool_calls not already rendered via content array
      for (const tc of extractToolCalls(aiMsg)) {
        const renderId = tc.id || toolCallFingerprint(tc);
        if (seenRenderIds.has(renderId)) continue;
        seenRenderIds.add(renderId);
        const canonical = dedupedByFingerprint.get(toolCallFingerprint(tc)) ?? tc;
        renderItems.push({
          kind: "toolcall",
          key: `tc-${renderId}`,
          tc: canonical,
          result: toolResultMap.get(canonical.id || "") ?? toolResults?.get(canonical.id || ""),
        });
      }
    }
  }

  // Emit any tool calls from top-level tool_calls that weren't captured by
  // the content-array traversal (e.g. streamed messages that only have tool_calls)
  for (const tc of deduplicatedToolCalls) {
    const renderId = tc.id || toolCallFingerprint(tc);
    if (seenRenderIds.has(renderId)) continue;
    seenRenderIds.add(renderId);
    renderItems.push({
      kind: "toolcall",
      key: `tc-${renderId}`,
      tc,
      result: toolResultMap.get(tc.id || "") ?? toolResults?.get(tc.id || ""),
    });
  }

  if (renderItems.length === 0) return null;

  return (
    <div className="group">
      <div className="min-w-0 space-y-2">
        {renderItems.map((item) => {
          if (item.kind === "reasoning") {
            return <ReasoningBlock key={item.key} text={item.text} />;
          }
          if (item.kind === "text") {
            return (
              <div key={item.key} className="prose prose-sm max-w-none">
                <MarkdownWithCitations text={item.text} />
              </div>
            );
          }
          if (item.kind === "toolcall") {
            return (
              <ToolCallCard
                key={item.key}
                toolCall={item.tc}
                result={item.result}
              />
            );
          }
          return null;
        })}

        {allText && <MessageActions content={allText} />}
      </div>
    </div>
  );
}, (prev, next) => {
  // Skip re-render if the turn has the same ID and identical message references.
  if (prev.turn.id !== next.turn.id) return false;
  if (prev.turn.aiMessages.length !== next.turn.aiMessages.length) return false;
  if (prev.turn.toolMessages.length !== next.turn.toolMessages.length) return false;
  if (prev.toolResults !== next.toolResults) return false;
  return prev.turn.aiMessages.every((m, i) => m === next.turn.aiMessages[i]) &&
    prev.turn.toolMessages.every((m, i) => m === next.turn.toolMessages[i]);
});
