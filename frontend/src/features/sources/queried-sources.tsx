import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SUPPORTED_ATS_TEXT, atsLabel } from "@/features/companies/ats";
import type { CompanySearch, GeographicCoverage, SourceSearchResult } from "@/types/sources";

export type CandidateBoard = CompanySearch["boards"][number];

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

/**
 * Ce qui a été retrouvé pour l'entreprise tapée dans la recherche. Rien n'est caché : un site
 * suivi automatiquement est annoncé, un doute est soumis à l'utilisateur, un échec est expliqué.
 */
function Entreprise({
  recherche,
  onFollowBoard,
}: {
  recherche: CompanySearch;
  onFollowBoard?: (board: CandidateBoard) => void;
}) {
  const nom = recherche.query;
  switch (recherche.status) {
    case "followed":
      return (
        <p role="status" className="text-sm text-foreground">
          Site carrières de <strong>{recherche.followed_name ?? nom}</strong> trouvé et ajouté à vos
          entreprises suivies ; seules ses offres ont été lues. Vous pouvez la retirer dans les
          paramètres.
        </p>
      );
    case "tracked":
      return (
        <p role="status" className="text-sm text-foreground-muted">
          Recherche limitée à l&apos;entreprise suivie « {nom} ».
        </p>
      );
    case "disabled":
      return (
        <p role="status" className="text-sm text-foreground">
          « {nom} » est dans vos entreprises suivies mais désactivée : réactivez-la dans les
          paramètres pour lire ses offres.
        </p>
      );
    case "not_found":
      return (
        <p role="status" className="text-sm text-foreground">
          Aucun site carrières public ({SUPPORTED_ATS_TEXT}) trouvé pour « {nom} ». Cela ne veut pas
          dire que l&apos;entreprise n&apos;a pas d&apos;offres : elle utilise peut-être un autre
          outil, que l&apos;application ne sait pas encore lire. Vérifiez l&apos;orthographe du nom.
        </p>
      );
    case "candidates":
      return (
        <div role="status" className="flex flex-col gap-2 text-sm">
          <p className="text-foreground">
            Des sites carrières existent mais leur nom ne correspond pas clairement à « {nom} » :
            confirmez avant de suivre.
          </p>
          <ul className="flex flex-col gap-2">
            {recherche.boards.map((b) => (
              <li
                key={`${b.ats_kind}:${b.token}`}
                className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border px-3 py-2"
              >
                <span className="text-foreground">
                  {b.board_name ?? b.token} · {atsLabel(b.ats_kind)} · {b.offer_count} offre
                  {b.offer_count > 1 ? "s" : ""}
                </span>
                {onFollowBoard ? (
                  <Button
                    variant="secondary"
                    onClick={() => onFollowBoard(b)}
                    aria-label={`Suivre ${b.board_name ?? b.token} (${atsLabel(b.ats_kind)})`}
                  >
                    Suivre
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      );
  }
}

/** Sources interrogées par la dernière recherche : chaque échec est nommé, jamais masqué. */
export function QueriedSources({
  result,
  onFollowBoard,
}: {
  result: SourceSearchResult;
  onFollowBoard?: (board: CandidateBoard) => void;
}) {
  const entreprise = result.company_search ? (
    <Entreprise recherche={result.company_search} onFollowBoard={onFollowBoard} />
  ) : null;
  if (!result.queried) {
    if (entreprise) return <section aria-label="Sources interrogées">{entreprise}</section>;
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
      {entreprise}
      {result.coverage ? <Couverture couverture={result.coverage} /> : null}
    </section>
  );
}
