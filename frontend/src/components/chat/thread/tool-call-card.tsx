"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import remarkGfm from "remark-gfm";
import { Loader2, ChevronDown } from "lucide-react";
import { useStreamContext } from "../assistant";
import { getMessageDetail } from "@/lib/api";
import type { ExtractedToolCall, ToolDisplayContext, ToolDisplayConfig } from "./types";
import {
  truncateText,
  getToolArgString,
  extractToolResultText,
  tryParseJSONObject,
} from "./helpers";

// ============================================================
// Constants
// ============================================================

const TOOL_LABELS: Record<string, string> = {
  terminal: "命令执行",
  rag_search: "知识库检索",
  load_skill: "读取技能",
  save_ppt: "保存PPT",
  save_narration: "保存口播稿",
  get_ppt_detail: "获取PPT详情",
  get_style_template: "获取风格模版",
  clarify_form: "信息收集",
};

const SKILL_NAME_LABELS: Record<string, string> = {
  "html-ppt": "PPT技能",
  "narrate": "口播稿技能",
};

function getToolLabel(name: string): string {
  return TOOL_LABELS[name] || name;
}

// ============================================================
// Helper components
// ============================================================

function ToolTextBlock({ value }: { value: string }) {
  return (
    <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-md border border-border/50 bg-background/70 px-3 py-2 text-[11px] leading-relaxed text-muted-foreground">
      {value || "无返回内容"}
    </pre>
  );
}

// ============================================================
// Tool display config
// ============================================================

const DEFAULT_TOOL_DISPLAY: ToolDisplayConfig = {
  label: ({ toolCall }) => getToolLabel(toolCall.name),
  expandable: false,
};

