"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toaster";

import { useDemo, useDisableDemo, useEnableDemo } from "./use-demo";

export function DemoPanel() {
  const demo = useDemo();
  const activer = useEnableDemo();
  const desactiver = useDisableDemo();
  const actif = demo.data?.enabled ?? false;

  return (
    <Panel
      title="Mode démonstration"
      actions={
        demo.data ? (
          <Badge variant={actif ? "warning" : "neutral"}>{actif ? "Actif" : "Inactif"}</Badge>
        ) : null
      }
    >
      {demo.isPending ? (
        <Skeleton className="h-16 w-full" role="status" aria-label="Chargement" />
      ) : demo.isError ? (
        <p role="alert" className="text-sm">
          Impossible de lire l&apos;état du mode démonstration : {demo.error.message}
        </p>
      ) : (
        <div className="flex flex-col gap-4 text-sm">
          <p className="text-foreground-muted">
            Ajoute quelques offres <strong>fictives</strong>, clairement signalées, pour découvrir
            l&apos;application. Elles ne se mélangent jamais à vos données : l&apos;activation est
            refusée si vous avez déjà des offres ou candidatures réelles, et l&apos;ajout de données
            réelles est bloqué tant que la démonstration est active.
          </p>
          {actif ? (
            <>
              <p>
                {demo.data.offers} offre(s) fictive(s), {demo.data.applications} candidature(s)
                créée(s) à partir d&apos;elles. La désactivation les supprime avec les documents qui
                en dérivent ; vos données réelles ne sont jamais touchées.
              </p>
              <div>
                <Button
                  variant="secondary"
                  loading={desactiver.isPending}
                  onClick={() =>
                    desactiver.mutate(undefined, {
                      onSuccess: () => toast.success("Mode démonstration désactivé."),
                      onError: (e) => toast.error(e.message),
                    })
                  }
                >
                  Désactiver et supprimer les données fictives
                </Button>
              </div>
            </>
          ) : (
            <div>
              <Button
                variant="secondary"
                loading={activer.isPending}
                onClick={() =>
                  activer.mutate(undefined, {
                    onSuccess: () => toast.success("Mode démonstration activé."),
                    onError: (e) => toast.error(e.message),
                  })
                }
              >
                Activer le mode démonstration
              </Button>
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}
