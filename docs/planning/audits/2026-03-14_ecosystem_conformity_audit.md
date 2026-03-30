---
date: 2026-03-14
author: ecosystem-specialist
type: audit
scope: workspace
workspace: ss-fha
---

# ss-fha Ecosystem Conformity Audit

## Executive Summary

ss-fha is **partially conformant** with ecosystem conventions. Runtime entrypoints are structurally sound and the symlink deployment pattern is correct, but a cluster of drift findings in the planning directory and the architecture doc's module table will compound if left unaddressed. One significant drift issue exists: the ecosystem-side `architecture.md` (the copy agents actually read at session startup) contains a stale path reference to a utility candidates document that diverges from the workspace-local copy (which points to `~/dev/dcl-utils/`, a directory that does not currently exist).

**Finding counts**: 0 blocking, 8 drift, 4 advisory, 2 needing clarification.

**Highest-priority items for immediate attention**:
1. The ecosystem-side `architecture.md` is out of sync with the workspace-local `architecture.md` on the `utility_package_candidates` path — agents read the stale copy.
2. The `architecture.md` module table lists four unimplemented modules (`workflow.py`, `execution.py`, `resource_management.py`, `sensitivity_analysis.py`, `log.py`) as current and omits the existing `io/` directory.
3. The codex `AGENTS.md` `workspace_specific` block has no injection sentinels, meaning `refresh_injections.py` cannot manage that block and it is effectively orphaned from automated maintenance.

---

## Per-Dimension Findings

### Dimension 1: Runtime entrypoints — both harnesses

**What was checked**: Frontmatter fields, Commandment #1 text, three-tier injection structure, sentinel presence and format, `$AGENTIC_WORKSPACE` variable usage, auto-generated comment line, and presence of `settings.local.json` at the ecosystem-side runtime directory. Peer comparison against `lassiterdc-utils` on `settings.local.json`.

**Finding 1.1** `[DRIFT]` — Missing `workspace_specific` injection sentinels in the codex `AGENTS.md`.

The `workspace_specific` section in `/home/dcl3nd/dev/agentic-workspace/prompts/runtimes/codex/workspaces/projects/ss-fha/AGENTS.md` (and its symlink at `/home/dcl3nd/dev/ss-fha/AGENTS.md`) contains the workspace-specific file references as a bare markdown list with no `<!-- injection-start: workspace_specific -->` / `<!-- injection-end: workspace_specific -->` sentinels wrapping it. The `all_workspaces_runtimes` and `project_runtimes` blocks in the same file do have correct sentinels and auto-generated comment lines. Without the `workspace_specific` sentinels, `refresh_injections.py` cannot locate or update this block; any future change to the workspace's injected docs would require a manual edit to the codex entrypoint rather than an automated refresh. This same pattern exists in the peer workspace (`lassiterdc-utils` codex `AGENTS.md` also lacks these sentinels), indicating a systemic gap in how codex workspace-specific blocks are generated. The Claude Code `CLAUDE.md` does have the correct sentinels.

**Finding 1.2** `[ADVISORY][NEEDS CLARIFICATION]` — No `settings.local.json` at the ss-fha Claude Code runtime directory.

`/home/dcl3nd/dev/agentic-workspace/prompts/runtimes/claude_code/workspaces/projects/ss-fha/` contains only `CLAUDE.md`. The peer workspace `lassiterdc-utils` has a `settings.local.json` file in its equivalent directory, granting auto-approved permissions for common Bash commands and skills. Without this file, Claude Code will prompt for permission on every tool use in ss-fha sessions, which slows routine work. Since `lassiterdc-utils` is a Python computation project of similar character, the absence in ss-fha appears to be a gap rather than an intentional exclusion — but only the workspace owner can confirm.

**Finding 1.3** `[ADVISORY]` — Both `CLAUDE.md` and `AGENTS.md` at the workspace root are symlinks and untracked in git.

The workspace root `CLAUDE.md` symlinks to the ecosystem-managed copy; same for `AGENTS.md`. This is the correct deployment pattern for keeping them in sync with `refresh_injections.py` outputs. The untracked git status is intentional and correct — tracking the symlink in ss-fha would be inappropriate since the authoritative file lives in the agentic-workspace repo. No action required on the symlinks themselves. Noted for awareness; not a protocol violation.

