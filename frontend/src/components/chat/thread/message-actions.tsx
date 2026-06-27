"use client";

import { useState, useCallback } from "react";
import {
  Brain,
  ChevronDown,
  Copy,
  Check,
  ThumbsUp,
  ThumbsDown,
} from "lucide-react";

// ============================================================
// ReasoningBlock
// ============================================================

export function ReasoningBlock({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  if (!text?.trim()) return null;
  const preview =
    text.length > 120 ? text.slice(0, 120) + "..." : text;

  return (
    <div className="rounded-lg border border-accent/20 bg-accent/5 not-prose">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 px-3 py-2 text-xs text-accent/80 hover:text-accent"
      >
        <Brain size={13} />
        <span>思考过程 ({text.length} 字符)</span>
        <ChevronDown
          size={13}
          className={`ml-auto transition-transform ${expanded ? "rotate-180" : ""}`}
        />
      </button>
      {expanded ? (
        <pre className="border-t border-accent/10 px-3 py-2 text-xs text-muted-foreground whitespace-pre-wrap max-h-60 overflow-y-auto">
          {text}
        </pre>
      ) : (
        <p className="px-3 pb-2 text-[11px] text-muted-foreground/70 italic">
          {preview}
        </p>
      )}
    </div>
  );
}

// ============================================================
// MessageActions
// ============================================================

export function MessageActions({ content }: { content: string }) {
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<"like" | "dislike" | null>(null);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard may fail */
    }
  }, [content]);

  return (
    <div className="mt-1.5 flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
      <button
        onClick={handleCopy}
        className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground"
        title="复制消息"
      >
        {copied ? (
          <Check size={14} className="text-green-400" />
        ) : (
          <Copy size={14} />
        )}
      </button>
      <button
        onClick={() =>
          setFeedback(feedback === "like" ? null : "like")
        }
        className={`rounded-md p-1 transition-colors ${feedback === "like"
          ? "text-green-400"
          : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
          }`}
        title="有帮助"
      >
        <ThumbsUp size={14} />
      </button>
      <button
        onClick={() =>
          setFeedback(feedback === "dislike" ? null : "dislike")
        }
        className={`rounded-md p-1 transition-colors ${feedback === "dislike"
          ? "text-red-400"
          : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
          }`}
        title="没有帮助"
      >
        <ThumbsDown size={14} />
      </button>
    </div>
  );
}

// ============================================================
// TypingIndicator
// ============================================================

export function TypingIndicator() {
  return (
    <div className="flex items-center gap-1.5">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 rounded-full bg-muted-foreground/50 animate-bounce"
          style={{ animationDelay: `${i * 150}ms` }}
        />
      ))}
    </div>
  );
}

// ============================================================
// EmptyState
// ============================================================

export function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-3 py-20 text-center">
      <div className="flex h-12 w-12 items-center justify-center text-accent">
        <svg viewBox="0 0 120 120" className="h-6 w-6" aria-hidden="true">
          <path d="M60,22 C82,22 100,40 100,62 C100,84 82,102 60,102 C45,102 32,94 25,82" stroke="currentColor" strokeWidth="4" fill="none" strokeLinecap="round"/>
          <path d="M60,42 C71,42 80,51 80,62 C80,73 71,82 60,82 C52,82 46,78 43,72" stroke="#C75B3A" strokeWidth="3" fill="none" strokeLinecap="round"/>
          <circle cx="60" cy="62" r="4" fill="currentColor"/>
        </svg>
      </div>
      <div className="max-w-sm space-y-2">
        <p className="text-sm text-foreground">
          我是 <span className="font-medium">Rumi</span> —— 文档知识的 AI 工作台助手，帮你把文档变成知识、演示和声音。
        </p>
        <p className="text-sm text-muted-foreground">有什么我可以帮你的吗？</p>
      </div>
    </div>
  );
}
