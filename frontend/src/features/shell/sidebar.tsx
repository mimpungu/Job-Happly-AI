import Link from "next/link";

import { SidebarNav } from "./sidebar-nav";

/** Barre latérale fixe, visible à partir du point de rupture `lg`. */
export function Sidebar() {
  return (
    <aside className="hidden w-64 shrink-0 flex-col gap-6 border-r border-border bg-background-secondary p-4 lg:flex">
      <Link href="/dashboard" className="px-3 py-2 text-lg font-semibold text-foreground">
        Happly AI
      </Link>
      <SidebarNav />
    </aside>
  );
}