---

### Dimension 2: Workspace prompt documents

**What was checked**: Frontmatter completeness on both workspace prompt docs, `temp_parent` presence, `architecture.md` section checklist per `architecture-doc-conventions.md`, module table accuracy, and glossary overlap between `ss-fha_glossary.md` and the three domain glossaries.

**Finding 2.1** `[DRIFT]` — `architecture.md` module table lists five unimplemented modules as current and omits the existing `io/` directory.

The module table in `/home/dcl3nd/dev/agentic-workspace/prompts/workspaces/projects/ss-fha/architecture.md` includes rows for `workflow.py`, `execution.py`, `resource_management.py`, `sensitivity_analysis.py`, and `log.py`. None of these files exist in the current codebase (`/home/dcl3nd/dev/ss-fha/src/ss_fha/`). They are planned for work chunks 04A–04B (Snakemake workflow integration and execution strategy). The `io/` directory (`zarr_io.py`, `gis_io.py`, `netcdf_io.py`) is implemented but has no module table row — only an inline mention inside the `analysis/` description. Presenting aspirational modules as current and omitting an existing module directory constitutes documentation currency drift that will mislead agents reasoning about codebase structure.

**Finding 2.2** `[DRIFT]` — `architecture.md` is missing the `Active plan references` and `Gotchas` sections required by `architecture-doc-conventions.md` for project workspaces.

Per `architecture-doc-conventions.md`, project workspace `architecture.md` files must include: Purpose statement, Module table, Active plan references, Refactoring context, Gotchas, and Environment setup. The current `architecture.md` has a Purpose statement (opening paragraph), Key Modules table, Refactoring context, Environment, and Code Style. `Active plan references` (dedicated links to current `docs/planning/` plans) and `Gotchas` (non-obvious behaviors, known limitations) are missing. The Refactoring context section does reference the main refactor plan by path, which partially serves the active plan references function, but the convention calls for a dedicated section.

**Finding 2.3** `[DRIFT]` — Ecosystem-side `architecture.md` is out of sync with the workspace-local copy on the `utility_package_candidates` path.

Commit `d1d123e` updated the workspace-local `architecture.md` (`/home/dcl3nd/dev/ss-fha/architecture.md`) to reference `~/dev/dcl-utils/docs/planning/utility_package_candidates.md`. The ecosystem-side copy (the file agents actually load at startup via injection) still reads `~/dev/lassiterdc-utils/docs/planning/utility_package_candidates.md`. The directory `~/dev/dcl-utils/` does not exist on disk; `~/dev/lassiterdc-utils/` does exist and contains `utility_package_candidates.md`. The ecosystem copy points to a valid-but-potentially-outdated location while the workspace-local copy points to a path that does not exist. The two `architecture.md` files are diverged because the commit updated only the workspace-tracked copy, not the ecosystem copy. Agents receive the ecosystem copy at session startup.

**Finding 2.4** `[ADVISORY]` — `ss-fha_glossary.md` and `flood_risk_management.md` both define `event_iloc` with complementary but non-identical definitions.

The `flood_risk_management.md` definition is brief: "The canonical flat integer index uniquely identifying a single simulated event within an analysis." The `ss-fha_glossary.md` table entry adds ss-fha-specific detail: the iloc mapping CSV name (`ss_event_iloc_mapping.csv`), the `event_id` / `event_number` distinction, and the DataTree context. Both documents are injected at ss-fha session startup, so the term appears twice. The definitions do not conflict, but the duplication creates minor redundancy. A resolution would require deciding whether the richer definition should be promoted to the shared domain glossary or the generic one should be removed from it — a decision for the ecosystem maintainer.

**Finding 2.5** `[ADVISORY]` — Both `architecture.md` and `ss-fha_glossary.md` declare `workspace_type: all` and `workspaces: all` despite being workspace-specific documents.

