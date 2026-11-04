import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { dashboard, erreurApi, json } from "@/features/applications/fixtures";
import type { DashboardMetrics } from "@/types/applications";

import { DashboardView } from "./dashboard-view";
import { formatMoney } from "./format";

// Mercredi 4 novembre 2026 à 12 h, heure locale : les dates des données sont construites de la
// même façon pour que le test ne dépende pas du fuseau de la machine.
const MAINTENANT = new Date(2026, 10, 4, 12, 0);
const local = (jour: number, h: number, m = 0) => new Date(2026, 10, jour, h, m).toISOString();

const USAGE_IA = {
  daily_spend: [
    { date: "2026-11-01", cost: "0" },
    { date: "2026-11-02", cost: "0.25" },
    { date: "2026-11-03", cost: "0.15" },
    { date: "2026-11-04", cost: "0" },
  ],
  alerts: [],
  currency: "EUR",
  spent_today: "0",
  spent_month: "0.4",
  daily_budget: "1",
};

/** `usage` : réponse de `/ai/usage` ; `null` simule une panne de ce seul service. */
function afficher(
  metrics: DashboardMetrics | (() => Response),
  usage: typeof USAGE_IA | null = USAGE_IA,
) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (String(url).includes("/ai/usage")) {
        return usage === null ? erreurApi("internal_error", "Erreur interne.", 500) : json(usage);
      }
      return typeof metrics === "function" ? metrics() : json(metrics);
    }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      {/* Emplacement du titre, normalement fourni par l'en-tête de la coque. */}
      <div id="page-heading" />
      <DashboardView now={MAINTENANT} />
    </QueryClientProvider>,
  );
}

const donnees = (surcharge: Partial<DashboardMetrics> = {}) =>
  dashboard({
    interviews: [
      {
        application_id: "c1",
        occurred_at: local(4, 9, 30),
        job_title: "Développeur Python",
        company_name: "Acme",
        description: "Entretien technique",
      },
      {
        application_id: "c2",
        occurred_at: local(4, 15, 0),
        job_title: "Data Engineer",
        company_name: "Beta",
        description: null,
      },
      {
        application_id: "c3",
        occurred_at: local(6, 10),
        job_title: "Autre",
        company_name: null,
        description: null,
      },
      {
        application_id: "c4",
        occurred_at: local(28 - 31 + 0 + 0 + 0 || 1, 10),
        job_title: "Passé",
        company_name: null,
        description: null,
      },
    ],
    ...surcharge,
  });

const carte = async (nom: string) =>
  (await screen.findByRole("region", { name: nom })) as HTMLElement;

afterEach(() => vi.unstubAllGlobals());

describe("DashboardView — en-tête", () => {
  it("salue l'utilisateur par son prénom, sans l'inventer quand il est inconnu", async () => {
    afficher(donnees());
    expect(
      await screen.findByRole("heading", { level: 1, name: /Bon retour, Alea/ }),
    ).toBeInTheDocument();
  });

  it("reste poli sans prénom", async () => {
    afficher(donnees({ display_name: null }));
    const titre = await screen.findByRole("heading", { level: 1 });
    expect(titre).toHaveAccessibleName("Bon retour");
    expect(titre).not.toHaveTextContent(",");
  });

  it("affiche le titre pendant le chargement", () => {
    afficher(() => new Response(null, { status: 200 }));
    expect(screen.getByRole("heading", { level: 1, name: /Bon retour/ })).toBeInTheDocument();
  });
});

