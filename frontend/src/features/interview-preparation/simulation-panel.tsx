"use client";

import { Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toaster";
import { formatDateTime } from "@/features/applications/format";
import type {
  AssistMode,
  InterviewQuestion,
  Simulation,
  SimulationAnswer,
} from "@/types/interviews";

import { CATEGORY_LABELS, MODE_OPTIONS } from "./labels";
import {
  useAnswerQuestion,
  useCompleteSimulation,
  useDeleteSimulation,
  useSimulations,
  useStartSimulation,
} from "./use-interviews";

export function SimulationPanel({ applicationId }: { applicationId: string }) {
  const simulations = useSimulations(applicationId);
  const demarrer = useStartSimulation(applicationId);
  const [ouverte, setOuverte] = useState<string | null>(null);

  if (simulations.isPending)
    return <Skeleton className="h-40 w-full" role="status" aria-label="Chargement" />;
  if (simulations.isError) {
    return (
      <EmptyState
        title="Impossible de charger les simulations"
        description={simulations.error.message}
        action={<Button onClick={() => void simulations.refetch()}>Réessayer</Button>}
      />
    );
  }

  const courante = simulations.data.find((s) => s.id === ouverte) ?? null;
  const lancer = () =>
    demarrer.mutate(6, {
      onSuccess: (s) => setOuverte(s.id),
      onError: (erreur) => toast.error(erreur.message),
    });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={lancer} loading={demarrer.isPending}>
          Démarrer une simulation
        </Button>
        <p className="text-sm text-foreground-muted">
          6 questions tirées de votre préparation. Aucun appel IA au démarrage.
        </p>
      </div>

      {courante ? (
        <SimulationSession
          key={courante.id}
          applicationId={applicationId}
          simulation={courante}
          onClose={() => setOuverte(null)}
        />
      ) : null}

      <Panel title="Historique des simulations">
        {simulations.data.length === 0 ? (
          <p className="text-sm text-foreground-muted">Aucune simulation pour cette candidature.</p>
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {simulations.data.map((s) => (
              <HistoryRow
                key={s.id}
                applicationId={applicationId}
                simulation={s}
                onOpen={() => setOuverte(s.id)}
              />
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}

function HistoryRow({
  applicationId,
  simulation,
  onOpen,
}: {
  applicationId: string;
  simulation: Simulation;
  onOpen: () => void;
}) {
  const supprimer = useDeleteSimulation(applicationId);
  const { summary } = simulation;
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm">
      <div className="flex flex-col gap-1">
        <span>{formatDateTime(simulation.created_at)}</span>
        <span className="text-foreground-muted">
          {summary.answered}/{summary.total} réponses
          {summary.average_score !== null ? ` · score moyen ${summary.average_score}/100` : ""}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <Badge variant={simulation.status === "completed" ? "success" : "neutral"}>
          {simulation.status === "completed" ? "Terminée" : "En cours"}
        </Badge>
        <Button variant="secondary" size="sm" onClick={onOpen}>
          Ouvrir
        </Button>
        <Button
          variant="ghost"
          size="sm"
          aria-label={`Supprimer la simulation du ${formatDateTime(simulation.created_at)}`}
          loading={supprimer.isPending}
          onClick={() =>
            supprimer.mutate(simulation.id, {
              onSuccess: () => toast.success("Simulation supprimée."),
              onError: (erreur) => toast.error(erreur.message),
            })
          }
        >
          <Trash2 className="size-4" aria-hidden="true" />
        </Button>
      </div>
    </li>
  );
}

function SimulationSession({
  applicationId,
  simulation,
  onClose,
}: {
  applicationId: string;
  simulation: Simulation;
  onClose: () => void;
}) {
  const terminer = useCompleteSimulation(applicationId);
  const reponses = new Map(simulation.answers.map((a) => [a.question_id, a]));
  const lectureSeule = simulation.status === "completed";
  const { summary } = simulation;

  return (
    <Panel
      title={lectureSeule ? "Simulation terminée" : "Simulation en cours"}
      actions={
        <Button variant="ghost" size="sm" onClick={onClose}>
          Fermer
        </Button>
      }
    >
      <div className="flex flex-col gap-6">
        {summary.average_score !== null ? (
          <p className="text-sm" role="status">
            {summary.answered}/{summary.total} réponses · score moyen{" "}
            <strong>{summary.average_score}/100</strong>
          </p>
        ) : (
          <p className="text-sm text-foreground-muted">Aucune réponse pour le moment.</p>
        )}
        <ol className="flex flex-col gap-6">
          {simulation.questions.map((q, i) => (
            <AnswerForm
              key={q.id}
              index={i + 1}
              applicationId={applicationId}
              simulationId={simulation.id}
              question={q}
              answer={reponses.get(q.id)}
              readOnly={lectureSeule}
            />
          ))}
        </ol>
        {lectureSeule ? null : (
          <div>
            <Button
              loading={terminer.isPending}
              onClick={() =>
                terminer.mutate(simulation.id, {
                  onSuccess: () => toast.success("Simulation terminée."),
                  onError: (erreur) => toast.error(erreur.message),
                })
              }
            >
              Terminer la simulation
            </Button>
          </div>
        )}
      </div>
    </Panel>
  );
}

function AnswerForm({
  index,
  applicationId,
  simulationId,
  question,
  answer,
  readOnly,
}: {
  index: number;
  applicationId: string;
  simulationId: string;
  question: InterviewQuestion;
  answer: SimulationAnswer | undefined;
  readOnly: boolean;
}) {
  const envoyer = useAnswerQuestion(applicationId, simulationId);
  const [texte, setTexte] = useState(answer?.text ?? "");
  const [mode, setMode] = useState<AssistMode>("none");

  const soumettre = () =>
    envoyer.mutate(
      { questionId: question.id, text: texte, mode },
      { onError: (erreur) => toast.error(erreur.message) },
    );

  return (
    <li className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="neutral">{CATEGORY_LABELS[question.category]}</Badge>
        <span className="text-xs text-foreground-muted">Question {index}</span>
      </div>
      <p className="font-medium">{question.text}</p>
      <Field label="Votre réponse">
        {(champ) => (
          <Textarea
            {...champ}
            rows={5}
            maxLength={5000}
            value={texte}
            readOnly={readOnly}
            onChange={(e) => setTexte(e.target.value)}
          />
        )}
      </Field>
      {readOnly ? null : (
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Commentaire d'IA (facultatif)">
            {(champ) => (
              <Select
                {...champ}
                value={mode}
                options={MODE_OPTIONS}
                onChange={(e) => setMode(e.target.value as AssistMode)}
              />
            )}
          </Field>
          <Button
            variant="secondary"
            loading={envoyer.isPending}
            disabled={texte.trim().length === 0}
            onClick={soumettre}
          >
            Évaluer ma réponse
          </Button>
        </div>
      )}
      {answer ? <FeedbackView answer={answer} /> : null}
    </li>
  );
}

function FeedbackView({ answer }: { answer: SimulationAnswer }) {
  const f = answer.feedback;
  return (
    <div className="rounded-md border border-border p-3 text-sm" aria-label="Retour sur la réponse">
      <p className="font-medium">Score : {f.score}/100</p>
      {f.strengths.length > 0 ? (
        <ul className="mt-2 list-disc pl-5 text-foreground-muted">
          {f.strengths.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      ) : null}
      {f.improvements.length > 0 ? (
        <>
          <p className="mt-2 font-medium">À améliorer</p>
          <ul className="list-disc pl-5">
            {f.improvements.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </>
      ) : null}
      {f.ai_status === "applied" ? (
        <>
          <p className="mt-2 font-medium">Commentaires de l&apos;IA</p>
          <ul className="list-disc pl-5">
            {f.ai_comments.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </>
      ) : null}
      {f.ai_status === "unavailable" ? (
        <p role="status" className="mt-2 text-foreground-muted">
          Commentaire d&apos;IA indisponible : le retour ci-dessus reste valable.
        </p>
      ) : null}
    </div>
  );
}