Both files live under `prompts/workspaces/projects/ss-fha/` and are injected only into ss-fha sessions. The `workspaces: all` claim is technically inaccurate, but this matches the peer workspace `lassiterdc-utils` — both its `architecture.md` and `lassiterdc-utils_glossary.md` use the same values. This appears to be an ecosystem-wide convention or a known schema inaccuracy rather than an ss-fha-specific gap. `temp_parent` is present on both documents, confirming they are scheduled for cleanup once the schema is stable.

---

### Dimension 3: Workspace root entrypoint files

**What was checked**: Whether `CLAUDE.md` and `AGENTS.md` at the workspace root are symlinks or copies, sync status, three-tier injection structure, sentinel format, whether `AGENTS.md` is a misfiled artifact, and why they are untracked.

Both `/home/dcl3nd/dev/ss-fha/CLAUDE.md` and `/home/dcl3nd/dev/ss-fha/AGENTS.md` are confirmed symlinks pointing to their respective ecosystem-managed counterparts:
- `~/dev/agentic-workspace/prompts/runtimes/claude_code/workspaces/projects/ss-fha/CLAUDE.md`
- `~/dev/agentic-workspace/prompts/runtimes/codex/workspaces/projects/ss-fha/AGENTS.md`

Because they are symlinks, they are always in sync with the ecosystem-managed files. The `AGENTS.md` at the workspace root is not a misfiled artifact — its content is the correct codex runtime entrypoint for this workspace. The untracked git status is correct. The `workspace_specific` sentinel gap noted in Dimension 1 manifests here as well via the symlink, so the same fix resolves both dimensions.

---

### Dimension 4: Glossary coverage

**What was checked**: Whether the three injected domain glossaries (`flood_risk_management`, `hydrology`, `statistics`) are appropriate for the project domain, and whether any actively used domain lacks glossary coverage.

The three injected glossaries are well-matched to the ss-fha domain: `flood_risk_management.md` covers simulation types, FHA approaches, and `event_iloc`; `hydrology.md` covers storm surge/tide, return period, and AEP; `statistics.md` covers copulas, vine copulas, KNN resampling, and Poisson processes. All three are relevant to the bootstrapping and stochastic weather generator work at the core of ss-fha.

**Finding 4.1** `[ADVISORY][NEEDS CLARIFICATION]` — No glossary coverage for Snakemake workflow orchestration or HPC/SLURM execution concepts.

The ss-fha pipeline is orchestrated by Snakemake, and upcoming work chunks 04A–04B implement `LocalConcurrentExecutor` and `SlurmExecutor`. A `snakemake-workspace` tool workspace exists in the ecosystem with a `snakemake-workspace_glossary.md`, but it is not injected into ss-fha sessions. There is no HPC/SLURM glossary. Whether this gap matters depends on whether agents frequently need to reason about Snakemake DAG construction or SLURM configuration in ss-fha sessions. If the snakemake specialist is regularly delegated to for those concerns, this gap may be acceptable.

---

### Dimension 5: Planning artifact hygiene

**What was checked**: Directory structure conformance, naming conventions on active plan files and directories, `plans.md`/`ideas.md` currency, multi-phase plan phase completion status, active plan `completed:` status vs. git log, and the `audits/` directory extension.

**Finding 5.1** `[DRIFT]` — `plans.md` is absent and `ideas.md` does not follow the current protocol format.

Per `planning-document-lifecycle.md`, `docs/planning/plans.md` and `docs/planning/ideas.md` are persistent auto-generated tracking files produced by `scripts/generate_planning_tables.py`. `plans.md` is missing entirely. `ideas.md` is a manually written header-only stub (no priority table, no individual idea files). The `docs/planning/ideas/` directory for atomic per-idea files does not exist. No `generate_planning_tables.py` script exists in the ss-fha workspace. The planning system's discoverability layer — the tool that lets agents and developers see all active plans and ideas at a glance — is effectively absent.

**Finding 5.2** `[DRIFT]` — Active multi-phase plan subdirectories use date-prefixed names, violating the naming convention; the planning `README.md` also prescribes this stale convention.

`docs/planning/refactors/2026-02-25_full_codebase_refactor/` and `docs/planning/refactors/2026-03-04_old_code_alignment_testing/` both use date-prefixed directory names. Per `planning-document-lifecycle.md`, active plan files and directories must use `snake_case` with no date prefix; the creation date belongs in `created:` frontmatter. The grandfathering exception in the protocol applies only to files already in `completed/` or `implemented/` — these are active plan directories. The `docs/planning/README.md` explicitly prescribes the old convention (`YYYY-MM-DD_descriptive_snake_case_name.md`), which contradicts the ecosystem protocol and will perpetuate the pattern.

