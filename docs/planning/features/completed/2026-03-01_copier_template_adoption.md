# Copier Template Adoption

- **Created**: 2026-03-01
- **Last edited**: 2026-03-01 — initial draft

---

## Task Understanding

### Requirements

1. Bring the ss-fha repo under Copier template management using `copier-python-template`
2. Migrate from Zensical docs to MkDocs (template standard)
3. Migrate planning directory structure to template convention (`docs/planning/{bugs,features,refactors}/completed/`)
4. Consolidate `.prompts/philosphy.md` content into template-standard docs (`CLAUDE.md`, `CONTRIBUTING.md`, `architecture.md`)
5. Delete superseded local skill prompts (`.prompts/implementation_plan.md`, `proceed_with_implementation.md`, `qaqc_and_commit.md`) — now global skills
6. Fix `environment.yaml` env name (`triton_swmm_toolkit` → `ss_fha`)
7. Adopt `HISTORY.md` changelog convention; delete `CHANGELOG/` directory
8. Remove cookiecutter residuals (`CODE_OF_CONDUCT.md`, Cookiecutter attribution in README)
9. Preserve all project-specific content (GitHub workflows, pyproject.toml, source code, tests)

### Assumptions

1. The copier-python-template is available locally at `~/dev/copier-python-template` with a tagged release
2. The repo is on the `refactoring` branch; all work will be committed there
3. The `docs.yml` GitHub Actions workflow must be updated from Zensical to MkDocs commands
4. `pyproject.toml` docs dependency group must switch from `zensical` to `mkdocs`/`mkdocs-material`/`mkdocstrings[python]`
5. The `ci.yml` type-check job references `ty` which the developer has noted should not be used — this is a pre-existing issue, not in scope for this plan
6. The `justfile` has Zensical references that must be updated to MkDocs

### Success Criteria

- `.copier-answers.yml` present with correct variable values
- `copier update --trust --skip-tasks --defaults` completes cleanly
- `.claude/settings.local.json` preserved with original permissions
- All 30+ planning doc references to `.prompts/philosphy.md` updated to `CONTRIBUTING.md`
- No content from `.prompts/philosphy.md` is lost — every block has a verified destination
- `ruff check .` and `ruff format --check .` pass
- MkDocs builds locally: `uv run --group docs mkdocs build --strict`
- `.prompts/` directory fully deleted
- Cookiecutter residuals (`CODE_OF_CONDUCT.md`, `CHANGELOG/`) deleted

---

## Evidence from Codebase

- **`.prompts/philosphy.md`** (261 lines): Contains Terminology (lines 1–36), "About this code base" (lines 40–48), Development Philosophy (lines 50–189), Architecture/Key Modules (lines 196–236), and Testing Strategy (lines 240–261). All content must migrate.
- **`.prompts/` skill files**: All 3 are superseded by global skills in `~/.claude/skills/` (symlinked from `~/dev/claude-workspace/skills/`).
- **30+ planning docs** reference `.prompts/philosphy.md` on line 13 via relative path `../../../../../.prompts/philosphy.md`. Path depth changes from 6 to 5 levels when `active/` is removed.
- **`environment.yaml`**: env name is `triton_swmm_toolkit` (line 19) — wrong for this project.
- **`zensical.toml`**: Current docs config. `docs.yml` workflow uses `zensical build --clean`. `justfile` lines 61, 65 use `zensical serve`/`zensical build`.
- **`pyproject.toml`**: docs dependency group has `zensical` + `mkdocstrings-python`. `[tool.esbonio.sphinx]` section is stale (references Sphinx).
- **`requirements.txt`**: Has stale Sphinx deps (`sphinx`, `sphinx-rtd-theme`, `nbsphinx`, `jupyter`, `sphinxcontrib-mermaid`).
- **`.readthedocs.yaml`**: Stale — references `docs/conf.py` (Sphinx) and has duplicate `sphinx:` keys.
- **`README.md`**: References Zensical (line 18) and Cookiecutter (line 59).
- **`CONTRIBUTING.md`**: Cookiecutter-era boilerplate. "Deploying" section (lines 113–139) has project-specific release process worth preserving.
- **`.github/workflows/publish.yml`**: Hardened (pinned SHAs, attestation) — must keep.
- **`.github/workflows/ci.yml`**, `codeql.yml`, `zizmor.yml`, `dependabot.yml`: Not in template — keep as-is.
- **`.claude/settings.local.json`**: Contains project-specific permission allows — must restore after copier.
- **`ENVIRONMENT_SNAPSHOT.md`**: References conda env name `ss-fha` — already correct; keep as-is.
- **No `tests/__init__.py`** at root level (tests use `conftest.py` and `fixtures/__init__.py`).
- **`justfile`**: Has Zensical and `ty` references; Zensical lines need updating.

