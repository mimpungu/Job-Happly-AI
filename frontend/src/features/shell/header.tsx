"use client";

import { Bell, Settings, UserRound } from "lucide-react";
import Link from "next/link";

import { Dropdown, DropdownContent, DropdownItem, DropdownTrigger } from "@/components/ui/dropdown";
import { IconButton } from "@/components/ui/icon-button";
import { ManualOfferDialog } from "@/features/jobs/manual-offer-dialog";

import { MobileNav } from "./mobile-nav";
import { ThemeToggle } from "./theme-toggle";

/**
 * En-tête de page : à gauche l'emplacement du titre (rempli par `PageHeading` quand la page en
 * fournit un), à droite les actions de l'application, présentes sur toutes les pages.
 */
export function Header() {
  return (
    <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-4 px-4 pt-4 sm:px-6 lg:px-10 lg:pt-9">
      <div className="flex min-w-0 flex-1 basis-80 items-center gap-3">
        <MobileNav />
        <div id="page-heading" className="min-w-0 flex-1" />
      </div>
      <div className="ml-auto flex items-center gap-3">
        <ThemeToggle />
        <Dropdown>
          <DropdownTrigger asChild>
            <IconButton aria-label="Profil" variant="circle" size="lg">
              <UserRound className="size-5" aria-hidden="true" />
            </IconButton>
          </DropdownTrigger>
          <DropdownContent align="end">
            <DropdownItem asChild>
              <Link href="/cv-studio">
                <UserRound className="size-4" aria-hidden="true" />
                Mon profil
              </Link>
            </DropdownItem>
            <DropdownItem asChild>
              <Link href="/settings">
                <Settings className="size-4" aria-hidden="true" />
                Paramètres
              </Link>
            </DropdownItem>
          </DropdownContent>
        </Dropdown>
        <Dropdown>
          <DropdownTrigger asChild>
            <IconButton aria-label="Notifications" variant="circle" size="lg">
              <Bell className="size-5" aria-hidden="true" />
            </IconButton>
          </DropdownTrigger>
          <DropdownContent align="end">
            <p className="px-2.5 py-2 text-sm text-foreground-muted">Aucune notification.</p>
          </DropdownContent>
        </Dropdown>
        <ManualOfferDialog trigger="primary" />
      </div>
    </header>
  );
}
