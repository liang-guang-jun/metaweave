import axios from "axios";
import { api } from "@/shared/api/client";
import { setAccessToken, setTokenHeader } from "@/shared/lib/auth";
import type { PasswordPolicy } from "@/shared/lib/validation";

type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in?: number;
};

type RegisterResponse = { user_id: string };

/** Client-visible service configuration served by `/healthz`. */
export type ServiceStatus = {
  register_enabled: boolean;
  register_skip_verify: boolean;
  token_header: string;
  password_policy: PasswordPolicy;
};

type HealthzResponse = ServiceStatus & { status: string };

/** Read registration availability, the token header and the password policy. */
export async function getServiceStatus(): Promise<ServiceStatus> {
  const response = await api.get<HealthzResponse>("/healthz");
  // Remember where the API expects the token before any authenticated call.
  setTokenHeader(response.data.token_header);
  return response.data;
}

export function getApiError(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail))
      return detail
        .map((item: { msg?: string }) => item.msg)
        .filter(Boolean)
        .join(", ");
  }
  return fallback;
}

export async function registerUser(email: string, password: string) {
  const response = await api.post<RegisterResponse>("/iam/users", {
    email,
    password,
  });
  return response.data;
}

export async function loginUser(
  email: string,
  password: string,
  tenantId?: string,
) {
  const form = new URLSearchParams({ username: email, password });
  const response = await api.post<TokenResponse>("/iam/auth/token", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  let token = response.data.access_token;
  setAccessToken(token);
  if (tenantId) {
    const tenantResponse = await api.post<TokenResponse>(
      "/iam/auth/tenant-token",
      undefined,
      { headers: { "X-Tenant-ID": tenantId } },
    );
    token = tenantResponse.data.access_token;
  }
  setAccessToken(token);
  return response.data;
}
