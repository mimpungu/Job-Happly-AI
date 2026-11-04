"use client";

import Link from "next/link";

import { useDemo } from "./use-demo";

/** Bandeau permanent tant que la démonstration est active : on ne la confond jamais avec le réel. */
export function DemoBanner() {
  const demo = useDemo();
  // API injoignable ou démonstration inactive : rien à signaler.
  if (!demo.data?.enabled) return null;
  return (
    <div
      role="status"
      className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-warning/40 bg-warning-soft px-4 py-3 text-sm text-on-warning-soft"
    >
      <span>
        <strong>Mode démonstration actif</strong> : les offres affichées sont fictives. Aucune
        donnée réelle n&apos;est mêlée à celles-ci.
      </span>
      <Link href="/settings" className="font-medium underline underline-offset-4">
        Désactiver dans les paramètres
      </Link>
    </div>
  );
}
