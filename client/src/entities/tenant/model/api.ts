import { api } from "@/shared/api/client";
import { setAccessToken } from "@/shared/lib/auth";
import type { Tenant } from "./types";

type TenantPageResponse = {
  items: Array<{ tenant_id: string; name: string }>;
  total: number;
  page: number;
  size: number;
  pages: number;
  has_next: boolean;
};

export type TenantPage = {
  items: Tenant[];
  total: number;
  page: number;
  size: number;
  pages: number;
  hasNext: boolean;
};

export async function listTenants(
  keyword = "",
  page = 1,
  size = 100,
): Promise<TenantPage> {
  const response = await api.get<TenantPageResponse>("/iam/auth/tenants", {
    params: { keyword, page, size },
  });
  return {
    ...response.data,
    items: response.data.items.map((item) => ({
      id: item.tenant_id,
      name: item.name,
      description: "",
    })),
    hasNext: response.data.has_next,
  };
}

export async function createTenant(name: string, description?: string) {
  const response = await api.post<{ tenant_id: string }>("/iam/tenants", {
    name,
    ...(description ? { description } : {}),
  });
  return {
    id: response.data.tenant_id,
    name,
    description: description ?? "",
  } satisfies Tenant;
}

export async function selectTenant(tenantId: string) {
  const response = await api.post<{ access_token: string }>(
    "/iam/auth/tenant-token",
    undefined,
    { headers: { "X-Tenant-ID": tenantId } },
  );
  setAccessToken(response.data.access_token);
  return response.data;
}
