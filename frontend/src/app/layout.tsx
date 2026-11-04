import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { RegionalBoundary } from "@/features/localization/regional-boundary";
import { LocaleProvider } from "@/i18n/locale-provider";
import { QueryProvider } from "@/lib/query-provider";

import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

/**
 * Thème appliqué avant le premier affichage : choix enregistré, sinon préférence du système,
 * sinon sombre. Sans cela la page s'afficherait un instant dans le mauvais thème.
 */
const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem("happly-theme");if(t!=="light"&&t!=="dark"){t=window.matchMedia("(prefers-color-scheme: light)").matches?"light":"dark"}document.documentElement.dataset.theme=t}catch(e){document.documentElement.dataset.theme="dark"}})()`;

export const metadata: Metadata = {
  title: "Happly AI",
  description: "Assistant personnel de recherche d'emploi",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="fr" className={`${inter.variable} h-full antialiased`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="min-h-full flex flex-col">
        <LocaleProvider>
          <QueryProvider>
            <TooltipProvider>
              <RegionalBoundary>{children}</RegionalBoundary>
            </TooltipProvider>
          </QueryProvider>
          <Toaster />
        </LocaleProvider>
      </body>
    </html>
  );
}