---

## Implementation Strategy

### Chosen approach

**Pre-build → Copier copy → Restore → Clean → Fix references → Verify**

Prepare all rebuilt content files before running copier, then run `copier copy --overwrite`, then restore files that copier would have clobbered, then clean up superseded files, then fix all stale references in bulk.

### Alternatives considered

- **Manual creation without copier**: Would produce equivalent files but would not establish the copier tracking (`.copier-answers.yml`) needed for future template updates. Rejected.
- **Copier copy first, then build content**: Riskier because copier's template-generated placeholders would need to be identified and replaced rather than simply overwritten with pre-built content. The prepare-first approach is more predictable.

### Trade-offs

The prepare-first approach requires writing content to files that copier will immediately overwrite, but this is intentional — the pre-built files serve as the "source of truth" that we restore after copier runs.

---

## File-by-File Change Plan

### Phase 1: Pre-copier preparation

| File | Action | Details |
|---|---|---|
| `docs/planning/active/refactors/full_codebase_refactor/` | **Move** | → `docs/planning/refactors/2026-02-25_full_codebase_refactor/` (rename `active/refactors/full_codebase_refactor` to template convention) |
| `docs/planning/active/` | **Delete** | Empty after move |
| `docs/planning/utility_package_candidates.md` | **Keep** | Stays at `docs/planning/` (not type-specific) |
| `environment.yaml` | **Edit** | Line 19: `name: triton_swmm_toolkit` → `name: ss_fha` |
| `CLAUDE.md` | **Create** (pre-build) | Template skeleton populated with: Terminology section from `.prompts/philosphy.md`, "About this code base" context, conda env name `ss_fha`, refactoring context note |
| `CONTRIBUTING.md` | **Create** (pre-build) | Template version + all Development Philosophy content from `.prompts/philosphy.md` + Deploying section from old `CONTRIBUTING.md` |
| `architecture.md` | **Create** (pre-build) | Template skeleton populated with: Key Modules table, Testing Strategy, Sources of Inspiration, Configuration System, Workflow Phases from `.prompts/philosphy.md` |
| `README.md` | **Create** (pre-build) | Template structure with ss-fha-specific content; no Cookiecutter refs |
| `HISTORY.md` | **Create** (pre-build) | Template header + `## v0.1.0\n\nFirst release on PyPI.` |
| `.gitignore` | **Prepare** (save custom patterns) | Note project-specific patterns to re-add: `*_archive*`, `hydroshare_data/*` |
| `requirements.txt` | **Create** (pre-build) | `mkdocs\nmkdocs-material\nmkdocstrings[python]` |
| `mkdocs.yml` | **Create** (pre-build) | Template version with ss-fha variables substituted |

### Phase 2: Run copier

| Command | Details |
|---|---|
| `copier copy --overwrite --trust --defaults ~/dev/copier-python-template .` with `--data` flags | Variables: project_name="SS-FHA", project_slug="ss-fha", package_name="ss_fha", author_name="Daniel Lassiter", author_email="daniel.lassiter@outlook.com", github_username="lassiterdc", description="Semicontinuous simulation-based flood hazard assessment framework", python_version="3.11", conda_env_name="ss_fha" |

### Phase 3: Post-copier restoration

