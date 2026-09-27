import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AppProviders, AppRouter } from "@/app";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppProviders>
      <AppRouter />
    </AppProviders>
  </StrictMode>,
);
