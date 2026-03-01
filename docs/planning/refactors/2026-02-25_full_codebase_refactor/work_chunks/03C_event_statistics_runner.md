# Work Chunk 03C: Event Statistics Analysis and Runner

**Phase**: 3C — Analysis Modules + Runner Scripts (Event Statistics)
**Last edited**: 2026-02-25

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/refactors/2026-02-25_full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`CONTRIBUTING.md`](../../../../CONTRIBUTING.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: Work chunks 02C (event_statistics core) and 03A complete.

---

## Task Understanding

### Requirements

Implement the event statistics analysis module and runner script.

**Replaces**: `_old_code_to_refactor/d0_computing_event_statistic_probabilities.py`

**Files to create:**

1. `src/ss_fha/analysis/event_comparison.py`:
   - Loads event summary CSVs (via `ss_fha.io`)
   - Calls `ss_fha.core.event_statistics` functions
   - Writes event return period outputs (zarr or CSV as appropriate)
   - Supports Workflows 1 and 4

2. `src/ss_fha/runners/event_stats_runner.py`:
   - CLI args: `--config <yaml>`
   - Logs completion marker

### Key Design Decisions

- **`n_years` is derived from event data** (record length), not a config default. The runner must compute this from the loaded data and log it.
- Event-to-flood mapping (the "fragile CSV" noted in the master plan) must be formalized. Define the expected column schema for event CSV files clearly and validate on load.

### Success Criteria

- Runner executes end-to-end with synthetic event summaries
- Event return periods written to output; output passes basic sanity checks (no NaN, return periods > 0)

---

## Evidence from Codebase

Before implementing, inspect:

1. `_old_code_to_refactor/d0_computing_event_statistic_probabilities.py`
2. `src/ss_fha/core/event_statistics.py` (02C)
3. `_old_code_to_refactor/__inputs.py` — event CSV column name conventions

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/analysis/event_comparison.py` | Event statistics orchestration |
| `src/ss_fha/runners/event_stats_runner.py` | CLI runner |

### Modified Files

| File | Change |
|------|--------|
| `_old_code_to_refactor/d0_*.py` | Add refactoring status block |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| Event CSV schema varies between datasets | Validate expected columns on load; raise `DataError` with column list if missing |
| `n_years` computed from event data may be wrong if data has gaps | Log the computed `n_years` prominently; user can verify |

---

## Validation Plan

```bash
python -m ss_fha.runners.event_stats_runner --config /tmp/ssfha_test/config.yaml
pytest tests/test_end_to_end.py::test_event_statistics -v
```

---

## Documentation and Tracker Updates

- Update `full_codebase_refactor.md` tracking table: `d0_*` → `COMPLETE`.

---

## Definition of Done

- [ ] `src/ss_fha/analysis/event_comparison.py` implemented
- [ ] `src/ss_fha/runners/event_stats_runner.py` implemented
- [ ] `n_years` computed from data and logged; no hardcoded year values
- [ ] Event CSV schema validated on load
- [ ] Integration test passes with synthetic event summaries
- [ ] `full_codebase_refactor.md` tracking table updated
- [ ] **Move this document to `../implemented/` once all boxes above are checked**
