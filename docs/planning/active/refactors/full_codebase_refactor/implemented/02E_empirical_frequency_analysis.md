# Work Chunk 02E: Extract `core/empirical_frequency_analysis.py`

**Phase**: 2E — Core Computation (Empirical Frequency Primitives)
**Last edited**: 2026-02-26

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`.prompts/philosphy.md`](../../../../../.prompts/philosphy.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: Work chunks 02A, 02C, and 02D complete.

---

## Task Understanding

### Purpose

Three functions currently housed in `flood_probability.py` and `event_statistics.py`
have **zero flood-domain knowledge** and belong in a shared
`empirical_frequency_analysis.py` module:

| Function | Current home | Why it's domain-agnostic |
|---|---|---|
| `calculate_positions()` | `flood_probability.py` | Computes empirical CDF plotting positions from any 1-D numeric array via the Hazen family formula. No flood, no hydrology. |
| `calculate_return_period()` | `flood_probability.py` | Converts plotting positions to return periods given an event rate. Purely arithmetic. |
| `_compute_return_periods_for_series()` | `event_statistics.py` | Sorts a `pd.Series`, calls `calculate_positions` + `calculate_return_period`, and assembles an output DataFrame with CDF and return period columns. The only coupling to project context is reading `ASSIGN_DUP_VALS_MAX_RETURN` from constants — which is eliminated by making it an explicit argument. |

Moving all three into a dedicated module:

1. Removes conceptual mis-placement — `flood_probability` and `event_statistics`
   are domain-specific; these primitives are not.
2. Fixes a code smell: `geospatial.py` currently imports
   `_compute_return_periods_for_series` from `event_statistics` — a
   cross-module call to a private function. Making it public in
   `empirical_frequency_analysis` removes the `_` prefix and makes the
   dependency explicit.
3. Cleans up the dependency graph:
   - `flood_probability` → `empirical_frequency_analysis`
   - `event_statistics` → `empirical_frequency_analysis`
   - `geospatial` → `empirical_frequency_analysis`
4. Supports future extraction into a shared utility package (all three functions
   are domain-agnostic; add them to `utility_package_candidates.md` as part of
   this chunk).

This is a **pure internal refactor** — no new functionality. The only
user-visible changes are import paths and the removal of the `_` prefix on
`compute_return_periods_for_series`.

---

### Scope

#### Functions to move

| Current location | Current name | New location | New name | Signature change? |
|---|---|---|---|---|
| `src/ss_fha/core/flood_probability.py` | `calculate_positions()` | `src/ss_fha/core/empirical_frequency_analysis.py` | `calculate_positions()` | None |
| `src/ss_fha/core/flood_probability.py` | `calculate_return_period()` | `src/ss_fha/core/empirical_frequency_analysis.py` | `calculate_return_period()` | None |
| `src/ss_fha/core/event_statistics.py` | `_compute_return_periods_for_series()` | `src/ss_fha/core/empirical_frequency_analysis.py` | `compute_return_periods_for_series()` | `assign_dup_vals_max_return: bool` added as explicit required argument (replaces implicit read of `ASSIGN_DUP_VALS_MAX_RETURN` constant) |

#### Signature change detail for `compute_return_periods_for_series`

Old signature (private, in `event_statistics.py`):
```python
def _compute_return_periods_for_series(
    s: pd.Series,
    n_years: int,
    alpha: float,
    beta: float,
    varname: str | None = None,
) -> pd.DataFrame:
```

New signature (public, in `empirical_frequency_analysis.py`):
```python
def compute_return_periods_for_series(
    s: pd.Series,
    n_years: int,
    alpha: float,
    beta: float,
    assign_dup_vals_max_return: bool,
    varname: str | None = None,
) -> pd.DataFrame:
```

`assign_dup_vals_max_return` is a required argument (no default), per the
project philosophy. Callers pass `ASSIGN_DUP_VALS_MAX_RETURN` from
`ss_fha.constants` explicitly — this makes the constant usage visible at the
call site rather than hidden inside the function.

Note: `varname` retains `None` as a default because it is a convenience
parameter with a well-defined fallback (`s.name`) that is almost always correct.
This is the kind of default the philosophy permits.

#### Import sites to update

| File | Change |
|---|---|
| `src/ss_fha/core/flood_probability.py` | Remove definitions of `calculate_positions`, `calculate_return_period`; add `from ss_fha.core.empirical_frequency_analysis import calculate_positions, calculate_return_period`; remove `from scipy.stats.mstats import plotting_positions` (no longer used in this file) |
| `src/ss_fha/core/event_statistics.py` | Remove definition of `_compute_return_periods_for_series`; update import line to `from ss_fha.core.empirical_frequency_analysis import calculate_return_period, compute_return_periods_for_series` (note: `calculate_positions` is only used inside the moved function and is no longer needed here); update all internal call sites to use the new name (drop `_` prefix) and pass `assign_dup_vals_max_return=ASSIGN_DUP_VALS_MAX_RETURN`; update module docstring (line 11) to reference `empirical_frequency_analysis` instead of `flood_probability` |
| `src/ss_fha/core/geospatial.py` | Replace the lazy import `from ss_fha.core.event_statistics import _compute_return_periods_for_series` (inside function body) with a **top-level** `from ss_fha.core.empirical_frequency_analysis import compute_return_periods_for_series`; add top-level `from ss_fha.constants import ASSIGN_DUP_VALS_MAX_RETURN`; update call site to pass `assign_dup_vals_max_return=ASSIGN_DUP_VALS_MAX_RETURN` |
| `tests/test_flood_probability.py` | Update imports for `calculate_positions` and `calculate_return_period` to come from `ss_fha.core.empirical_frequency_analysis` (not `flood_probability`). These are still needed in `TestComputeEmpCdfAndReturnPds.test_matches_lower_level_functions` as reference values — the import source changes but the tests are not removed. |

**Do not add re-exports** to `flood_probability.py` or `event_statistics.py`.
The philosophy forbids aliases and backward-compatibility shims.

#### Internal call sites for `_compute_return_periods_for_series` in `event_statistics.py`

There are two call sites in `event_statistics.py` (lines 473 and 488) and one
in `geospatial.py` (line 303 inside `compute_min_return_period_of_feature_impact`).
All three must be updated to:
- Use the new name (no `_` prefix)
- Pass `assign_dup_vals_max_return=ASSIGN_DUP_VALS_MAX_RETURN`
- Import `ASSIGN_DUP_VALS_MAX_RETURN` from `ss_fha.constants` if not already imported

#### Functions explicitly NOT moved

`compute_emp_cdf_and_return_pds()` stays in `flood_probability.py`. It uses
`xr.apply_ufunc` over a spatial flood-depth grid — its inputs (`da_wlevel`,
`x`/`y` dims, NaN-fill of `0.0` for dry cells) and outputs are flood-specific.
The fact that it internally calls `calculate_positions` and
`calculate_return_period` doesn't make it domain-agnostic.

#### Module docstring for `empirical_frequency_analysis.py`

The new module docstring should:
- Explain the Hazen family formula with the `(alpha, beta)` named method table
  (currently in `flood_probability.py` module docstring — move it verbatim).
- Note that all three functions are domain-agnostic and tracked as utility
  package candidates.
- State that `flood_probability.py`, `event_statistics.py`, and `geospatial.py`
  all import from here.

The `flood_probability.py` module docstring should be trimmed to remove the
plotting-positions exposition; replace with a one-line cross-reference:
```
Plotting positions and return period conversion:
    see ``ss_fha.core.empirical_frequency_analysis``.
```

#### `utility_package_candidates.md` update

Add dedicated entries for all three functions. Note: `calculate_positions` and
`calculate_return_period` are referenced only vaguely in the existing table (as
a note on the `empirical_multivariate_return_periods` entry); they do not have
dedicated rows yet. Create dedicated rows for all three, noting the new module
location (`ss_fha.core.empirical_frequency_analysis`).

---

### Tests

#### Existing tests to move

The existing tests for `calculate_positions` and `calculate_return_period` in
`tests/test_flood_probability.py` (14 tests) must be **moved** to a new
`tests/test_empirical_frequency_analysis.py`, importing from the new module.
The tests themselves are unchanged.

After moving, `test_flood_probability.py` should no longer import
`calculate_positions` or `calculate_return_period` from `flood_probability`.
`TestComputeEmpCdfAndReturnPds.test_matches_lower_level_functions` still uses
these functions as reference values and must import them from
`ss_fha.core.empirical_frequency_analysis` instead.

#### New tests for `compute_return_periods_for_series`

`_compute_return_periods_for_series` currently has no dedicated unit tests (it
is tested indirectly through `compute_univariate_event_return_periods` in
`test_event_statistics.py`). Now that it is public and has a new explicit
argument, add a small focused test class in
`tests/test_empirical_frequency_analysis.py`:

| Test | What it checks |
|---|---|
| `test_output_columns` | Output DataFrame has expected column names `[varname, f"{varname}_emp_cdf", f"{varname}_return_pd_yrs"]` |
| `test_sorted_ascending` | Output is sorted ascending by statistic value |
| `test_return_period_positive` | All return period values are positive |
| `test_varname_override` | Passing an explicit `varname` renames the value column correctly |
| `test_assign_dup_max_return_true` | When `assign_dup_vals_max_return=True`, duplicate values receive the maximum return period of their group |
| `test_assign_dup_max_return_false` | When `assign_dup_vals_max_return=False`, duplicate values receive progressively increasing CDF values |

---

## Success Criteria

- [ ] `src/ss_fha/core/empirical_frequency_analysis.py` exists with
      `calculate_positions`, `calculate_return_period`, and
      `compute_return_periods_for_series` (public, explicit `assign_dup_vals_max_return` arg).
- [ ] Neither `calculate_positions` nor `calculate_return_period` remains
      defined in `flood_probability.py`.
- [ ] `_compute_return_periods_for_series` no longer exists in `event_statistics.py`.
- [ ] All import sites updated (no re-exports, no aliases).
- [ ] `geospatial.py` no longer imports a private function from `event_statistics`.
- [ ] `tests/test_empirical_frequency_analysis.py` contains the 14 moved tests
      plus 6 new tests for `compute_return_periods_for_series` (20 total).
- [ ] `tests/test_flood_probability.py` no longer imports `calculate_positions`
      or `calculate_return_period` from `flood_probability`; any remaining
      imports of these functions point to `ss_fha.core.empirical_frequency_analysis`.
- [ ] `utility_package_candidates.md` updated: existing entries for
      `calculate_positions` / `calculate_return_period` reflect new module;
      `compute_return_periods_for_series` added.
- [ ] Full test suite passes (165 + 6 new = 171 tests).
- [ ] `full_codebase_refactor.md` tracking table updated; Phase 2E marked complete.
- [ ] This document moved to `implemented/`.

---

## Commit

This entire chunk is a single dedicated commit with message:

```
refactor(core): extract empirical frequency primitives — work chunk 02E

Move calculate_positions(), calculate_return_period(), and
_compute_return_periods_for_series() from flood_probability.py /
event_statistics.py into a new empirical_frequency_analysis.py.
All three are domain-agnostic and tracked as utility package candidates.

_compute_return_periods_for_series is renamed to
compute_return_periods_for_series (public) and gains an explicit
assign_dup_vals_max_return: bool argument, replacing the implicit
read of ASSIGN_DUP_VALS_MAX_RETURN. All call sites updated.

Fixes cross-module private import: geospatial.py no longer imports
a _private function from event_statistics.

Update all import sites; no re-exports or aliases. Add 6 new tests
for compute_return_periods_for_series.

171/165 tests pass (6 new).
```

---

## Decision Log

**2026-02-26 — Preflight review (Opus 4.6)**

- **test_flood_probability.py import handling**: `TestComputeEmpCdfAndReturnPds.test_matches_lower_level_functions` legitimately uses `calculate_positions`/`calculate_return_period` as reference values. Decision: update imports in that file to point at `empirical_frequency_analysis` rather than removing them. Success criterion reworded accordingly. (Approved by developer.)
- **geospatial.py lazy import**: The lazy import of `_compute_return_periods_for_series` inside the function body was a workaround for the private-function code smell. Decision: move to a top-level import when updating to the new public function. No circular dependency risk. (Approved by developer.)
- **Master plan architecture tree**: `empirical_frequency_analysis.py` description omits `compute_return_periods_for_series`; `flood_probability.py` description is stale post-refactor. Both to be updated during implementation.
- **utility_package_candidates.md**: Existing table has no dedicated rows for `calculate_positions`/`calculate_return_period` — only a vague note. All three functions get new dedicated rows.
- **event_statistics.py import**: After removing `_compute_return_periods_for_series`, `calculate_positions` is no longer used in that file. Updated import to include only `calculate_return_period` from `empirical_frequency_analysis`.
