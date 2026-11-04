import type {
  Certification,
  Education,
  Experience,
  ItemSection,
  Language,
  ProfileDocument,
  Skill,
} from "@/types/profile";

export const EMPTY_PREFERENCES = {
  job_titles: [],
  country_codes: [],
  cities: [],
  remote_types: [],
  employment_types: [],
  salary_min: null,
  salary_currency: null,
  application_languages: [],
} as const;

export function emptyDocument(): ProfileDocument {
  return {
    identity: {
      first_name: null,
      last_name: null,
      email: null,
      phone: null,
      city: null,
      country_code: null,
      headline: null,
    },
    summary: null,
    experiences: [],
    educations: [],
    skills: [],
    languages: [],
    certifications: [],
    preferences: {
      ...EMPTY_PREFERENCES,
      job_titles: [],
      country_codes: [],
      cities: [],
      remote_types: [],
      employment_types: [],
      application_languages: [],
    },
  };
}

const base = { id: null, origin: "manual", validated: false, source_text: null } as const;

export const NEW_ITEMS: { [S in ItemSection]: () => ProfileDocument[S][number] } = {
  experiences: (): Experience => ({
    ...base,
    title: null,
    company: null,
    location: null,
    start: null,
    end: null,
    is_current: false,
    description: null,
    achievements: [],
  }),
  educations: (): Education => ({
    ...base,
    degree: null,
    institution: null,
    field_of_study: null,
    start: null,
    end: null,
    description: null,
  }),
  skills: (): Skill => ({ ...base, name: "", category: null, level: null }),
  languages: (): Language => ({
    ...base,
    language_code: "",
    proficiency: null,
    level_text: null,
  }),
  certifications: (): Certification => ({
    ...base,
    name: "",
    issuer: null,
    issued_on: null,
    expires_on: null,
    credential_url: null,
  }),
};

/** Champs obligatoires manquants pour qu'un élément puisse être confirmé. */
export function missingFields(
  section: ItemSection,
  item: ProfileDocument[ItemSection][number],
): string[] {
  const manquants: string[] = [];
  const e = item as Experience & Education & Skill & Language & Certification;
  switch (section) {
    case "experiences":
      if (!e.title) manquants.push("intitulé");
      if (!e.company) manquants.push("entreprise");
      if (!e.start) manquants.push("date de début");
      break;
    case "educations":
      if (!e.degree) manquants.push("diplôme");
      if (!e.institution) manquants.push("établissement");
      break;
    case "skills":
      if (!e.name.trim()) manquants.push("nom");
      break;
    case "languages":
      if (!e.language_code) manquants.push("langue");
      if (!e.proficiency) manquants.push("niveau");
      break;
    case "certifications":
      if (!e.name.trim()) manquants.push("nom");
      break;
  }
  return manquants;
}

/** Modifier le contenu d'un élément retire sa confirmation : il doit être relu à nouveau. */
export function patchItem<S extends ItemSection>(
  doc: ProfileDocument,
  section: S,
  index: number,
  patch: Partial<ProfileDocument[S][number]>,
): ProfileDocument {
  const liste = doc[section] as ProfileDocument[S][number][];
  const confirmation = "validated" in patch ? {} : { validated: false };
  const suivants = liste.map((item, i) =>
    i === index ? { ...item, ...patch, ...confirmation } : item,
  );
  return { ...doc, [section]: suivants };
}

export function addItem(doc: ProfileDocument, section: ItemSection): ProfileDocument {
  return { ...doc, [section]: [...doc[section], NEW_ITEMS[section]()] };
}

export function removeItem(
  doc: ProfileDocument,
  section: ItemSection,
  index: number,
): ProfileDocument {
  return { ...doc, [section]: doc[section].filter((_, i) => i !== index) };
}

export function confirmItem(
  doc: ProfileDocument,
  section: ItemSection,
  index: number,
): ProfileDocument {
  return patchItem(doc, section, index, { validated: true } as Partial<
    ProfileDocument[ItemSection][number]
  >);
}

