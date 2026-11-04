"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

/** Recherche globale : envoie vers la recherche d'offres ; « / » place le curseur dans le champ. */
export function GlobalSearch({ onNavigate }: { onNavigate?: () => void }) {
  const router = useRouter();
  const champ = useRef<HTMLInputElement>(null);
  const [terme, setTerme] = useState("");

  useEffect(() => {
    const raccourci = (e: KeyboardEvent) => {
      if (e.key !== "/" || e.ctrlKey || e.metaKey || e.altKey) return;
      const cible = e.target;
      if (
        cible instanceof HTMLElement &&
        (cible.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(cible.tagName))
      )
        return;
      e.preventDefault();
      champ.current?.focus();
    };
    document.addEventListener("keydown", raccourci);
    return () => document.removeEventListener("keydown", raccourci);
  }, []);

  const rechercher = (event: FormEvent) => {
    event.preventDefault();
    const valeur = terme.trim();
    if (!valeur) return;
    router.push(`/jobs?q=${encodeURIComponent(valeur)}`);
    onNavigate?.();
  };

  return (
    <form
      role="search"
      onSubmit={rechercher}
      className="flex h-12 items-center gap-3 rounded-full bg-background-secondary px-4 text-foreground-muted focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-(--focus-ring-color)"
    >
      <Search className="size-5 shrink-0" aria-hidden="true" />
      <input
        ref={champ}
        type="search"
        aria-label="Recherche globale"
        aria-keyshortcuts="/"
        placeholder="Rechercher une offre…"
        value={terme}
        onChange={(e) => setTerme(e.target.value)}
        className="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-foreground-muted [&::-webkit-search-cancel-button]:hidden"
      />
      <kbd
        aria-hidden="true"
        className="flex size-7 shrink-0 items-center justify-center rounded-full bg-surface-elevated text-xs text-foreground-muted"
      >
        /
      </kbd>
    </form>
  );
}