| File | Action | Details |
|---|---|---|
| `.claude/settings.local.json` | **Restore** | `git checkout -- .claude/settings.local.json` |
| `.github/workflows/publish.yml` | **Restore** | `git checkout -- .github/workflows/publish.yml` |
| `pyproject.toml` | **Restore** | `git checkout -- pyproject.toml`, then edit: remove `[tool.esbonio.sphinx]` section, change docs group from `["zensical", "mkdocstrings-python"]` to `["mkdocs", "mkdocs-material", "mkdocstrings-python"]` |
| `environment.yaml` | **Restore** | `git checkout -- environment.yaml`, then re-apply env name fix (`triton_swmm_toolkit` → `ss_fha`) |
| `src/ss_fha/__init__.py` | **Restore** | `git checkout -- src/ss_fha/__init__.py` |
| `CLAUDE.md` | **Overwrite** | Write pre-built CLAUDE.md content (copier generated placeholder) |
| `CONTRIBUTING.md` | **Overwrite** | Write pre-built CONTRIBUTING.md content |
| `architecture.md` | **Overwrite** | Write pre-built architecture.md content |
| `README.md` | **Overwrite** | Write pre-built README.md content |
| `HISTORY.md` | **Overwrite** | Write pre-built HISTORY.md content |
| `.gitignore` | **Edit** | Append project-specific patterns: `*_archive*`, `hydroshare_data/*` |
| `requirements.txt` | **Overwrite** | Write pre-built requirements.txt |
| `mkdocs.yml` | **Overwrite** | Write pre-built mkdocs.yml |
| `.readthedocs.yaml` | **Keep** | Template's version is correct (MkDocs-based); no action needed |

### Phase 4: Clean up superseded files

| File | Action | Details |
|---|---|---|
| `.prompts/philosphy.md` | **Delete** | Content fully migrated to CLAUDE.md, CONTRIBUTING.md, architecture.md |
| `.prompts/implementation_plan.md` | **Delete** | Superseded by global skill |
| `.prompts/proceed_with_implementation.md` | **Delete** | Superseded by global skill |
| `.prompts/qaqc_and_commit.md` | **Delete** | Superseded by global skill |
| `.prompts/` | **Delete** | Empty directory |
| `CODE_OF_CONDUCT.md` | **Delete** | Cookiecutter cruft, single-developer project |
| `CHANGELOG/v0.1.0.md` | **Delete** | Content migrated to HISTORY.md |
| `CHANGELOG/` | **Delete** | Empty directory |
| `zensical.toml` | **Delete** | Replaced by mkdocs.yml |

### Phase 5: Update docs.yml workflow and justfile

| File | Action | Details |
|---|---|---|
| `.github/workflows/docs.yml` | **Edit** | Change `uv run --group docs zensical build --clean` → `uv run --group docs mkdocs build --strict` |
| `justfile` | **Edit** | Line 61: `zensical serve` → `mkdocs serve`; Line 65: `zensical build --clean` → `mkdocs build --strict` |
| `pyproject.toml` | **Verify** | Confirm `[tool.esbonio.sphinx]` removed and docs group updated (done in Phase 3) |

### Phase 6: Fix stale references

| Target | Find | Replace | Count |
|---|---|---|---|
| All planning docs (line 13) | `[.prompts/philosphy.md](../../../../../.prompts/philosphy.md) — project development philosophy; all implementation decisions must align with it.` | `[CONTRIBUTING.md](../../../../CONTRIBUTING.md) — project development philosophy; all implementation decisions must align with it.` | ~22 files (work_chunks + implemented) |
| `full_codebase_refactor.md` | `.prompts/philosophy.md` | `CONTRIBUTING.md` | ~3 occurrences |
| `MEMORY.md` (auto-memory) | `.prompts/philosphy.md` | `CONTRIBUTING.md` | 1 occurrence |
| `MEMORY.md` (auto-memory) | Planning paths referencing `active/refactors/` | Updated paths under `refactors/2026-02-25_full_codebase_refactor/` | Multiple |

**Note on relative link depth**: After removing `active/`, the planning docs move from depth 6 (`docs/planning/active/refactors/full_codebase_refactor/work_chunks/`) to depth 5 (`docs/planning/refactors/2026-02-25_full_codebase_refactor/work_chunks/`). The relative link to `CONTRIBUTING.md` from work_chunks is `../../../../CONTRIBUTING.md` (4 levels up to repo root). From `implemented/` it's also `../../../../CONTRIBUTING.md`.

### Phase 7: Verify

| Check | Command / Action |
|---|---|
| Ruff lint | `uv run ruff check .` |
| Ruff format | `uv run ruff format --check .` |
| MkDocs build | `uv run --group docs mkdocs build --strict` |
| Copier answers | `cat .copier-answers.yml` — verify all variables correct |
| Copier update | `copier update --trust --skip-tasks --defaults` — verify completes cleanly |
| `.claude/settings.local.json` | Verify contents match original |
| No stale references | `grep -rn '.prompts/' . --include='*.md' --include='*.py'` — should return zero results |
| Source code intact | `uv run pytest` — existing tests still pass |

