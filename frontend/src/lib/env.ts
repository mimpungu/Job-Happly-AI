/** Variables d'environnement publiques du frontend, validées une seule fois. */
function lireUrlApi(): string {
  const valeur = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
  try {
    return new URL(valeur).toString().replace(/\/$/, "");
  } catch {
    throw new Error(`NEXT_PUBLIC_API_URL invalide : "${valeur}"`);
  }
}

export const env = {
  apiUrl: lireUrlApi(),
} as const;
