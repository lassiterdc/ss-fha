# Work Chunk 03B: Workflow 2 — Flood Hazard Uncertainty (Bootstrap CI)

**Phase**: 3B — Analysis Modules + Runner Scripts (Uncertainty)
**Last edited**: 2026-02-25

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/refactors/2026-02-25_full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`CONTRIBUTING.md`](../../../../CONTRIBUTING.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: Work chunks 03A complete (Workflow 1 outputs exist and are validated).

---

## Task Understanding

### Requirements

Implement Workflow 2 (Bootstrap Confidence Intervals) with a Snakemake fan-out/fan-in pattern. Each bootstrap sample is an independent Snakemake job. A combine step aggregates all samples and computes quantiles.

**Replaces**: `_old_code_to_refactor/c1_fpm_confidence_intervals_bootstrapping.py` and `c1b_fpm_confidence_intervals_bootstrapping.py`

**Files to create:**

1. `src/ss_fha/analysis/uncertainty.py` — orchestration module:
   - `prepare_bootstrap_run(config, paths)` — setup, validate inputs
   - `combine_and_quantile(config, paths, sim_type)` — post-processing step

2. `src/ss_fha/runners/bootstrap_runner.py` — single sample runner:
   - CLI args: `--config <yaml>`, `--sample-id <int>`, `--sim-type <str>`
   - Computes return periods for one bootstrap resample
   - Writes output to `bootstrap_samples_dir / f"{sim_type}_{sample_id:04d}.zarr"`
   - Logs completion marker

3. `src/ss_fha/runners/bootstrap_combine_runner.py` — combine step:
   - CLI args: `--config <yaml>`, `--sim-type <str>`
   - Reads all sample zarrs, combines, computes 0.05/0.5/0.95 quantiles
   - Writes combined CI zarr
   - Validates no missing samples (NA check)
   - Logs completion marker

### Key Design Decisions

- **Fan-out design**: Snakemake will invoke `bootstrap_runner.py` once per sample_id (0 to N-1). Each invocation must be fully independent — no shared state between samples.
- **`--sample-id` determines RNG seed** (see 02B: `base_seed + sample_id` pattern).
- **Memory budget**: A single sample zarr for 10x10 test grid is tiny; at full scale it may be hundreds of MB. The combine step must not load all samples into memory simultaneously — use streaming/chunked reading.
- **Completion verification**: The combine runner checks for NA values and logs the check result. Fail fast if any NAs are found.
- **`n_bootstrap_samples` from config** — no hardcoded values.

### Success Criteria

- `bootstrap_runner.py --sample-id 0` runs independently with synthetic data
- `bootstrap_combine_runner.py` correctly combines 5 synthetic samples (test case)
- Combined output has 0.05/0.5/0.95 quantile variables
- Integration test runs full Workflow 2 on synthetic test case

---

## Evidence from Codebase

Before implementing, inspect:

1. `_old_code_to_refactor/c1_fpm_confidence_intervals_bootstrapping.py`
2. `_old_code_to_refactor/c1b_fpm_confidence_intervals_bootstrapping.py`
3. `src/ss_fha/core/bootstrapping.py` (02B) — import from here
4. Runner script pattern from 03A

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/analysis/uncertainty.py` | Bootstrap orchestration |
| `src/ss_fha/runners/bootstrap_runner.py` | Single-sample CLI runner |
| `src/ss_fha/runners/bootstrap_combine_runner.py` | Combine + quantile CLI runner |
| (add tests to) `tests/test_end_to_end.py` | Workflow 2 integration test |

### Modified Files

| File | Change |
|------|--------|
| `_old_code_to_refactor/c1_*.py`, `c1b_*.py` | Add refactoring status blocks |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| Combine step loads all 500 samples at once — OOM | Use `xr.open_mfdataset` with dask, or stream-combine samples sequentially |
| Sample zarr missing (failed job) | Combine runner lists expected samples, fails with `DataError` listing which are missing |
| Partial NA values in combined output (sample computed OK but grid partially invalid) | `check_for_na_in_combined_bs_zarr()` from 02B; fail and log which samples have NAs |

---

## Validation Plan

```bash
# Single sample run
python -m ss_fha.runners.bootstrap_runner --config /tmp/ssfha_test/config.yaml --sample-id 0 --sim-type compound

# Combine (after running samples 0-4)
python -m ss_fha.runners.bootstrap_combine_runner --config /tmp/ssfha_test/config.yaml --sim-type compound

# Integration test
pytest tests/test_end_to_end.py::test_workflow2_uncertainty -v
```

---

## Documentation and Tracker Updates

- Update `full_codebase_refactor.md` tracking table: `c1_*`, `c1b_*` → `COMPLETE`.

---

## Definition of Done

- [ ] `src/ss_fha/analysis/uncertainty.py` implemented
- [ ] `src/ss_fha/runners/bootstrap_runner.py` — single sample, fully independent
- [ ] `src/ss_fha/runners/bootstrap_combine_runner.py` — streaming combine, NA validation
- [ ] All runners log structured completion markers
- [ ] Integration test passes with 5 synthetic samples
- [ ] `full_codebase_refactor.md` tracking table updated
- [ ] **Move this document to `../implemented/` once all boxes above are checked**
