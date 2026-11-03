"use client";

import { Plus } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type {
  Certification,
  Education,
  Experience,
  Language,
  LanguageProficiency,
  ProfileDocument,
  Skill,
  SkillLevel,
} from "@/types/profile";

import { DateField } from "./date-field";
import { missingFields } from "./draft";
import { ItemCard } from "./item-card";

export interface SectionProps {
  doc: ProfileDocument;
  onChange: (doc: ProfileDocument) => void;
  patch: <S extends keyof PatchMap>(section: S, index: number, patch: Partial<PatchMap[S]>) => void;
  add: (section: keyof PatchMap) => void;
  remove: (section: keyof PatchMap, index: number) => void;
  confirm: (section: keyof PatchMap, index: number) => void;
}

export interface PatchMap {
  experiences: Experience;
  educations: Education;
  skills: Skill;
  languages: Language;
  certifications: Certification;
}

const vide = (valeur: string): string | null => (valeur.trim() === "" ? null : valeur);

function TextField({
  label,
  value,
  onChange,
  maxLength = 200,
  hint,
}: {
  label: string;
  value: string | null;
  onChange: (valeur: string | null) => void;
  maxLength?: number;
  hint?: string;
}) {
  return (
    <Field label={label} hint={hint}>
      {(champ) => (
        <Input
          {...champ}
          value={value ?? ""}
          maxLength={maxLength}
          onChange={(e) => onChange(vide(e.target.value))}
        />
      )}
    </Field>
  );
}

function SectionList({
  title,
  addLabel,
  onAdd,
  empty,
  children,
  count,
}: {
  title: string;
  addLabel: string;
  onAdd: () => void;
  empty: string;
  count: number;
  children: ReactNode;
}) {
  return (
    <section aria-label={title} className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-foreground">{title}</h2>
        <Button variant="secondary" size="sm" onClick={onAdd}>
          <Plus className="size-4" aria-hidden="true" />
          {addLabel}
        </Button>
      </div>
      {count === 0 ? <p className="text-sm text-foreground-muted">{empty}</p> : null}
      <ul className="flex flex-col gap-4">{children}</ul>
    </section>
  );
}

export function IdentitySection({ doc, onChange }: Pick<SectionProps, "doc" | "onChange">) {
  const { identity } = doc;
  const maj = (champ: keyof typeof identity, valeur: string | null) =>
    onChange({ ...doc, identity: { ...identity, [champ]: valeur } });
  return (
    <section aria-label="Identité" className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold text-foreground">Identité</h2>
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          label="Prénom"
          value={identity.first_name}
          maxLength={120}
          onChange={(v) => maj("first_name", v)}
        />
        <TextField
          label="Nom"
          value={identity.last_name}
          maxLength={120}
          onChange={(v) => maj("last_name", v)}
        />
        <TextField
          label="E-mail"
          value={identity.email}
          maxLength={320}
          onChange={(v) => maj("email", v)}
        />
        <TextField
          label="Téléphone"
          value={identity.phone}
          maxLength={40}
          onChange={(v) => maj("phone", v)}
        />
        <TextField
          label="Ville"
          value={identity.city}
          maxLength={120}
          onChange={(v) => maj("city", v)}
        />
        <TextField
          label="Pays"
          value={identity.country_code}
          maxLength={2}
          hint="Code ISO, ex. FR"
          onChange={(v) => maj("country_code", v ? v.toUpperCase() : null)}
        />
      </div>
      <TextField
        label="Titre professionnel"
        value={identity.headline}
        onChange={(v) => maj("headline", v)}
      />
      <Field label="Résumé">
        {(champ) => (
          <Textarea
            {...champ}
            rows={4}
            maxLength={3000}
            value={doc.summary ?? ""}
            onChange={(e) => onChange({ ...doc, summary: vide(e.target.value) })}
          />
        )}
      </Field>
    </section>
  );
}