**Finding 5.3** `[DRIFT]` — Work chunks 03B and 03C are marked "Pending" in the README status table but are implemented and their docs are in `work_chunks/implemented/`.

Git commits `49ec337` (Workflow 2 bootstrap CI — 03B) and `bb2a8a5` (event statistics analysis and runner — 03C) confirm both are implemented. The phase docs `03B_workflow2_uncertainty.md` and `03C_event_statistics_runner.md` are in `work_chunks/implemented/`, consistent with completion. The `work_chunks/README.md` status table still lists both as "Pending," which will mislead a cold agent picking up the plan.

**Finding 5.4** `[ADVISORY]` — Two `audit`-type directories exist (`docs/planning/audit/` and `docs/planning/audits/`) with inconsistent naming, and neither is defined by the planning lifecycle protocol.

`docs/planning/audit/` (singular) contains `se_review_2026-03-14.md`; `docs/planning/audits/` (plural) contains the current audit file. The protocol defines three type subdirectories: `bugs/`, `features/`, `refactors/`. The `audit/audits/` type is an undocumented extension. Having two differently named directories for the same artifact type is a structural inconsistency that suggests the directories were created in separate sessions without awareness of each other. Neither has a `completed/` subdirectory. Both are untracked in git. This extension should be consolidated and either formally documented in the planning lifecycle protocol or added to the workspace README.

---

### Dimension 6: Documentation currency

**What was checked**: Recent commits (last 15) for structural changes, then verification that `architecture.md` module table, config system, and workflow phases still reflect current codebase structure.

Recent structural changes of note from the git log: 03C event statistics runner implemented (`bb2a8a5`), 03B bootstrap CI implemented (`49ec337`), `utility_package_candidates` path migrated to `dcl-utils` (`d1d123e`), copier-workspace path update (`329e69f`).

**Finding 6.1** `[DRIFT]` — Module table in ecosystem `architecture.md` not updated after multiple implementation commits.

This is the same gap as Finding 2.1, viewed from the documentation currency angle. After commits 49ec337 (03B) and bb2a8a5 (03C), neither the module table nor the section describing workflow phases was updated to reflect that analysis modules and runners for workflows 1–3 are now implemented. The documentation-currency protocol requires checking whether changes affect the architecture described in workspace instruction files.

**Finding 6.2** `[DRIFT]` — Ecosystem-side `architecture.md` not updated after commit `d1d123e` migrated the `utility_package_candidates` path.

Same gap as Finding 2.3. Commit `d1d123e` updated five references in the workspace but not the ecosystem-side architecture doc. The documentation-currency protocol was not applied to the ecosystem copy during this change.

---

### Dimension 7: Peer comparison

**What was checked**: ss-fha compared to `lassiterdc-utils` across runtime entrypoint structure (both harnesses), workspace prompt doc completeness, `settings.local.json` presence, and planning directory structure. No second peer was needed — the key differences were determinable from this single comparison.

| Dimension | lassiterdc-utils | ss-fha | Assessment |
|-----------|-----------------|---------|------------|
| Claude Code `CLAUDE.md` — all three sentinel tiers | Conformant | Conformant | Equal |
| Codex `AGENTS.md` — `workspace_specific` sentinels | Missing | Missing | Shared gap |
| `settings.local.json` | Present | Absent | Gap in ss-fha |
| Workspace-root symlinks, untracked | Correct | Correct | Equal |
| `architecture.md` required sections | Minimal (missing Active plan refs, Gotchas) | Richer but stale module table; also missing Active plan refs and Gotchas | Both drift |
| `plans.md` / `ideas.md` auto-generated | Both absent | `plans.md` absent; `ideas.md` stub | Shared gap |
| Planning dir naming convention | No active date-prefixed dirs | Two active date-prefixed dirs | Gap in ss-fha only |

