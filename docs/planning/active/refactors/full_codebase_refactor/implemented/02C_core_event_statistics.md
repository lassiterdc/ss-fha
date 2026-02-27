# Work Chunk 02C: Core Event Statistics Module

**Phase**: 2C — Core Computation (Event Statistics)
**Last edited**: 2026-02-26

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`.prompts/philosphy.md`](../../../../../.prompts/philosphy.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: Work chunks 02A and 02B complete.

---

## Task Understanding

### Requirements

Extract and port the event statistics functions from `_old_code_to_refactor/__utils.py` into `src/ss_fha/core/event_statistics.py`. Pure computation only — no I/O.

**Functions to migrate** (all found in `_old_code_to_refactor/__utils.py`):

| Old function | New name / location | Notes |
|---|---|---|
| `compute_return_periods()` + `compute_return_periods_for_series()` | `_compute_return_periods_for_series()` | Private helper; calls `calculate_positions` / `calculate_return_period` from `flood_probability.py` |
| `compute_univariate_event_return_periods()` | `compute_univariate_event_return_periods()` | Parameterize all globals; use `weather_event_indices` for subsetting |
| `compute_AND_multivar_return_period_for_sample()` | `_compute_AND_multivar_return_period_for_sample()` | Private reference implementation; port docstring from `_work/figuring_out_multivariate_return_periods.py` verbatim |
| `compute_OR_multivar_return_period_for_sample()` | `_compute_OR_multivar_return_period_for_sample()` | Same |
| `empirical_multivariate_return_periods()` (apply-based) | `_empirical_multivariate_return_periods_reference()` | Private; slow; kept only for validation against vectorized version |
| `empirical_multivariate_return_periods()` | `empirical_multivariate_return_periods()` | **New vectorized numpy implementation**; must match reference exactly |
| `compute_all_multivariate_return_period_combinations()` | `compute_all_multivariate_return_period_combinations()` | Remove hardcoded surge-only constraint; compute all bi- and tri-variate combinations |
| `bs_samp_of_univar_event_return_period()` | `bs_samp_of_univar_event_return_period()` | Parameterize all globals |
| `bs_samp_of_multivar_event_return_period()` | `bs_samp_of_multivar_event_return_period()` | Parameterize all globals |
| `analyze_bootstrapped_samples()` | `analyze_bootstrapped_samples()` | Orchestration-adjacent but pure computation; no file I/O |
| `return_df_of_evens_within_ci_including_event_stats()` | `return_df_of_events_within_ci()` | Typo fixed in name; pure computation |

**Functions explicitly NOT migrated here** (runner layer, not pure computation):
- `prepare_for_bootstrapping()` — file system / resume logic → runner
- `bootstrapping_return_period_estimates()` — orchestration loop → runner
- `write_bootstrapped_samples_to_single_zarr()` — I/O → runner
- `check_for_na_in_combined_bs_zarr()` — I/O → runner

---

### Key Design Decisions

#### Weather event indexers — never hardcode `event_type`, `year`, `event_id`

All subsetting of weather time series must use `weather_event_indices: list[str]` (a new field on `SsfhaConfig`). The old code hardcodes `event_type`, `year`, `event_id` throughout — **replace every instance** with the user-supplied index names.

Validation rules for `weather_event_indices`:
- `"year"` is always required (used for bootstrap year resampling and exceedance probability denominators). Common aliases (`"yr"`, `"y"`) are accepted; the actual string is used as-is for subsetting (no normalization). Accepted aliases are defined in `WEATHER_EVENT_INDEX_YEAR_ALIASES` in `src/ss_fha/constants.py`.
- `"event_iloc"` is supported as the sole indexer for datasets already indexed by flat integer (skip the iloc-mapping join in that case).
- All entries must match column names in `sim_event_iloc_mapping` CSV and dimensions in `sim_event_timeseries` NetCDF — validated at config load time (not here).

#### `event_iloc` vs. multi-index

For spatial gridded data (zarrs): `event_iloc` is the canonical dimension (established in 02A/02B).

For tabular event statistics (this module): the multi-index defined by `weather_event_indices` (e.g., `(event_type, year, event_id)`) is the natural form and is what downstream bootstrap code uses. These two representations are bridged by the `sim_event_iloc_mapping` CSV, which the runner layer manages. Functions in this module receive DataFrames already indexed by the multi-index.

#### `ASSIGN_DUP_VALS_MAX_RETURN` — constant in `constants.py`

```python
# constants.py
# When True, events with identical statistic values are all assigned the
# maximum return period of their group rather than progressively increasing
# CDF values. Always False in Norfolk. The semantically correct choice for
# other case studies is unresolved. Promote to SsfhaConfig when resolved.
ASSIGN_DUP_VALS_MAX_RETURN: bool = False
```

> **Deviation from original plan**: The plan specified a private module-level constant (`_ASSIGN_DUP_VALS_MAX_RETURN`) in `event_statistics.py`. Per `philosophy.md`, all module-level constants belong in `constants.py`. It is therefore defined there as a public constant and imported by `event_statistics.py`.

Do not expose as a function argument or config field. Every call site in the old code uses the same global (always `False`); this is never varied.

#### Multivariate return period math — AND vs. OR semantics

Port the docstrings from `_work/figuring_out_multivariate_return_periods.py` verbatim into `_compute_AND_multivar_return_period_for_sample()` and `_compute_OR_multivar_return_period_for_sample()`. The math is correct and the docstrings make the complement-space inversion explicit:

- **AND exceedance**: E_AND = {X1 > z1 AND X2 > z2} — both drivers simultaneously exceed. F_AND uses `.any()` (OR logic in complement space). F_AND ≥ F_OR ⟹ RP_AND ≥ RP_OR.
- **OR exceedance**: E_OR = {X1 > z1 OR X2 > z2} — at least one driver exceeds. F_OR uses `.all()` (AND logic in complement space). RP_OR ≤ RP_AND.

The math at first glance can be counterintuitive; the docstrings are the guard against future confusion.

#### Vectorized multivariate implementation

The `apply()`-based reference implementation is O(n²) in Python function call overhead. Replace with a vectorized numpy broadcast:

```python
# comparisons[i, j, v] = True if df.values[j, v] <= df.values[i, v]
comparisons = df.values[np.newaxis, :, :] <= df.values[:, np.newaxis, :]  # (n, n, vars)
and_counts = comparisons.any(axis=2).sum(axis=1)  # F_AND: any var of j <= i
or_counts  = comparisons.all(axis=2).sum(axis=1)  # F_OR:  all vars of j <= i
```

Memory note: O(n² × n_vars) booleans. At n=1000, 3 vars: ~3 MB — fine. At n=10,000: ~3 GB — add a comment flagging this threshold.

**Test requirements:**
1. Exact match between vectorized and reference outputs (assert `np.allclose`, tolerance 1e-12).
2. Benchmark: assert vectorized is at least 10× faster than reference. Use `time.perf_counter()`. If speedup is ≥ 10× but < 50×, add a note suggesting further optimization if bootstrap runtime is still unacceptable.
3. Test comment: "Discrepancies may indicate a bug in the reference implementation, not the vectorized one — the reference was ported directly from old code and was never independently validated mathematically."

#### Multivariate combinations — no hardcoded surge constraint

The old code forced all combinations to include max water level as one variable. This was research-specific. The new code computes **all** bi- and tri-variate combinations of whatever event statistics are computed, with no constraint on which variables must be included.

#### `n_years` is always explicit

The old code reads `N_YEARS_SYNTHESIZED` from a global. Every function that needs `n_years` receives it as an explicit argument with no default.

#### Config fields added to `SsfhaConfig`

Two new fields, both required when `is_comparative_analysis: false` and `fha_approach: ssfha`:

```yaml
weather_event_indices: [event_type, year, event_id]

event_statistic_variables:
  precip_intensity:             # required
    variable_name: mm_per_hr
    units: mm_per_hr
    max_intensity_windows_min: [5, 30, 60, 1440]
  boundary_stage:               # optional — omit for rain-only analyses
    variable_name: waterlevel_m
    units: m
    max_intensity_windows_min: [360, 1440]   # list OR null (null = simple max over all timesteps)
```

The Pydantic sub-models:

```python
class EventStatisticVariableConfig(BaseModel):
    variable_name: str
    units: str
    max_intensity_windows_min: list[int] | None  # None = simple max; no default

class EventStatisticsConfig(BaseModel):
    precip_intensity: EventStatisticVariableConfig
    boundary_stage: EventStatisticVariableConfig | None = None
```

`EventStatisticsConfig` is a new field on `SsfhaConfig`. The field name in Python matches the YAML key:
```python
event_statistic_variables: EventStatisticsConfig | None = None
```

> **Deviation from original plan**: The field was named `event_statistics` in the plan but implemented as `event_statistic_variables` to match the YAML key exactly and avoid ambiguity with the broader concept of "event statistics."

Validator on `SsfhaConfig`: if `is_comparative_analysis=False` and `fha_approach="ssfha"`, `event_statistic_variables` and `weather_event_indices` are required.

#### `is_comparative_analysis` toggle

```python
is_comparative_analysis: bool = False
```

When `True`, validator raises `ConfigurationError` if any of the following are present: `event_statistics`, `alt_fha_analyses` (non-empty), `toggle_mcds=True`. Comparative analysis configs are intentionally minimal.

---

### Success Criteria

- Univariate return periods match known-good values from old scripts
- Vectorized multivariate implementation matches reference exactly (np.allclose, 1e-12) and is ≥10× faster
- `weather_event_indices` used everywhere time series are subset; no hardcoded `event_type/year/event_id`
- All new config fields validate correctly; comparative analysis validation raises on forbidden fields
- Tests pass

---

## Evidence from Codebase

Before implementing, inspect:

1. `_old_code_to_refactor/__utils.py` — all functions listed in the migration table above
2. `_old_code_to_refactor/d0_computing_event_statistic_probabilities.py` — usage context
3. `_work/figuring_out_multivariate_return_periods.py` — AND/OR docstrings to port verbatim
4. `src/ss_fha/core/flood_probability.py` (02A) — `calculate_positions`, `calculate_return_period` to reuse
5. `src/ss_fha/config/model.py` — current `SsfhaConfig`; add new fields here

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/core/event_statistics.py` | All ported functions; vectorized multivariate implementation |
| `tests/test_event_statistics.py` | Unit tests with pre-computed reference values + benchmark |

### Modified Files

| File | Change |
|------|--------|
| `src/ss_fha/config/model.py` | Add `EventStatisticVariableConfig`, `EventStatisticsConfig`; add `weather_event_indices`, `event_statistics`, `is_comparative_analysis` to `SsfhaConfig`; update `validate_toggle_dependencies` |
| `cases/norfolk_ssfha_comparison/analysis_ssfha_combined.yaml` | Add `weather_event_indices` and `event_statistic_variables` sections |
| `cases/norfolk_ssfha_comparison/analysis_ssfha_rainonly.yaml` | Add `is_comparative_analysis: true` |
| `cases/norfolk_ssfha_comparison/analysis_ssfha_surgeonly.yaml` | Add `is_comparative_analysis: true` |
| `cases/norfolk_ssfha_comparison/analysis_ssfha_triton_only_combined.yaml` | Add `is_comparative_analysis: true` |
| `cases/norfolk_ssfha_comparison/analysis_bds_combined.yaml` | No change needed (`BdsConfig` is unaffected) |
| `cases/norfolk_ssfha_comparison/analysis_bds_rainonly.yaml` | No change needed |
| `cases/norfolk_ssfha_comparison/analysis_bds_surgeonly.yaml` | No change needed |
| `_old_code_to_refactor/__utils.py` | Update refactoring status block |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| AND/OR semantics are counterintuitive (complement-space inversion) | Port docstrings from `_work/figuring_out_multivariate_return_periods.py` verbatim; include sanity-check assertions in tests (RP_AND ≥ RP_OR for all events) |
| Vectorized implementation may differ from reference due to floating-point order | Test with `np.allclose(rtol=1e-12)`; if discrepancy exists, investigate reference first |
| `weather_event_indices` aliases (`yr`, `y`) not normalized | Normalization dropped — dynamic lookup via `WEATHER_EVENT_INDEX_YEAR_ALIASES` (constants.py) is cleaner; alias is preserved as-is for subsetting |
| `event_iloc`-only indexed data breaks multi-index assumptions | Check for `event_iloc` as sole indexer; skip iloc-mapping join in that path |
| Memory blow-up for large n in vectorized multivariate | Add comment: "n > ~5000 events will exceed 1 GB memory for 3-variable combinations; consider chunked implementation if this is encountered" |
| `n_years` was hardcoded in old code | Search for `N_YEARS_SYNTHESIZED` in all ported functions; replace with explicit argument |

---

## Validation Plan

```bash
pytest tests/test_event_statistics.py -v
pytest tests/test_event_statistics.py::test_univariate_return_periods_known_values -v
pytest tests/test_event_statistics.py::test_multivariate_reference_vs_vectorized -v
pytest tests/test_event_statistics.py::test_vectorized_speedup -v
pytest tests/test_event_statistics.py::test_and_rp_ge_or_rp -v
pytest tests/test_event_statistics.py::test_comparative_analysis_validation -v
```

---

## Documentation and Tracker Updates

- Update `full_codebase_refactor.md` tracking table: event statistics functions migrated.
- Update `_old_code_to_refactor/__utils.py` refactoring status block.

---

## Definition of Done

- [x] `src/ss_fha/core/event_statistics.py` implemented with all functions from migration table
- [x] `ASSIGN_DUP_VALS_MAX_RETURN = False` in `constants.py` with explanatory comment (not a private module constant — see deviation note above)
- [x] AND/OR docstrings ported verbatim from `_work/figuring_out_multivariate_return_periods.py`
- [x] Vectorized `empirical_multivariate_return_periods()` matches reference to 1e-12
- [x] Vectorized implementation is ≥10× faster than reference (asserted in test)
- [x] `weather_event_indices` used for all time series subsetting; no hardcoded index names
- [x] `n_years` is an explicit argument with no default on all functions that use it
- [x] `EventStatisticsConfig`, `weather_event_indices`, `is_comparative_analysis` added to `model.py`
- [x] Comparative analysis YAMLs updated with `is_comparative_analysis: true`
- [x] Primary analysis YAML updated with `weather_event_indices` and `event_statistic_variables`
- [x] All tests pass
- [x] Refactoring status block updated in `_old_code_to_refactor/__utils.py`
- [x] `full_codebase_refactor.md` tracking table updated
- [x] **Move this document to `../implemented/` once all boxes above are checked**