export function ExperiencesSection({ doc, patch, add, remove, confirm }: SectionProps) {
  return (
    <SectionList
      title="Expériences professionnelles"
      addLabel="Ajouter une expérience"
      onAdd={() => add("experiences")}
      count={doc.experiences.length}
      empty="Aucune expérience. Ajoutez-en une ou importez un CV."
    >
      {doc.experiences.map((e, i) => (
        <ItemCard
          key={e.id ?? `nouveau-${i}`}
          title={e.title ?? `Expérience ${i + 1}`}
          origin={e.origin}
          validated={e.validated}
          missing={missingFields("experiences", e)}
          sourceText={e.source_text}
          onConfirm={() => confirm("experiences", i)}
          onRemove={() => remove("experiences", i)}
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label="Intitulé"
              value={e.title}
              onChange={(v) => patch("experiences", i, { title: v })}
            />
            <TextField
              label="Entreprise"
              value={e.company}
              onChange={(v) => patch("experiences", i, { company: v })}
            />
            <TextField
              label="Lieu"
              value={e.location}
              onChange={(v) => patch("experiences", i, { location: v })}
            />
            <div />
            <DateField
              label="Début"
              value={e.start}
              onChange={(v) => patch("experiences", i, { start: v })}
            />
            <div className="flex flex-col gap-2">
              <DateField
                label="Fin"
                value={e.end}
                disabled={e.is_current}
                onChange={(v) => patch("experiences", i, { end: v })}
              />
              <label className="flex items-center gap-2 text-sm text-foreground">
                <input
                  type="checkbox"
                  className="size-4 accent-accent"
                  checked={e.is_current}
                  onChange={(ev) =>
                    patch("experiences", i, {
                      is_current: ev.target.checked,
                      ...(ev.target.checked ? { end: null } : {}),
                    })
                  }
                />
                Poste actuel
              </label>
            </div>
          </div>
          <Field label="Description">
            {(champ) => (
              <Textarea
                {...champ}
                maxLength={5000}
                value={e.description ?? ""}
                onChange={(ev) => patch("experiences", i, { description: vide(ev.target.value) })}
              />
            )}
          </Field>
          <Field label="Réalisations" hint="Une par ligne.">
            {(champ) => (
              <Textarea
                {...champ}
                rows={4}
                value={e.achievements.join("\n")}
                onChange={(ev) =>
                  patch("experiences", i, {
                    achievements: ev.target.value.split("\n").filter((l) => l.trim() !== ""),
                  })
                }
              />
            )}
          </Field>
        </ItemCard>
      ))}
    </SectionList>
  );
}

export function EducationsSection({ doc, patch, add, remove, confirm }: SectionProps) {
  return (
    <SectionList
      title="Formations"
      addLabel="Ajouter une formation"
      onAdd={() => add("educations")}
      count={doc.educations.length}
      empty="Aucune formation."
    >
      {doc.educations.map((f, i) => (
        <ItemCard
          key={f.id ?? `nouveau-${i}`}
          title={f.degree ?? `Formation ${i + 1}`}
          origin={f.origin}
          validated={f.validated}
          missing={missingFields("educations", f)}
          sourceText={f.source_text}
          onConfirm={() => confirm("educations", i)}
          onRemove={() => remove("educations", i)}
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label="Diplôme"
              value={f.degree}
              onChange={(v) => patch("educations", i, { degree: v })}
            />
            <TextField
              label="Établissement"
              value={f.institution}
              onChange={(v) => patch("educations", i, { institution: v })}
            />
            <TextField
              label="Domaine"
              value={f.field_of_study}
              onChange={(v) => patch("educations", i, { field_of_study: v })}
            />
            <div />
            <DateField
              label="Début"
              value={f.start}
              onChange={(v) => patch("educations", i, { start: v })}
            />
            <DateField
              label="Fin ou obtention"
              value={f.end}
              onChange={(v) => patch("educations", i, { end: v })}
            />
          </div>
        </ItemCard>
      ))}
    </SectionList>
  );
}

const NIVEAUX_COMPETENCE: { value: SkillLevel; label: string }[] = [
  { value: "beginner", label: "Débutant" },
  { value: "intermediate", label: "Intermédiaire" },
  { value: "advanced", label: "Avancé" },
  { value: "expert", label: "Expert" },
];

