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
  /** Libellé français : repli et nom des tests ; l'affichage passe par `messageKey`. */
  label: string;
  /** Clé de traduction sous `nav` (fichiers `i18n/messages`). */
  messageKey: string;
  href: string;
  icon: LucideIcon;
  /** Entrée rangée en bas de la barre latérale, séparée des sections de travail. */
  bottom?: boolean;
}

/** Navigation principale (spécification §16). L'ordre est celui de la barre latérale. */
export const NAVIGATION_ITEMS: readonly NavigationItem[] = [
  { label: "Tableau de bord", messageKey: "dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Recherche d'emploi", messageKey: "jobs", href: "/jobs", icon: Search },
  { label: "Offres sauvegardées", messageKey: "savedJobs", href: "/saved-jobs", icon: Bookmark },
  { label: "Espace CV", messageKey: "cvStudio", href: "/cv-studio", icon: FileText },
  {
    label: "Lettres de motivation",
    messageKey: "coverLetters",
    href: "/cover-letters",
    icon: Mail,
  },
  {
    label: "Candidatures",
    messageKey: "applications",
    href: "/applications",
    icon: BriefcaseBusiness,
  },
  {
    label: "Préparation d'entretien",
    messageKey: "interviews",
    href: "/interview-preparation",
    icon: MessagesSquare,
  },
  { label: "Centre IA", messageKey: "aiCenter", href: "/ai-center", icon: Bot },
  { label: "Paramètres", messageKey: "settings", href: "/settings", icon: Settings, bottom: true },
];

/** Une entrée est active pour sa route exacte et pour ses sous-routes. */
export function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
