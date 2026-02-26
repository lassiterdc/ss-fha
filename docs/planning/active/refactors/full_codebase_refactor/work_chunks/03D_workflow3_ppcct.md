# Work Chunk 03D: Workflow 3 — PPCCT Validation

**Phase**: 3D — Analysis Modules + Runner Scripts (PPCCT)
**Last edited**: 2026-02-25

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`.prompts/philosphy.md`](../../../../../.prompts/philosphy.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: Phase 1 and 2 complete. Workflow 3 is **independent of Workflow 1** — uses raw TRITON outputs directly.

---

## Task Understanding

### Requirements

Implement the Probability Plot Correlation Coefficient Test (PPCCT) validation workflow.

**Replaces**: `b2_sim_vs_obs_fld_ppct.py`, `b2b_sim_vs_obs_flod_ppct.py`, `b2c_sim_vs_obs_fld_ppct.py`, `b2d_sim_vs_obs_fld_ppct.py`

**Note**: `b2d` includes plotting — the computation goes here, but plotting goes in Phase 5. Keep the computation/plot boundary clean.

**Files to create:**

1. `src/ss_fha/analysis/ppcct.py`:
   - PPCCT computation: correlation coefficient between simulated and observed flood depth quantiles at each gridcell
   - Bootstrap uncertainty for PPCCT
   - Output: pass/fail maps, p-values, PPCCT correlation grids

2. `src/ss_fha/runners/ppcct_runner.py`:
   - CLI args: `--config <yaml>`
   - Only runs when `toggle_ppcct=True` (validate this in runner, not just in config)
   - Logs completion marker

### Key Design Decisions

- **`toggle_ppcct=False` → runner raises `ConfigurationError`** if invoked despite toggle being off — defensive check.
- **Observed data path and obs event summaries** are required when this runner is invoked; validate explicitly.
- **Significance level `alpha`** comes from `config.ppcct.alpha` — no default in function signatures.

### Success Criteria

- PPCCT runner executes with synthetic sim + observed data
- Output contains expected variables (correlation grid, p-value grid, pass/fail boolean)
- Mathematical correctness: PPCCT result for a perfectly matching sim/obs pair is 1.0

---

## Evidence from Codebase

Before implementing, inspect:

1. `_old_code_to_refactor/b2_sim_vs_obs_fld_ppct.py` through `b2d_*.py` — all four scripts
2. `src/ss_fha/core/flood_probability.py` (02A) — shared plotting position logic

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/analysis/ppcct.py` | PPCCT computation |
| `src/ss_fha/runners/ppcct_runner.py` | CLI runner |

### Modified Files

| File | Change |
|------|--------|
| `_old_code_to_refactor/b2*.py` | Add refactoring status blocks |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| PPCCT mathematical correctness is critical | Test against a perfectly correlated synthetic dataset (expect r=1.0) and a random dataset (expect r near 0) |
| `b2d` mixes computation and plotting | Extract computation only; leave a `#TODO: plotting → Phase 5` comment |

---

## Validation Plan

```bash
python -m ss_fha.runners.ppcct_runner --config /tmp/ssfha_test/config.yaml
pytest tests/test_end_to_end.py::test_workflow3_ppcct -v
pytest tests/ -k "ppcct" -v
```

---

## Documentation and Tracker Updates

- Update `full_codebase_refactor.md` tracking table: `b2_*`, `b2b_*`, `b2c_*`, `b2d_*` → `PARTIAL` (computation done, plotting deferred to Phase 5).

---

## Definition of Done

- [ ] `src/ss_fha/analysis/ppcct.py` implemented
- [ ] `src/ss_fha/runners/ppcct_runner.py` implemented with toggle guard
- [ ] Mathematical correctness verified (r=1 for perfect sim/obs match)
- [ ] Plotting deferred cleanly to Phase 5 (no matplotlib in this module)
- [ ] Integration test passes
- [ ] `full_codebase_refactor.md` tracking table updated
- [ ] **Move this document to `../implemented/` once all boxes above are checked**