The shared gaps (codex sentinels, missing `plans.md`) are ecosystem-wide issues. The `settings.local.json` absence and date-prefix naming are ss-fha-specific.

---

## Prioritized Action List

1. **Sync ecosystem-side `architecture.md` with workspace-local copy**
   `[DRIFT]` | `straightforward-edit`
   Update `/home/dcl3nd/dev/agentic-workspace/prompts/workspaces/projects/ss-fha/architecture.md` to match the `utility_package_candidates` path and any other content in the workspace-local copy (`/home/dcl3nd/dev/ss-fha/architecture.md`). Consider making the ecosystem copy the single source of truth to prevent future divergence.

2. **Update `architecture.md` module table to reflect current codebase state**
   `[DRIFT]` | `straightforward-edit`
   Remove the five unimplemented module rows (`workflow.py`, `execution.py`, `resource_management.py`, `sensitivity_analysis.py`, `log.py`) or clearly label them as planned/future. Add a row for `io/` (`zarr_io.py`, `gis_io.py`, `netcdf_io.py`). Apply to both the ecosystem copy and the workspace-local copy.

3. **Add `workspace_specific` injection sentinels to the codex `AGENTS.md`**
   `[DRIFT]` | `script`
   Wrap the `workspace_specific` content in `<!-- injection-start: workspace_specific -->` / `<!-- injection-end: workspace_specific -->` sentinels in `/home/dcl3nd/dev/agentic-workspace/prompts/runtimes/codex/workspaces/projects/ss-fha/AGENTS.md`. The same fix is needed for `lassiterdc-utils` and likely all codex workspace entrypoints — investigate whether this is a `refresh_injections.py` script gap rather than a per-workspace manual edit.

4. **Add `Active plan references` and `Gotchas` sections to `architecture.md`**
   `[DRIFT]` | `straightforward-edit`
   Per `architecture-doc-conventions.md`, add an `## Active Plan References` section linking to the two active refactor plan directories and a `## Gotchas` section documenting known non-obvious behaviors (e.g., the `compound` vs. `combined` historic event_type mismatch documented in `ss-fha_glossary.md`, the dual `architecture.md` copies).

5. **Update `work_chunks/README.md` status table for 03B and 03C**
   `[DRIFT]` | `straightforward-edit`
   Change the status of `03B_workflow2_uncertainty.md` and `03C_event_statistics_runner.md` from "Pending" to "Complete" in `/home/dcl3nd/dev/ss-fha/docs/planning/refactors/2026-02-25_full_codebase_refactor/work_chunks/README.md`.

6. **Update `docs/planning/README.md` to reflect current naming convention**
   `[DRIFT]` | `straightforward-edit`
   Remove the `YYYY-MM-DD_` prefix from the naming convention description; replace with `snake_case` with `created:` frontmatter. Add the `implemented/` subdirectory to the multi-phase plan structure diagram. Add the `audits/` type directory if it is retained.

7. **Consolidate `audit/` and `audits/` directories**
   `[DRIFT]` | `human-decision`
   Choose one canonical name (`audits/` is preferred for consistency with the plural convention of `bugs/`, `features/`, `refactors/`), move `se_review_2026-03-14.md` into it, remove the empty alternative directory, and add a `completed/` subdirectory. Then either document `audits/` as a recognized planning type in the workspace README or propose adding it to `planning-document-lifecycle.md` in the ecosystem.

8. **Rename active multi-phase plan subdirectories to remove date prefixes**
   `[DRIFT]` | `human-decision`
   Use `git mv` to rename `2026-02-25_full_codebase_refactor/` → `full_codebase_refactor/` and `2026-03-04_old_code_alignment_testing/` → `old_code_alignment_testing/`. Move the dates to `created:` frontmatter in `full_codebase_refactor.md` and `master.md`. Update the path reference in `architecture.md`'s Refactoring Context section and any other cross-references.

9. **Add `plans.md` and `ideas/` directory structure to the planning system**
   `[DRIFT]` | `human-decision`
   Adopt or copy `scripts/generate_planning_tables.py` to auto-generate `plans.md` and the `ideas.md` priority table. Create `docs/planning/ideas/` for atomic per-idea files. Convert the current manual `ideas.md` stub to the auto-generated format by running the script.

