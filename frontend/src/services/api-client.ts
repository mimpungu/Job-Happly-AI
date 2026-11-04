import { env } from "@/lib/env";
import type { ApiErrorBody } from "@/types/jobs";

/** Erreur renvoyée par l'API (corps normalisé) ou échec réseau (`status` = 0). */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    /** Détail par champ pour une erreur de validation (ex. `experiences[0].company`). */
    readonly details: readonly { field: string; message: string }[] = [],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function estCorpsErreur(valeur: unknown): valeur is ApiErrorBody {
  if (typeof valeur !== "object" || valeur === null || !("error" in valeur)) return false;
  const erreur = (valeur as { error: unknown }).error;
  return (
    typeof erreur === "object" &&
    erreur !== null &&
    typeof (erreur as { message?: unknown }).message === "string"
  );
}

/** Appel JSON vers l'API locale. Ne renvoie jamais de détail technique à l'utilisateur. */
export async function apiFetch<T>(chemin: string, init?: RequestInit): Promise<T> {
  let reponse: Response;
  try {
    reponse = await fetch(`${env.apiUrl}${chemin}`, {
      ...init,
      headers: {
        Accept: "application/json",
        // Un FormData fixe lui-même son Content-Type (avec la frontière multipart).
        ...(typeof init?.body === "string" ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(
      "Impossible de joindre le serveur local. Est-il démarré ?",
      0,
      "network_error",
    );
  }
  if (reponse.status === 204) return undefined as T;
  let corps: unknown;
  try {
    corps = await reponse.json();
  } catch {
    corps = undefined;
  }
  if (!reponse.ok) {
    if (estCorpsErreur(corps)) {
      throw new ApiError(
        corps.error.message,
        reponse.status,
        corps.error.code,
        corps.error.details ?? [],
      );
    }
    throw new ApiError("Réponse inattendue du serveur.", reponse.status, "unexpected_response");
  }
  return corps as T;
}
