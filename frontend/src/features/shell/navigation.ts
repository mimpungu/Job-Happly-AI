import {
  Bot,
  BriefcaseBusiness,
  Bookmark,
  FileText,
  LayoutDashboard,
  MessagesSquare,
  Search,
  Settings,
  Mail,
  type LucideIcon,
} from "lucide-react";

export interface NavigationItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

/** Navigation principale (spécification §16). L'ordre est celui de la barre latérale. */
export const NAVIGATION_ITEMS: readonly NavigationItem[] = [
  { label: "Tableau de bord", href: "/dashboard", icon: LayoutDashboard },
  { label: "Recherche d'emploi", href: "/jobs", icon: Search },
  { label: "Offres sauvegardées", href: "/saved-jobs", icon: Bookmark },
  { label: "Espace CV", href: "/cv-studio", icon: FileText },
  { label: "Lettres de motivation", href: "/cover-letters", icon: Mail },
  { label: "Candidatures", href: "/applications", icon: BriefcaseBusiness },
  { label: "Préparation d'entretien", href: "/interview-preparation", icon: MessagesSquare },
  { label: "Centre IA", href: "/ai-center", icon: Bot },
  { label: "Paramètres", href: "/settings", icon: Settings },
];

/** Une entrée est active pour sa route exacte et pour ses sous-routes. */
export function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
