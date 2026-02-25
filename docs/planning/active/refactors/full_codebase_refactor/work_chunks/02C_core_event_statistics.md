# Work Chunk 02C: Core Event Statistics Module

**Phase**: 2C — Core Computation (Event Statistics)
**Last edited**: 2026-02-25

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

**Functions to migrate (verify exact names in `__utils.py`):**

- `compute_univariate_event_return_periods()` — return periods for individual event drivers (rainfall, surge) using their own empirical CDFs
- `compute_all_multivariate_return_period_combinations()` — generates all combinations of event drivers and their joint return periods
- `empirical_multivariate_return_periods()` — empirical joint return period computation
- Bootstrap sampling functions for event return period uncertainty (likely variants of the bootstrapping module functions, specialized for event data)

### Key Design Decisions

- **The `synthetic_years` field is not a default** — it is derived from the length of the weather record and must be passed explicitly as an argument. The old code may have it hardcoded; fix this.
- **Mathematical alert**: Multivariate return periods are a known area of mathematical complexity. The master plan flags "combinatorial explosion" as a risk. Read the old implementation carefully before porting.
- **No I/O**: Strip any CSV reading from these functions.

### Success Criteria

- Univariate return periods match known-good values from old scripts
- Multivariate combination count is validated before running (warn if combinatorially large)
- Tests use pre-computed event sets with known return periods

---

## Evidence from Codebase

Before implementing, inspect:

1. `_old_code_to_refactor/__utils.py` — event statistics functions
2. `_old_code_to_refactor/d0_computing_event_statistic_probabilities.py` — how these are used
3. `src/ss_fha/core/flood_probability.py` (02A) — may share plotting position logic

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/core/event_statistics.py` | Ported event return period functions |
| `tests/test_event_statistics.py` | Unit tests with pre-computed reference values |

### Modified Files

| File | Change |
|------|--------|
| `_old_code_to_refactor/__utils.py` | Update refactoring status block |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| Multivariate combinations explode combinatorially | Add a guard: compute expected combination count and raise `DataError` if above a configurable threshold |
| `synthetic_years` was hardcoded in old code | Identify all hardcoded year values; replace with explicit `n_years` argument |
| Joint return period methods have multiple valid implementations | Document the specific method used and cite a reference |

---

## Validation Plan

```bash
pytest tests/test_event_statistics.py -v
pytest tests/test_event_statistics.py::test_univariate_return_periods_known_values -v
pytest tests/test_event_statistics.py::test_multivariate_combination_guard -v
```

---

## Documentation and Tracker Updates

- Update `full_codebase_refactor.md` tracking table: `__utils.py` — event statistics functions migrated.

---

## Definition of Done

- [ ] `src/ss_fha/core/event_statistics.py` implemented
- [ ] `synthetic_years` (or `n_years`) is an explicit argument with no default
- [ ] Combinatorial explosion guard implemented
- [ ] All tests pass with pre-computed reference values
- [ ] Refactoring status block updated in `_old_code_to_refactor/__utils.py`
- [ ] `full_codebase_refactor.md` tracking table updated
- [ ] **Move this document to `implemented/` once all boxes above are checked**
