#!/usr/bin/env bash
# Tests backend (unitaires + intégration PostgreSQL) et frontend (Vitest).
# La base de test est un projet Docker dédié, jamais la base de développement.
source "$(dirname "$0")/_common.sh"
"$(dirname "$0")/reset-test.sh" > /dev/null
export HAPPLY_TEST_DATABASE_URL="postgresql://happly_test:test-only@127.0.0.1:55432/happly_test"
(cd backend && uv run pytest)
(cd frontend && pnpm test)
