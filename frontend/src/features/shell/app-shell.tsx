import type { ReactNode } from "react";

import { Header } from "./header";
import { Sidebar } from "./sidebar";

/** Structure commune des pages : barre latérale, conteneur arrondi, en-tête et contenu. */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh bg-background">
      <a
        href="#contenu"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-surface-elevated focus:px-3 focus:py-2 focus:text-sm"
      >
        Aller au contenu
      </a>
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col lg:py-4 lg:pr-4">
        <div className="flex flex-1 flex-col bg-shell lg:rounded-3xl lg:border lg:border-border">
          <Header />
          <main
            id="contenu"
            className="mx-auto w-full max-w-[96rem] flex-1 p-4 sm:p-6 lg:px-10 lg:pb-10 lg:pt-8"
          >
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