10. **Confirm or add `settings.local.json` for ss-fha Claude Code runtime**
    `[ADVISORY][NEEDS CLARIFICATION]` | `human-decision`
    Review the `lassiterdc-utils` `settings.local.json` as a template and create an equivalent at `$AGENTIC_WORKSPACE/prompts/runtimes/claude_code/workspaces/projects/ss-fha/settings.local.json` if the current permission-prompt behavior in Claude Code sessions is undesirable.

11. **Assess Snakemake/HPC glossary injection for upcoming workflow work chunks**
    `[ADVISORY][NEEDS CLARIFICATION]` | `human-decision`
    Decide whether to inject `snakemake-workspace_glossary.md` into ss-fha sessions given that Snakemake workflow construction is a major upcoming work chunk (04A). If yes, add it to the `workspace_specific` injection block and run `refresh_injections.py`.

12. **Remove `temp_parent` from workspace prompt docs when schema is stable**
    `[ADVISORY]` | `straightforward-edit`
    Both `architecture.md` and `ss-fha_glossary.md` carry `temp_parent` as a transitional field scheduled for removal once the frontmatter schema is stable. Track this cleanup as part of the ecosystem schema stabilization effort.

---

## Appendix: Audit Prompt

Audit the ss-fha workspace for conformity with agentic-workspace ecosystem best practices.

- **Workspace root:** `/home/dcl3nd/dev/ss-fha`
- **Ecosystem root:** `/home/dcl3nd/dev/agentic-workspace` — in all paths below, `$AGENTIC_WORKSPACE` expands to this absolute path
- Treat the ecosystem as ground truth. Do not audit or critique it.

---

### Hard constraints

These rules apply throughout the entire audit. They are not negotiable and must be held even after many file reads:

1. **Read-only.** Do not write to, edit, or create any file except the single output file listed in the scope guards. Do not fix issues — document them only.
2. **All reads before any writes.** Complete all seven dimension checks before writing a single line to the output file. Write findings in one contiguous operation.
3. **Ecosystem is ground truth.** Do not critique, flag, or suggest changes to any file under the ecosystem root. If an ecosystem document appears inconsistent, treat it as correct and assess the workspace against it.

---

### Ecosystem artifacts to read before auditing

Read these before beginning dimension checks. They are the authoritative references you will audit against:

- `$AGENTIC_WORKSPACE/prompts/glossary/agentic_ecosystem.md` — canonical frontmatter schema, delivery values, doc_type values, injection system vocabulary
- `$AGENTIC_WORKSPACE/prompts/instructions/protocols/injection-conventions.md` — three-tier injection structure, sentinel format, chain-read scope
- `$AGENTIC_WORKSPACE/prompts/instructions/protocols/architecture-doc-conventions.md` — required and optional sections for project `architecture.md` files
- `$AGENTIC_WORKSPACE/prompts/instructions/protocols/planning-document-lifecycle.md` — naming convention, completion rules, plans.md/ideas.md lifecycle
- `$AGENTIC_WORKSPACE/prompts/instructions/protocols/documentation-currency.md` — what "in step with the codebase" means for workspace instruction files

---

### Audit dimensions

**1. Runtime entrypoints — both harnesses**

Examine the two managed entrypoints for ss-fha:
- `$AGENTIC_WORKSPACE/prompts/runtimes/claude_code/workspaces/projects/ss-fha/CLAUDE.md`
- `$AGENTIC_WORKSPACE/prompts/runtimes/codex/workspaces/projects/ss-fha/AGENTS.md`

For each, check:
- Frontmatter fields are present and valid per the `agentic_ecosystem.md` schema (`doc_type`, `delivery`, `workspace_type`, `workspaces`, `harness_scope`, `description`)
- Commandment #1 (inline literal bootstrap text) is present and unmodified — compare against the canonical text in `$AGENTIC_WORKSPACE/prompts/runtimes/claude_code/CLAUDE.md` or the codex equivalent
- All three injection tiers are present in order: `all_workspaces_runtimes`, `project_runtimes`, `workspace_specific`
- Each tier's content block is wrapped in the correct `<!-- injection-start: <group> -->` / `<!-- injection-end: <group> -->` sentinels
- The `workspace_specific` block uses the `$AGENTIC_WORKSPACE` variable form (not `~/dev/agentic-workspace/`) for ecosystem-side paths
- No sentinel block appears to have been hand-edited (comment line inside the block reads `AUTO-GENERATED by refresh_injections.py`)

