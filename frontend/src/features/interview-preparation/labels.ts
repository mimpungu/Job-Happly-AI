import type {
  AssistMode,
  InterviewFormat,
  InterviewOutcome,
  InterviewStage,
  QuestionCategory,
} from "@/types/interviews";

export const CATEGORY_LABELS: Record<QuestionCategory, string> = {
  hr: "RH",
  behavioral: "Comportementale",
  technical: "Technique",
};

export const STAGE_LABELS: Record<InterviewStage, string> = {
  hr_screen: "Entretien RH",
  technical: "Entretien technique",
  manager: "Entretien manager",
  final: "Entretien final",
  other: "Autre",
};

export const FORMAT_LABELS: Record<InterviewFormat, string> = {
  phone: "Téléphone",
  video: "Visioconférence",
  onsite: "Sur site",
  other: "Autre",
};

export const OUTCOME_LABELS: Record<InterviewOutcome, string> = {
  pending: "En attente",
  positive: "Positive",
  negative: "Négative",
  cancelled: "Annulé",
};

export const MODE_OPTIONS: { value: AssistMode; label: string }[] = [
  { value: "none", label: "Sans IA (règles locales)" },
  { value: "local", label: "Modèle local (rien ne quitte votre machine)" },
  { value: "ai", label: "IA selon vos réglages (consentement et plafond)" },
];

export const options = <T extends string>(labels: Record<T, string>) =>
  (Object.keys(labels) as T[]).map((value) => ({ value, label: labels[value] }));