---

## Content Preservation Audit

Every content block from `.prompts/philosphy.md` must have a verified destination. This table will be checked off during implementation.

| Source block | Lines | Destination | Section |
|---|---|---|---|
| Terminology table (System/Analysis/Comparative) | 1–22 | `CLAUDE.md` | Terminology |
| Terminology table (Combined/Compound/etc.) | 23–36 | `CLAUDE.md` | Terminology |
| "About this code base" | 40–48 | `architecture.md` | Project Overview |
| "Critical context" refactoring note | 45–48 | `CLAUDE.md` | Architecture Patterns |
| "Never commit without explicit permission" | 53–54 | `CONTRIBUTING.md` | Development Principles |
| "Raise questions rather than make assumptions" | 56–58 | `CONTRIBUTING.md` | Development Principles (already in template) |
| "Plan, then implement" | 60–64 | `CONTRIBUTING.md` | Development Principles (already in template) |
| `#user:` prefixed statements | 66–71 | `CONTRIBUTING.md` | Development Principles |
| "Let's do things right" | 73–81 | `CONTRIBUTING.md` | Development Principles (already in template) |
| "Most function arguments should not have defaults" | 83–85 | `CONTRIBUTING.md` | Development Principles (already in template) |
| "Backward compatibility is NOT a priority" | 87–105 | `CONTRIBUTING.md` | Development Principles (already in template) |
| "Error handling" | 107–110 | `CONTRIBUTING.md` | Development Principles (already in template: Fail-fast, Preserve context) |
| "Log-Based Checks over File Existence" | 112–117 | `CONTRIBUTING.md` | Development Principles (already in template) |
| "Use Pydantic models" | 119 | `CONTRIBUTING.md` | Development Principles |
| "Runner scripts + CLI args" | 121 | `CONTRIBUTING.md` | Development Principles |
| "Robust logging in runner scripts" | 123 | `CONTRIBUTING.md` | Development Principles |
| "Utility package candidates" | 125–128 | `CONTRIBUTING.md` | Development Principles (already in template) |
| "Snakemake rule generation" | 130–132 | `CONTRIBUTING.md` | Development Principles |
| "No cruft" | 134 | `CONTRIBUTING.md` | Development Principles (already in template) |
| "No shims for poorly formatted inputs" | 136–138 | `CONTRIBUTING.md` | Development Principles |
| "Avoid aliases" | 140 | `CONTRIBUTING.md` | Development Principles (already in template) |
| "Data type preferences" | 142–146 | `CONTRIBUTING.md` | Development Principles |
| "System agnostic software" | 148–151 | `CONTRIBUTING.md` | Development Principles (already in template) |
| "All hardcoded constants" | 153–157 | `CONTRIBUTING.md` | Development Principles |
| Type checking section | 159–185 | `CONTRIBUTING.md` | Development Principles |
| "All variables, imports, function arguments should be used" | 187–190 | `CONTRIBUTING.md` | Development Principles (already in template) |
| "Functions all have helpful docstrings" | 192 | `CONTRIBUTING.md` | Development Principles (already in template) |
| Architecture: Key Modules table | 198–208 | `architecture.md` | Key Modules |
| Architecture: Sources of inspiration | 209–236 | `architecture.md` | Sources of Inspiration |
| Testing strategy | 240–261 | `architecture.md` | Testing Strategy |

---

## Risks and Edge Cases

| Risk | Severity | Mitigation |
|---|---|---|
| Copier overwrites `.claude/settings.local.json` | High | Restore immediately with `git checkout` in Phase 3 |
| MkDocs build fails due to missing/broken API references | Medium | `docs/api.md` references `ss_fha` — the package is minimal but importable. Build with `--strict` to catch warnings. |
| 30+ relative link rewrites introduce typos | Medium | Use `grep -rn '.prompts/' . --include='*.md'` to verify zero stale references remain |
| `copier copy` validation task fails | Medium | The template has a validation task that checks `package_name` is a valid Python identifier. `ss_fha` is valid, so this should pass. |
| Planning doc relative links break after directory move | Medium | Test by checking that links resolve. The depth change (6→5) affects all `../` chains. |
| `environment.yaml` env name change confuses existing conda env | Low | This only changes the file — the existing conda env on disk is unaffected until `conda env update` is run |
| `pyproject.toml` docs deps change breaks `uv sync` | Low | Simply run `uv sync` after editing to resolve |
| `mkdocs.yml` Mermaid fence config | Low | Template includes pymdownx.superfences with mermaid config — should work out of the box |

