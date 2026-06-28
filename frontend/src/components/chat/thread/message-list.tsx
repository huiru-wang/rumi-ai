"use client";

import { groupMessagesIntoTurns } from "./helpers";
import { HumanBubble } from "./human-bubble";
import { AITurnBubble } from "./ai-turn-bubble";

// ============================================================
// MessageList — groups messages into turns and renders bubbles
// ============================================================

export function MessageList({ messages }: { messages: any[] }) {
  const turns = groupMessagesIntoTurns(messages);

  return (
    <>
      {turns.map((entry) => {
        if (entry.type === "human") {
          return <HumanBubble key={entry.id} text={entry.text} pending={entry.pending} />;
        }
        return <AITurnBubble key={entry.turn.id} turn={entry.turn} />;
      })}
    </>
  );
}
