const USER_ID_KEY = "rumi-ai-user-id";

export function getUserId(): string {
  if (typeof window === "undefined") return "anonymous";

  let userId = localStorage.getItem(USER_ID_KEY);
  if (!userId) {
    userId = crypto.randomUUID();
    localStorage.setItem(USER_ID_KEY, userId);
  }
  return userId;
}