Also check whether a `settings.local.json` permissions file exists at `$AGENTIC_WORKSPACE/prompts/runtimes/claude_code/workspaces/projects/ss-fha/`. Compare against the peer workspace (`lassiterdc-utils`) to assess whether its absence is a gap.

**2. Workspace prompt documents**

Examine the two workspace-specific prompt docs:
- `$AGENTIC_WORKSPACE/prompts/workspaces/projects/ss-fha/architecture.md`
- `$AGENTIC_WORKSPACE/prompts/workspaces/projects/ss-fha/ss-fha_glossary.md`

For each, check:
- Frontmatter is complete and valid (all required fields from `agentic_ecosystem.md`)
- `temp_parent` is present; note whether it is a candidate for removal (it is a transitional field scheduled for cleanup once the schema is stable)

For `architecture.md` specifically, check against the section checklist in `architecture-doc-conventions.md` for project workspaces:
- Purpose statement, module table, configuration system, active plan references, refactoring context, gotchas, environment setup
- Assess whether the module table and refactoring context reflect the current state of the codebase at a high level — do not perform a deep code review, but do verify that module names and key file paths listed are not obviously stale

For `ss-fha_glossary.md` specifically, check for substantive overlap with the three domain glossaries (`flood_risk_management`, `hydrology`, `statistics`). Flag terms defined in both places if the definitions conflict or are redundant.

**3. Workspace root entrypoint files**

The ss-fha workspace root contains a `CLAUDE.md` and an `AGENTS.md` (both untracked in git). These are *separate* from the managed ecosystem-side entrypoints in dimension 1.

Assess each:
- Is it a symlink to, or a copy of, the ecosystem-managed entrypoint? If a copy, are they in sync?
- Does its content conform to the same three-tier injection structure and sentinel format as the ecosystem-managed version?
- Does the `AGENTS.md` at the workspace root appear to be a misfiled artifact (i.e., content that belongs under `$AGENTIC_WORKSPACE/prompts/runtimes/codex/...` rather than at the workspace root)?
- Why is each file untracked — intentional exclusion, oversight, or pending integration?

**4. Glossary coverage**

Verify that the three domain glossaries injected into ss-fha's `workspace_specific` block are appropriate for the project domain:
- `$AGENTIC_WORKSPACE/prompts/glossary/flood_risk_management.md`
- `$AGENTIC_WORKSPACE/prompts/glossary/hydrology.md`
- `$AGENTIC_WORKSPACE/prompts/glossary/statistics.md`

Check whether any domain the workspace actively uses (e.g., HPC/execution, Snakemake workflow orchestration) lacks glossary coverage and whether that gap is intentional.

**5. Planning artifact hygiene**

Examine `docs/planning/` in the workspace root:
- Check that the directory structure conforms to the `planning-document-lifecycle.md` convention: type subdirectories (`bugs/`, `features/`, `refactors/`) each with a `completed/` subdirectory; `ideas/` as a flat store; `README.md`, `plans.md`, `ideas.md` as persistent tracking files
- Verify that no active plan file uses a date-prefixed filename (the protocol requires `snake_case` with no date prefix; date belongs in `created:` frontmatter). Grandfathered `completed/` entries are acceptable — flag only active plan files
- Check `plans.md` and `ideas.md`: are they present, and do they appear to reflect the current contents of their respective directories (i.e., not obviously stale relative to the visible active plans)?
- Scan active multi-phase plan directories (e.g., `docs/planning/refactors/2026-02-25_full_codebase_refactor/`) for phases that appear completed but whose docs have not been moved to `completed/` (the per-phase subdirectory within a multi-phase plan)
- Scan frontmatter and titles of active plan files (do not read full plan bodies) for any plan where `completed: true` is missing but the plan title or frontmatter description matches a commit message from the recent git log. Flag candidate matches; do not make definitive determinations about completion status.
- Note the `docs/planning/audits/` directory: the planning-document-lifecycle protocol does not define an `audits/` type directory. Assess whether this is an undocumented extension, a deviation, or a candidate for integration into the lifecycle protocol

