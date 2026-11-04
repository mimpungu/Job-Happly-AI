import type { OfferFilters, OfferSort, StateFilter } from "@/types/jobs";

export const SORTS: readonly { value: OfferSort; label: string }[] = [
  { value: "published_desc", label: "Plus récentes" },
  { value: "published_asc", label: "Plus anciennes" },
  { value: "title_asc", label: "Intitulé (A→Z)" },
  { value: "company_asc", label: "Entreprise (A→Z)" },
  { value: "salary_desc", label: "Salaire décroissant" },
  { value: "recently_seen", label: "Vues récemment" },
  { value: "score_desc", label: "Meilleure compatibilité" },
];

export const EMPLOYMENT_TYPES = [
  { value: "permanent", label: "CDI" },
  { value: "fixed_term", label: "CDD" },
  { value: "internship", label: "Stage" },
  { value: "apprenticeship", label: "Alternance" },
  { value: "freelance", label: "Freelance" },
  { value: "part_time", label: "Temps partiel" },
  { value: "temporary", label: "Intérim" },
  { value: "other", label: "Autre" },
] as const;

export const REMOTE_TYPES = [
  { value: "on_site", label: "Sur site" },
  { value: "hybrid", label: "Hybride" },
  { value: "remote", label: "Télétravail" },
] as const;

export const DEFAULT_FILTERS: OfferFilters = {
  text: "",
  company: "",
  city: "",
  country: "",
  employmentType: "",
  remoteType: "",
  salaryMin: "",
  salaryCurrency: "EUR",
  publishedSince: "",
  minScore: "",
  language: "",
  maxExperience: "",
  multilingual: false,
  titles: "",
  sort: "published_desc",
  state: "visible",
  page: 1,
};

const SORT_VALUES = new Set<string>(SORTS.map((s) => s.value));
const STATE_VALUES = new Set<string>(["visible", "saved", "ignored", "all"]);

/** Un score minimal n'est accepté que s'il est un entier de 0 à 100 ; sinon pas de filtre. */
function scoreValide(valeur: string): string {
  const nombre = Number(valeur);
  return valeur !== "" && Number.isInteger(nombre) && nombre >= 0 && nombre <= 100 ? valeur : "";
}

/** Entier de 0 à `max` ; sinon pas de filtre. */
function entierBorne(valeur: string, max: number): string {
  const nombre = Number(valeur);
  return valeur !== "" && Number.isInteger(nombre) && nombre >= 0 && nombre <= max ? valeur : "";
}

/** Liste d'intitulés saisie à la virgule : valeurs nettoyées, sans doublon, bornées. */
export function parseTitles(saisie: string): string[] {
  const vus = new Set<string>();
  for (const brut of saisie.split(",")) {
    const titre = brut.trim().slice(0, 100);
    if (titre) vus.add(titre);
  }
  return [...vus].slice(0, 10);
}

/** Une valeur d'URL est une entrée non fiable : toute valeur inattendue retombe sur le défaut. */
export function filtersFromParams(params: URLSearchParams): OfferFilters {
  const lire = (cle: string) => (params.get(cle) ?? "").trim();
  const tri = lire("sort");
  const etat = lire("state");
  const page = Number.parseInt(lire("page"), 10);
  return {
    text: lire("text"),
    company: lire("company"),
    city: lire("city"),
    country: lire("country").toUpperCase(),
    employmentType: lire("employment"),
    remoteType: lire("remote"),
    salaryMin: lire("salary_min"),
    salaryCurrency: lire("currency").toUpperCase() || DEFAULT_FILTERS.salaryCurrency,
    publishedSince: lire("since"),
    minScore: scoreValide(lire("min_score")),
    language: /^[a-z]{2}$/i.test(lire("language")) ? lire("language").toLowerCase() : "",
    maxExperience: entierBorne(lire("max_experience"), 40),
    multilingual: lire("multilingual") === "1",
    titles: lire("titles"),
    sort: SORT_VALUES.has(tri) ? (tri as OfferSort) : DEFAULT_FILTERS.sort,
    state: STATE_VALUES.has(etat) ? (etat as StateFilter) : DEFAULT_FILTERS.state,
    page: Number.isInteger(page) && page >= 1 ? page : 1,
  };
}

