import { Badge } from "@/components/ui/badge";
import type { AiStatus } from "@/types/interviews";

/** Dit toujours ce que l'IA a fait ou n'a pas pu faire : jamais d'échec silencieux. */
export function AiNotice({ ai }: { ai: AiStatus }) {
  if (ai.status === "not_requested") return null;
  if (ai.status === "applied") {
    return (
      <p className="text-sm text-foreground-muted">
        <Badge variant="accent">IA</Badge> {ai.added ?? 0} question(s) ajoutée(s) par l&apos;IA.
      </p>
    );
  }
  return (
    <p role="status" className="text-sm text-foreground-muted">
      <Badge variant="warning">IA indisponible</Badge> {ai.reason ?? "Réponse impossible."} La
      préparation de base reste complète.
    </p>
  );
}
