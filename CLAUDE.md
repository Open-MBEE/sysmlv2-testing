# CLAUDE.md

Read `AGENTS.md` first — it is the real contract for this repo. The short
version: this is a pipeline (pipe input → pinned tool → capture output →
scripted compare → log), never write `ledger/*.ttl` by hand, and never let
an LLM decide an `earl:outcome` — that is `adapters/compare.py`'s job.

Skills: `.claude/skills/ledger-testing/SKILL.md` — how to ledger a test
end to end using the `svt` CLI.
