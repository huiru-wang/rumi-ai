// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Message = any;

interface UseLiveMessagesState {
  threadId: string | null;
  isInitialHistoryLoading: boolean;
}

export function shouldUseLiveMessages(state: UseLiveMessagesState): boolean {
  return !state.threadId || !state.isInitialHistoryLoading;
}

interface GetLiveMessagesInput<T> {
  historyMessages: T[];
  streamMessages: T[];
  getMessageKey: (message: T) => string;
}

export function getLiveMessagesAfterHistory<T>(input: GetLiveMessagesInput<T>): T[] {
  const { historyMessages, streamMessages, getMessageKey } = input;
  if (historyMessages.length === 0) return streamMessages;

  const lastHistoryKey = getMessageKey(historyMessages[historyMessages.length - 1]);
  const lastHistoryIndex = streamMessages.findIndex(
    (message) => getMessageKey(message) === lastHistoryKey,
  );

  if (lastHistoryIndex < 0) return [];
  return streamMessages.slice(lastHistoryIndex + 1);
}

interface SelectLiveMessagesInput<T> extends GetLiveMessagesInput<T> {
  canUseLiveMessages: boolean;
}

export function selectLiveMessagesForDisplay<T>(input: SelectLiveMessagesInput<T>): T[] {
  if (!input.canUseLiveMessages) return [];
  return getLiveMessagesAfterHistory(input);
}

interface PreserveDisplayedInput<T> {
  isLoading: boolean;
  historyMessages: T[];
  streamMessages: T[];
  liveMessages: T[];
  nextDisplayedMessages: T[];
  previousDisplayedMessages: T[];
  getMessageKey: (message: T) => string;
}

export function shouldPreserveDisplayedMessages<T>(input: PreserveDisplayedInput<T>): boolean {
  if (input.isLoading) return false;
  if (input.historyMessages.length === 0) return false;
  if (input.streamMessages.length === 0) return false;
  if (input.liveMessages.length > 0) return false;
  if (input.previousDisplayedMessages.length <= input.nextDisplayedMessages.length) return false;

  const lastHistoryKey = input.getMessageKey(input.historyMessages[input.historyMessages.length - 1]);
  const hasHistoryAnchor = input.streamMessages.some(
    (message) => input.getMessageKey(message) === lastHistoryKey,
  );
  return !hasHistoryAnchor;
}

interface DebugSnapshotInput<T> {
  phase: string;
  threadId: string | null;
  isLoading: boolean;
  historyMessages: T[];
  streamMessages: T[];
  liveMessages: T[];
  displayedMessages: T[];
  optimisticMessages: T[];
  getMessageKey: (message: T) => string;
}

export function createMessageDebugSnapshot<T>(input: DebugSnapshotInput<T>) {
  const lastHistoryMessage = input.historyMessages[input.historyMessages.length - 1];
  const lastHistoryKey = lastHistoryMessage ? input.getMessageKey(lastHistoryMessage) : undefined;
  const indexInStream = lastHistoryKey
    ? input.streamMessages.findIndex((message) => input.getMessageKey(message) === lastHistoryKey)
    : undefined;

  return {
    phase: input.phase,
    threadId: input.threadId,
    isLoading: input.isLoading,
    history: summarizeMessageList(input.historyMessages),
    stream: summarizeMessageList(input.streamMessages),
    live: summarizeMessageList(input.liveMessages),
    displayed: summarizeMessageList(input.displayedMessages),
    optimistic: summarizeMessageList(input.optimisticMessages),
    anchor: {
      lastHistoryKey,
      indexInStream,
      reason: getAnchorReason(input.historyMessages, input.streamMessages, indexInStream),
    },
  };
}

function getAnchorReason<T>(
  historyMessages: T[],
  streamMessages: T[],
  indexInStream: number | undefined,
): string {
  if (historyMessages.length === 0) return "no-history";
  if (streamMessages.length === 0) return "no-stream";
  if (indexInStream === -1) return "missing-history-anchor";
  return "ok";
}

function summarizeMessageList(messages: Message[]) {
  return {
    count: messages.length,
    last: summarizeMessageForDebug(messages[messages.length - 1]),
  };
}

function summarizeMessageForDebug(message: Message) {
  if (!message) return undefined;
  return {
    type: message?._getType?.() || message?.type || message?.role || "message",
    id: message?.id || message?.message_id,
    rowId: message?._rowId,
    contentLength: getContentLength(message?.content),
    toolCalls: Array.isArray(message?.tool_calls) ? message.tool_calls.length : 0,
    name: message?.name,
  };
}

function getContentLength(content: unknown): number {
  if (typeof content === "string") return content.length;
  return JSON.stringify(content ?? "").length;
}
