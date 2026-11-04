/** Contrats de l'API des CV et lettres de motivation (EPIC 012 et 013). */

export type ResumeStyle = "classic" | "modern" | "compact";
export type LengthTarget = "auto" | "one_page" | "two_pages";
export type RewriteMode = "none" | "local" | "ai";

export interface AtsCheck {
  name: string;
  status: string;
  message: string;
  details?: string | null;
}

export interface AtsReport {
  score: number;
  passed: boolean;
  checks: AtsCheck[];
  page_count: number;
  keywords_found: string[];
  keywords_missing: string[];
}

export interface AiRewriteMeta {
  requested: RewriteMode;
  status: "not_requested" | "applied" | "partial" | "unchanged" | "unavailable";
  rewritten: number;
  rejected: number;
  provider: string | null;
  reason: string | null;
}

export interface ResumeVersion {
  id: string;
  version: number;
  created_at: string;
  size_bytes: number;
  ats_report: AtsReport | null;
  generation: {
    origin: string;
    style?: string | null;
    length_target?: string | null;
    ai_rewrite?: AiRewriteMeta | null;
  } | null;
}

export interface ResumeDocument {
  id: string;
  title: string;
  language: string;
  offer_id: string | null;
  created_at: string;
  versions: ResumeVersion[];
}

export interface ResumeRequest {
  offer_id?: string;
  style: ResumeStyle;
  length_target: LengthTarget;
  language: string;
  rewrite_mode: RewriteMode;
}

export interface LetterAudit {
  score: number;
  passed: boolean;
  word_count: number;
  length_status: string;
  cv_coherent: boolean;
  page_count: number | null;
  spelling_issues: string[];
  generic_phrases_detected: string[];
  issues: string[];
}

export interface LetterVersion {
  id: string;
  version: number;
  created_at: string;
  size_bytes: number;
  audit: LetterAudit | null;
}

export interface LetterContent {
  subject: string;
  salutation: string;
  introduction: string;
  background_highlight: string;
  added_value: string;
  closing_and_call_to_action: string;
  complimentary_close: string;
  signature: string;
  word_count: number;
}

export interface CoverLetter {
  id: string;
  title: string;
  language: string;
  offer_id: string | null;
  created_at: string;
  versions: LetterVersion[];
  content: LetterContent | null;
}

export interface LetterRequest {
  offer_id: string;
  language: "fr" | "en";
  recipient_name?: string;
  motivation?: string;
}
