import { Badge } from "@/components/ui/badge";
import type { GeographicCoverage, SourceSearchResult } from "@/types/sources";

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

/** Couverture géographique : ce que les sources déclarent, sans rien affirmer de plus. */
function Couverture({ couverture }: { couverture: GeographicCoverage }) {
  if (couverture.requested.length === 0) return null;
  return (
    <div role="note" className="flex flex-col gap-1 text-foreground-muted">
      {couverture.declared.length > 0 ? (
        <p>Pays couverts par une source interrogée : {couverture.declared.join(", ")}.</p>
      ) : null}
      {couverture.undeclared.length > 0 ? (
        <p>
          <strong className="text-foreground">
            Aucune source interrogée ne déclare couvrir : {couverture.undeclared.join(", ")}.
          </strong>{" "}
          Les résultats pour ces pays viennent seulement des offres déjà collectées
          {couverture.sources_without_declared_countries.length > 0
            ? " et des entreprises suivies, dont la couverture n'est pas déclarée"
            : ""}
          .
        </p>
      ) : null}
    </div>
  );
}

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
      {result.coverage ? <Couverture couverture={result.coverage} /> : null}
    </section>
  );
}
