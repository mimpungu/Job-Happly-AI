import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Panel } from "@/components/ui/card";
import type { MatchItem, MatchKind } from "@/types/matching";

import { KIND_LABELS } from "./labels";

const ORDRE: readonly MatchKind[] = ["present", "partial", "absent", "unverifiable"];
const VARIANTES: Record<MatchKind, BadgeProps["variant"]> = {
  present: "success",
  partial: "warning",
  absent: "danger",
  unverifiable: "neutral",
};

/** Compétences exigées par l'offre, classées en quatre états distincts (spécification §8). */
export function SkillMatchPanel({ items }: { items: readonly MatchItem[] }) {
  if (items.length === 0) {
    return (
      <Panel title="Compétences">
        <p className="text-sm text-foreground-muted">
          Aucune compétence n&apos;a pu être repérée automatiquement dans cette offre.
        </p>
      </Panel>
    );
  }
  const absentes = items.some((i) => i.kind === "absent");
  return (
    <Panel title="Compétences">
      <div className="flex flex-col gap-4">
        {ORDRE.map((kind) => {
          const groupe = items.filter((i) => i.kind === kind);
          if (groupe.length === 0) return null;
          return (
            <section key={kind} aria-label={KIND_LABELS[kind]} className="flex flex-col gap-2">
              <h3 className="text-sm font-medium text-foreground">
                {KIND_LABELS[kind]} ({groupe.length})
              </h3>
              <ul className="flex flex-col gap-1.5">
                {groupe.map((item) => (
                  <li
                    key={`${kind}-${item.label}`}
                    className="flex flex-wrap items-baseline gap-2 text-sm"
                  >
                    <Badge variant={VARIANTES[kind]}>{item.label}</Badge>
                    {item.detail ? (
                      <span className="text-foreground-muted">{item.detail}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
        {absentes ? (
          <p className="text-xs text-foreground-muted">
            « Absente de votre profil » ne veut pas dire que vous ne la maîtrisez pas : si vous la
            connaissez, ajoutez-la dans l&apos;Espace CV.
          </p>
        ) : null}
      </div>
    </Panel>
  );
}
