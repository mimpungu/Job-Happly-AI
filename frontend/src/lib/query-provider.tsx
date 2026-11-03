"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

/** Un client de requêtes par session de navigation (jamais partagé entre utilisateurs côté serveur). */
export function QueryProvider({ children }: { children: ReactNode }) {
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 15_000 } } }),
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
