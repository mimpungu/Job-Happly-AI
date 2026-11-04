"use client";

import { ArrowLeft } from "lucide-react";
import { useTranslations } from "next-intl";
import { usePathname, useRouter } from "next/navigation";

import { IconButton } from "@/components/ui/icon-button";

// Page d'accueil de l'application : il n'y a rien avant.
const RACINES = new Set(["/", "/dashboard"]);

/**
 * Revient à la vue précédente, quelle qu'elle soit (fiche, onglet, filtre). Sans historique (page
 * ouverte directement), retombe sur le tableau de bord plutôt que de ne rien faire.
 */
export function BackButton() {
  const t = useTranslations("shell");
  const router = useRouter();
  const pathname = usePathname();
  if (RACINES.has(pathname)) return null;

  const revenir = () => {
    if (window.history.length > 1) router.back();
    else router.push("/dashboard");
  };

  return (
    <IconButton aria-label={t("back")} variant="circle" onClick={revenir}>
      <ArrowLeft className="size-5" aria-hidden="true" />
    </IconButton>
  );
}
