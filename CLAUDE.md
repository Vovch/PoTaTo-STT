# Claude / Claude Code

**Canonical agent instructions for this repository are in [`AGENTS.md`](./AGENTS.md).** Read and follow that file first.

## Why this file exists

Some Anthropic tools look for `CLAUDE.md` in the repo root. This project standardizes on **`AGENTS.md`** (tool-agnostic, [agents.md](https://agentsmd.io/) style) so Copilot, Cursor, Codex, and Claude share one instruction set.

## Maintenance

- **Avoid duplicating long rules** in both `CLAUDE.md` and `AGENTS.md` — that drifts. Add or change behavior in `AGENTS.md`; keep `CLAUDE.md` to this pointer unless Claude-specific constraints are truly needed (then add a short bullet list here only).