/** Paramètres d'URL de l'interface : seules les valeurs non vides et non par défaut sont écrites. */
export function filtersToParams(filters: OfferFilters): URLSearchParams {
  const params = new URLSearchParams();
  const ecrire = (cle: string, valeur: string) => {
    if (valeur) params.set(cle, valeur);
  };
  ecrire("text", filters.text.trim());
  ecrire("company", filters.company.trim());
  ecrire("city", filters.city.trim());
  ecrire("country", filters.country.trim().toUpperCase());
  ecrire("employment", filters.employmentType);
  ecrire("remote", filters.remoteType);
  if (filters.salaryMin.trim()) {
    params.set("salary_min", filters.salaryMin.trim());
    params.set("currency", filters.salaryCurrency.trim().toUpperCase());
  }
  ecrire("since", filters.publishedSince);
  ecrire("min_score", filters.minScore);
  ecrire("language", filters.language);
  ecrire("max_experience", filters.maxExperience);
  if (filters.multilingual) params.set("multilingual", "1");
  ecrire("titles", filters.titles.trim());
  if (filters.sort !== DEFAULT_FILTERS.sort) params.set("sort", filters.sort);
  if (filters.state !== DEFAULT_FILTERS.state) params.set("state", filters.state);
  if (filters.page > 1) params.set("page", String(filters.page));
  return params;
}

/** Paramètres de la requête `GET /offers` (voir docs/API.md). */
export function filtersToApiQuery(filters: OfferFilters, pageSize: number): URLSearchParams {
  const params = new URLSearchParams();
  const ecrire = (cle: string, valeur: string) => {
    if (valeur) params.set(cle, valeur);
  };
  ecrire("text", filters.text.trim());
  ecrire("company", filters.company.trim());
  ecrire("city", filters.city.trim());
  ecrire("country_codes", filters.country.trim().toUpperCase());
  ecrire("employment_types", filters.employmentType);
  ecrire("remote_types", filters.remoteType);
  if (filters.salaryMin.trim()) {
    params.set("salary_min", filters.salaryMin.trim());
    params.set("salary_currency", filters.salaryCurrency.trim().toUpperCase());
  }
  if (filters.publishedSince) params.set("published_since", `${filters.publishedSince}T00:00:00Z`);
  if (filters.minScore) params.set("min_score", filters.minScore);
  ecrire("language", filters.language);
  ecrire("max_experience_years", filters.maxExperience);
  if (filters.multilingual) params.set("multilingual", "true");
  params.set("sort", filters.sort);
  params.set("state", filters.state);
  params.set("page", String(filters.page));
  params.set("page_size", String(pageSize));
  return params;
}

/** Corps `filter` d'une recherche sauvegardée (sans page : jamais mémorisée). */
export function filtersToSavedCriteria(filters: OfferFilters): Record<string, unknown> {
  const criteres: Record<string, unknown> = { sort: filters.sort, state: filters.state };
  if (filters.text.trim()) criteres.text = filters.text.trim();
  if (filters.company.trim()) criteres.company = filters.company.trim();
  if (filters.city.trim()) criteres.city = filters.city.trim();
  if (filters.country.trim()) criteres.country_codes = [filters.country.trim().toUpperCase()];
  if (filters.employmentType) criteres.employment_types = [filters.employmentType];
  if (filters.remoteType) criteres.remote_types = [filters.remoteType];
  if (filters.salaryMin.trim()) {
    criteres.salary_min = filters.salaryMin.trim();
    criteres.salary_currency = filters.salaryCurrency.trim().toUpperCase();
  }
  if (filters.publishedSince) criteres.published_since = `${filters.publishedSince}T00:00:00Z`;
  if (filters.minScore) criteres.min_score = filters.minScore;
  if (filters.language) criteres.language = filters.language;
  if (filters.maxExperience) criteres.max_experience_years = Number(filters.maxExperience);
  if (filters.multilingual) criteres.multilingual = true;
  return criteres;
}

/** Inverse de `filtersToSavedCriteria` : réapplique une recherche sauvegardée au formulaire. */
export function filtersFromSavedCriteria(criteres: Record<string, unknown>): OfferFilters {
  const texte = (cle: string) =>
    typeof criteres[cle] === "string" ? (criteres[cle] as string) : "";
  const premier = (cle: string) => {
    const valeur = criteres[cle];
    return Array.isArray(valeur) && typeof valeur[0] === "string" ? valeur[0] : "";
  };
  const depuis = texte("published_since");
  const params = new URLSearchParams();
  params.set("sort", texte("sort"));
  params.set("state", texte("state"));
  const base = filtersFromParams(params);
  return {
    ...base,
    text: texte("text"),
    company: texte("company"),
    city: texte("city"),
    country: premier("country_codes"),
    employmentType: premier("employment_types"),
    remoteType: premier("remote_types"),
    salaryMin: texte("salary_min"),
    salaryCurrency: texte("salary_currency") || DEFAULT_FILTERS.salaryCurrency,
    publishedSince: depuis.slice(0, 10),
    minScore:
      texte("min_score") ||
      (typeof criteres.min_score === "number" ? String(criteres.min_score) : ""),
    language: texte("language"),
    maxExperience:
      typeof criteres.max_experience_years === "number"
        ? String(criteres.max_experience_years)
        : "",
    multilingual: criteres.multilingual === true,
    page: 1,
  };
}
