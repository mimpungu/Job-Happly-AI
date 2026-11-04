import type {
  ApplicationDetail,
  ApplicationItem,
  ApplicationStats,
  DashboardMetrics,
  Dossier,
} from "@/types/applications";

/** Jeux de données des tests ; les dates sont à midi UTC pour rester stables d'un fuseau à l'autre. */
export const candidature = (surcharge: Partial<ApplicationItem> = {}): ApplicationItem => ({
  id: "c1",
  offer_id: "o1",
  offer: {
    offer_id: "o1",
    title: "Développeur Python",
    company_name: "Acme",
    location: "Paris",
    country_code: "FR",
    application_url: "https://careers.example.test/apply",
  },
  status: "to_apply",
  created_at: "2026-11-01T12:00:00Z",
  updated_at: "2026-11-02T12:00:00Z",
  applied_at: null,
  follow_up_at: null,
  response_received_at: null,
  cv_version_id: null,
  letter_version_id: null,
  ...surcharge,
});

export const detail = (surcharge: Partial<ApplicationDetail> = {}): ApplicationDetail => ({
  ...candidature(),
  contacts: [],
  events: [
    {
      id: "e1",
      application_id: "c1",
      kind: "status_change",
      occurred_at: "2026-11-01T12:00:00Z",
      from_status: null,
      to_status: "to_apply",
      body: "Création de la candidature dans le CRM.",
    },
  ],
  documents: [],
  allowed_transitions: ["documents_to_prepare", "ready_to_send", "abandoned"],
  can_confirm_submission: true,
  ...surcharge,
});

export const dossier = (surcharge: Partial<Dossier> = {}): Dossier => ({
  application_id: "c1",
  offer_id: "o1",
  job_title: "Développeur Python",
  company_name: "Acme",
  application_url: "https://careers.example.test/apply",
  has_cv: false,
  cv_version_id: null,
  has_letter: false,
  letter_version_id: null,
  is_ready_to_send: false,
  missing_elements: ["CV personnalisé manquant", "Lettre de motivation manquante"],
  warnings: [],
  ...surcharge,
});

export const stats = (surcharge: Partial<ApplicationStats> = {}): ApplicationStats => ({
  total_applications: 3,
  sent_applications: 2,
  interviews_count: 1,
  offers_received_count: 0,
  rejections_count: 0,
  response_rate: 50,
  active_applications: 3,
  pending_follow_ups_count: 1,
  due_follow_ups_count: 1,
  responses_count: 1,
  ...surcharge,
});

export const dashboard = (surcharge: Partial<DashboardMetrics> = {}): DashboardMetrics => ({
  display_name: "Alea",
  total_offers_found: 12,
  active_offers_count: 10,
  active_offers_trend: { current: 4, previous: 3, percent: 33.3 },
  new_offers_count: 4,
  relevant_offers_count: 3,
  relevance_threshold: 70,
  top_matches: [
    { offer_id: "o1", title: "Développeur Python", company_name: "Acme", score: 66.2 },
    { offer_id: "o2", title: "Data Engineer", company_name: "Beta", score: 61 },
    { offer_id: "o3", title: "Backend Engineer", company_name: null, score: 55.5 },
  ],
  active_applications_count: 5,
  applications_trend: { current: 3, previous: 4, percent: -25 },
  applications_sent_count: 2,
  interviews_count: 1,
  response_rate: 50,
  funnel: { offers: 12, tracked: 6, sent: 4, responses: 2, offers_received: 1 },
  applications_by_status: {
    new_offer: 1,
    to_analyze: 0,
    to_apply: 1,
    documents_to_prepare: 0,
    ready_to_send: 0,
    sent: 1,
    pending: 1,
    interview: 1,
    second_interview: 0,
    offer_received: 1,
    rejected: 1,
    abandoned: 0,
  },
  interviews: [
    {
      application_id: "c1",
      occurred_at: "2026-11-04T09:30:00Z",
      job_title: "Développeur Python",
      company_name: "Acme",
      description: "Entretien technique",
    },
  ],
  ai_budget: { spent: "0.400000", limit: "10.00", currency: "EUR", period: "monthly" },
  recent_searches: [
    {
      id: "s1",
      started_at: "2026-11-03T12:00:00Z",
      status: "succeeded",
      result_count: 12,
      label: "python · Lyon",
    },
  ],
  recent_activities: [
    {
      application_id: "c1",
      kind: "note",
      occurred_at: "2026-11-03T12:00:00Z",
      body: "Bon contact",
      job_title: "Développeur Python",
      company_name: "Acme",
    },
  ],
  ...surcharge,
});

export const json = (corps: unknown, statut = 200) =>
  new Response(JSON.stringify(corps), { status: statut });

export const erreurApi = (code: string, message: string, statut: number) =>
  json({ error: { code, message } }, statut);
