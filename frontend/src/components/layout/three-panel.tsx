"use client";

import React, { useState, useCallback, useRef, type ReactNode } from "react";

interface ThreePanelProps {
  left: React.ReactNode;
  center: React.ReactNode;
  right: React.ReactNode;
  rightCollapsed?: boolean;
  onRightToggle?: () => void;
}

const MIN_SIDE_WIDTH = 240;
const MAX_SIDE_WIDTH = 400;
const DEFAULT_LEFT_WIDTH = 280;
const DEFAULT_RIGHT_WIDTH = 300;

export function ThreePanel({ left, center, right, rightCollapsed = false, onRightToggle }: ThreePanelProps) {
  const [leftWidth, setLeftWidth] = useState(DEFAULT_LEFT_WIDTH);
  const [rightWidth, setRightWidth] = useState(DEFAULT_RIGHT_WIDTH);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleMouseDown = useCallback(
    (side: "left" | "right") => (event: React.MouseEvent) => {
      event.preventDefault();
      const startX = event.clientX;
      const startLeftWidth = leftWidth;
      const startRightWidth = rightWidth;

      const handleMouseMove = (moveEvent: MouseEvent) => {
        const deltaX = moveEvent.clientX - startX;
        if (side === "left") {
          const newWidth = Math.min(
            MAX_SIDE_WIDTH,
            Math.max(MIN_SIDE_WIDTH, startLeftWidth + deltaX)
          );
          setLeftWidth(newWidth);
        } else {
          const newWidth = Math.min(
            MAX_SIDE_WIDTH,
            Math.max(MIN_SIDE_WIDTH, startRightWidth - deltaX)
          );
          setRightWidth(newWidth);
        }
      };

      const handleMouseUp = () => {
        document.removeEventListener("mousemove", handleMouseMove);
        document.removeEventListener("mouseup", handleMouseUp);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      };

      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    },
    [leftWidth, rightWidth]
  );

  // Helper to wrap right panel with collapse callback
  const renderRight = (): ReactNode => {
    if (rightCollapsed) return null;
    // Clone and inject props into right panel if it's a function component
    if (typeof right === "object" && right !== null && "type" in (right as object)) {
      const element = right as React.ReactElement<{ collapsed?: boolean; onToggle?: () => void }>;
      if (element.type === "function") {
        return React.cloneElement(element, { collapsed: rightCollapsed, onToggle: onRightToggle });
      }
    }
    return right;
  };

  return (
    <div ref={containerRef} className="flex h-full w-full overflow-hidden">
      {/* Left Panel */}
       <div
        className="shrink-0 overflow-y-auto border-r border-border"
        style={{ width: leftWidth }}
      >
        {left}
      </div>

      {/* Left Resize Handle */}
      <div
        className="w-1 shrink-0 cursor-col-resize bg-transparent transition-colors hover:bg-accent/30"
        onMouseDown={handleMouseDown("left")}
      />

      {/* Center Panel */}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {center}
      </div>

      {/* Right Panel */}
      {renderRight() ? (
        <div
          className="shrink-0 overflow-y-auto border-l border-border"
          style={{ width: rightWidth }}
        >
          {renderRight()}
        </div>
      ) : (
        /* Collapsed: show toggle button in center panel area */
        <div className="flex w-8 shrink-0 items-center justify-center border-l border-border bg-background">
          <button
            type="button"
            onClick={onRightToggle}
            className="flex items-center justify-center rounded p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-label="展开产出"
            title="展开产出"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        </div>
      )}

      {/* Right Resize Handle (only when expanded) */}
      {!rightCollapsed && (
        <div
          className="w-1 shrink-0 cursor-col-resize bg-transparent transition-colors hover:bg-accent/30"
          onMouseDown={handleMouseDown("right")}
          title="拖拽调整产出侧边栏宽度"
        />
      )}
    </div>
  );
}
