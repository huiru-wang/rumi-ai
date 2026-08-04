const USER_ID_KEY = "rumi-ai-user-id";
const USER_NICKNAME_KEY = "rumi-ai-user-nickname";
const USER_SOURCE_KEY = "rumi-ai-user-source";
const OPEN_USER_ID_KEY = "rumi-ai-open-user-id";
const OPEN_USER_NICKNAME_KEY = "rumi-ai-open-user-nickname";

export type UserSource = "invite" | "open";

export function getUserId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(USER_ID_KEY);
}

export function getUserNickname(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(USER_NICKNAME_KEY);
}

export function getUserSource(): UserSource | null {
  if (typeof window === "undefined") return null;
  const source = localStorage.getItem(USER_SOURCE_KEY);
  return source === "invite" || source === "open" ? source : null;
}

export function getOpenUser(): { userId: string; nickname: string } | null {
  if (typeof window === "undefined") return null;
  const userId = localStorage.getItem(OPEN_USER_ID_KEY);
  if (!userId) return null;
  return {
    userId,
    nickname: localStorage.getItem(OPEN_USER_NICKNAME_KEY) || "访客",
  };
}

export function setAccessUser(
  userId: string,
  nickname: string,
  source: UserSource,
): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(USER_ID_KEY, userId);
  localStorage.setItem(USER_SOURCE_KEY, source);
  if (nickname) {
    localStorage.setItem(USER_NICKNAME_KEY, nickname);
  } else {
    localStorage.removeItem(USER_NICKNAME_KEY);
  }
  if (source === "open") {
    localStorage.setItem(OPEN_USER_ID_KEY, userId);
    localStorage.setItem(OPEN_USER_NICKNAME_KEY, nickname);
  }
}

export function setInviteUser(userId: string, nickname: string): void {
  setAccessUser(userId, nickname, "invite");
}

export function clearCurrentUser(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(USER_ID_KEY);
  localStorage.removeItem(USER_NICKNAME_KEY);
  localStorage.removeItem(USER_SOURCE_KEY);
}

export function clearInviteUser(): void {
  clearCurrentUser();
}
