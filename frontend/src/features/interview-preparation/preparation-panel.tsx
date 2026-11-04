"use client";

import { Sparkles } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toaster";
import type { AnswerOutline, AssistMode, InterviewQuestion, Preparation } from "@/types/interviews";

import { AiNotice } from "./ai-notice";
import { CATEGORY_LABELS, MODE_OPTIONS } from "./labels";
import { useGeneratePreparation, usePreparation } from "./use-interviews";
import { TaskCostNote } from "@/features/ai/task-cost-note";

export function PreparationPanel({ applicationId }: { applicationId: string }) {
  const preparation = usePreparation(applicationId);
  const generer = useGeneratePreparation(applicationId);
  const [mode, setMode] = useState<AssistMode>("none");

  const lancer = () =>
    generer.mutate(mode, {
      onSuccess: () => toast.success("Préparation générée."),
      onError: (erreur) => toast.error(erreur.message),
    });

  const commande = (
    <div className="flex flex-wrap items-end gap-3">
      <Field label="Assistance">
        {(champ) => (
          <Select
            {...champ}
            value={mode}
            options={MODE_OPTIONS}
            onChange={(e) => setMode(e.target.value as AssistMode)}
          />
        )}
      </Field>
      <Button onClick={lancer} loading={generer.isPending}>
        {preparation.data ? "Régénérer la préparation" : "Préparer l'entretien"}
      </Button>
      <div className="basis-full">
        <TaskCostNote task="interview_questions" enabled={mode === "ai"} />
      </div>
    </div>
  );

  if (preparation.isPending) {
    return <Skeleton className="h-48 w-full" role="status" aria-label="Chargement" />;
  }
  if (preparation.isError) {
    return (
      <EmptyState
        title="Impossible de charger la préparation"
        description={preparation.error.message}
        action={<Button onClick={() => void preparation.refetch()}>Réessayer</Button>}
      />
    );
  }
  if (!preparation.data) {
    return (
      <div className="flex flex-col gap-4">
        <EmptyState
          icon={Sparkles}
          title="Aucune préparation"
          description="La préparation est générée à la demande, à partir de votre profil validé et de l'offre. Sans IA, elle ne coûte rien."
        />
        {commande}
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-6">
      {commande}
      <PreparationContentView preparation={preparation.data} />
    </div>
  );
}

function PreparationContentView({ preparation }: { preparation: Preparation }) {
  const { content, meta } = preparation;
  const trames = new Map(content.answers.map((a) => [a.question_id, a]));
  return (
    <div className="flex flex-col gap-6">
      <AiNotice ai={meta.ai} />
      {content.warnings.length > 0 ? (
        <ul className="flex flex-col gap-1 rounded-md border border-warning/40 bg-warning-soft p-3 text-sm text-on-warning-soft">
          {content.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      ) : null}

      <Panel title="Présentation personnelle">
        <p className="whitespace-pre-line text-sm leading-relaxed">{content.pitch}</p>
        <p className="mt-3 text-xs text-foreground-muted">
          Les passages entre crochets sont à compléter par vous : ils ne peuvent pas être déduits de
          votre parcours.
        </p>
      </Panel>

      <Panel title="Expériences à mettre en avant">
        {content.highlights.length === 0 ? (
          <p className="text-sm text-foreground-muted">Aucune expérience dans le profil validé.</p>
        ) : (
          <ul className="flex flex-col gap-4">
            {content.highlights.map((h) => (
              <li key={h.experience_label} className="flex flex-col gap-1">
                <p className="font-medium">{h.experience_label}</p>
                {h.matched_terms.length > 0 ? (
                  <p className="flex flex-wrap gap-1.5">
                    {h.matched_terms.map((t) => (
                      <Badge key={t} variant="success">
                        {t}
                      </Badge>
                    ))}
                  </p>
                ) : null}
                <ul className="list-disc pl-5 text-sm text-foreground-muted">
                  {h.achievements.map((a) => (
                    <li key={a}>{a}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title="Questions probables et trames de réponse">
        <ul className="flex flex-col gap-5">
          {content.questions.map((q) => (
            <QuestionItem key={q.id} question={q} outline={trames.get(q.id)} />
          ))}
        </ul>
      </Panel>

      {content.skills_to_prepare.length > 0 ? (
        <Panel title="Compétences de l'offre à préparer">
          <p className="mb-2 text-sm text-foreground-muted">
            Demandées par l&apos;offre mais absentes de votre profil : préparez comment les aborder,
            sans prétendre les maîtriser.
          </p>
          <p className="flex flex-wrap gap-1.5">
            {content.skills_to_prepare.map((s) => (
              <Badge key={s} variant="warning">
                {s}
              </Badge>
            ))}
          </p>
        </Panel>
      ) : null}

      <Panel title="Questions à poser au recruteur">
        <ul className="list-disc pl-5 text-sm leading-relaxed">
          {content.recruiter_questions.map((q) => (
            <li key={q}>{q}</li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

function QuestionItem({
  question,
  outline,
}: {
  question: InterviewQuestion;
  outline: AnswerOutline | undefined;
}) {
  return (
    <li className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="neutral">{CATEGORY_LABELS[question.category]}</Badge>
        {question.skill_gap ? <Badge variant="warning">Compétence absente du profil</Badge> : null}
        {question.source === "ai" ? <Badge variant="accent">IA</Badge> : null}
      </div>
      <p className="font-medium">{question.text}</p>
      <p className="text-xs text-foreground-muted">{question.rationale}</p>
      {outline ? (
        <details className="rounded-md border border-border p-3 text-sm">
          <summary className="cursor-pointer font-medium">Trame de réponse</summary>
          <dl className="mt-2 flex flex-col gap-2">
            <div>
              <dt className="text-xs text-foreground-muted">Situation (votre parcours)</dt>
              <dd>{outline.situation}</dd>
            </div>
            <div>
              <dt className="text-xs text-foreground-muted">Actions</dt>
              <dd>
                {outline.actions.length ? (
                  <ul className="list-disc pl-5">
                    {outline.actions.map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                ) : (
                  "À compléter"
                )}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-foreground-muted">Résultat</dt>
              <dd className="text-foreground-muted">
                À compléter : {outline.to_complete.join(" ; ")}
              </dd>
            </div>
          </dl>
        </details>
      ) : null}
    </li>
  );
}