const TOOL_DISPLAY_CONFIG: Record<string, ToolDisplayConfig> = {
  rag_search: {
    label: () => "知识库检索",
    expandable: true,
    summary: ({ toolCall }) => {
      const query = getToolArgString(toolCall.args, ["query"]);
      return query ? `查询：${truncateText(query)}` : "";
    },
    details: ({ result }) => <ToolTextBlock value={extractToolResultText(result)} />,
  },
  terminal: {
    label: () => "命令执行",
    expandable: false,
    summary: () => "",
  },
  load_skill: {
    label: ({ toolCall }) => {
      const skillName = getToolArgString(toolCall.args, ["skill_name", "name"]);
      const displayName = skillName ? (SKILL_NAME_LABELS[skillName] || skillName) : "";
      const filePaths = toolCall.args["file_paths"] as string[] | undefined;
      if (filePaths && filePaths.length > 0) {
        return displayName ? `读取技能：${displayName}` : "读取技能";
      }
      return displayName ? `读取技能：${displayName}` : "读取技能";
    },
    expandable: false,
    summary: ({ toolCall }) => {
      const skillName = getToolArgString(toolCall.args, ["skill_name", "name"]);
      const filePaths = toolCall.args["file_paths"] as string[] | undefined;
      if (filePaths && filePaths.length > 0) {
        return filePaths.join(", ");
      }
      return "SKILL.md";
    },
    details: ({ result }) => {
      const rawText = extractToolResultText(result);
      const mdComponents = {
        code: ({ className, children, ...rest }: any) => {
          const match = /language-(\w+)/.exec(className || "");
          const codeString = String(children).replace(/\n$/, "");
          if (match) {
            return (
              <SyntaxHighlighter
                style={oneDark}
                language={match[1]}
                PreTag="div"
                customStyle={{ margin: 0, borderRadius: "0.5rem", fontSize: "0.85em" }}
              >
                {codeString}
              </SyntaxHighlighter>
            );
          }
          return <code className={className} {...rest}>{children}</code>;
        },
        table: ({ children, ...rest }: any) => (
          <div className="overflow-x-auto">
            <table className="w-max min-w-full" {...rest}>{children}</table>
          </div>
        ),
        h1: ({ children, ...rest }: any) => <h1 className="text-lg font-bold mt-4 mb-2" {...rest}>{children}</h1>,
        h2: ({ children, ...rest }: any) => <h2 className="text-base font-semibold mt-3 mb-2" {...rest}>{children}</h2>,
        h3: ({ children, ...rest }: any) => <h3 className="text-sm font-medium mt-2 mb-1" {...rest}>{children}</h3>,
        p: ({ children, ...rest }: any) => <p className="my-1" {...rest}>{children}</p>,
        ul: ({ children, ...rest }: any) => <ul className="list-disc list-inside my-1 space-y-1" {...rest}>{children}</ul>,
        ol: ({ children, ...rest }: any) => <ol className="list-decimal list-inside my-1 space-y-1" {...rest}>{children}</ol>,
        li: ({ children, ...rest }: any) => <li className="text-xs" {...rest}>{children}</li>,
        blockquote: ({ children, ...rest }: any) => <blockquote className="border-l-2 border-accent/50 pl-2 my-1 text-xs" {...rest}>{children}</blockquote>,
        a: ({ href, children, ...rest }: any) => <a href={href} className="text-accent underline" target="_blank" rel="noopener noreferrer" {...rest}>{children}</a>,
      };

      const data = tryParseJSONObject(rawText);
      if (data?.files) {
        const entries = Object.entries(data.files);
        if (entries.length === 0) {
          return <ToolTextBlock value="(no content)" />;
        }
        return (
          <div className="max-h-96 overflow-y-auto space-y-3">
            {entries.map(([path, content]) => (
              <div key={path}>
                <p className="text-[10px] text-accent mb-1 font-medium">{path}</p>
                <div className="rounded border border-border/40 bg-background/50 p-2 max-h-64 overflow-y-auto">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                    {String(content ?? "")}
                  </ReactMarkdown>
                </div>
              </div>
            ))}
          </div>
        );
      }
      if (typeof data?.content === "string") {
        let content = data.content;
        if (content.startsWith("---")) {
          const endIdx = content.indexOf("---", 3);
          if (endIdx !== -1) {
            content = content.slice(endIdx + 3).trim();
          }
        }
        return (
          <div className="max-h-96 overflow-y-auto rounded border border-border/40 bg-background/50 p-2">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
              {content}
            </ReactMarkdown>
          </div>
        );
      }
      return <ToolTextBlock value={rawText} />;
    },
  },
  save_ppt: {
    label: () => "保存PPT",
    expandable: false,
    summary: ({ toolCall }) => {
      const filename = getToolArgString(toolCall.args, ["filename"]);
      if (filename) return filename;
      const title = getToolArgString(toolCall.args, ["title"]);
      if (title) {
        const safeTitle = title.replace(/ /g, "_").replace(/\//g, "_");
        return `${safeTitle}.html`;
      }
      return "";
    },
  },
  save_narration: {
    label: () => "保存口播稿",
    expandable: false,
    summary: ({ toolCall }) => {
      return getToolArgString(toolCall.args, ["title"]);
    },
  },
  get_ppt_detail: {
    label: () => "获取PPT详情",
    expandable: false,
    summary: () => "",
  },
  get_style_template: {
    label: () => "获取风格模版",
    expandable: false,
    summary: () => "",
  },
  clarify_form: {
    label: () => "信息收集",
    expandable: true,
  },
};

// ============================================================
// ClarifyFormSummary
// ============================================================

function ClarifyFormSummary({
  toolCall,
  result,
}: {
  toolCall: ExtractedToolCall;
  result: any;
}) {
  const { threadId } = useStreamContext();
  const [expanded, setExpanded] = useState(false);
  const [loadedResult, setLoadedResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const title = (toolCall.args as Record<string, unknown>)?.title as string || "信息收集";
  const fields = (toolCall.args as Record<string, unknown>)?.fields as Array<{
    name: string;
    label: string;
  }> | undefined;

  const needsLazyLoad = result && result.content === "" && !!result.id && !!threadId;
  const resultText = loadedResult !== null ? loadedResult : extractToolResultText(result);

  const handleToggle = async () => {
    if (!expanded && needsLazyLoad && loadedResult === null) {
      setLoading(true);
      try {
        const detail = await getMessageDetail(threadId!, result.id);
        setLoadedResult(extractToolResultText(detail));
      } catch { /* ignore */ }
      setLoading(false);
    }
    setExpanded(!expanded);
  };

  let userValues: Record<string, unknown> = {};
  try {
    userValues = JSON.parse(resultText);
  } catch {
    const dictMatch = resultText.match(/用户填写的表单结果:\s*(\{[\s\S]*\})/);
    if (dictMatch) {
      try {
        const jsonStr = dictMatch[1]
          .replace(/'/g, '"')
          .replace(/True/g, "true")
          .replace(/False/g, "false")
          .replace(/None/g, "null");
        userValues = JSON.parse(jsonStr);
      } catch { /* use empty */ }
    }
  }

  if (userValues.cancelled) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-border/50 bg-muted/30 px-3 py-1.5 text-xs text-muted-foreground not-prose">
        <span className="text-yellow-400">✗</span>
        <span className="shrink-0 font-medium">信息收集</span>
        <span className="min-w-0 flex-1 truncate text-muted-foreground/80">{title} — 已取消</span>
      </div>
    );
  }

  const entries = fields
    ? fields
        .map((field) => ({
          label: field.label,
          value: userValues[field.name],
        }))
        .filter((entry) => entry.value !== undefined && entry.value !== "")
    : Object.entries(userValues).map(([key, value]) => ({
        label: key,
        value,
      }));

  return (
    <div className="overflow-hidden rounded-lg border border-border/50 bg-muted/30 text-xs text-muted-foreground not-prose">
      <button
        type="button"
        onClick={handleToggle}
        className="flex w-full items-center gap-2 px-3 py-1.5 text-left cursor-pointer hover:bg-muted/40"
      >
        <span className="text-green-400">✓</span>
        <span className="shrink-0 font-medium">信息收集</span>
        <span className="min-w-0 flex-1 truncate text-muted-foreground/80">
          {title}
        </span>
        <ChevronDown
          size={13}
          className={`ml-auto shrink-0 transition-transform ${expanded ? "rotate-180" : ""}`}
        />
      </button>
      {expanded && (
        <div className="border-t border-border/40 px-3 py-2 space-y-1.5">
          {loading ? (
            <div className="flex items-center gap-2 py-1 text-muted-foreground/60">
              <Loader2 size={12} className="animate-spin" />
              <span>加载中...</span>
            </div>
          ) : entries.length === 0 ? (
            <div className="text-muted-foreground/60">暂无数据</div>
          ) : (
            entries.map(({ label, value }) => (
              <div key={label} className="flex items-start gap-2">
                <span className="shrink-0 text-muted-foreground/70 min-w-[5rem]">
                  {label}:
                </span>
                <span className="text-foreground/90">
                  {Array.isArray(value) ? value.join("、") : String(value)}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================
// ToolCallCard
// ============================================================

export function ToolCallCard({
  toolCall,
  result,
}: {
  toolCall: ExtractedToolCall;
  result: any;
}) {
  const { threadId } = useStreamContext();
  const name = toolCall.name;
  const isDone = !!result;
  const [expanded, setExpanded] = useState(false);
  const [loadedResult, setLoadedResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  // clarify_form: 未完成时由 InterruptBlock 渲染交互式表单；已完成时显示只读摘要
  if (name === "clarify_form") {
    if (!isDone) return null;
    return <ClarifyFormSummary toolCall={toolCall} result={result} />;
  }

  // Detect lazy-loadable result: backend stripped tool message content in list API
  const needsLazyLoad = isDone && result && result.content === "" && !!result.id && !!threadId;
  const effectiveResult = loadedResult ?? result;

  const context: ToolDisplayContext = { toolCall, result: effectiveResult, isDone };
  const config = TOOL_DISPLAY_CONFIG[name] ?? DEFAULT_TOOL_DISPLAY;
  const expandable =
    typeof config.expandable === "function"
      ? config.expandable(context)
      : config.expandable;
  const label = config.label(context);
  const summary = config.summary?.(context);
  const details = config.details?.(context);
  const canExpand = isDone && expandable && !!details;

  if (!isDone) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-border/50 bg-muted/30 px-3 py-1.5 text-xs text-muted-foreground not-prose">
        <Loader2 size={13} className="animate-spin" />
        <span className="font-medium">{label}...</span>
        {summary && <span className="min-w-0 truncate text-muted-foreground/80">{summary}</span>}
      </div>
    );
  }

  const handleToggle = async () => {
    if (!expanded && needsLazyLoad && !loadedResult) {
      setLoading(true);
      try {
        const detail = await getMessageDetail(threadId!, result.id);
        setLoadedResult(detail);
      } catch { /* ignore */ }
      setLoading(false);
    }
    if (canExpand) setExpanded((value) => !value);
  };

  return (
    <div className="overflow-hidden rounded-lg border border-border/50 bg-muted/30 text-xs text-muted-foreground not-prose">
      <button
        type="button"
        onClick={handleToggle}
        disabled={!canExpand && !needsLazyLoad}
        className={`flex w-full items-center gap-2 px-3 py-1.5 text-left ${canExpand || needsLazyLoad ? "cursor-pointer hover:bg-muted/40" : "cursor-default"
          }`}
      >
        <span className="text-green-400">✓</span>
        <span className="shrink-0 font-medium">{label}</span>
        {summary && (
          <span className="min-w-0 flex-1 truncate text-muted-foreground/80">
            {summary}
          </span>
        )}
        {canExpand && (
          <ChevronDown
            size={13}
            className={`ml-auto shrink-0 transition-transform ${expanded ? "rotate-180" : ""
              }`}
          />
        )}
      </button>
      {canExpand && expanded && (
        <div className="border-t border-border/40 px-3 py-2">
          {loading ? (
            <div className="flex items-center gap-2 py-1 text-muted-foreground/60">
              <Loader2 size={12} className="animate-spin" />
              <span>加载中...</span>
            </div>
          ) : details}
        </div>
      )}
    </div>
  );
}
