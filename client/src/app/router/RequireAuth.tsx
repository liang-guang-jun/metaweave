import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { routes } from "@/shared/config/routes";
import { getAccessToken } from "@/shared/lib/auth";

type RequireAuthProps = {
  children: ReactNode;
};

/** Send unauthenticated visitors to the login page before rendering children. */
export function RequireAuth({ children }: RequireAuthProps) {
  const location = useLocation();

  if (!getAccessToken()) {
    return (
      <Navigate to={routes.login} replace state={{ from: location.pathname }} />
    );
  }

  return <>{children}</>;
}
