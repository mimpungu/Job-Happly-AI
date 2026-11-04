import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import type { CriterionResult, MatchResponse, WeightsResponse } from "@/types/matching";

import { CriteriaBreakdown } from "./criteria-breakdown";
import { bandOf } from "./labels";
import { MatchPanel } from "./match-panel";
import { ScoreIndicator } from "./score-indicator";
import { SkillMatchPanel } from "./skill-match-panel";
import { WeightsEditor, poidsValide } from "./weights-editor";

const json = (corps: unknown, statut = 200) =>
  new Response(JSON.stringify(corps), { status: statut });

function afficher(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      {ui}
      <Toaster />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("bandOf", () => {
  it("découpe 0-100 en trois repères de lecture", () => {
    expect(bandOf(100)).toBe("good");
    expect(bandOf(70)).toBe("good");
    expect(bandOf(69)).toBe("fair");
    expect(bandOf(40)).toBe("fair");
    expect(bandOf(39)).toBe("low");
    expect(bandOf(0)).toBe("low");
  });
});

describe("ScoreIndicator", () => {
  it("dit qu'une offre n'est pas évaluée plutôt que d'afficher 0", () => {
    render(<ScoreIndicator score={null} />);

    expect(screen.getByText("Non évalué")).toBeInTheDocument();
    expect(screen.queryByRole("meter")).toBeNull();
  });

  it("expose le score à un lecteur d'écran avec sa tranche et sa fiabilité", () => {
    render(<ScoreIndicator score="72.40" reliability="medium" />);

    const jauge = screen.getByRole("meter", { name: "Compatibilité" });
    expect(jauge).toHaveAttribute("aria-valuenow", "72");
    expect(jauge).toHaveAttribute(
      "aria-valuetext",
      "72 sur 100, bonne compatibilité, fiabilité moyenne",
    );
    expect(screen.getByText("Fiabilité moyenne")).toBeInTheDocument();
  });

  it("en version compacte, ne signale la fiabilité que lorsqu'elle est limitée", () => {
    const { rerender } = render(<ScoreIndicator score="80" reliability="high" />);
    expect(screen.queryByText(/Fiabilité/)).toBeNull();

    rerender(<ScoreIndicator score="80" reliability="low" />);
    expect(screen.getByText("Fiabilité faible")).toBeInTheDocument();
  });

  it("la version large nomme la tranche en toutes lettres (jamais la couleur seule)", () => {
    render(<ScoreIndicator score="35" reliability="high" size="large" />);

    expect(screen.getByText("Faible compatibilité")).toBeInTheDocument();
    expect(screen.getByText("Fiabilité élevée")).toBeInTheDocument();
  });
});

describe("SkillMatchPanel", () => {
  const items = [
    { kind: "present" as const, label: "SQL", detail: "Dans votre profil : SQL", criterion: null },
    {
      kind: "partial" as const,
      label: "MySQL",
      detail: "Proche de « PostgreSQL »",
      criterion: null,
    },
    { kind: "absent" as const, label: "Docker", detail: "Compétence souhaitée", criterion: null },
    {
      kind: "unverifiable" as const,
      label: "Esprit d'équipe",
      detail: "À évaluer vous-même",
      criterion: null,
    },
  ];

  it("distingue les quatre états et rappelle qu'absent ne veut pas dire incompétent", () => {
    render(<SkillMatchPanel items={items} />);

    for (const [titre, competence] of [
      ["Présente (1)", "SQL"],
      ["Transférable (1)", "MySQL"],
      ["Absente de votre profil (1)", "Docker"],
      ["À évaluer vous-même (1)", "Esprit d'équipe"],
    ] as const) {
      const groupe = screen.getByRole("region", { name: titre.replace(/ \(\d\)$/, "") });
      expect(within(groupe).getByRole("heading", { name: titre })).toBeInTheDocument();
      expect(within(groupe).getByText(competence)).toBeInTheDocument();
    }
    expect(screen.getByText(/ne veut pas dire que vous ne la maîtrisez pas/)).toBeInTheDocument();
  });

  it("n'affiche pas le rappel s'il n'y a aucune compétence absente", () => {
    render(<SkillMatchPanel items={items.slice(0, 2)} />);

    expect(screen.queryByText(/ne veut pas dire/)).toBeNull();
  });

  it("explique l'absence de compétences repérées", () => {
    render(<SkillMatchPanel items={[]} />);

    expect(screen.getByText(/Aucune compétence n'a pu être repérée/)).toBeInTheDocument();
  });
});

describe("CriteriaBreakdown", () => {
  const critere = (surcharge: Partial<CriterionResult>): CriterionResult => ({
    criterion: "skills",
    status: "evaluated",
    weight: "25",
    score: "0.8",
    explanation: "Explication.",
    items: [],
    uncertain: false,
    ...surcharge,
  });

  it("une donnée manquante n'est pas présentée comme une note de 0", () => {
    render(
      <CriteriaBreakdown
        criteria={[
          critere({}),
          critere({
            criterion: "salary",
            status: "missing_data",
            score: null,
            explanation: "L'offre ne précise pas de salaire.",
          }),
        ]}
      />,
    );

    expect(screen.getByText("Données manquantes — non compté")).toBeInTheDocument();
    expect(screen.getByText("L'offre ne précise pas de salaire.")).toBeInTheDocument();
    expect(screen.getAllByRole("meter")).toHaveLength(1); // seul le critère évalué a une jauge
  });

  it("calcule la part de chaque critère et signale un résultat à vérifier", () => {
    render(
      <CriteriaBreakdown
        criteria={[
          critere({ criterion: "skills", weight: "75" }),
          critere({ criterion: "experience", weight: "25", uncertain: true }),
        ]}
      />,
    );

    expect(screen.getByText("Poids 75 %")).toBeInTheDocument();
    expect(screen.getByText("Poids 25 %")).toBeInTheDocument();
    expect(screen.getByText("À vérifier")).toBeInTheDocument();
    expect(screen.getAllByText("80 %").length).toBe(2);
  });
});

describe("MatchPanel", () => {
  const reponse = (): MatchResponse => ({
    profile_version: 2,
    computed_at: "2026-11-04T12:00:00Z",
    result: {
      score: "72.00",
      coverage: "0.60",
      reliability: "medium",
      weights_version: "m1-abc",
      summary: "Score 72/100 — fiabilité moyenne.",
      disclaimer: "Score indicatif d'aide au tri. Ce n'est pas une probabilité d'être recruté.",
      matches: [],
      gaps: [],
      criteria: [
        {
          criterion: "skills",
          status: "evaluated",
          weight: "25",
          score: "0.8",
          explanation: "2 compétences présentes.",
          items: [{ kind: "present", label: "SQL", detail: null, criterion: "skills" }],
          uncertain: false,
        },
      ],
    },
  });

  it("affiche score, résumé, couverture, avertissement, compétences et détail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(reponse())));
    afficher(<MatchPanel offerId="o1" />);

    expect(screen.getByRole("status", { name: "Calcul de la compatibilité" })).toBeInTheDocument();
    expect(await screen.findByText("Score 72/100 — fiabilité moyenne.")).toBeInTheDocument();
    expect(screen.getByText(/Score calculé sur 60 % du poids des critères/)).toBeInTheDocument();
    expect(screen.getByText(/version 2 de votre profil/)).toBeInTheDocument();
    expect(screen.getByText(/Ce n'est pas une probabilité d'être recruté/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Détail par critère" })).toBeInTheDocument();
    expect(screen.getByText("SQL")).toBeInTheDocument();
  });

  it("renvoie vers l'Espace CV quand aucun profil n'est validé", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        json(
          {
            error: {
              code: "no_validated_profile",
              message: "Validez votre profil dans « Espace CV ».",
            },
          },
          409,
        ),
      ),
    );
    afficher(<MatchPanel offerId="o1" />);

    expect(await screen.findByText("Compatibilité indisponible")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Valider mon profil" })).toHaveAttribute(
      "href",
      "/cv-studio",
    );
    expect(screen.queryByRole("button", { name: "Réessayer" })).toBeNull();
  });

  it("propose de réessayer après une erreur inattendue", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));
    afficher(<MatchPanel offerId="o1" />);

    expect(await screen.findByText("Impossible de calculer la compatibilité")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Réessayer" })).toBeInTheDocument();
  });
});