export function isDirty(draft: ProfileDocument, saved: ProfileDocument | null): boolean {
  return JSON.stringify(draft) !== JSON.stringify(saved ?? emptyDocument());
}

export function hasContent(doc: ProfileDocument): boolean {
  return isDirty(doc, null);
}

/** Nombre d'éléments importés pas encore confirmés (reste à relire). */
export function pendingReview(doc: ProfileDocument): number {
  const sections: ItemSection[] = [
    "experiences",
    "educations",
    "skills",
    "languages",
    "certifications",
  ];
  return sections.reduce((total, s) => total + doc[s].filter((i) => !i.validated).length, 0);
}

const SECTION_LABELS: Record<string, string> = {
  experiences: "Expérience",
  educations: "Formation",
  skills: "Compétence",
  languages: "Langue",
  certifications: "Certification",
  identity: "Identité",
};

const FIELD_LABELS: Record<string, string> = {
  title: "intitulé",
  company: "entreprise",
  start: "date de début",
  degree: "diplôme",
  institution: "établissement",
  proficiency: "niveau",
  first_name: "prénom",
  last_name: "nom",
  email: "e-mail",
  name: "nom",
};

/** Traduit un chemin d'erreur serveur (`experiences[0].company`) en phrase lisible. */
export function describePath(path: string): string {
  const element = /^(\w+)\[(\d+)\](?:\.(\w+))?$/.exec(path);
  if (element) {
    const [, section = "", position = "0", champ] = element;
    const nom = `${SECTION_LABELS[section] ?? section} ${Number(position) + 1}`;
    return champ ? `${nom} : ${FIELD_LABELS[champ] ?? champ}` : nom;
  }
  const simple = /^(\w+)\.(\w+)$/.exec(path);
  if (simple) {
    const [, section = "", champ = ""] = simple;
    return `${SECTION_LABELS[section] ?? section} : ${FIELD_LABELS[champ] ?? champ}`;
  }
  return path;
}

/** `experiences.0.end` (Pydantic) et `experiences[0].end` (service) désignent le même champ. */
export function normalizePath(path: string): string {
  return path.replace(/\.(\d+)(?=\.|$)/g, "[$1]");
}

const ACTIONS: Record<string, string> = {
  create: "Ajout",
  update: "Modification",
  delete: "Suppression",
  validate: "Validation",
  import: "Import",
};

const ENTITES: Record<string, string> = {
  identity: "identité",
  summary: "résumé",
  preferences: "préférences",
  experience: "expérience",
  education: "formation",
  skill: "compétence",
  language: "langue",
  certification: "certification",
  profile: "profil",
};

const CHAMPS_JOURNAL: Record<string, string> = {
  validated: "confirmation",
  title: "intitulé",
  company: "entreprise",
  degree: "diplôme",
  institution: "établissement",
  name: "nom",
  level: "niveau",
  proficiency: "niveau",
  start: "début",
  end: "fin",
  first_name: "prénom",
  last_name: "nom",
  summary: "résumé",
};

/** Phrase lisible pour une ligne du journal des modifications. */
export function describeChange(
  record: Pick<
    { entity_type: string; action: string; label: string | null; changes: Record<string, unknown> },
    "entity_type" | "action" | "label" | "changes"
  >,
): string {
  if (record.entity_type === "profile")
    return record.label ?? ACTIONS[record.action] ?? record.action;
  const action = ACTIONS[record.action] ?? record.action;
  const entite = ENTITES[record.entity_type] ?? record.entity_type;
  const nom =
    record.label && record.entity_type !== "identity" && record.entity_type !== "preferences"
      ? ` « ${record.label} »`
      : "";
  const champs =
    record.action === "update"
      ? Object.keys(record.changes)
          .map((c) => CHAMPS_JOURNAL[c] ?? c)
          .join(", ")
      : "";
  return `${action} — ${entite}${nom}${champs ? ` (${champs})` : ""}`;
}
