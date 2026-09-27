import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { RequireAuth } from "./RequireAuth";
import { AuthPage } from "@/pages/auth/ui/AuthPage";
import { WorkspacePage } from "@/pages/workspace/ui/WorkspacePage";
import { routes } from "@/shared/config/routes";

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path={routes.login}
          element={<AuthPage key="login" mode="login" />}
        />
        <Route
          path={routes.register}
          element={<AuthPage key="register" mode="register" />}
        />
        <Route
          path={routes.tenantPattern}
          element={<AuthPage key="tenant" mode="login" />}
        />
        <Route
          path={routes.workspace}
          element={
            <RequireAuth>
              <WorkspacePage />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to={routes.login} replace />} />
      </Routes>
    </BrowserRouter>
  );
}
