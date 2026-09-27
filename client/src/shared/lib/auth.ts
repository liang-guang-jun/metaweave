export const AUTH_TOKEN_KEY = "metaweave.access-token";

export function getAccessToken(): string | null {
  return window.sessionStorage.getItem(AUTH_TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  window.sessionStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  window.sessionStorage.removeItem(AUTH_TOKEN_KEY);
}
