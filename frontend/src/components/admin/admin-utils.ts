export interface SessionStorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

const ADMIN_TOKEN_KEY = "rumi-ai-admin-token";

export function buildTrendPolyline(
  values: number[],
  width: number,
  height: number,
): string {
  if (values.length === 0) return "";
  const max = Math.max(...values);
  const step = values.length > 1 ? width / (values.length - 1) : 0;
  return values
    .map((value, index) => {
      const x = index * step;
      const y = max === 0 ? height : height - (value / max) * height;
      return `${Number(x.toFixed(2))},${Number(y.toFixed(2))}`;
    })
    .join(" ");
}

export function readAdminToken(storage: SessionStorageLike): string | null {
  return storage.getItem(ADMIN_TOKEN_KEY);
}

export function writeAdminToken(
  storage: SessionStorageLike,
  token: string | null,
): void {
  if (token) {
    storage.setItem(ADMIN_TOKEN_KEY, token);
  } else {
    storage.removeItem(ADMIN_TOKEN_KEY);
  }
}
