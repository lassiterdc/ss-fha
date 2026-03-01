# Work Chunk 02B: Core Bootstrapping Module

**Phase**: 2B — Core Computation (Bootstrapping)
**Last edited**: 2026-02-26

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`CONTRIBUTING.md`](../../../../CONTRIBUTING.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: Work chunk 02A complete (`ss_fha.core.flood_probability` importable, since bootstrapping calls its return period functions).

---

## Task Understanding

### Requirements

Port the pure computation pieces of the bootstrapping workflow from `_old_code_to_refactor/__utils.py` and `_old_code_to_refactor/c1_fpm_confidence_intervals_bootstrapping.py` into `src/ss_fha/core/bootstrapping.py`.

**Scope of this chunk (single-sample computation only):**

| New function | Source | Purpose |
|---|---|---|
| `draw_bootstrap_years(n_years_synthesized, base_seed, sample_id)` | New (replaces unseeded `np.random.choice` in `c1`) | Draw `n_years_synthesized` years with replacement from `np.arange(n_years_synthesized)` using seeded RNG |
| `assemble_bootstrap_sample(resampled_years, years_with_events, event_iloc_mapping, da_flood_probs)` | Core of `bootstrapping_return_period_estimates` (I/O stripped) | Filter resampled years to those with events, reassign sequential event_iloc values, return stacked DataArray |
| `compute_return_period_indexed_depths(da_stacked, alpha, beta, n_years)` | Core of `bootstrapping_return_period_estimates` (I/O stripped) | Sort flood depths along event_number and assign return period coordinate |
| `sort_last_dim(arr)` | `__utils.py` line 1008 | Helper: `np.sort(arr, axis=-1)` — used internally by `compute_return_period_indexed_depths` |

**Deferred to Phase 3B runner (`runners/bootstrap_runner.py`):**
- Combining many per-sample zarr files into one dataset — `write_bootstrapped_samples_to_single_zarr` in old code
- Computing quantile CIs across samples — inline `xr.DataArray.quantile()` call in `c1b`
- Post-combine NaN QA check — derived from `check_for_na_in_combined_bs_zarr` in old code

The Phase 3B planning document must make it explicit that these combining/aggregation steps are runner responsibilities and are NOT part of `core/bootstrapping.py`.

### Key Design Decisions

- **Scope boundary**: This chunk covers only what is needed to process *one* bootstrap sample. Combining N samples, computing CIs, and QA-checking the combined output are Phase 3B runner concerns.
- **Snakemake fan-out target**: `draw_bootstrap_years` + `assemble_bootstrap_sample` + `compute_return_period_indexed_depths` together constitute one Snakemake rule invocation per `sample_id`. Each job is fully independent.
- **No I/O**: All functions receive already-loaded xarray/numpy objects. The runner layer handles reading the base flood probability dataset and writing per-sample zarr outputs.
- **No defaults on any argument** (per philosophy.md). `base_seed`, `sample_id`, `alpha`, `beta`, `n_years` are all required.
- **Seeded RNG**: Use `np.random.default_rng(seed=base_seed + sample_id)`. `base_seed` is a required argument (also a `SsfhaConfig` field to facilitate run-level reproducibility). This pattern ensures each sample is reproducible independently, which is necessary for Snakemake fan-out where sample ordering varies.
- **Year pool correctness (critical)**: Draw from `np.arange(n_years_synthesized)` (all synthetic years, including event-free ones), not from the years present in the dataset. Years drawn that have no events contribute zero events to the bootstrap sample. Using only years-with-events as the pool shrinks the effective denominator and systematically overstates return periods. Test this explicitly.
- **NaN is always an error**: The base flood probability dataset uses 0.0 for dry gridcells, not NaN. If NaN values appear in an assembled bootstrap sample, `assemble_bootstrap_sample` must raise `SSFHAError` immediately. Error message must prompt investigation: *"NaN values found in bootstrap sample {sample_id}. If your model outputs NaN for dry gridcells, convert to 0.0 before calling this function. If NaN values are unexpected, this may indicate missing events or corrupted input data — please investigate before proceeding."*
- **`base_seed` in config**: Add `bootstrap_base_seed: int` as a required field within the uncertainty block of `SsfhaConfig`. No sensitivity analysis on the seed is anticipated; the field exists purely for reproducibility documentation.

### Success Criteria

- `draw_bootstrap_years` produces reproducible year arrays for a given `base_seed + sample_id`
- `assemble_bootstrap_sample` correctly includes event-free years (zero-event contribution) from the full `n_years_synthesized` pool
- `compute_return_period_indexed_depths` produces return-period-indexed depths that match direct application of `calculate_positions` + `calculate_return_period` from `core/flood_probability`
- NaN in assembled sample raises `SSFHAError` with diagnostic message
- All `tests/test_bootstrapping.py` tests pass

---

## Evidence from Codebase

Inspected before implementation:

1. `_old_code_to_refactor/__utils.py` lines 1008–1299 — `sort_last_dim`, `check_for_na_in_combined_bs_zarr`, `prepare_for_bootstrapping`, `bootstrapping_return_period_estimates`
2. `_old_code_to_refactor/c1_fpm_confidence_intervals_bootstrapping.py` — bootstrap orchestration loop, year resampling pattern
3. `_old_code_to_refactor/c1b_fpm_confidence_intervals_bootstrapping.py` — combine and quantile steps (deferred to Phase 3B)
4. `src/ss_fha/core/flood_probability.py` (02A) — `calculate_positions`, `calculate_return_period` called internally

**Key finding from inspection**: `bootstrapping_return_period_estimates` is deeply I/O-coupled (writes 2 temp zarrs + 1 output zarr, returns None). The pure computation kernel is extractable but requires restructuring. `combine_bootstrap_samples` and `compute_bootstrap_quantiles` do not exist as named functions in `__utils.py` — they are inline logic in `c1b`. The original plan's function list was inaccurate.

---

## Implementation Strategy

### Chosen Approach

Extract the pure computation kernel from `bootstrapping_return_period_estimates`, restructure as three composable functions, add seeded RNG via `np.random.default_rng`. Each function is independently testable and together they constitute one complete bootstrap sample computation.

### Alternatives Considered

- **Single global seed**: Rejected — doesn't work for parallel execution where sample_id ordering may vary.
- **Port `bootstrapping_return_period_estimates` with I/O intact**: Rejected — violates no-I/O philosophy and couples the core to file paths.
- **Defer entire 02B until runner architecture is clearer**: Rejected — the pure computation kernel is well-defined and testable independently.

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/core/bootstrapping.py` | Four functions: `draw_bootstrap_years`, `assemble_bootstrap_sample`, `compute_return_period_indexed_depths`, `sort_last_dim` |
| `tests/test_bootstrapping.py` | Unit tests including reproducibility, year-pool correctness, NaN guard, return period accuracy |

### Modified Files

| File | Change |
|------|--------|
| `_old_code_to_refactor/__utils.py` | Update refactoring status block |
| `src/ss_fha/config/model.py` | Add `bootstrap_base_seed: int` to uncertainty config block |
| `docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md` | Update Phase 2B description and tracking table |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| A bootstrap sample that draws only event-free years produces empty stacked DataArray | Handle gracefully: return empty DataArray with correct dims, or raise with clear message — decide during implementation |
| NaN in assembled sample | Fail-fast with `SSFHAError` and diagnostic message (see Key Design Decisions) |
| `base_seed + sample_id` integer overflow for large sample_id | Use `int(base_seed) + int(sample_id)` — numpy RNG accepts arbitrarily large seeds |
| Return period coordinate quantization (old code rounds to 0.5yr intervals to save disk space) | Do NOT quantize in this function — quantization is a storage concern for the runner layer |

---

## Validation Plan

```bash
# Basic unit tests
pytest tests/test_bootstrapping.py -v

# Reproducibility
pytest tests/test_bootstrapping.py::TestDrawBootstrapYears::test_reproducibility -v

# Year pool correctness: event-free years included
pytest tests/test_bootstrapping.py::TestAssembleBootstrapSample::test_event_free_years_included -v

# NaN guard
pytest tests/test_bootstrapping.py::TestAssembleBootstrapSample::test_nan_raises -v

# Return period accuracy
pytest tests/test_bootstrapping.py::TestComputeReturnPeriodIndexedDepths::test_matches_flood_probability_functions -v

# Import smoke test
python -c "from ss_fha.core.bootstrapping import draw_bootstrap_years, assemble_bootstrap_sample, compute_return_period_indexed_depths; print('OK')"
```

---

## Documentation and Tracker Updates

- Update `full_codebase_refactor.md` tracking table: `__utils.py` — bootstrap functions migrated (partial).
- Update Phase 2B and Phase 3B descriptions in master plan to clarify scope boundary.
- Document RNG seeding strategy in `bootstrapping.py` module docstring.

---

## Definition of Done

- [x] `src/ss_fha/core/bootstrapping.py` implemented with four functions
- [x] Seeded RNG with `base_seed + sample_id` pattern implemented and documented
- [x] `draw_bootstrap_years` samples from `np.arange(n_years_synthesized)` (not from dataset years)
- [x] `assemble_bootstrap_sample` raises `SSFHAError` on NaN with diagnostic message
- [x] No I/O in any function
- [x] `bootstrap_base_seed` added to `SsfhaConfig` uncertainty block (as part of `UncertaintyConfig` which also includes `n_bootstrap_samples`)
- [x] All `tests/test_bootstrapping.py` tests pass (26 tests; 127 total)
- [x] Refactoring status block updated in `_old_code_to_refactor/__utils.py`
- [x] `full_codebase_refactor.md` tracking table and Phase 2B/3B descriptions updated
- [x] `event_number` → `event_iloc` rename applied throughout; vocabulary entry added to `CLAUDE.md` Terminology section
- [x] Moved to `../implemented/`
