import type { ReactNode } from "react";

export interface ExtractedToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
}

export interface AITurn {
  id: string;
  aiMessages: any[];
  toolMessages: any[];
}

export interface DisplayRun {
  key: string;
  run_id: string | null;
  status: "history" | "active";
  messages: any[];
}

export type RenderItem =
  | { kind: "reasoning"; key: string; text: string }
  | { kind: "text"; key: string; text: string }
  | { kind: "toolcall"; key: string; tc: ExtractedToolCall; result: any };

export interface SlashCommand {
  command: string;
  label: string;
  description: string;
  icon: ReactNode;
  placeholder?: string;
}

export interface ToolDisplayContext {
  toolCall: ExtractedToolCall;
  result: any;
  isDone: boolean;
}

export interface ToolDisplayConfig {
  label: (ctx: ToolDisplayContext) => string;
  expandable: boolean | ((ctx: ToolDisplayContext) => boolean);
  summary?: (ctx: ToolDisplayContext) => ReactNode;
  details?: (ctx: ToolDisplayContext) => ReactNode;
}

export interface CitationEntry {
  docName: string;
  detail: string;
}
