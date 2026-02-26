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

**Functions to migrate (verify exact names and signatures in `__utils.py`):**

- `compute_emp_cdf_and_return_pds()` — empirical CDF + return period computation across the spatial grid
- `calculate_positions()` — Weibull or Stendinger plotting positions
- `calculate_return_period()` — convert plotting position to return period
- `compute_return_periods_for_series()` — apply return period computation to a 1D series
- `sort_dimensions()` — xarray dimension ordering utility

### Key Design Decisions

- **No defaults on arguments** (per philosophy.md). The `plotting_position_method` argument must always be passed explicitly; no fallback to `"weibull"`.
- **No I/O**: If the old implementations load or write data, strip that out. The function signature receives already-loaded xarray objects.
- **Mathematical correctness is critical** — this is a probability codebase. Before accepting any function port, validate against hand-computed examples or scipy/numpy reference implementations.
- **Alert for errors**: The master plan explicitly flags that plotting position methods (Weibull vs. Stendinger) produce subtly different results. Tests must verify both methods against a known analytical distribution.

### Success Criteria

- All functions importable from `ss_fha.core.flood_probability`
- Unit tests validate return period computation against hand-computed and scipy reference values
- Both Weibull and Stendinger methods tested against analytical distributions with known CDF
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
| `src/ss_fha/core/flood_probability.py` | Ported computation functions |
| `tests/test_flood_probability.py` | Unit tests including scipy reference validation |

### Modified Files

| File | Change |
|------|--------|
| `_old_code_to_refactor/__utils.py` | Update refactoring status block to note migrated functions |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| Mathematical errors introduced during porting | Test against scipy `stats.expon.cdf` or similar analytical distribution with known return periods |
| Weibull vs. Stendinger: subtle numerical differences cause silent errors | Explicitly test both methods; assert they differ by known amounts for a given dataset |
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
- [ ] `src/ss_fha/core/flood_probability.py` implemented with all five functions
- [ ] No I/O in any function (verified by code review)
- [ ] No default argument values on any function except obvious flags like `verbose`
- [ ] Unit tests validate against scipy/numpy reference implementations
- [ ] Both Weibull and Stendinger methods tested
- [ ] Refactoring status block updated in `_old_code_to_refactor/__utils.py`
- [ ] `full_codebase_refactor.md` tracking table updated
- [ ] **Move this document to `../implemented/` once all boxes above are checked**
