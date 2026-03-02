# Work Chunk 03A: Workflow 1 — Flood Hazard Assessment

**Phase**: 3A — Analysis Modules + Runner Scripts (Flood Hazard)
**Last edited**: 2026-03-01 — preflight review: resolved decisions on masking, alpha/beta config, sim-type CLI values, output naming; fixed terminology and test file references

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/refactors/2026-02-25_full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`CONTRIBUTING.md`](../../../../CONTRIBUTING.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: All Phase 1 and Phase 2 work chunks complete.

---

## Task Understanding

### Requirements

Implement Workflow 1 (Flood Hazard Assessment) as an analysis module and a Snakemake-invocable runner script. This is the foundational workflow; Workflow 2 depends on its outputs.

**Replaces**: `_old_code_to_refactor/b1_analyze_triton_outputs_fld_prob_calcs.py`

**Files to create:**

1. `src/ss_fha/analysis/__init__.py`
2. `src/ss_fha/analysis/flood_hazard.py`:
   - Orchestrates flood probability computation from TRITON outputs
   - Loads TRITON zarr outputs (via `ss_fha.io.zarr_io`)
   - Applies watershed mask (via `ss_fha.io.gis_io` + `ss_fha.core.geospatial`)
   - Calls `ss_fha.core.flood_probability` functions
   - Writes flood probability zarr outputs (via `ss_fha.io.zarr_io`)
   - Supports multiple simulation types: combined, surge-only, rain-only, triton-only-combined

3. `src/ss_fha/runners/__init__.py`
4. `src/ss_fha/runners/flood_hazard_runner.py`:
   - CLI entry point (argparse): `--config <yaml_path>` + `--sim-type <combined|surge_only|rain_only|triton_only_combined>`
   - Logs to stdout (captured by Snakemake)
   - Calls `analysis.flood_hazard` functions
   - Writes completion marker to log (per philosophy.md log-based completion checks)

### Key Design Decisions

- **Per philosophy.md**: runner scripts log to stdout; Snakemake captures this as a logfile. Use structured log messages with timestamps.
- **Log-based completion check**: the runner must emit a specific completion log line (e.g., `"COMPLETE: flood_hazard combined"`) that Snakemake rules can verify.
- **`--sim-type`** controls which TRITON output is loaded; the config provides the path for that sim type. Values use underscores: `combined`, `surge_only`, `rain_only`, `triton_only_combined`.
- **Fail fast**: if the TRITON zarr path for the requested `--sim-type` is not in the config, raise `ConfigurationError` immediately.
- **No QAQC plots in this chunk** — visualization is Phase 5. Stub the toggle guard with a planning-doc reference comment per `planning-document-lifecycle.md` conventions.
- **Watershed masking**: apply the watershed mask before computing flood probabilities; cells outside the watershed are set to NaN. This reduces computation and produces cleaner output.
- **Input zarr is already flat on `event_iloc`**: no stacking step needed — TRITON-SWMM_toolkit produces the flat schema upstream.
- **`alpha` and `beta` plotting position parameters**: add to `SsfhaConfig` (no defaults — users must choose explicitly). This requires modifying `config/model.py`.
- **Output naming**: `{flood_probs_dir}/{sim_type}.zarr` (e.g., `flood_probabilities/combined.zarr`).

### Success Criteria

- `python -m ss_fha.runners.flood_hazard_runner --config test_config.yaml --sim-type combined` runs end-to-end with synthetic data
- Output zarr exists and passes `assert_zarr_valid()`
- Integration test in `tests/test_flood_hazard_workflow.py` using `build_minimal_test_case` passes

---

## Evidence from Codebase

Before implementing, inspect:

1. `_old_code_to_refactor/b1_analyze_triton_outputs_fld_prob_calcs.py` — full script to understand all steps
2. `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/process_timeseries_runner.py` — runner script pattern (argparse, logging, completion marker)
3. `src/ss_fha/core/flood_probability.py` (02A)
4. `src/ss_fha/io/zarr_io.py` (01D)

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/analysis/__init__.py` | Package stub |
| `src/ss_fha/analysis/flood_hazard.py` | Workflow 1 orchestration |
| `src/ss_fha/runners/__init__.py` | Package stub |
| `src/ss_fha/runners/flood_hazard_runner.py` | CLI entry point |
| `tests/test_flood_hazard_workflow.py` | Integration test for Workflow 1 |

### Modified Files

| File | Change |
|------|--------|
| `src/ss_fha/config/model.py` | Add `alpha` and `beta` plotting position fields to `SsfhaConfig` |
| `tests/utils_for_testing.py` | Tighten `assert_flood_probs_valid()` to check for `empirical_cdf` and `return_pd_yrs` |
| `_old_code_to_refactor/b1_analyze_triton_outputs_fld_prob_calcs.py` | Add refactoring status block |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| TRITON zarr schema varies — wrong variable/dimension names | Validate zarr schema before processing; raise `DataError` with clear message |
| Runner called with sim-type not in config | Raise `ConfigurationError` immediately with fix hint |
| Dask chunking: wrong chunk sizes cause memory issues | Use chunking strategy from old code initially; document for later optimization |
| **Full-scale `.compute()` OOM** — zarr V3 can't serialize dask masked arrays, so `ds_flood_probs.compute()` materializes ~25 GB at full scale (3700 events x 550x550 grid) | Workaround applied with code comment + risk entry in master plan. Must be profiled during Phase 6 case study validation. See `full_codebase_refactor.md` Risks table for mitigation options. |

---

## Validation Plan

```bash
# Integration test (primary validation — uses synthetic data via build_minimal_test_case)
conda run -n ss-fha pytest tests/test_flood_hazard_workflow.py -v

# Existing tests still pass
conda run -n ss-fha pytest tests/ -v
```

---

## Documentation and Tracker Updates

- Update `full_codebase_refactor.md` tracking table: `b1_*` → `COMPLETE`.
- Add refactoring status block to `_old_code_to_refactor/b1_analyze_triton_outputs_fld_prob_calcs.py`.

---

## Definition of Done

- [x] `src/ss_fha/analysis/flood_hazard.py` implemented
- [x] `src/ss_fha/runners/flood_hazard_runner.py` implemented with argparse CLI
- [x] Runner logs to stdout with structured messages and a completion marker
- [x] Runner fails fast with `ConfigurationError` for missing sim-type config
- [x] Integration test using synthetic test case passes
- [x] Output zarr passes `assert_zarr_valid()` and `assert_flood_probs_valid()`
- [x] `full_codebase_refactor.md` tracking table updated
- [ ] **Move this document to `../implemented/` once all boxes above are checked**
