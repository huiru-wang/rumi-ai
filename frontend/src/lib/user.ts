const USER_ID_KEY = "rumi-ai-user-id";
const USER_NICKNAME_KEY = "rumi-ai-user-nickname";

export function getUserId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(USER_ID_KEY);
}

export function getUserNickname(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(USER_NICKNAME_KEY);
}

export function setInviteUser(userId: string, nickname: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(USER_ID_KEY, userId);
  if (nickname) {
    localStorage.setItem(USER_NICKNAME_KEY, nickname);
  } else {
    localStorage.removeItem(USER_NICKNAME_KEY);
  }
}

export function clearInviteUser(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(USER_ID_KEY);
  localStorage.removeItem(USER_NICKNAME_KEY);
}
