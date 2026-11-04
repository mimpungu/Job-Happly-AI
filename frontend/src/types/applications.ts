import type { ApplicationStatus } from "./application-status";

/** Types de l'API de suivi de candidatures (`/api/v1/applications`, `/api/v1/dashboard`). */

export interface OfferSummaryRef {
  offer_id: string;
  title: string;
  company_name: string | null;
  location: string | null;
  country_code: string | null;
  application_url: string;
}

export interface ApplicationItem {
  id: string;
  offer_id: string;
  offer: OfferSummaryRef | null;
  status: ApplicationStatus;
  created_at: string;
  updated_at: string;
  applied_at: string | null;
  follow_up_at: string | null;
  response_received_at: string | null;
  cv_version_id: string | null;
  letter_version_id: string | null;
}

export type EventKind = "status_change" | "note" | "interview" | "follow_up" | "other";

export interface TimelineEvent {
  id: string;
  application_id: string;
  kind: EventKind;
  occurred_at: string;
  from_status: ApplicationStatus | null;
  to_status: ApplicationStatus | null;
  body: string | null;
}

export interface Contact {
  id: string;
  application_id: string;
  name: string;
  email: string | null;
  phone: string | null;
  role: string | null;
  created_at: string | null;
}

export interface AssociatedDocument {
  document_version_id: string;
  document_id: string;
  kind: "cv" | "cover_letter";
  title: string;
  version: number;
  quality_passed: boolean | null;
  quality_score: number | null;
  /** Vrai pour la version actuellement retenue pour cette candidature. */
  is_current: boolean;
}

export interface ApplicationDetail extends ApplicationItem {
  contacts: Contact[];
  events: TimelineEvent[];
  documents: AssociatedDocument[];
  /** Statuts atteignables depuis le statut courant ; l'envoi se confirme à part. */
  allowed_transitions: ApplicationStatus[];
  can_confirm_submission: boolean;
}

export interface ApplicationPage {
  items: ApplicationItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface KanbanColumn {
  status: ApplicationStatus;
  /** Total réel de la colonne, même quand `items` n'en montre qu'une partie. */
  count: number;
  items: ApplicationItem[];
  has_more: boolean;
}

export interface KanbanView {
  columns: KanbanColumn[];
}

export interface Dossier {
  application_id: string;
  offer_id: string;
  job_title: string;
  company_name: string | null;
  application_url: string | null;
  has_cv: boolean;
  cv_version_id: string | null;
  has_letter: boolean;
  letter_version_id: string | null;
  is_ready_to_send: boolean;
  missing_elements: string[];
  warnings: string[];
}

export interface ApplicationStats {
  total_applications: number;
  sent_applications: number;
  interviews_count: number;
  offers_received_count: number;
  rejections_count: number;
  /** `null` tant qu'aucune candidature n'est envoyée : jamais de 0 % sans donnée. */
  response_rate: number | null;
  active_applications: number;
  pending_follow_ups_count: number;
  due_follow_ups_count: number;
  responses_count: number;
}

export interface ApplicationFilters {
  status: ApplicationStatus | "";
  company: string;
  title: string;
  /** « tous » | relance planifiée | relance échue. */
  followUp: "" | "planned" | "due";
  page: number;
}

export interface DocumentChoice {
  versionId: string;
  kind: "cv" | "cover_letter";
  label: string;
}

export interface AIBudget {
  /** Décimaux sérialisés en chaîne par l'API. */
  spent: string;
  limit: string | null;
  currency: string | null;
  period: string;
}

export interface RecentSearch {
  id: string;
  started_at: string;
  status: string;
  result_count: number | null;
  label: string;
}

export interface RecentActivity {
  application_id: string;
  kind: EventKind;
  occurred_at: string;
  body: string | null;
  job_title: string;
  company_name: string | null;
}

export interface MonthlyTrend {
  current: number;
  previous: number;
  /** Variation en % ; `null` sans mois précédent (aucune division par zéro). */
  percent: number | null;
}

export interface TopMatch {
  offer_id: string;
  title: string;
  company_name: string | null;
  /** Score de compatibilité sur 100 calculé par le moteur de correspondance. */
  score: number;
}

export interface InterviewEvent {
  application_id: string;
  occurred_at: string;
  job_title: string;
  company_name: string | null;
  description: string | null;
}

/** Chaque étape est un sous-ensemble de la précédente. */
export interface Funnel {
  offers: number;
  tracked: number;
  sent: number;
  responses: number;
  offers_received: number;
}

/** Chaque `null` signifie « pas de donnée », jamais zéro. */
export interface DashboardMetrics {
  display_name: string | null;
  total_offers_found: number;
  active_offers_count: number;
  active_offers_trend: MonthlyTrend;
  new_offers_count: number;
  relevant_offers_count: number | null;
  relevance_threshold: number;
  top_matches: TopMatch[];
  active_applications_count: number;
  applications_trend: MonthlyTrend;
  applications_sent_count: number;
  interviews_count: number;
  response_rate: number | null;
  funnel: Funnel;
  applications_by_status: Record<ApplicationStatus, number>;
  interviews: InterviewEvent[];
  ai_budget: AIBudget;
  recent_searches: RecentSearch[];
  recent_activities: RecentActivity[];
}

/** Document généré tel que listé par `/resumes` et `/cover-letters`. */
export interface GeneratedDocumentRef {
  id: string;
  title: string;
  versions: { id: string; version: number }[];
}
