---
master: docs/planning/audits/ecosystem_conformity_remediation/master.md
created: 2026-03-14
description: Write a structured triage checklist for the four human-decision audit findings — codex sentinels, directory renames, settings.local.json, Snakemake glossary.
---

*Written: 2026-03-14*

# Phase 2: Human-Decision Triage Doc

---

## Scope

Write one file — `docs/planning/audits/ecosystem_conformity_triage.md` — containing a structured checklist for the four audit findings that require human judgment before acting. This phase produces a decision artifact, not implemented changes.

---

## File-by-File Change Plan

### `docs/planning/audits/ecosystem_conformity_triage.md` (new file)

Create with the following content covering the four triage items:

**Item A — Codex `AGENTS.md` missing `workspace_specific` sentinels** (audit action 3)

Context: Both `ss-fha` and `lassiterdc-utils` codex `AGENTS.md` files have no `<!-- injection-start: workspace_specific -->` / `<!-- injection-end: workspace_specific -->` sentinels around their workspace-specific block. This means `refresh_injections.py` cannot manage that block automatically.

Decision: Is this a `refresh_injections.py` script gap (fix once, fixes all codex workspace entrypoints), or a per-file manual edit?

Options:
- Fix `refresh_injections.py` to emit sentinels for codex workspace-specific blocks (ecosystem-wide fix, correct long-term approach)
- Manually add sentinels to each affected file (quick, but does not prevent regression)

Recommended: investigate `refresh_injections.py` first; if codex blocks are simply not generated with sentinels, fix the script.

---

**Item B — Active multi-phase plan directories use date-prefix names** (audit action 8)

Context: `2026-02-25_full_codebase_refactor/` and `2026-03-04_old_code_alignment_testing/` violate the current `snake_case` no-date-prefix convention. `docs/planning/README.md` now documents the correct convention (fixed in Phase 1), but these dirs remain mis-named.

Decision: Rename now or grandfather?

Options:
- **Rename now** with `git mv`: `full_codebase_refactor/` and `old_code_alignment_testing/`. Move dates to `created:` frontmatter in `master.md` / top-level plan doc. Update all cross-references (grep both repos). Higher effort, cleaner.
- **Grandfather**: leave existing dirs as-is (they are grandfathered per protocol since they predate the convention). Only enforce on new plans going forward.

Recommended: grandfather — the convention change is recent, the blast radius for cross-reference updates is non-trivial, and the protocol explicitly allows grandfathering.

---

**Item C — `settings.local.json` absent from Claude Code runtime dir** (audit action 10)

Context: `lassiterdc-utils` has `~/dev/agentic-workspace/prompts/runtimes/claude_code/workspaces/projects/lassiterdc-utils/settings.local.json` granting auto-approved permissions for common Bash commands and skills. ss-fha lacks this — Claude Code will prompt for permission on every tool use.

Decision: Create one? If yes, what permissions to grant?

Options:
- Create, modeled on `lassiterdc-utils/settings.local.json`
- Leave absent if the default permission behavior is acceptable

Recommended: create — routine ss-fha sessions involve many Bash, Read, Edit, Glob, and Grep calls. The friction is real.

---

**Item D — No Snakemake/HPC glossary injected** (audit action 11)

Context: Upcoming work chunks 04A–04B implement Snakemake workflow construction and SLURM/local execution strategies. A `snakemake-workspace_glossary.md` exists in the ecosystem but is not injected into ss-fha sessions.

Decision: Inject `snakemake-workspace_glossary.md` ahead of work chunk 04A?

Options:
- Add to `workspace_specific` injection block in both harness entrypoints and run `refresh_injections.py`
- Leave absent and delegate Snakemake reasoning to the snakemake-specialist as needed

Recommended: inject — agents building the Snakemake workflow will reason more accurately with the vocabulary available.

---

## Definition of Done

- [ ] `docs/planning/audits/ecosystem_conformity_triage.md` written with all four items
- [ ] Each item includes: context, decision options, recommendation
- [ ] `completed: true` set in frontmatter; doc moved to `implemented/`; phase status in `master.md` updated
