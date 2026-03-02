# Work Chunk 03C: Event Statistics Analysis and Runner

**Phase**: 3C — Analysis Modules + Runner Scripts (Event Statistics)
**Last edited**: 2026-03-02

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/refactors/2026-02-25_full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`CONTRIBUTING.md`](../../../../CONTRIBUTING.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: Work chunks 02C (event_statistics core) and 03A complete.

---

## Step 0: Consult xarray-specialist (REQUIRED before implementing output format)

**Decision C (zarr output structure) is unresolved.** Do not begin implementation until this is resolved.

Invoke the `xarray-specialist` agent with the prompt at:

```
.scratch/2026-03-02_15-21_zarr-specialist-prompt.md
```

The specialist should write findings to `.scratch/YYYY-MM-DD_HH-MM_zarr-output-structure-findings.md`.

**Questions the specialist must answer before implementation:**
1. Best xarray/zarr structure for two differently-indexed Datasets in one store (no dead space)
2. Better indexing scheme for the multivariate `event_stats` string dimension
3. Whether zarr groups are EDA-discoverable without knowing group names in advance
4. Whether a single NetCDF file can hold two differently-indexed Datasets (h5netcdf group support)
5. Any zarr v3 + xarray 2025.12 gotchas for this use case

Once findings are returned, update this plan with the output format decision before proceeding.

---

## Task Understanding

### Requirements

Implement the event statistics analysis module and runner script.

**Replaces**: `_old_code_to_refactor/d0_computing_event_statistic_probabilities.py`

**Files to create:**

1. `src/ss_fha/analysis/event_comparison.py`:
   - Loads event summary CSVs (via `ss_fha.io`)
   - Calls `ss_fha.core.event_statistics` functions
   - Writes event return period outputs (zarr v3 primary, NetCDF secondary — see Decision C below)
   - Supports Workflows 1 and 4

2. `src/ss_fha/runners/event_stats_runner.py`:
   - CLI args: `--config <yaml>`, `--system-config <yaml>`, `--overwrite`
   - Logs completion marker: `"COMPLETE: event_stats"`
   - Fail-fast with `ConfigurationError` for missing/invalid config

### Scope

**In scope**: Univariate event return periods + multivariate event return periods only.

**Out of scope** (deferred to future chunk `03C-ext` or `03G`): Bootstrap event statistic uncertainty (CI on return period estimates and on statistic values such as "1-year 24-hr rainfall depth"). Future chunk should be toggle-guarded. Note: bootstrap samples from `bs_samp_of_univar_event_return_period` already include statistic values, so CIs on both return periods and statistic values are derivable from the same bootstrap run.

### Key Design Decisions

#### Decision A — `n_years` source ✅ RESOLVED
Use `config.n_years_synthesized` (a required field on `SsfhaConfig`). Do **not** derive `n_years` from record length — the synthesized record has 1000 years but only 954 have events; deriving from `len(ds.year)` would give the wrong value. Log the value at run start.

#### Decision B — Bootstrap scope ✅ RESOLVED
Bootstrap event statistics are **out of scope** for 03C. Implement univariate + multivariate only. A future chunk will add bootstrap support, toggle-guarded via config. The master refactor plan has been updated accordingly.

#### Decision C — Output format ⚠️ UNRESOLVED — see Step 0 above
Resolved so far:
- All outputs in a **single zarr store** (not two separate files)
- Zarr v3 primary format; NetCDF secondary (user-configurable, existing config intention)
- No dead space (NaN-padded dense arrays are not acceptable)
- EDA-friendly (discoverable without knowing internal naming conventions)

Unresolved:
- Whether zarr groups or another pattern is the right structure for two differently-indexed Datasets
- Whether h5netcdf supports HDF5 groups (needed for NetCDF dual-format parity)
- Better indexing for the multivariate `event_stats` string dimension

#### CF metadata — ✅ RESOLVED
No CF compliance. Use descriptive `attrs` only (`long_name`, `units`, `description`) on xarray variables. Do not install or use `cf_xarray`.

- Event-to-flood mapping (the "fragile CSV" noted in the master plan) must be formalized. Define the expected column schema for event CSV files clearly and validate on load.

### Success Criteria

- Runner executes end-to-end with synthetic event summaries
- Event return periods written to output; output passes basic sanity checks (no NaN, return periods > 0)

---

## Evidence from Codebase

Before implementing, inspect:

1. `_old_code_to_refactor/d0_computing_event_statistic_probabilities.py`
2. `src/ss_fha/core/event_statistics.py` (02C)
3. `_old_code_to_refactor/__inputs.py` — event CSV column name conventions

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/analysis/event_comparison.py` | Event statistics orchestration |
| `src/ss_fha/runners/event_stats_runner.py` | CLI runner |

### Modified Files

| File | Change |
|------|--------|
| `_old_code_to_refactor/d0_*.py` | Add refactoring status block |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| Event CSV schema varies between datasets | Validate expected columns on load; raise `DataError` with column list if missing |
| `n_years` derived from data instead of config | Always use `config.n_years_synthesized`; log the value at run start |

---

## Validation Plan

```bash
python -m ss_fha.runners.event_stats_runner --config /tmp/ssfha_test/config.yaml
pytest tests/test_end_to_end.py::test_event_statistics -v
```

---

## Documentation and Tracker Updates

- Update `full_codebase_refactor.md` tracking table: `d0_*` → `COMPLETE`.
- Update master plan bootstrap event stats note (future chunk).

---

## Definition of Done

- [ ] xarray-specialist consulted; Decision C resolved and this plan updated
- [ ] `src/ss_fha/analysis/event_comparison.py` implemented
- [ ] `src/ss_fha/runners/event_stats_runner.py` implemented
- [ ] `n_years` sourced from `config.n_years_synthesized`; logged at run start
- [ ] Event CSV schema validated on load
- [ ] Integration test passes with synthetic event summaries
- [ ] `full_codebase_refactor.md` tracking table updated
- [ ] **Move this document to `../implemented/` once all boxes above are checked**
