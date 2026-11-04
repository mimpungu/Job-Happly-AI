import { GlobalSearch } from "./global-search";
import { Logo } from "./logo";
import { SidebarNav } from "./sidebar-nav";

/** Barre latérale fixe, visible à partir du point de rupture `lg`. */
export function Sidebar() {
  return (
    <aside className="sticky top-0 hidden h-dvh w-72 shrink-0 flex-col gap-8 px-5 py-8 lg:flex xl:w-80">
      <div className="px-2">
        <Logo />
      </div>
      <GlobalSearch />
      <SidebarNav />
    </aside>
  );
}