**6. Documentation currency**

Check whether the workspace instruction files reflect recent codebase activity, scoped to the git log:
- Review recent commits (last 10–15) to identify structural changes: new modules, renamed files, changed configuration patterns
- For each structural change identified, check whether `architecture.md` still accurately describes module names, file paths, and configuration flow
- Do not evaluate whether code style or implementation details match — only whether the architecture doc's structural claims (module table, config system, workflow phases) remain accurate

**7. Peer comparison**

Compare ss-fha against `lassiterdc-utils` as the primary peer (both are Python computation project workspaces under the same ecosystem). If a meaningful structural difference is found in `lassiterdc-utils`, check one additional peer from the project workspace list for confirmation. Do not compare against more than two peers total.

Comparison scope: runtime entrypoint structure (both harnesses), workspace prompt doc completeness, presence of `settings.local.json`, planning directory structure. Do not compare codebase content or domain-specific design choices.

---

### Scope guards

- Read-only everywhere except the single output file (`docs/planning/audits/2026-03-14_ecosystem_conformity_audit.md`)
- Do not fix any issues — document them only
- Do not read into `src/` beyond directory listings and `__init__.py` files; this is sufficient to verify structural claims in `architecture.md` without constituting a code review
- Do not compare against more than two peer workspaces
- Complete all dimension checks before writing any findings; write findings in a single pass to the output file
- If you cannot determine whether something is a gap versus an intentional deviation, flag it `[NEEDS CLARIFICATION]` and describe what evidence would resolve it

---

### Severity rubric

Classify each finding with one severity label. Definitions:

- `[BLOCKING]` — the gap actively breaks or silently degrades agent operation today: a malformed entrypoint that would cause a harness to load wrong context, a missing sentinel that would cause `refresh_injections.py` to corrupt the file on the next run, or a broken path reference that causes a silent read failure at session startup
- `[DRIFT]` — the workspace has deviated from an ecosystem convention in a way that does not break operation today but will cause confusion or silent misalignment over time (e.g., a section missing from `architecture.md`, a stale module name, a plan file with a date-prefix filename)
- `[ADVISORY]` — an observation worth noting for ecosystem health that is not a convention violation: e.g., a glossary term that could be consolidated, a `temp_parent` field that is a candidate for removal, a planning directory extension that should be documented

Apply `[NEEDS CLARIFICATION]` as an **overlay** on any of the above when the evidence is ambiguous and a human decision is needed before the finding can be acted on. Write it as: `[DRIFT][NEEDS CLARIFICATION]` or `[ADVISORY][NEEDS CLARIFICATION]`. Do not use `[NEEDS CLARIFICATION]` alone — every finding needs a severity estimate even under uncertainty.

---

### Output structure

Write findings into this file, replacing only the placeholder line (`*Findings will be written here by the ecosystem-specialist agent.*`). The `## Appendix` section and everything below it must remain intact. Use `##` headings for the three output sections and `###` headings for per-dimension subsections:

**1. Executive summary** (≤200 words)
- One-sentence conformity verdict: is ss-fha substantially conformant, partially conformant, or significantly drifted from ecosystem conventions?
- Count of findings by severity: N blocking, N drift, N advisory, N needing clarification
- The two or three highest-priority items for immediate attention

**2. Per-dimension findings**
One subsection per audit dimension, using the heading `### Dimension N: <name>` where N and name match the dimension numbers and titles in this prompt. Within each subsection:
- State what was checked
- List each finding with its severity label and a one-paragraph description of the gap, what convention it violates, and what file(s) are involved
- If a dimension is fully conformant, say so explicitly rather than omitting it

**3. Prioritized action list**
A flat ranked list of all actionable findings, ordered by severity then operational impact (i.e., how many agent sessions or files are affected by leaving the gap unaddressed). For each item:
- Short title
- Severity label
- Owner type: `human-decision` (requires judgment call), `script` (run `refresh_injections.py` or another generator), or `straightforward-edit` (mechanical change with clear correct answer)
- One-sentence description of the required action
