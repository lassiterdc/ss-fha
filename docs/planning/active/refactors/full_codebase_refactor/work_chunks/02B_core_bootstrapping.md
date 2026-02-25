# Work Chunk 02B: Core Bootstrapping Module

**Phase**: 2B — Core Computation (Bootstrapping)
**Last edited**: 2026-02-25

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`.prompts/philosphy.md`](../../../../../.prompts/philosphy.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: Work chunk 02A complete (`ss_fha.core.flood_probability` importable, since bootstrapping uses return period functions).

---

## Task Understanding

### Requirements

Extract and port the bootstrapping functions from `_old_code_to_refactor/__utils.py` into `src/ss_fha/core/bootstrapping.py`. Pure computation only — no I/O.

**Functions to migrate (verify exact names in `__utils.py`):**

- `prepare_for_bootstrapping()` — generates resampling index arrays
- `bootstrapping_return_period_estimates()` — computes return periods for a single bootstrap sample
- `combine_bootstrap_samples()` — stacks individual sample arrays along a new dimension
- `compute_bootstrap_quantiles()` — computes quantiles (0.05, 0.5, 0.95) across samples
- `check_for_na_in_combined_bs_zarr()` — validation function for combined output

### Key Design Decisions

- **This is the primary HPC parallelization target.** The design must accommodate Snakemake fan-out: each bootstrap sample is one rule invocation. `bootstrapping_return_period_estimates()` must be callable for a single sample by index (not all 500 at once).
- **No I/O**: `combine_bootstrap_samples()` receives already-loaded arrays, not paths.
- **`n_bootstrap_samples` and `sample_id` are always explicit arguments** — no defaults.
- **Reproducibility**: Bootstrap resampling must use a seeded RNG. The seed strategy (fixed global seed + sample_id offset, or per-run seed) should be decided here and documented.
- **Zero-event years must be included in resampling.** `n_years_synthesized` (from config) is the total number of synthetic years in the weather model run — 1000 for Norfolk. Only 954 of those years have ≥1 event and appear in `ds_sim_tseries.year`. The bootstrap year pool must be drawn from `np.arange(n_years_synthesized)` (all 1000), then intersected with the years present in the time series data. Years that are drawn but have no events correctly contribute zero events to that bootstrap sample. Using only the 954 years-with-events as the pool would shrink the effective denominator and systematically overstate return periods. This is a correctness-critical distinction — test it explicitly: a bootstrap sample that draws only event-free years should produce an all-NaN or all-zero result, not an error.
- **The same logic applies to observed return period calculations.** `n_years_observed` (from config) is the total length of the observed record, including any years with no events. For Norfolk all 18 observed years have events, but other case studies may not. `n_years_observed` must be passed explicitly as the denominator — never inferred from `len(obs_ds.year)`.

### Success Criteria

- `prepare_for_bootstrapping()` produces reproducible resampling indices for a given seed + sample_id
- `bootstrapping_return_period_estimates()` produces correct return period estimates for a single sample
- `compute_bootstrap_quantiles()` converges toward correct CI coverage with large sample count (statistical test)
- All `tests/test_bootstrapping.py` tests pass

---

## Evidence from Codebase

Before implementing, inspect:

1. `_old_code_to_refactor/__utils.py` — bootstrap functions
2. `_old_code_to_refactor/c1_fpm_confidence_intervals_bootstrapping.py` — how bootstrap is orchestrated
3. `_old_code_to_refactor/c1b_fpm_confidence_intervals_bootstrapping.py` — variant
4. `src/ss_fha/core/flood_probability.py` (02A) — `bootstrapping_return_period_estimates` will call flood probability functions

---

## Implementation Strategy

### Chosen Approach

Port the bootstrapping functions with seeded numpy RNG. Use `np.random.default_rng(seed=base_seed + sample_id)` pattern for reproducibility across parallel Snakemake runs. This ensures each sample is reproducible independently.

### Alternatives Considered

- **Single global seed**: Rejected — doesn't work for parallel execution where sample_id ordering may vary.
- **No seeding (non-reproducible)**: Rejected — scientific reproducibility is a requirement.

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/core/bootstrapping.py` | Ported bootstrap functions |
| `tests/test_bootstrapping.py` | Unit tests including CI coverage statistical test |

### Modified Files

| File | Change |
|------|--------|
| `_old_code_to_refactor/__utils.py` | Update refactoring status block |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| Bootstrap zarr files are multi-GB at full scale | Tests use 5 samples, 10x10 grid — never generate large data in tests |
| RNG seeding strategy affects reproducibility | Document seeding strategy in module docstring; test reproducibility explicitly |
| `check_for_na_in_combined_bs_zarr()` depends on zarr structure | Make this a pure function on xarray Dataset, not on zarr paths |
| Using wrong year pool shrinks denominator and biases return periods | Resample from `np.arange(n_years_synthesized)`, not from `ds.year.values`; test explicitly |

---

## Validation Plan

```bash
# Basic unit tests
pytest tests/test_bootstrapping.py -v

# Reproducibility: same seed + sample_id → same result
pytest tests/test_bootstrapping.py::test_bootstrap_reproducibility -v

# CI coverage: 95% CI should contain truth ~95% of the time
pytest tests/test_bootstrapping.py::test_ci_coverage_rate -v

# Import smoke test
python -c "from ss_fha.core.bootstrapping import prepare_for_bootstrapping; print('OK')"
```

---

## Documentation and Tracker Updates

- Update `full_codebase_refactor.md` tracking table: `__utils.py` — bootstrap functions migrated.
- Document the chosen RNG seeding strategy in a comment in `bootstrapping.py`.

---

## Definition of Done

- [ ] `src/ss_fha/core/bootstrapping.py` implemented with all five functions
- [ ] Seeded RNG with `base_seed + sample_id` pattern implemented and documented
- [ ] `bootstrapping_return_period_estimates()` callable for a single sample by index
- [ ] No I/O in any function
- [ ] All `tests/test_bootstrapping.py` tests pass
- [ ] Refactoring status block updated in `_old_code_to_refactor/__utils.py`
- [ ] `full_codebase_refactor.md` tracking table updated
- [ ] **Move this document to `implemented/` once all boxes above are checked**
