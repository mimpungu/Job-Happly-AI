"use client";

import { Menu, X } from "lucide-react";
import { Dialog } from "radix-ui";
import { useState } from "react";

import { IconButton } from "@/components/ui/icon-button";

import { SidebarNav } from "./sidebar-nav";

/** Tiroir de navigation pour tablette et mobile (sous le point de rupture `lg`). */
export function MobileNav() {
  const [open, setOpen] = useState(false);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <IconButton aria-label="Ouvrir le menu" className="lg:hidden">
          <Menu className="size-5" aria-hidden="true" />
        </IconButton>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/60 lg:hidden" />
        <Dialog.Content className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col gap-6 border-r border-border bg-background-secondary p-4 lg:hidden">
          <div className="flex items-center justify-between">
            <Dialog.Title className="px-3 text-lg font-semibold text-foreground">
              Happly AI
            </Dialog.Title>
            <Dialog.Description className="sr-only">Navigation principale</Dialog.Description>
            <Dialog.Close asChild>
              <IconButton aria-label="Fermer le menu">
                <X className="size-5" aria-hidden="true" />
              </IconButton>
            </Dialog.Close>
          </div>
          <SidebarNav onNavigate={() => setOpen(false)} />
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