---

## Validation Plan

1. **Ruff**: `uv run ruff check . && uv run ruff format --check .`
2. **MkDocs build**: `uv run --group docs mkdocs build --strict` (after `uv sync` to install new docs deps)
3. **Tests**: `uv run pytest` — all existing tests should pass unchanged
4. **Stale references**: `grep -rn '\.prompts/' . --include='*.md' --include='*.py'` — expect zero results
5. **Copier answers**: `grep _commit .copier-answers.yml` — verify present
6. **Copier update dry run**: `copier update --trust --skip-tasks --defaults` — verify completes cleanly, then `git checkout .` to undo
7. **Settings preserved**: `cat .claude/settings.local.json` — verify matches original

---

## Documentation and Tracker Updates

| Document | Update | Trigger |
|---|---|---|
| `MEMORY.md` (auto-memory) | Update planning paths, remove `.prompts/philosphy.md` reference, add copier status | After all phases complete |
| `docs/planning/refactors/2026-02-25_full_codebase_refactor/full_codebase_refactor.md` | Update any self-referencing paths if present | After directory move |
| `docs/planning/refactors/2026-02-25_full_codebase_refactor/work_chunks/README.md` | Update if it references parent paths | After directory move |

---

## Decisions Needed from User

None — all decisions were made during the pre-planning audit. The following assumptions carry low risk:

| Assumption | Risk |
|---|---|
| `description` copier variable: "Semicontinuous simulation-based flood hazard assessment framework" | Low — can be changed later via copier update |
| `ENVIRONMENT_SNAPSHOT.md` kept as-is (not deleted) | Low — project-specific reference doc, not a template concern |
| `ci.yml` `ty` type-check job left as-is (out of scope) | Low — pre-existing issue |
| `justfile` `ty` references left as-is (out of scope) | Low — pre-existing issue |

---

## Definition of Done

- [ ] `.copier-answers.yml` exists with correct variables
- [ ] `copier update --trust --skip-tasks --defaults` completes cleanly
- [ ] `.claude/settings.local.json` matches original content
- [ ] `CLAUDE.md` contains Terminology section and Architecture Patterns
- [ ] `CONTRIBUTING.md` contains all Development Philosophy content from former `.prompts/philosphy.md`
- [ ] `architecture.md` contains Key Modules, Testing Strategy, Sources of Inspiration
- [ ] `.prompts/` directory fully deleted
- [ ] `CODE_OF_CONDUCT.md` deleted
- [ ] `CHANGELOG/` directory deleted
- [ ] `zensical.toml` deleted
- [ ] `mkdocs.yml` present and builds: `uv run --group docs mkdocs build --strict`
- [ ] `docs.yml` workflow updated to mkdocs
- [ ] `justfile` updated to mkdocs
- [ ] `pyproject.toml` docs group updated, `[tool.esbonio.sphinx]` removed
- [ ] `environment.yaml` env name is `ss_fha`
- [ ] Planning directory at `docs/planning/refactors/2026-02-25_full_codebase_refactor/`
- [ ] Template planning directories exist: `docs/planning/{bugs,features,refactors}/completed/`
- [ ] Zero results from `grep -rn '\.prompts/' . --include='*.md' --include='*.py'`
- [ ] `ruff check .` passes
- [ ] `ruff format --check .` passes
- [ ] `uv run pytest` passes
- [ ] Content preservation audit table fully checked off
- [ ] `HISTORY.md` present with v0.1.0 entry
- [ ] `README.md` has no Cookiecutter references
- [ ] `requirements.txt` has MkDocs deps (not Sphinx)

---

## Self-Check Results

1. **Header/body alignment**: All section headers match their content.
2. **Section necessity**: All sections are load-bearing. The Content Preservation Audit table is critical for preventing silent content loss.
3. **Alignment with CONTRIBUTING.md**: The template's CONTRIBUTING.md already contains most development principles — the plan correctly identifies overlap and focuses on merging ss-fha-specific additions rather than duplicating.
4. **Task-relevance**: No extraneous information. All content directly supports implementation.
