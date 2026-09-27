export const AUTH_TOKEN_KEY = "metaweave.access-token";

const TOKEN_HEADER_KEY = "metaweave.token-header";

/**
 * Header fallback used before the API reports its configured `token.header`.
 * `Authorization` belongs to the hosting platform proxy, which rejects or
 * replaces tokens it does not recognise, so the API owns a dedicated header.
 */
export const DEFAULT_TOKEN_HEADER = "X-Bearer-Token";

/** Header the access token must be sent in, as configured by the API. */
export function getTokenHeader(): string {
  return (
    window.sessionStorage.getItem(TOKEN_HEADER_KEY) || DEFAULT_TOKEN_HEADER
  );
}

/** Remember the header name the API reported through /healthz. */
export function setTokenHeader(header: string): void {
  if (header) window.sessionStorage.setItem(TOKEN_HEADER_KEY, header);
}

export function getAccessToken(): string | null {
  return window.sessionStorage.getItem(AUTH_TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  window.sessionStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  window.sessionStorage.removeItem(AUTH_TOKEN_KEY);
}
