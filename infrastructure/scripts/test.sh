#!/usr/bin/env bash
# Tests backend et frontend.
source "$(dirname "$0")/_common.sh"
(cd backend && uv run pytest)
(cd frontend && pnpm test)
