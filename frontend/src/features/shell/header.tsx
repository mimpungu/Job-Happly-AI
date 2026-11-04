"use client";

import { Bell, Settings, User } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Dropdown, DropdownContent, DropdownItem, DropdownTrigger } from "@/components/ui/dropdown";
import { IconButton } from "@/components/ui/icon-button";
import { SearchInput } from "@/components/ui/input";

import { MobileNav } from "./mobile-nav";

export function Header() {
  const router = useRouter();
  const [terme, setTerme] = useState("");

  const rechercher = (event: FormEvent) => {
    event.preventDefault();
    const valeur = terme.trim();
    if (valeur) router.push(`/jobs?q=${encodeURIComponent(valeur)}`);
  };

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-background px-4">
      <MobileNav />
      <form role="search" onSubmit={rechercher} className="max-w-md flex-1">
        <SearchInput
          aria-label="Recherche globale"
          placeholder="Rechercher une offre…"
          onValueChange={setTerme}
        />
      </form>
      <div className="ml-auto flex items-center gap-1">
        <Dropdown>
          <DropdownTrigger asChild>
            <IconButton aria-label="Notifications">
              <Bell className="size-5" aria-hidden="true" />
            </IconButton>
          </DropdownTrigger>
          <DropdownContent align="end">
            <p className="px-2.5 py-2 text-sm text-foreground-muted">Aucune notification.</p>
          </DropdownContent>
        </Dropdown>
        <Dropdown>
          <DropdownTrigger asChild>
            <IconButton aria-label="Profil">
              <User className="size-5" aria-hidden="true" />
            </IconButton>
          </DropdownTrigger>
          <DropdownContent align="end">
            <DropdownItem asChild>
              <Link href="/settings">
                <Settings className="size-4" aria-hidden="true" />
                Paramètres
              </Link>
            </DropdownItem>
          </DropdownContent>
        </Dropdown>
      </div>
    </header>
  );
}
