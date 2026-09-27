import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { ThemeProvider } from "@/shared/theme/ThemeProvider";
import { GlobalStyle } from "@/app/styles/GlobalStyle";
import type { PropsWithChildren } from "react";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

// Drop toasts below the sticky workspace header (56px) with a small gap, while
// keeping sonner's default horizontal inset (24px).
const toastOffset = { top: 72 };

export function AppProviders({ children }: PropsWithChildren) {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <GlobalStyle />
        <Toaster
          position="top-right"
          richColors
          closeButton
          offset={toastOffset}
        />
        {children}
      </ThemeProvider>
    </QueryClientProvider>
  );
}
