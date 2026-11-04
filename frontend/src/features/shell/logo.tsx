import Link from "next/link";

/** Marque de l'application : un monogramme géométrique en couleur d'accent et le nom. */
export function Logo({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <Link
      href="/dashboard"
      onClick={onNavigate}
      className="flex items-center gap-3 rounded-md text-foreground"
    >
      <svg viewBox="0 0 32 32" className="size-9 text-accent" aria-hidden="true">
        <rect x="2" y="2" width="28" height="28" rx="9" fill="currentColor" />
        <path
          d="M10 22V10m12 12V10m-12 6h12"
          stroke="var(--color-on-accent)"
          strokeWidth="3"
          strokeLinecap="round"
          fill="none"
        />
      </svg>
      <span className="text-2xl font-semibold tracking-tighter">Happly AI</span>
    </Link>
  );
}
