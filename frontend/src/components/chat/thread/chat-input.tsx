"use client";

import { useState, useCallback, useRef, useEffect, type FormEvent } from "react";
import { SendHorizontal, Square, Zap } from "lucide-react";
import { useStreamContext } from "../assistant";
import type { SlashCommand } from "./types";
import { SLASH_COMMANDS } from "./human-bubble";
import { shouldFocusAfterLoadingChange } from "./chat-input-focus";

// ============================================================
// SlashCommandMenu
// ============================================================

function SlashCommandMenu({
  filter,
  selectedIndex,
  onSelect,
}: {
  filter: string;
  selectedIndex: number;
  onSelect: (cmd: SlashCommand) => void;
}) {
  const filtered = SLASH_COMMANDS.filter(
    (cmd) =>
      cmd.command.includes(filter.toLowerCase()) ||
      cmd.label.includes(filter),
  );

  if (filtered.length === 0) return null;

  return (
    <div className="absolute bottom-full left-0 right-0 mb-2 rounded-xl border border-border bg-muted shadow-xl overflow-hidden z-50">
      <div className="px-3 py-1.5 text-[11px] text-muted-foreground/60 uppercase tracking-wider border-b border-border/50">
        可用命令
      </div>
      {filtered.map((cmd, index) => (
        <button
          key={cmd.command}
          type="button"
          onMouseDown={(e) => {
            e.preventDefault();
            onSelect(cmd);
          }}
          className={`flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors ${index === selectedIndex
            ? "bg-accent/15 text-foreground"
            : "text-muted-foreground hover:bg-muted/30 hover:text-foreground"
            }`}
        >
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent">
            {cmd.icon}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">{cmd.label}</span>
            </div>
            <p className="text-xs text-muted-foreground/70 truncate">
              {cmd.description}
            </p>
          </div>
        </button>
      ))}
    </div>
  );
}

// ============================================================
// ChatInput
// ============================================================

