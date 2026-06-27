"use client";

import { memo } from "react";
import { FileOutput, Mic } from "lucide-react";
import type { SlashCommand } from "./types";

// ============================================================
// Constants (shared with chat-input)
// ============================================================

const PPT_REF_TAG_REGEX = /\[ppt-ref:([a-f0-9-]+):([^\]]+)\]/;

export const SLASH_COMMANDS: SlashCommand[] = [
  {
    command: "/ppt",
    label: "生成PPT",
    description: "基于知识库文档生成 HTML 演示文稿",
    icon: <FileOutput size={14} />,
    placeholder: "还可以输入PPT主题、页数、内容要求...",
  },
  {
    command: "/narrate",
    label: "生成口播稿",
    description: "基于PPT大纲生成口播稿并合成音频",
    icon: <Mic size={14} />,
    placeholder: "还可以输入口播稿风格、时长、内容详略要求...",
  },
];

// ============================================================
// HumanBubble
// ============================================================

export const HumanBubble = memo(function HumanBubble({
  text,
  pending,
}: {
  text: string;
  pending?: boolean;
}) {
  // Extract PPT reference tag if present
  const pptRefMatch = text.match(PPT_REF_TAG_REGEX);
  const pptRefTitle = pptRefMatch ? pptRefMatch[2] : null;
  // Remove the tag from display text (collapse residual double spaces)
  const cleanText = pptRefMatch
    ? text.replace(PPT_REF_TAG_REGEX, "").replace(/  +/g, " ").trim()
    : text;

  // Parse "/command rest" pattern to render pill + text
  // Allow command to be sent alone (e.g. "/ppt") or with additional text
  const slashMatch = cleanText.match(/^(\/\w+)(?:\s([\s\S]*))?$/);
  const command = slashMatch
    ? SLASH_COMMANDS.find((c) => c.command === slashMatch[1])
    : null;
  const displayText = command ? (slashMatch![2] || "") : cleanText;

  return (
    <div className="flex justify-end">
      <div
        className={`max-w-[80%] rounded-2xl rounded-br-md bg-accent/20 px-4 py-2.5 text-sm text-foreground ${pending ? "opacity-70" : ""
          }`}
      >
        {command && (
          <span className="inline-flex items-center gap-1 rounded-full bg-accent/15 border border-accent/30 px-2 py-0.5 text-xs text-accent mr-2 align-middle">
            {command.icon}
            <span className="font-medium">{command.label}</span>
            {pptRefTitle && (
              <span className="text-accent/70">：{pptRefTitle}</span>
            )}
          </span>
        )}
        <span className="whitespace-pre-wrap">{displayText}</span>
      </div>
    </div>
  );
}, (prev, next) => prev.text === next.text && prev.pending === next.pending);
