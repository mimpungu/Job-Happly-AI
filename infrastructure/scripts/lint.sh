#!/usr/bin/env bash
# Formatage, lint et typage des deux projets.
source "$(dirname "$0")/_common.sh"
(cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy)
(cd frontend && pnpm format:check && pnpm lint && pnpm typecheck)
