"use client";

import { groupMessagesIntoTurns } from "./helpers";
import { HumanBubble } from "./human-bubble";
import { AITurnBubble } from "./ai-turn-bubble";
import type { DisplayRun } from "./types";

// ============================================================
// MessageList — groups messages into turns and renders bubbles
// ============================================================

export function MessageList({ messages, runs }: { messages: any[]; runs?: DisplayRun[] }) {
  const displayRuns = runs?.length
    ? runs
    : [{ key: "legacy-flat-messages", run_id: null, status: "history" as const, messages }];

  return (
    <>
      {displayRuns.map((run) => {
        const turns = groupMessagesIntoTurns(run.messages);
        return turns.map((entry, index) => {
          const keyPrefix = `${run.key}:${index}`;
          if (entry.type === "human") {
            return (
              <HumanBubble
                key={`${keyPrefix}:human:${entry.id}`}
                text={entry.text}
                pending={entry.pending}
              />
            );
          }
          return (
            <AITurnBubble
              key={`${keyPrefix}:ai:${entry.turn.id}`}
              turn={entry.turn}
            />
          );
        });
      })}
    </>
  );
}