describe("DashboardView — indicateurs", () => {
  it("affiche les trois indicateurs avec leur variation réelle", async () => {
    afficher(donnees());
    const zone = await screen.findByLabelText("Indicateurs clés");
    const offres = within(zone).getByText("Offres actives").closest("div") as HTMLElement;
    expect(within(offres).getByText("10")).toBeInTheDocument();
    expect(within(offres).getByText(/\+33,3 %/)).toBeInTheDocument();

    const candidatures = within(zone)
      .getByText("Candidatures en cours")
      .closest("div") as HTMLElement;
    expect(within(candidatures).getByText("5")).toBeInTheDocument();
    expect(within(candidatures).getByText(/−25 %/)).toBeInTheDocument();
  });

  it("calcule les entretiens de la semaine et les compare à la semaine précédente", async () => {
    afficher(
      donnees({
        interviews: [
          {
            application_id: "a",
            occurred_at: local(3, 9),
            job_title: "A",
            company_name: null,
            description: null,
          },
          {
            application_id: "b",
            occurred_at: local(4, 9),
            job_title: "B",
            company_name: null,
            description: null,
          },
          {
            application_id: "c",
            occurred_at: local(5, 9),
            job_title: "C",
            company_name: null,
            description: null,
          },
          {
            application_id: "d",
            occurred_at: local(5, 11),
            job_title: "D",
            company_name: null,
            description: null,
          },
          {
            application_id: "e",
            occurred_at: new Date(2026, 9, 29, 9).toISOString(),
            job_title: "E",
            company_name: null,
            description: null,
          },
        ],
      }),
    );
    const zone = await screen.findByLabelText("Indicateurs clés");
    const entretiens = within(zone)
      .getByText("Entretiens cette semaine")
      .closest("div") as HTMLElement;

    expect(within(entretiens).getByText("4")).toBeInTheDocument();
    expect(within(entretiens).getByText(/\+300 %/)).toBeInTheDocument(); // 4 contre 1 la semaine dernière
  });

  it("n'invente aucune variation sans période de référence", async () => {
    afficher(
      donnees({
        active_offers_trend: { current: 5, previous: 0, percent: null },
        applications_trend: { current: 0, previous: 0, percent: null },
      }),
    );
    const zone = await screen.findByLabelText("Indicateurs clés");
    for (const nom of ["Offres actives", "Candidatures en cours"]) {
      const bloc = within(zone).getByText(nom).closest("div") as HTMLElement;
      expect(within(bloc).getByText("Pas de comparaison")).toBeInTheDocument();
      expect(within(bloc).queryByText(/%/)).not.toBeInTheDocument();
    }
  });
});

