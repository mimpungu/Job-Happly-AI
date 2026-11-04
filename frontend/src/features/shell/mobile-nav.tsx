"use client";

import { Menu, X } from "lucide-react";
import { Dialog } from "radix-ui";
import { useState } from "react";

import { IconButton } from "@/components/ui/icon-button";

import { GlobalSearch } from "./global-search";
import { Logo } from "./logo";
import { SidebarNav } from "./sidebar-nav";

/** Tiroir de navigation pour tablette et mobile (sous le point de rupture `lg`). */
export function MobileNav() {
  const [open, setOpen] = useState(false);
  const fermer = () => setOpen(false);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <IconButton aria-label="Ouvrir le menu" variant="circle" className="lg:hidden">
          <Menu className="size-5" aria-hidden="true" />
        </IconButton>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/60 lg:hidden" />
        <Dialog.Content className="fixed inset-y-0 left-0 z-50 flex w-80 max-w-[88vw] flex-col gap-6 overflow-y-auto border-r border-border bg-background p-5 lg:hidden">
          <div className="flex items-center justify-between">
            <Dialog.Title asChild>
              <div>
                <Logo onNavigate={fermer} />
              </div>
            </Dialog.Title>
            <Dialog.Description className="sr-only">Navigation principale</Dialog.Description>
            <Dialog.Close asChild>
              <IconButton aria-label="Fermer le menu">
                <X className="size-5" aria-hidden="true" />
              </IconButton>
            </Dialog.Close>
          </div>
          <GlobalSearch onNavigate={fermer} />
          <SidebarNav onNavigate={fermer} />
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
