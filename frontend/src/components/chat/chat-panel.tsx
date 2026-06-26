"use client";

import { Assistant, type ExternalCommand } from "./assistant";
import { StableMessageList } from "./thread";

interface ChatPanelProps {
  workspaceId: string;
  pptStyle?: string;
  voiceId?: string;
  currentPptTaskId?: string;
  onPptTaskIdConsumed?: () => void;
  externalCommand?: ExternalCommand | null;
  onExternalCommandConsumed?: () => void;
}

export function ChatPanel({ workspaceId, pptStyle, voiceId, currentPptTaskId, onPptTaskIdConsumed, externalCommand, onExternalCommandConsumed }: ChatPanelProps) {
  return (
    <Assistant
      workspaceId={workspaceId}
      pptStyle={pptStyle}
      voiceId={voiceId}
      currentPptTaskId={currentPptTaskId}
      onPptTaskIdConsumed={onPptTaskIdConsumed}
      externalCommand={externalCommand}
      onExternalCommandConsumed={onExternalCommandConsumed}
    >
      <StableMessageList />
    </Assistant>
  );
}