describe("WeightsEditor", () => {
  const vue = (surcharge: Partial<WeightsResponse> = {}): WeightsResponse => ({
    version: "m1-aaaa",
    is_default: true,
    criteria: [
      { key: "job_title", label: "Métier", weight: "20", default_weight: "20" },
      { key: "skills", label: "Compétences", weight: "25", default_weight: "25" },
      { key: "salary", label: "Salaire", weight: "5", default_weight: "5" },
    ],
    ...surcharge,
  });

  function simuler(initiale = vue()) {
    let etat = initiale;
    const appels: { url: string; methode: string; corps?: unknown }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const methode = init?.method ?? "GET";
        const corps = typeof init?.body === "string" ? JSON.parse(init.body) : undefined;
        appels.push({ url, methode, corps });
        if (url.endsWith("/matching/recompute"))
          return json({
            computed: 3,
            not_computable: 1,
            profile_version: 1,
            weights_version: etat.version,
          });
        if (methode === "PUT") {
          etat = vue({
            is_default: false,
            version: "m1-bbbb",
            criteria: etat.criteria.map((c) => ({ ...c, weight: String(corps.weights[c.key]) })),
          });
        }
        if (methode === "DELETE") etat = vue();
        return json(etat);
      }),
    );
    return appels;
  }

  it("valide la saisie d'un poids", () => {
    expect(poidsValide("25")).toBe(true);
    expect(poidsValide("0")).toBe(true);
    expect(poidsValide("12.5")).toBe(true);
    for (const invalide of ["", "  ", "abc", "-1", "101", "NaN", "Infinity"]) {
      expect(poidsValide(invalide)).toBe(false);
    }
  });

  it("affiche chaque critère avec son poids par défaut et sa part", async () => {
    simuler();
    afficher(<WeightsEditor />);

    expect(await screen.findByLabelText("Métier")).toHaveValue(20);
    expect(screen.getByText(/Par défaut : 25 · part actuelle : 50 %/)).toBeInTheDocument();
    expect(screen.getByText("Pondérations par défaut · version m1-aaaa")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enregistrer" })).toBeDisabled();
  });

  it("enregistre des poids personnalisés sous forme de nombres", async () => {
    const appels = simuler();
    afficher(<WeightsEditor />);
    const competences = await screen.findByLabelText("Compétences");

    await userEvent.clear(competences);
    await userEvent.type(competences, "40");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => expect(appels.some((a) => a.methode === "PUT")).toBe(true));
    expect(appels.find((a) => a.methode === "PUT")?.corps).toEqual({
      weights: { job_title: 20, skills: 40, salary: 5 },
    });
    expect(
      await screen.findByText(/Pondérations personnalisées · version m1-bbbb/),
    ).toBeInTheDocument();
    expect(await screen.findByText(/Recalculez les scores pour les appliquer/)).toBeInTheDocument();
  });

  it("refuse un poids invalide sans rien envoyer", async () => {
    const appels = simuler();
    afficher(<WeightsEditor />);
    const metier = await screen.findByLabelText("Métier");

    await userEvent.clear(metier);

    expect(screen.getByText("Saisissez un nombre entre 0 et 100.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enregistrer" })).toBeDisabled();
    expect(appels.filter((a) => a.methode === "PUT")).toHaveLength(0);
  });

  it("exige au moins un critère actif", async () => {
    simuler();
    afficher(<WeightsEditor />);

    for (const nom of ["Métier", "Compétences", "Salaire"]) {
      const champ = await screen.findByLabelText(nom);
      await userEvent.clear(champ);
      await userEvent.type(champ, "0");
    }

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Au moins un critère doit avoir un poids supérieur à 0",
    );
    expect(screen.getByRole("button", { name: "Enregistrer" })).toBeDisabled();
  });

  it("rétablit les valeurs par défaut", async () => {
    const appels = simuler(vue({ is_default: false, version: "m1-bbbb" }));
    afficher(<WeightsEditor />);
    await screen.findByLabelText("Métier");

    await userEvent.click(screen.getByRole("button", { name: "Rétablir les valeurs par défaut" }));

    expect(await screen.findByText("Pondérations par défaut rétablies.")).toBeInTheDocument();
    expect(appels.some((a) => a.methode === "DELETE")).toBe(true);
  });

  it("recalcule les scores et annonce le résultat", async () => {
    simuler();
    afficher(<WeightsEditor />);
    await screen.findByLabelText("Métier");

    await userEvent.click(screen.getByRole("button", { name: "Recalculer les scores" }));

    expect(
      await screen.findByText("3 offres évaluées · 1 sans donnée suffisante."),
    ).toBeInTheDocument();
  });

  it("interdit de recalculer avec des poids non enregistrés", async () => {
    simuler();
    afficher(<WeightsEditor />);
    const metier = await screen.findByLabelText("Métier");

    await userEvent.type(metier, "5");

    expect(screen.getByRole("button", { name: "Recalculer les scores" })).toBeDisabled();
  });
});
