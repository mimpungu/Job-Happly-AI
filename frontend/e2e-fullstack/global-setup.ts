import { execFileSync } from "node:child_process";
import { mkdirSync, rmSync } from "node:fs";
import path from "node:path";

/**
 * Prépare une base dédiée aux parcours E2E « pile complète » : supprimée puis recréée à chaque
 * lancement, migrée avec les vraies migrations. Le nom doit finir par `_test` : on n'efface jamais
 * une base de développement.
 */
const URL_ADMIN =
  process.env.HAPPLY_E2E_ADMIN_URL ?? "postgresql://happly_test:test-only@127.0.0.1:5432/postgres";
export const BASE_E2E = "happly_e2e_test";
export const URL_BASE =
  process.env.HAPPLY_E2E_DATABASE_URL ??
  `postgresql://happly_test:test-only@127.0.0.1:5432/${BASE_E2E}`;
export const STOCKAGE = process.env.HAPPLY_E2E_STORAGE ?? "/tmp/happly-e2e-storage";

export default function globalSetup(): void {
  if (!/_test$/.test(new URL(URL_BASE).pathname.slice(1))) {
    throw new Error("La base E2E doit avoir un nom finissant par _test.");
  }
  const psql = (sql: string) =>
    execFileSync("psql", [URL_ADMIN, "-v", "ON_ERROR_STOP=1", "-c", sql], { stdio: "pipe" });
  psql(`DROP DATABASE IF EXISTS ${BASE_E2E} WITH (FORCE)`);
  psql(`CREATE DATABASE ${BASE_E2E}`);
  execFileSync("uv", ["run", "alembic", "upgrade", "head"], {
    cwd: path.resolve(__dirname, "../../backend"),
    env: { ...process.env, HAPPLY_DATABASE_URL: URL_BASE },
    stdio: "pipe",
  });
  rmSync(STOCKAGE, { recursive: true, force: true });
  mkdirSync(STOCKAGE, { recursive: true });
}