export function SkillsSection({ doc, patch, add, remove, confirm }: SectionProps) {
  return (
    <SectionList
      title="Compétences"
      addLabel="Ajouter une compétence"
      onAdd={() => add("skills")}
      count={doc.skills.length}
      empty="Aucune compétence."
    >
      {doc.skills.map((s, i) => (
        <ItemCard
          key={s.id ?? `nouveau-${i}`}
          title={s.name || `Compétence ${i + 1}`}
          origin={s.origin}
          validated={s.validated}
          missing={missingFields("skills", s)}
          sourceText={s.source_text}
          onConfirm={() => confirm("skills", i)}
          onRemove={() => remove("skills", i)}
        >
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Nom">
              {(champ) => (
                <Input
                  {...champ}
                  maxLength={120}
                  value={s.name}
                  onChange={(e) => patch("skills", i, { name: e.target.value })}
                />
              )}
            </Field>
            <TextField
              label="Catégorie"
              value={s.category}
              maxLength={80}
              onChange={(v) => patch("skills", i, { category: v })}
            />
            <Field label="Niveau" hint="Facultatif : « non renseigné » n'est pas « débutant ».">
              {({ id }) => (
                <Select
                  id={id}
                  options={NIVEAUX_COMPETENCE}
                  placeholder="Non renseigné"
                  value={s.level ?? ""}
                  onChange={(e) =>
                    patch("skills", i, { level: (e.target.value || null) as SkillLevel | null })
                  }
                />
              )}
            </Field>
          </div>
        </ItemCard>
      ))}
    </SectionList>
  );
}

const NIVEAUX_LANGUE: { value: LanguageProficiency; label: string }[] = [
  { value: "a1", label: "A1" },
  { value: "a2", label: "A2" },
  { value: "b1", label: "B1" },
  { value: "b2", label: "B2" },
  { value: "c1", label: "C1" },
  { value: "c2", label: "C2" },
  { value: "native", label: "Langue maternelle" },
];

export function LanguagesSection({ doc, patch, add, remove, confirm }: SectionProps) {
  return (
    <SectionList
      title="Langues"
      addLabel="Ajouter une langue"
      onAdd={() => add("languages")}
      count={doc.languages.length}
      empty="Aucune langue."
    >
      {doc.languages.map((lg, i) => (
        <ItemCard
          key={lg.id ?? `nouveau-${i}`}
          title={lg.language_code ? lg.language_code.toUpperCase() : `Langue ${i + 1}`}
          origin={lg.origin}
          validated={lg.validated}
          missing={missingFields("languages", lg)}
          sourceText={lg.source_text}
          onConfirm={() => confirm("languages", i)}
          onRemove={() => remove("languages", i)}
        >
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Code langue" hint="Ex. fr, en, es">
              {(champ) => (
                <Input
                  {...champ}
                  maxLength={10}
                  value={lg.language_code}
                  onChange={(e) =>
                    patch("languages", i, { language_code: e.target.value.toLowerCase().trim() })
                  }
                />
              )}
            </Field>
            <Field
              label="Niveau"
              hint={
                lg.level_text && !lg.proficiency
                  ? `Dans le CV : « ${lg.level_text} » — choisissez un niveau.`
                  : undefined
              }
            >
              {({ id }) => (
                <Select
                  id={id}
                  options={NIVEAUX_LANGUE}
                  placeholder="À préciser"
                  value={lg.proficiency ?? ""}
                  onChange={(e) =>
                    patch("languages", i, {
                      proficiency: (e.target.value || null) as LanguageProficiency | null,
                    })
                  }
                />
              )}
            </Field>
          </div>
        </ItemCard>
      ))}
    </SectionList>
  );
}

export function CertificationsSection({ doc, patch, add, remove, confirm }: SectionProps) {
  return (
    <SectionList
      title="Certifications"
      addLabel="Ajouter une certification"
      onAdd={() => add("certifications")}
      count={doc.certifications.length}
      empty="Aucune certification."
    >
      {doc.certifications.map((c, i) => (
        <ItemCard
          key={c.id ?? `nouveau-${i}`}
          title={c.name || `Certification ${i + 1}`}
          origin={c.origin}
          validated={c.validated}
          missing={missingFields("certifications", c)}
          sourceText={c.source_text}
          onConfirm={() => confirm("certifications", i)}
          onRemove={() => remove("certifications", i)}
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Nom">
              {(champ) => (
                <Input
                  {...champ}
                  maxLength={200}
                  value={c.name}
                  onChange={(e) => patch("certifications", i, { name: e.target.value })}
                />
              )}
            </Field>
            <TextField
              label="Organisme"
              value={c.issuer}
              onChange={(v) => patch("certifications", i, { issuer: v })}
            />
            <DateField
              label="Obtenue"
              value={c.issued_on}
              onChange={(v) => patch("certifications", i, { issued_on: v })}
            />
            <DateField
              label="Expire"
              value={c.expires_on}
              onChange={(v) => patch("certifications", i, { expires_on: v })}
            />
          </div>
        </ItemCard>
      ))}
    </SectionList>
  );
}
