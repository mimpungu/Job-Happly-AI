import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import type { NotificationPreferences } from "@/types/notifications";

import { NotificationSettingsPanel } from "./notification-settings-panel";

const json = (corps: unknown, statut = 200) =>
  new Response(JSON.stringify(corps), { status: statut });

const PREFS: NotificationPreferences = {
  in_app_enabled: true,
  email_enabled: false,
  email_recipient: null,
  email_consent_given: false,
  notify_new_offers: true,
  notify_relevant_matches: true,
  min_relevance_score: 70,
  notify_search_errors: true,
  notify_follow_up_reminders: true,
  notify_ai_budget_alerts: true,
  daily_digest_enabled: false,
  daily_digest_time: "08:00",
  timezone: "Europe/Paris",
};

function simuler() {
  const appels: { methode: string; corps?: string }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: string, init?: RequestInit) => {
      appels.push({ methode: init?.method ?? "GET", corps: init?.body as string | undefined });
      if ((init?.method ?? "GET") === "PUT")
        return json({ ...PREFS, ...JSON.parse(init!.body as string) });
      return json(PREFS);
    }),
  );
  return appels;
}

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <NotificationSettingsPanel />
      <Toaster />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("NotificationSettingsPanel", () => {
  it("enregistre les événements choisis et le résumé quotidien", async () => {
    const appels = simuler();
    afficher();

    await userEvent.click(await screen.findByLabelText("Nouvelles offres collectées"));
    await userEvent.click(screen.getByLabelText("Résumé quotidien"));
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => expect(appels.some((a) => a.methode === "PUT")).toBe(true));
    const corps = JSON.parse(appels.find((a) => a.methode === "PUT")?.corps ?? "{}");
    expect(corps).toMatchObject({
      notify_new_offers: false,
      daily_digest_enabled: true,
      min_relevance_score: 70,
      email_enabled: false,
    });
  });

  it("n'active jamais l'e-mail sans l'accord explicite de l'utilisateur", async () => {
    simuler();
    afficher();

    const activer = await screen.findByLabelText("Activer l'envoi par e-mail");

    expect(activer).toBeDisabled();
    await userEvent.click(
      screen.getByLabelText(/J'accepte l'envoi de ces notifications par e-mail/),
    );
    expect(activer).toBeEnabled();
    await userEvent.click(activer);
    // Sans adresse valide, l'enregistrement reste impossible.
    expect(screen.getByRole("button", { name: "Enregistrer" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Adresse e-mail"), "moi@exemple.test");
    expect(screen.getByRole("button", { name: "Enregistrer" })).toBeEnabled();
  });

  it("retirer l'accord désactive aussitôt l'envoi par e-mail", async () => {
    simuler();
    afficher();

    const accord = await screen.findByLabelText(
      /J'accepte l'envoi de ces notifications par e-mail/,
    );
    await userEvent.click(accord);
    await userEvent.click(screen.getByLabelText("Activer l'envoi par e-mail"));
    await userEvent.click(accord);

    expect(screen.getByLabelText("Activer l'envoi par e-mail")).not.toBeChecked();
    expect(screen.getByLabelText("Activer l'envoi par e-mail")).toBeDisabled();
  });

  it("affiche l'erreur du serveur si le chargement échoue", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json({ error: { code: "internal_error", message: "Erreur interne." } }, 500),
      ),
    );
    afficher();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Impossible de lire vos préférences",
    );
  });
});
