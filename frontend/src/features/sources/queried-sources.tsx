import { Badge } from "@/components/ui/badge";
import type { SourceSearchResult } from "@/types/sources";

const ERREURS: Record<string, string> = {
  SourceUnavailableError: "source indisponible",
  SourceTimeoutError: "délai dépassé",
  RateLimitedError: "quota atteint",
  AccessDeniedError: "accès refusé (source écartée, jamais contournée)",
  AuthenticationFailedError: "identifiants refusés",
  NotConfiguredError: "non configurée",
  InvalidResponseError: "réponse illisible",
  CircuitOpenError: "source écartée temporairement",
};

/** Sources interrogées par la dernière recherche : chaque échec est nommé, jamais masqué. */
export function QueriedSources({ result }: { result: SourceSearchResult }) {
  if (!result.queried) {
    return (
      <p role="status" className="text-sm text-foreground-muted">
        Aucune source activée : seules les offres déjà collectées sont affichées. Suivez des
        entreprises dans les paramètres.
      </p>
    );
  }
  return (
    <section aria-label="Sources interrogées" className="flex flex-col gap-2 text-sm">
      <h2 className="font-medium text-foreground">
        {result.sources.length} source{result.sources.length > 1 ? "s" : ""} interrogée
        {result.sources.length > 1 ? "s" : ""}
        {result.status === "partial" ? " — résultats partiels" : ""}
      </h2>
      <ul className="flex flex-col gap-1">
        {result.sources.map((s) => (
          <li key={s.source_key} className="flex flex-wrap items-center gap-2">
            <span className="text-foreground">{s.source_name}</span>
            {s.status === "ok" ? (
              <Badge variant="success">
                {s.created} nouvelle{s.created > 1 ? "s" : ""} · {s.fetched} lue
                {s.fetched > 1 ? "s" : ""}
              </Badge>
            ) : (
              <Badge variant="danger">
                Échec : {ERREURS[s.error_type ?? ""] ?? "erreur inattendue"}
              </Badge>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
