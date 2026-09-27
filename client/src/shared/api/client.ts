import axios from "axios";
import { storageKeys } from "@/shared/config/storage";
import { routes } from "@/shared/config/routes";
import { clearAccessToken, getAccessToken } from "@/shared/lib/auth";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000",
  headers: { Accept: "application/json" },
});

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  const tenantId = window.localStorage.getItem(storageKeys.activeTenantId);
  const requestedTenantId =
    config.headers["X-Tenant-ID"] ?? config.headers["x-tenant-id"];
  if (tenantId && !requestedTenantId) config.headers["X-Tenant-ID"] = tenantId;
  return config;
});

/** Auth surfaces where a 401 must not trigger a redirect loop. */
function isAuthPath(pathname: string) {
  return (
    pathname === routes.login ||
    pathname === routes.register ||
    pathname.startsWith("/tenant/")
  );
}

api.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      clearAccessToken();
      if (!isAuthPath(window.location.pathname))
        window.location.assign(routes.login);
    }
    return Promise.reject(error);
  },
);