describe("DashboardView — meilleures correspondances", () => {
  it("classe les trois offres avec leur score réel", async () => {
    afficher(donnees());
    const liste = await screen.findByRole("list", { name: "Offres les plus compatibles" });
    const lignes = within(liste).getAllByRole("listitem");

    expect(lignes).toHaveLength(3);
    expect(
      within(lignes[0] as HTMLElement).getByRole("link", { name: "Développeur Python" }),
    ).toHaveAttribute("href", "/jobs/o1");
    expect(within(lignes[0] as HTMLElement).getByText(/66,2/)).toBeInTheDocument();
    expect(within(lignes[2] as HTMLElement).getByText("Entreprise inconnue")).toBeInTheDocument();
    expect(within(lignes[1] as HTMLElement).getByLabelText("Rang 2")).toBeInTheDocument();
  });

  it("invite à valider le profil quand aucun score n'existe", async () => {
    afficher(donnees({ top_matches: [], relevant_offers_count: null }));
    expect(await screen.findByText(/Aucun score n'est encore calculé/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Valider mon profil" })).toHaveAttribute(
      "href",
      "/cv-studio",
    );
  });

  it("distingue « rien à proposer » de « rien de calculé »", async () => {
    afficher(donnees({ top_matches: [], relevant_offers_count: 0 }));
    expect(await screen.findByText(/déjà suivies ou ignorées/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Chercher des offres" })).toHaveAttribute(
      "href",
      "/jobs",
    );
  });
});

describe("DashboardView — agenda des entretiens", () => {
  it("affiche les entretiens du jour courant, avec leur heure et leur candidature", async () => {
    afficher(donnees());
    const liste = await screen.findByRole("list", { name: "Entretiens du jour" });

    expect(within(liste).getAllByRole("listitem")).toHaveLength(2);
    expect(within(liste).getByRole("link", { name: /Développeur Python — Acme/ })).toHaveAttribute(
      "href",
      "/applications/c1",
    );
    expect(within(liste).getByText(/09:30 · Entretien technique/)).toBeInTheDocument();
    expect(within(liste).getByText(/^15:00$/)).toBeInTheDocument();
  });

  it("marque le jour sélectionné et signale les jours avec entretien", async () => {
    afficher(donnees());
    const jours = await screen.findByRole("list", { name: "Jours de la semaine" });

    expect(
      within(jours).getByRole("button", { name: /mercredi 4 novembre : 2 entretiens/ }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      within(jours).getByRole("button", { name: /vendredi 6 novembre : 1 entretien$/ }),
    ).toBeInTheDocument();
    expect(
      within(jours).getByRole("button", { name: /^J 5, jeudi 5 novembre$/ }),
    ).toBeInTheDocument();
  });

  it("change de jour et de semaine", async () => {
    afficher(donnees());
    await userEvent.click(await screen.findByRole("button", { name: /vendredi 6 novembre/ }));
    const liste = screen.getByRole("list", { name: "Entretiens du jour" });
    expect(within(liste).getByRole("link", { name: /Autre/ })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Semaine suivante" }));
    expect(screen.getByRole("button", { name: /lundi 9 novembre/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Semaine précédente" }));
    expect(screen.getByRole("button", { name: /lundi 2 novembre/ })).toBeInTheDocument();
  });

  it("dit qu'aucun entretien n'est enregistré, sans en inventer", async () => {
    afficher(donnees({ interviews: [] }));
    expect(await screen.findByText(/Aucun entretien enregistré/)).toBeInTheDocument();
  });

  it("dit qu'un jour est libre quand d'autres jours ne le sont pas", async () => {
    afficher(donnees());
    await userEvent.click(await screen.findByRole("button", { name: /jeudi 5 novembre/ }));
    expect(screen.getByText("Aucun entretien ce jour-là.")).toBeInTheDocument();
  });
});

describe("DashboardView — progression de la recherche", () => {
  it("affiche chaque étape avec son nombre réel", async () => {
    afficher(donnees());
    const zone = await carte("Progression de la recherche");

    for (const [etape, valeur] of [
      ["Offres", "12"],
      ["Suivies", "6"],
      ["Envoyées", "4"],
      ["Réponses", "2"],
      ["Offres reçues", "1"],
    ] as const) {
      const bloc = (await within(zone).findByText(etape, { selector: "p" }))
        .parentElement as HTMLElement;
      expect(within(bloc).getByText(valeur)).toBeInTheDocument();
    }
  });

  it("expose conversion et perte de chaque étape aux claviers et lecteurs d'écran", async () => {
    afficher(donnees());
    const zone = await carte("Progression de la recherche");

    const etape = await within(zone).findByRole("button", {
      name: /6 suivies \| Conversion : 50 % \| Perte : −50 %/,
    });
    expect(etape).toHaveAttribute("aria-pressed", "true"); // deuxième étape active par défaut

    const premiere = within(zone).getByRole("button", { name: "12 offres" });
    await userEvent.hover(premiere);
    expect(premiere).toHaveAttribute("aria-pressed", "true");
    expect(etape).toHaveAttribute("aria-pressed", "false");
  });

  it("désigne le plus gros écart et propose d'agir dessus", async () => {
    afficher(donnees());
    const zone = await carte("Progression de la recherche");

    expect(
      await within(zone).findByText(/Le plus gros écart : de « Offres » à « Suivies »/),
    ).toBeInTheDocument();
    expect(within(zone).getByRole("link", { name: "Suivre davantage d'offres" })).toHaveAttribute(
      "href",
      "/jobs",
    );
  });

  it("explique l'absence de données au lieu de dessiner un entonnoir vide", async () => {
    afficher(
      donnees({ funnel: { offers: 0, tracked: 0, sent: 0, responses: 0, offers_received: 0 } }),
    );
    const zone = await carte("Progression de la recherche");

    expect(
      await within(zone).findByText(/Aucune donnée : l'entonnoir se dessine/),
    ).toBeInTheDocument();
    expect(within(zone).getByText(/Pas encore assez de données/)).toBeInTheDocument();
    expect(within(zone).queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("DashboardView — statut et activité", () => {
  it("répartit les candidatures par étape avec une légende textuelle", async () => {
    afficher(donnees());
    const zone = await carte("Statut des candidatures");

    const repartition = await within(zone).findByRole("img");
    expect(repartition).toHaveAttribute("aria-label", expect.stringContaining("En préparation 2"));
    expect(repartition).toHaveAttribute("aria-label", expect.stringContaining("Offres reçues 1"));
    expect(within(zone).getByText(/Envoyées · 2/)).toBeInTheDocument();
    expect(within(zone).getByText(/Clôturées · 1/)).toBeInTheDocument();
    expect(within(zone).getByText(/Taux de réponse : 50 %/)).toBeInTheDocument();
  });

  it("n'annonce aucun taux de réponse sans candidature envoyée", async () => {
    afficher(donnees({ response_rate: null, applications_sent_count: 0 }));
    const zone = await carte("Statut des candidatures");
    expect(await within(zone).findByText(/Aucune candidature envoyée/)).toBeInTheDocument();
    expect(within(zone).queryByText(/Taux de réponse :/)).not.toBeInTheDocument();
  });

  it("affiche l'activité récente avec son type, son ancienneté et un lien", async () => {
    afficher(
      donnees({
        recent_activities: [
          {
            application_id: "c1",
            kind: "interview",
            occurred_at: new Date(MAINTENANT.getTime() - 2 * 3600_000).toISOString(),
            body: "Entretien technique",
            job_title: "Développeur Python",
            company_name: "Acme",
          },
        ],
      }),
    );
    const liste = await screen.findByRole("list", { name: "Dernières activités" });

    expect(within(liste).getByText("Entretien")).toBeInTheDocument();
    expect(within(liste).getByText("Acme")).toBeInTheDocument();
    expect(within(liste).getByRole("link", { name: "Développeur Python" })).toHaveAttribute(
      "href",
      "/applications/c1",
    );
    expect(within(liste).getByText(/il y a \d+ heures?|à l'instant/)).toBeInTheDocument();
  });

  it("indique l'absence d'activité", async () => {
    afficher(donnees({ recent_activities: [] }));
    expect(await screen.findByText(/Aucune activité/)).toBeInTheDocument();
  });
});

describe("DashboardView — compléments", () => {
  it("n'invente aucun chiffre : « pas de donnée » s'affiche comme tel, jamais comme zéro", async () => {
    afficher(donnees({ relevant_offers_count: null, top_matches: [] }));
    const zone = await carte("Offres à traiter");

    const pertinentes = (await within(zone).findByText("Offres pertinentes")).closest(
      "div",
    ) as HTMLElement;
    expect(within(pertinentes).getByText("—")).toBeInTheDocument();
    expect(within(pertinentes).getByText(/validez votre profil/)).toBeInTheDocument();
  });

  it("affiche les offres à traiter et le seuil de pertinence", async () => {
    afficher(donnees());
    const zone = await carte("Offres à traiter");
    const nouvelles = (await within(zone).findByText("Nouvelles offres")).closest(
      "div",
    ) as HTMLElement;
    expect(within(nouvelles).getByText("4")).toBeInTheDocument();
    expect(within(zone).getByText("Score d'au moins 70")).toBeInTheDocument();
    expect(within(zone).getByText(/12 offres trouvées au total/)).toBeInTheDocument();
  });

  it("montre la consommation face au plafond mensuel", async () => {
    afficher(donnees());
    const zone = await carte("Budget IA du mois");
    const jauge = await within(zone).findByRole("progressbar", { name: /plafond mensuel/ });
    expect(jauge).toHaveAttribute("aria-valuenow", "4");
    expect(within(zone).getByText(/Dépensé/)).toHaveTextContent(/0,40\s€ sur 10,00\s€/);
  });

  it("montre la dépense par jour du mois dans la carte", async () => {
    afficher(donnees());
    const zone = await carte("Budget IA du mois");

    const graphique = await within(zone).findByRole("img", { name: /Dépense du mois par jour/ });
    expect(graphique).toHaveAccessibleName(/0,4 EUR au total sur 4 jours/);
  });

  it("garde la jauge si le graphique ne peut pas être chargé", async () => {
    afficher(donnees(), null);
    const zone = await carte("Budget IA du mois");

    expect(await within(zone).findByRole("progressbar", { name: /plafond mensuel/ })).toBeVisible();
    expect(within(zone).queryByRole("img")).not.toBeInTheDocument();
  });

  it("explique l'absence de plafond au lieu d'afficher une jauge vide", async () => {
    afficher(
      donnees({ ai_budget: { spent: "0", limit: null, currency: null, period: "monthly" } }),
    );
    const zone = await carte("Budget IA du mois");
    expect(await within(zone).findByText(/Aucun plafond mensuel défini/)).toBeInTheDocument();
    expect(within(zone).queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("liste les dernières recherches, ou dit qu'il n'y en a pas", async () => {
    const { unmount } = afficher(donnees());
    const liste = await screen.findByRole("list", { name: "Dernières recherches" });
    expect(within(liste).getByText("python · Lyon")).toBeInTheDocument();
    expect(within(liste).getByText(/Réussie · 12 résultats/)).toBeInTheDocument();
    unmount();

    afficher(donnees({ recent_searches: [] }));
    expect(await screen.findByText("Aucune recherche lancée pour le moment.")).toBeInTheDocument();
  });
});

describe("DashboardView — erreur", () => {
  it("annonce une erreur et permet de réessayer", async () => {
    let echec = true;
    afficher(() => (echec ? erreurApi("internal_error", "Erreur interne.", 500) : json(donnees())));

    expect(await screen.findByText("Impossible de charger le tableau de bord")).toBeInTheDocument();
    echec = false;
    await userEvent.click(screen.getByRole("button", { name: "Réessayer" }));
    expect(
      await screen.findByRole("heading", { level: 2, name: "Progression de la recherche" }),
    ).toBeInTheDocument();
  });
});

describe("formatMoney", () => {
  it("formate avec la devise quand elle est connue", () => {
    expect(formatMoney("0.400000", "EUR")).toMatch(/0,40\s€/);
  });

  it("sans devise, n'invente pas de symbole", () => {
    expect(formatMoney("12.5", null)).toBe("12,5");
  });
});
