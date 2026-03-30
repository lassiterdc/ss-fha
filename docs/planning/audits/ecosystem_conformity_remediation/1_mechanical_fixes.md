---
master: docs/planning/audits/ecosystem_conformity_remediation/master.md
created: 2026-03-14
description: Apply all straightforward audit findings — architecture.md currency, work chunks README, planning README, audit directory consolidation.
---

*Written: 2026-03-14*

# Phase 1: Mechanical Fixes

---

## Scope

Docs-only edits with a clear correct answer. No code changes. Spans two repos — two commits required.

---

## File-by-File Change Plan

### 1. `~/dev/agentic-workspace/prompts/workspaces/projects/ss-fha/architecture.md` (ecosystem copy — agents read this at startup)

- **Module table**: remove rows for `workflow.py`, `execution.py`, `resource_management.py`, `sensitivity_analysis.py`, `log.py` (unimplemented). Add row for `io/` (`zarr_io.py`, `gis_io.py`, `netcdf_io.py`).
- **Add `## Active Plan References` section** (after Workflow Phases):
  ```
  ## Active Plan References

  - Full codebase refactor: `docs/planning/refactors/2026-02-25_full_codebase_refactor/full_codebase_refactor.md`
  - Old-code alignment testing: `docs/planning/refactors/2026-03-04_old_code_alignment_testing/master.md`
  ```
- **Add `## Gotchas` section** (after Active Plan References):
  ```
  ## Gotchas

  - **Dual `architecture.md` copies**: The ecosystem copy (`~/dev/agentic-workspace/prompts/workspaces/projects/ss-fha/architecture.md`) is what agents load at session startup. The workspace-local copy (`~/dev/ss-fha/architecture.md`) is tracked in git. Keep them in sync; if they diverge, the ecosystem copy takes precedence for agent behavior.
  - **`compound` vs. `combined` historic event_type**: In legacy data, the historic event is typed `compound`; the refactored code expects `combined`. See `ss-fha_glossary.md` for the full mapping.
  - **Unimplemented modules**: `workflow.py`, `execution.py`, `resource_management.py`, `sensitivity_analysis.py`, and `log.py` are planned for work chunks 04A–04B and do not yet exist. Do not import from them.
  ```
- **`utility_package_candidates` path**: leave as `~/dev/lassiterdc-utils/` (already correct in ecosystem copy — verify, no edit needed if confirmed).

### 2. `/home/dcl3nd/dev/ss-fha/architecture.md` (workspace-local copy — repo root)

- Same module table, `Active Plan References`, and `Gotchas` additions as the ecosystem copy.
- **`utility_package_candidates` path**: update from `~/dev/dcl-utils/` → `~/dev/lassiterdc-utils/`.
- If file does not exist at repo root, skip — ecosystem copy is authoritative.

### 3. `docs/planning/refactors/2026-02-25_full_codebase_refactor/work_chunks/README.md`

- Change `03B_workflow2_uncertainty.md` status: `Pending` → `Complete`
- Change `03C_event_statistics_runner.md` status: `Pending` → `Complete`

### 4. `docs/planning/README.md`

- Replace naming convention description: remove `YYYY-MM-DD_descriptive_snake_case_name.md`; replace with "planning docs use a descriptive `snake_case` name with **no date prefix**; creation date belongs in `created:` YAML frontmatter"
- Add `implemented/` to the multi-phase plan structure diagram
- Add `audits/` as a recognized type directory in the Structure section (alongside `bugs/`, `features/`, `refactors/`)

### 5. Consolidate `docs/planning/audit/` → `docs/planning/audits/`

- Move `docs/planning/audit/se_review_2026-03-14.md` → `docs/planning/audits/se_review_2026-03-14.md`
- Remove `docs/planning/audit/` directory
- Create `docs/planning/audits/completed/.gitkeep`

---

## Validation

```bash
# Confirm unimplemented modules absent from src
ls /home/dcl3nd/dev/ss-fha/src/ss_fha/
# Expected: no workflow.py, execution.py, resource_management.py, sensitivity_analysis.py, log.py

# Confirm io/ exists
ls /home/dcl3nd/dev/ss-fha/src/ss_fha/io/

# Confirm audit/ (singular) is gone
ls /home/dcl3nd/dev/ss-fha/docs/planning/

# Confirm audits/completed/ exists
ls /home/dcl3nd/dev/ss-fha/docs/planning/audits/

# Confirm lassiterdc-utils path exists
ls ~/dev/lassiterdc-utils/docs/planning/utility_package_candidates.md
```

Visual review: both `architecture.md` copies have module table, Active Plan References, Gotchas, and correct `utility_package_candidates` path.

---

## Definition of Done

- [ ] Ecosystem `architecture.md` module table updated (5 rows removed, `io/` added)
- [ ] Ecosystem `architecture.md` `Active Plan References` section added
- [ ] Ecosystem `architecture.md` `Gotchas` section added
- [ ] Ecosystem `architecture.md` `utility_package_candidates` path confirmed `~/dev/lassiterdc-utils/`
- [ ] Workspace-local `architecture.md` receives same updates (or confirmed absent)
- [ ] Work chunks README: 03B and 03C status → Complete
- [ ] Planning `README.md` naming convention updated; `implemented/` and `audits/` added
- [ ] `docs/planning/audit/se_review_2026-03-14.md` moved to `docs/planning/audits/`
- [ ] `docs/planning/audit/` directory removed
- [ ] `docs/planning/audits/completed/.gitkeep` created
- [ ] Validation commands pass
- [ ] Two commits: one in `ss-fha`, one in `agentic-workspace`
- [ ] Pre-completion accuracy check run
- [ ] `completed: true` set in frontmatter; doc moved to `implemented/`; phase status in `master.md` updated
