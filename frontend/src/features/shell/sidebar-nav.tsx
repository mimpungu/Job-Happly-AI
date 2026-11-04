"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/cn";

import { isActive, NAVIGATION_ITEMS } from "./navigation";

export interface SidebarNavProps {
  /** Appelé après un clic sur un lien (ex. fermer le tiroir mobile). */
  onNavigate?: () => void;
}

/** Entrées en pastilles ; l'entrée « bottom » (Paramètres) est rejetée en bas de la colonne. */
export function SidebarNav({ onNavigate }: SidebarNavProps) {
  const pathname = usePathname();
  return (
    <nav aria-label="Navigation principale" className="flex min-h-0 flex-1 flex-col">
      <ul className="flex flex-1 flex-col gap-1.5">
        {NAVIGATION_ITEMS.map(({ label, href, icon: Icon, bottom }) => {
          const active = isActive(pathname, href);
          return (
            <li key={href} className={cn(bottom && "mt-auto")}>
              <Link
                href={href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex h-12 items-center gap-3 rounded-full px-4 text-base font-medium transition-colors",
                  "duration-(--duration-fast)",
                  active
                    ? "bg-accent text-on-accent"
                    : "text-foreground-muted hover:bg-background-secondary hover:text-foreground",
                )}
              >
                <Icon className="size-5 shrink-0" aria-hidden="true" />
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
