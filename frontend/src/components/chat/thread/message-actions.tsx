"use client";

import { useState, useCallback } from "react";
import {
  Brain,
  ChevronDown,
  Copy,
  Check,
  ListChecks,
  Mic,
  Presentation,
  Search,
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

const EMPTY_STATE_ACTIONS = [
  {
    icon: Search,
    title: "问文档内容",
    examples: ["总结这份报告的核心结论", "找出关于市场规模的依据"],
  },
  {
    icon: ListChecks,
    title: "整理知识结构",
    examples: ["整理成一页决策摘要", "提炼观点、风险和行动项"],
  },
  {
    icon: Presentation,
    title: "生成演示 PPT",
    examples: ["生成 8 页路演 PPT", "做一份产品介绍汇报"],
  },
  {
    icon: Mic,
    title: "生成口播和音频",
    examples: ["给 PPT 生成 5 分钟口播稿", "合成自然语气的讲解音频"],
  },
];

export function EmptyState() {
  return (
    <div className="flex flex-col items-center py-14 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-accent/20 bg-accent/10 text-accent shadow-sm">
        <svg viewBox="0 0 120 120" className="h-7 w-7" aria-hidden="true">
          <path d="M60,22 C82,22 100,40 100,62 C100,84 82,102 60,102 C45,102 32,94 25,82" stroke="currentColor" strokeWidth="4" fill="none" strokeLinecap="round" />
          <path d="M60,42 C71,42 80,51 80,62 C80,73 71,82 60,82 C52,82 46,78 43,72" stroke="#C75B3A" strokeWidth="3" fill="none" strokeLinecap="round" />
          <circle cx="60" cy="62" r="4" fill="currentColor" />
        </svg>
      </div>
      <div className="mt-5 max-w-xl space-y-2">
        <h2 className="text-lg font-semibold tracking-normal text-foreground">
          我是 Rumi，把文档变成知识、演示和声音
        </h2>
        <p className="text-sm leading-6 text-muted-foreground">
          上传 PDF、Word 或 Markdown 后，你可以直接让我整理资料、回答问题、生成 PPT，或为演示稿配出口播音频。
        </p>
      </div>
      <div className="mt-6 rounded-lg border border-accent/25 bg-accent/10 px-4 py-2.5 text-sm font-medium text-foreground">
        第一步：先在左侧上传文档，然后在对话框输入你的任务。
      </div>
      <div className="mt-7 grid w-full max-w-2xl grid-cols-1 gap-3 sm:grid-cols-2">
        {EMPTY_STATE_ACTIONS.map((action) => {
          const Icon = action.icon;
          return (
            <div
              key={action.title}
              className="rounded-lg border border-border bg-muted/25 p-4 text-left transition-colors hover:border-accent/30 hover:bg-muted/35"
            >
              <div className="flex items-center gap-2.5">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent">
                  <Icon size={16} />
                </span>
                <h3 className="text-sm font-medium text-foreground">
                  {action.title}
                </h3>
              </div>
              <div className="mt-3 space-y-1.5">
                {action.examples.map((example) => (
                  <p key={example} className="text-xs leading-5 text-muted-foreground">
                    “{example}”
                  </p>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
