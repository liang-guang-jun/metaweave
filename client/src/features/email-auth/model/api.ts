import axios from "axios";
import { api } from "@/shared/api/client";
import { setAccessToken } from "@/shared/lib/auth";

type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in?: number;
};

type RegisterResponse = { user_id: string };

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
