# Work Chunk 02A: Core Flood Probability Module

**Phase**: 2A — Core Computation (Flood Probability)
**Last edited**: 2026-02-25

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`.prompts/philosphy.md`](../../../../../.prompts/philosphy.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: All Phase 1 work chunks complete (01A–01G).

---

## Task Understanding

### Requirements

Extract and port the flood probability computation functions from `_old_code_to_refactor/__utils.py` into `src/ss_fha/core/flood_probability.py`. These are **pure computation functions** — no I/O, no file operations, no side effects.

**Functions to migrate (verified in `__utils.py`):**

- `compute_emp_cdf_and_return_pds()` — empirical CDF + return period computation across the spatial grid
- `calculate_positions()` — plotting positions via `scipy.stats.mstats.plotting_positions(alpha, beta)`
- `calculate_return_period()` — convert plotting position to return period
- `sort_dimensions()` — xarray dimension ordering utility → goes in `src/ss_fha/core/utils.py` (not flood_probability.py)

**Deferred (not in this chunk):**
- `compute_return_periods_for_series()` — 1D series wrapper; needed only for univariate event-level analysis (Phase 2+), not for the gridded spatial CDF pipeline

### Key Design Decisions

- **No defaults on arguments** (per philosophy.md). All arguments — including `alpha`, `beta`, `fillna_val`, and `n_years` — must be passed explicitly at every call site.
- **`alpha` and `beta` floats** are the plotting position interface (passed directly to `scipy.stats.mstats.plotting_positions`). Config field descriptions must document named method equivalents (e.g., Weibull = alpha=0, beta=0; Cunnane = alpha=0.4, beta=0.4) and refer users to scipy docs. Do not use a method string enum.
- **No I/O**: Strip all file export, zarr writes, benchmarking prints, and qaqc_plots from ported functions. The function signature receives already-loaded xarray objects.
- **`sys.exit()` → `SSFHAError`**: Old code uses `sys.exit()` when NaNs present in `calculate_positions`. Replaced with `raise SSFHAError(...)`. (`DataError` was not used because its signature requires a `filepath`, which is inappropriate for a pure computation validation failure.)
- **Mathematical correctness is critical** — this is a probability codebase. Before accepting any function port, validate against hand-computed examples or scipy/numpy reference implementations.
- **`eCDF_stendinger` and `eCDF_wasserman` are validation artifacts** in the old code — not to be ported. They confirmed scipy's `plotting_positions` was giving expected results.

### Success Criteria

- All functions importable from `ss_fha.core.flood_probability`
- Unit tests validate return period computation against hand-computed and scipy reference values
- Tests validate both alpha=0/beta=0 (Weibull) and alpha=0.4/beta=0.4 (Cunnane) against analytical distributions with known CDF
- Zero I/O in any function

---

## Evidence from Codebase

Before implementing, inspect:

1. `_old_code_to_refactor/__utils.py` — locate all five target functions; read their full implementations before porting
2. `_old_code_to_refactor/b1_analyze_triton_outputs_fld_prob_calcs.py` — see how these functions are called in context
3. `src/ss_fha/config/defaults.py` (01A) — `DEFAULT_PLOTTING_POSITION_METHOD` and `DEFAULT_RETURN_PERIODS` are available but should NOT be used as function defaults

---

## Implementation Strategy

### Chosen Approach

Read each function in `__utils.py`, strip any I/O, add type annotations, then write the ported version. Do not refactor the algorithm — port first, then test, then refactor only if the tests reveal issues.

### Alternatives Considered

- **Refactor while porting**: Rejected — increases risk of introducing mathematical errors; port faithfully first.
- **Wrap old code**: Rejected — the goal is clean, testable module functions, not wrappers.

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/core/__init__.py` | Package stub |
| `src/ss_fha/core/flood_probability.py` | `calculate_positions`, `calculate_return_period`, `compute_emp_cdf_and_return_pds` |
| `src/ss_fha/core/utils.py` | `sort_dimensions` (generic xarray utility; also added to utility_package_candidates.md) |
| `tests/test_flood_probability.py` | Unit tests including scipy reference validation |

### Modified Files

| File | Change |
|------|--------|
| `_old_code_to_refactor/__utils.py` | Update refactoring status block to note migrated functions |
| `docs/planning/utility_package_candidates.md` | Add `sort_dimensions` as candidate |
| `docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md` | Update tracking table for migrated functions |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| Mathematical errors introduced during porting | Test against scipy `stats.expon.cdf` or similar analytical distribution with known return periods |
| Different alpha/beta values produce subtly different results | Test with alpha=0/beta=0 (Weibull) and alpha=0.4/beta=0.4 (Cunnane); assert they differ by known amounts for a given dataset |
| `sort_dimensions()` is a utility — may not belong in `flood_probability.py` | If it's genuinely general-purpose, put it in a `core/utils.py` module instead |
| Old function may mix return period computation with plotting | Strip plotting; plotting belongs in `visualization/` (Phase 5) |

---

## Validation Plan

```bash
# Run unit tests
pytest tests/test_flood_probability.py -v

# Numerical validation against scipy
pytest tests/test_flood_probability.py::test_return_periods_match_scipy -v

# Both plotting position methods
pytest tests/test_flood_probability.py::test_weibull_positions -v
pytest tests/test_flood_probability.py::test_stendinger_positions -v

# Import smoke test
python -c "from ss_fha.core.flood_probability import compute_emp_cdf_and_return_pds; print('OK')"
```

---

## Documentation and Tracker Updates

- Update `full_codebase_refactor.md` tracking table: `__utils.py` — mark flood probability functions as migrated.
- Add refactoring status block to `_old_code_to_refactor/__utils.py` if not already added in 01D.

---

## Definition of Done

- [ ] `src/ss_fha/core/__init__.py` created
- [ ] `src/ss_fha/core/utils.py` created with `sort_dimensions`
- [ ] `src/ss_fha/core/flood_probability.py` implemented with three functions (`calculate_positions`, `calculate_return_period`, `compute_emp_cdf_and_return_pds`)
- [ ] No I/O in any function (verified by code review)
- [ ] No default argument values on any function except obvious flags like `verbose`
- [ ] Unit tests validate against scipy/numpy reference implementations
- [ ] Tests cover alpha=0/beta=0 (Weibull) and alpha=0.4/beta=0.4 (Cunnane) variants
- [ ] `docs/planning/utility_package_candidates.md` updated with `sort_dimensions`
- [ ] Refactoring status block updated in `_old_code_to_refactor/__utils.py`
- [ ] `full_codebase_refactor.md` tracking table updated
- [ ] **Move this document to `../implemented/` once all boxes above are checked**
