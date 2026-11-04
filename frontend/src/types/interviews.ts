/** Contrats de l'API de préparation aux entretiens (EPIC 016). */

export const ASSIST_MODES = ["none", "local", "ai"] as const;
export type AssistMode = (typeof ASSIST_MODES)[number];

export type QuestionCategory = "hr" | "behavioral" | "technical";
export type InterviewStage = "hr_screen" | "technical" | "manager" | "final" | "other";
export type InterviewFormat = "phone" | "video" | "onsite" | "other";
export type InterviewOutcome = "pending" | "positive" | "negative" | "cancelled";

export interface InterviewQuestion {
  id: string;
  category: QuestionCategory;
  text: string;
  rationale: string;
  skill: string | null;
  skill_gap: boolean;
  source: "rules" | "ai";
}

export interface Highlight {
  experience_label: string;
  matched_terms: string[];
  achievements: string[];
}

export interface AnswerOutline {
  question_id: string;
  experience_label: string | null;
  situation: string | null;
  actions: string[];
  result: string | null;
  to_complete: string[];
}

export interface PreparationContent {
  questions: InterviewQuestion[];
  pitch: string;
  pitch_to_complete: string[];
  highlights: Highlight[];
  answers: AnswerOutline[];
  recruiter_questions: string[];
  skills_matched: string[];
  skills_to_prepare: string[];
  warnings: string[];
}

export interface AiStatus {
  requested: AssistMode;
  status: "not_requested" | "applied" | "unavailable";
  added?: number;
  reason?: string;
}

export interface Preparation {
  id: string;
  application_id: string;
  content: PreparationContent;
  meta: { language: string; cv_version_id: string | null; ai: AiStatus };
  created_at: string;
  updated_at: string;
}

export interface AnswerFeedback {
  score: number;
  strengths: string[];
  improvements: string[];
  unverified_numbers: string[];
  ai_comments: string[];
  ai_status: "applied" | "unavailable" | null;
}

export interface SimulationAnswer {
  question_id: string;
  text: string;
  answered_at: string;
  feedback: AnswerFeedback;
}

export interface SimulationSummary {
  answered: number;
  total: number;
  /** `null` sans réponse : pas de moyenne sans donnée. */
  average_score: number | null;
  best_question_id: string | null;
  weakest_question_id: string | null;
  unanswered: string[];
}

export interface Simulation {
  id: string;
  application_id: string;
  status: "in_progress" | "completed";
  questions: InterviewQuestion[];
  answers: SimulationAnswer[];
  summary: SimulationSummary;
  created_at: string | null;
  completed_at: string | null;
}

export interface FollowUpDraft {
  subject: string;
  body: string;
  suggested_follow_up_at: string;
}

export interface Interview {
  id: string;
  application_id: string;
  stage: InterviewStage;
  format: InterviewFormat;
  scheduled_at: string | null;
  location: string | null;
  interviewers: string[];
  notes: string | null;
  outcome: InterviewOutcome;
  feedback_notes: string | null;
  follow_up_draft: FollowUpDraft | null;
  created_at: string;
  updated_at: string;
}

export interface InterviewInput {
  stage: InterviewStage;
  format: InterviewFormat;
  scheduled_at: string | null;
  location: string | null;
  interviewers: string[];
  notes: string | null;
  outcome: InterviewOutcome;
  feedback_notes: string | null;
}
