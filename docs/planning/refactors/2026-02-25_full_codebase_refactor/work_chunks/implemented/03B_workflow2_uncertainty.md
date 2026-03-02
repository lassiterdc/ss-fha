# Work Chunk 03B: Workflow 2 — Flood Hazard Uncertainty (Bootstrap CI)

**Phase**: 3B — Analysis Modules + Runner Scripts (Uncertainty)
**Status**: COMPLETE — 2026-03-02
**Replaces**: `_old_code_to_refactor/c1_fpm_confidence_intervals_bootstrapping.py` and `c1b_fpm_confidence_intervals_bootstrapping.py`

---

## What Was Built

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/analysis/uncertainty.py` | Bootstrap orchestration — `prepare_bootstrap_run`, `run_bootstrap_sample`, `combine_and_quantile` |
| `src/ss_fha/runners/bootstrap_runner.py` | Single-sample Snakemake runner: `--config`, `--sample-id`, `--sim-type`, `--overwrite` |
| `src/ss_fha/runners/bootstrap_combine_runner.py` | Fan-in combine + quantile runner: `--config`, `--sim-type`, `--overwrite` |
| `tests/test_workflow2_uncertainty.py` | 17 integration tests covering all functions and both runners |
| `docs/planning/bugs/tech_debt_known_risks.md` | Dask quantile + OOM risk tracking (created during preflight) |

### Modified Files

| File | Change |
|------|--------|
| `src/ss_fha/paths.py` | Added `fha_dir` field; all workflow subdirs now under `output_dir / fha_id /` (Decision 1) |
| `tests/test_paths.py` | Updated assertions + 2 new path structure tests |
| `tests/fixtures/test_case_builder.py` | Added `build_synthetic_event_iloc_mapping()` (Poisson arrivals, vary-per-year assertion) and `build_uncertainty_test_case()` |
| `src/ss_fha/io/gis_io.py` | Fixed latent bug: `da_ref.shape[-2:]` → `(da_ref.sizes["y"], da_ref.sizes["x"])` in `create_mask_from_polygon` and `rasterize_features` |
| `src/ss_fha/config/model.py` | Added `bootstrap_quantiles: list[float]` to `UncertaintyConfig` |
| `src/ss_fha/examples/config_templates/norfolk_default.yaml` | Added `bootstrap_quantiles: [0.05, 0.50, 0.95]` |
| `cases/norfolk_ssfha_comparison/analysis_ssfha_*.yaml` (4 files) | Added `bootstrap_quantiles: [0.05, 0.50, 0.95]` |
| `_old_code_to_refactor/c1_*.py`, `c1b_*.py` | Added refactoring status blocks |

---

## Key Design Decisions

### Decision 1: `fha_id` namespacing in `ProjectPaths`

All Norfolk analysis configs share `output_dir: outputs/norfolk_ssfha_comparison/`. Without namespacing, two configs with the same `sim_type` would produce colliding output paths. All workflow subdirs now live under `output_dir / fha_id /`, matching the master plan's Snakemake wildcard design.

```python
fha_dir = out / config.fha_id
return cls(
    output_dir=out,
    fha_dir=fha_dir,
    flood_probs_dir=fha_dir / "flood_probabilities",
    bootstrap_dir=fha_dir / "bootstrap",
    bootstrap_samples_dir=fha_dir / "bootstrap" / "samples",
    ...
)
```

### Decision 2: `bootstrap_quantiles` is user config, not a constant

`bootstrap_quantiles` is a required field on `UncertaintyConfig` — not hardcoded in `uncertainty.py` or `constants.py`. This allows different case studies to request different CI widths without code changes.

### Decision 3: Streaming combine via Dask

`combine_and_quantile` uses `xr.open_mfdataset(..., chunks="auto")` with Dask to open all sample zarrs lazily and compute quantiles without loading all samples into RAM simultaneously. `join="outer"` is set explicitly to handle samples with different `return_pd_yrs` lengths. Known risk: may be slow at full scale (500 samples × 550×550 grid); see `docs/planning/bugs/tech_debt_known_risks.md`.

### Decision 4: Bootstrap sample materialization before sorting

`da_sample.compute()` is called before `compute_return_period_indexed_depths` because `apply_ufunc` requires core dimensions (`event_iloc`) to be unchunked. Materializing at per-sample level is memory-safe (bounded by n_events × nx × ny floats per sample).

### Decision 5: No `--system-config` in bootstrap runners

Watershed mask is applied in Workflow 1. Bootstrap runners work on pre-masked `flood_probs` zarrs — no system config needed.

---

## Requirements

- Bootstrap runner (`bootstrap_runner.py`) must be independently invocable per `sample_id` — no shared state between samples.
- RNG seed = `base_seed + sample_id` (from `UncertaintyConfig.bootstrap_base_seed`). Each sample independently reproducible.
- Combine runner verifies all expected sample zarrs exist before combining; raises `DataError` listing missing paths.
- Inline NA check in combine runner; raises `DataError` if any NA values found.
- All runners log to stdout (Snakemake capture) with structured completion markers.

---

## Completion markers

- `bootstrap_runner.py`: `"COMPLETE: bootstrap_sample {sim_type} {sample_id:04d}"`
- `bootstrap_combine_runner.py`: `"COMPLETE: bootstrap_combine {sim_type}"`

---

## Test coverage

All 17 tests in `tests/test_workflow2_uncertainty.py` pass. Full suite: 199/199.

Key tests:
- `test_iloc_mapping_*` — validates Poisson event mapping builder
- `test_prepare_bootstrap_run_*` — validation and error cases
- `test_run_bootstrap_sample_*` — output schema, RNG independence, overwrite, missing inputs
- `test_combine_and_quantile_*` — output schema, NA check, missing sample detection, overwrite
- `test_bootstrap_runner_returns_zero_on_success` — runner exit code and completion marker
- `test_bootstrap_combine_runner_returns_zero_on_success` — combine runner exit code and marker

---

## Decision Log

### Decision 1: Output path namespacing — `fha_id` in `ProjectPaths`

See "Key Design Decisions" above.

**Impact**: `paths.py` and `tests/test_paths.py` updated. Existing `test_flood_hazard_workflow.py` tests use `tmp_path` as `output_dir` and `fha_id: synthetic_ssfha`, so output paths became `tmp_path/synthetic_ssfha/flood_probabilities/...` — tests updated.
