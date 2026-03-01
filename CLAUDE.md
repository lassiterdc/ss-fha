# CLAUDE.md

Read these files before beginning any task:

- `CONTRIBUTING.md`
- `architecture.md`

---

## Planning Document Lifecycle

Read `~/dev/claude-workspace/specialist_agent_docs/planning-document-lifecycle.md` for the full lifecycle rules.

---

## Environment

This project uses a conda environment named `ss-fha`.

- **Running tools**: Use `conda run -n ss-fha <command>` or activate the environment first with `conda activate ss-fha`.
- **Copier updates**: When running `copier update` through `conda run`, pass `--defaults` since there is no interactive terminal: `conda run -n ss-fha copier update --trust --skip-tasks --defaults`.

---

## Code Style

- **Python**: >=3.11
- **Formatter/linter**: `ruff format` and `ruff check` — run before submitting any code. Line length and all style rules are enforced by `pyproject.toml`; write code that will survive `ruff format` unchanged.
- **Type checker**: Pyright/Pylance — address squiggles organically as scripts are touched; do not leave new `# type: ignore` comments unless the issue is a known type checker limitation

---

## Terminology

See domain glossaries for shared definitions:
- `~/dev/claude-workspace/glossary/flood_risk_management.md` — combined, compound, rain-only, surge-only, BDS, SSFHA, MCDS, event_iloc
- `~/dev/claude-workspace/glossary/hydrology.md` — storm surge, storm tide, tidal phase, return period, AEP
- `~/dev/claude-workspace/glossary/statistics.md` — marginal distribution, copula, vine copula, KNN resampling, Poisson process

### System vs. Analysis vs. Comparative Analysis

These terms align with TRITON-SWMM_toolkit's `system_config` / `analysis_config` distinction, extended with a third tier for multi-FHA comparison workflows:

| Term | Meaning | Config file pattern |
|------|---------|---------------------|
| **System** | The fixed physical and geographic context for a case study — the spatial domain, CRS, and all geospatial input files. Shared across all analyses of the same study area. | `system.yaml` |
| **Analysis** | The primary flood hazard computation for a study area — the FHA method, model output inputs, weather record parameters, event statistics configuration, workflow toggles, and execution settings. Owns the event return period calculations and may reference comparative analyses. | `analysis_<id>.yaml` |
| **Comparative analysis** | An alternative FHA approach referenced from the analysis config via `alt_fha_analyses`. Uses the same system but different model outputs, `fha_approach`, or driver configuration. Does not own event statistics or list further comparative analyses. Marked explicitly with `is_comparative_analysis: true`. | `analysis_<id>.yaml` (lighter schema) |

**Rule**: Parameters that belong to the geographic domain go in the system config. Parameters that describe a specific computation go in the analysis config. When in doubt: if two analyses of the same study area would always share the value, it's often a system parameter; if they could differ, it's an analysis parameter.

**Analysis vs. comparative analysis rules:**
- Event return period calculations (`event_statistic_variables`, `weather_event_indices`) belong to the **analysis**, never the comparative analysis. Event statistics are computed once and shared.
- A comparative analysis sets `is_comparative_analysis: true`. Validation raises an error if a comparative analysis config includes `event_statistic_variables`, `alt_fha_analyses`, or other analysis-only fields.
- An analysis with `fha_approach: ssfha` and `is_comparative_analysis: false` (the default) **requires** `event_statistic_variables` and `weather_event_indices`, regardless of whether `alt_fha_analyses` is empty.
- The distinction is explicit (`is_comparative_analysis` toggle), not inferred from schema content. This avoids silent misuse of a comparative config as a standalone analysis.

### Project-specific simulation and method terms

| Term | Meaning | Usage |
|------|---------|-------|
| **TRITON-only** | A simulation using the TRITON 2D model without SWMM coupling for urban drainage | Simulation type label |
| **event_iloc** | The canonical flat integer index uniquely identifying a single simulated event within the zarr model output. Connects simulation results to meteorological inputs via the iloc mapping CSV (e.g. `ss_event_iloc_mapping.csv`). Used as an xarray dimension name (`event_iloc`) and as a CSV column name. Not to be confused with `event_id` (the 3D sub-index within a year/event_type slice) or `event_number` (deprecated term — always use `event_iloc`). | xarray dim, CSV column, code variables |
| **ss** | When a boolean flag or branch distinguishes the semicontinuous simulation ensemble from design storms, use `ss` — never `ensemble`. The SSFHA output *is* an ensemble, but `ensemble` is too generic and obscures the distinction from BDS. Example: `is_ss: bool` rather than `is_ensemble: bool`. Legacy uses of `ensemble` as a branch variable in ported functions should be renamed to `is_ss` during porting. | function arguments, branch variable names |

---

## Architecture Patterns

**Critical context**: This code base is in the middle of a refactoring documented in `docs/planning/refactors/2026-02-25_full_codebase_refactor/full_codebase_refactor.md`. All code decisions and plans should:
- Reference the refactoring plan in decisions
- Propose changes to the refactoring plan if appropriate
- Keep the refactoring plan up to date if any changes are made that are relevant to it

---

## AI Working Norms

Read `~/dev/claude-workspace/specialist_agent_docs/ai-working-norms.md` for the full protocol.