export function ChatInput() {
  const [text, setText] = useState("");
  const [activeCommand, setActiveCommand] = useState<SlashCommand | null>(null);
  const [pillSubtitle, setPillSubtitle] = useState("");
  const [showCommands, setShowCommands] = useState(false);
  const [selectedCmdIndex, setSelectedCmdIndex] = useState(0);
  const { submit, stop, isLoading, externalCommand, onExternalCommandConsumed } = useStreamContext();
  const inputRef = useRef<HTMLInputElement>(null);
  const pptRefTagRef = useRef<string | null>(null);
  const wasLoadingRef = useRef(isLoading);

  // Listen for external command injection (e.g. from Mic button on PPT card)
  useEffect(() => {
    if (externalCommand) {
      const match = SLASH_COMMANDS.find((c) => c.command === externalCommand.command);
      if (match) {
        setActiveCommand(match);
        setPillSubtitle(externalCommand.subtitle || "");
        // Store PPT reference tag for embedding in message content
        const taskId = externalCommand.metadata?.pptTaskId;
        if (taskId && externalCommand.subtitle) {
          pptRefTagRef.current = `[ppt-ref:${taskId}:${externalCommand.subtitle}]`;
        } else {
          pptRefTagRef.current = null;
        }
        setText("");
        setShowCommands(false);
        inputRef.current?.focus();
      }
      onExternalCommandConsumed?.();
    }
  }, [externalCommand, onExternalCommandConsumed]);

  useEffect(() => {
    const wasLoading = wasLoadingRef.current;
    wasLoadingRef.current = isLoading;
    if (!shouldFocusAfterLoadingChange({ wasLoading, isLoading })) return;

    const focusId = window.requestAnimationFrame(() => {
      inputRef.current?.focus();
    });
    return () => window.cancelAnimationFrame(focusId);
  }, [isLoading]);

  const slashFilter = text.startsWith("/") ? text : "";
  const filteredCommands = SLASH_COMMANDS.filter(
    (cmd) =>
      cmd.command.includes(slashFilter.toLowerCase()) ||
      cmd.label.includes(slashFilter),
  );
  const isMenuVisible = showCommands && !activeCommand && filteredCommands.length > 0;

  const selectCommand = useCallback((cmd: SlashCommand) => {
    setActiveCommand(cmd);
    setPillSubtitle("");
    pptRefTagRef.current = null;
    setText("");
    setShowCommands(false);
    setSelectedCmdIndex(0);
    inputRef.current?.focus();
  }, []);

  const clearCommand = useCallback(() => {
    setActiveCommand(null);
    setPillSubtitle("");
    pptRefTagRef.current = null;
  }, []);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setText(value);
    if (!activeCommand && value.startsWith("/")) {
      setShowCommands(true);
      setSelectedCmdIndex(0);
    } else {
      setShowCommands(false);
    }
  }, [activeCommand]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      // Backspace on empty input clears the active pill
      if (e.key === "Backspace" && text === "" && activeCommand) {
        e.preventDefault();
        clearCommand();
        return;
      }
      if (!isMenuVisible) return;
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedCmdIndex((prev) =>
          prev <= 0 ? filteredCommands.length - 1 : prev - 1,
        );
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedCmdIndex((prev) =>
          prev >= filteredCommands.length - 1 ? 0 : prev + 1,
        );
      } else if (e.key === "Tab" || e.key === "Enter") {
        e.preventDefault();
        const cmd = filteredCommands[selectedCmdIndex];
        if (cmd) selectCommand(cmd);
      } else if (e.key === "Escape") {
        setShowCommands(false);
      }
    },
    [isMenuVisible, filteredCommands, selectedCmdIndex, selectCommand, text, activeCommand, clearCommand],
  );

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (isMenuVisible) return;
    if (isLoading) return;
    // Allow slash command to be sent alone, or with additional text
    const userText = text.trim();
    let content: string;
    if (activeCommand) {
      // Embed PPT reference tag right after command for persistent context
      const tag = (pillSubtitle && pptRefTagRef.current) ? ` ${pptRefTagRef.current}` : "";
      content = userText
        ? `${activeCommand.command}${tag} ${userText}`
        : `${activeCommand.command}${tag}`;
    } else {
      content = userText;
    }
    if (!content) return;
    submit(content);
    setText("");
    setActiveCommand(null);
    setPillSubtitle("");
    pptRefTagRef.current = null;
    setShowCommands(false);
  };

  const skipNextBlurRef = useRef(false);

  const openSkillMenu = useCallback(() => {
    if (activeCommand) {
      clearCommand();
      return;
    }
    skipNextBlurRef.current = true;
    setText("/");
    setShowCommands(true);
    setSelectedCmdIndex(0);
    inputRef.current?.focus();
  }, [activeCommand, clearCommand]);

  return (
    <div className="relative">
      {isMenuVisible && (
        <SlashCommandMenu
          filter={slashFilter}
          selectedIndex={selectedCmdIndex}
          onSelect={selectCommand}
        />
      )}
      <form
        onSubmit={handleSubmit}
        className="flex items-center gap-2 rounded-xl border border-border bg-muted/50 px-3 py-2 focus-within:border-accent/40"
      >
        <button
          type="button"
          onMouseDown={(e) => { e.preventDefault(); openSkillMenu(); }}
          disabled={isLoading}
          title={isLoading ? "任务执行中..." : "技能"}
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors ${
            isLoading
              ? "cursor-not-allowed text-muted-foreground/40"
              : activeCommand
                ? "bg-accent/20 text-accent"
                : "text-muted-foreground hover:bg-muted/50 hover:text-accent"
            }`}
        >
          <Zap size={16} />
        </button>

        {/* Pill token for active command */}
        {activeCommand && (
          <span className="flex items-center gap-1.5 rounded-full bg-accent/15 border border-accent/30 px-2.5 py-1 text-xs text-accent shrink-0 animate-in fade-in slide-in-from-left-2 duration-150">
            {activeCommand.icon}
            <span className="font-medium">{activeCommand.label}</span>
            {pillSubtitle && <span className="text-accent/70">：{pillSubtitle}</span>}
          </span>
        )}

        <input
          ref={inputRef}
          type="text"
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onBlur={() => {
            if (skipNextBlurRef.current) {
              skipNextBlurRef.current = false;
              return;
            }
            setTimeout(() => setShowCommands(false), 150);
          }}
          placeholder={activeCommand?.placeholder || (activeCommand ? "输入具体要求..." : "输入消息... 输入 / 查看可用命令")}
          disabled={isLoading}
          className="min-h-[36px] flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-50"
          autoFocus
        />
        {isLoading ? (
          <button
            type="button"
            onClick={() => stop()}
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-destructive/20 text-destructive transition-colors hover:bg-destructive/30"
          >
            <Square size={14} />
          </button>
        ) : (
          <button
            type="submit"
            disabled={!text.trim() && !activeCommand}
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-accent-foreground transition-colors hover:bg-accent/90 disabled:opacity-30"
          >
            <SendHorizontal size={14} />
          </button>
        )}
      </form>
    </div>
  );
}
