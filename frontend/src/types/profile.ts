/** Contrats de l'API du profil maître (voir docs/API.md). Les dates sont `{year, month|null}`. */

export interface DocDate {
  year: number;
  month: number | null;
}

export type DataOrigin = "imported" | "manual";
export type SkillLevel = "beginner" | "intermediate" | "advanced" | "expert";
export type LanguageProficiency = "a1" | "a2" | "b1" | "b2" | "c1" | "c2" | "native";

interface ItemBase {
  id: string | null;
  origin: DataOrigin;
  /** Confirmé par l'utilisateur après relecture. */
  validated: boolean;
  /** Extrait du CV d'origine (traçabilité). */
  source_text: string | null;
}

export interface Identity {
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  phone: string | null;
  city: string | null;
  country_code: string | null;
  headline: string | null;
}

export interface Experience extends ItemBase {
  title: string | null;
  company: string | null;
  location: string | null;
  start: DocDate | null;
  end: DocDate | null;
  is_current: boolean;
  description: string | null;
  achievements: string[];
}

export interface Education extends ItemBase {
  degree: string | null;
  institution: string | null;
  field_of_study: string | null;
  start: DocDate | null;
  end: DocDate | null;
  description: string | null;
}

export interface Skill extends ItemBase {
  name: string;
  category: string | null;
  level: SkillLevel | null;
}

export interface Language extends ItemBase {
  language_code: string;
  proficiency: LanguageProficiency | null;
  level_text: string | null;
}

export interface Certification extends ItemBase {
  name: string;
  issuer: string | null;
  issued_on: DocDate | null;
  expires_on: DocDate | null;
  credential_url: string | null;
}

export interface Preferences {
  job_titles: string[];
  country_codes: string[];
  cities: string[];
  remote_types: string[];
  employment_types: string[];
  salary_min: string | null;
  salary_currency: string | null;
  application_languages: string[];
}

export interface ProfileDocument {
  identity: Identity;
  summary: string | null;
  experiences: Experience[];
  educations: Education[];
  skills: Skill[];
  languages: Language[];
  certifications: Certification[];
  preferences: Preferences;
}

export type ProfileStatus = "draft" | "validated" | "archived";

export interface ProfileMeta {
  id: string;
  version: number;
  status: ProfileStatus;
  created_at: string;
  updated_at: string;
  validated_at: string | null;
}

export interface StoredProfile {
  meta: ProfileMeta;
  document: ProfileDocument;
}

export interface ChangeRecord {
  id: string;
  profile_version: number;
  created_at: string;
  entity_type: string;
  entity_id: string | null;
  action: string;
  label: string | null;
  changes: Record<string, unknown>;
}

export interface CvImportResult {
  filename: string;
  format: string;
  page_count: number | null;
  warnings: string[];
  text: string;
  proposed_document: ProfileDocument;
}

export type ItemSection = "experiences" | "educations" | "skills" | "languages" | "certifications";
