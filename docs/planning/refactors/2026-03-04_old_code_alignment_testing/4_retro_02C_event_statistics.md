---
created: 2026-03-04
last_edited: 2026-03-04 — initial draft
---

# Phase 4: Retroactive — 02C Event Statistics (Gaps)

## Dependencies

**Upstream**: Phase 1.
**Downstream**: None.

## Task Understanding

02C already has one aligned test via `_empirical_multivariate_return_periods_reference` in `event_statistics.py`. This phase:

1. **Migrates** the existing reference function test into the alignment package (testing old functions in place is the preference — the test in `test_event_statistics.py` tests the reference function, but the reference function itself is the old code, not a new function being compared against old code)
2. **Fills remaining gaps**: `compute_univariate_event_return_periods`, `compute_all_multivariate_return_period_combinations`, and bootstrap event return period functions

Note on the existing reference function: `_empirical_multivariate_return_periods_reference` lives in `src/ss_fha/core/event_statistics.py`. It is the *old* O(n²) apply-based implementation imported-in-place. In the alignment package, we should test the **new** vectorized `empirical_multivariate_return_periods` against the *old* `empirical_multivariate_return_periods` from `__utils.py` directly (not the ported reference). This is the true "old function in place" test.

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `tests/test_old_code_alignment/test_align_event_statistics.py` | Full alignment tests for 02C |

### No Changes to Source

The `_empirical_multivariate_return_periods_reference` function stays in `event_statistics.py` — it is used by existing tests in `test_event_statistics.py`. Do not remove it. The alignment package adds a complementary test that directly imports and calls the old `__utils.empirical_multivariate_return_periods`.

## Implementation Notes

Functions to import from `__utils`:
- `empirical_multivariate_return_periods(df_samples, n_years)` — compare against new vectorized version
- `compute_univariate_event_return_periods(ds_sim_tseries)` — compare against new version
- `compute_all_multivariate_return_period_combinations(df_rain_return_pds, df_wlevel_return_pds)` — compare against new version
- `bs_samp_of_univar_event_return_period(...)` — bootstrap single sample
- `bs_samp_of_multivar_event_return_period(...)` — bootstrap single sample

For `compute_univariate_event_return_periods`, the old function expects `ds_sim_tseries` with specific variables (rainfall intensities, water level). Use a small synthetic NetCDF with the expected structure.

## Validation Plan

```bash
conda run -n ss-fha pytest tests/test_old_code_alignment/test_align_event_statistics.py -v
conda run -n ss-fha pytest tests/ -v
```

## QAQC Notes

The QAQC report for this phase must include a **Lessons Learned** section summarizing any insights from implementation — particularly surprises, obstacles, or deviations from plan. Move observations into the Lessons Learned section below as they arise during implementation so the QAQC report can pull from it directly. Phase 8 synthesizes all phase lessons learned into the master refactor plan appendix.

## Definition of Done

- [ ] `test_align_event_statistics.py` written
- [ ] `empirical_multivariate_return_periods` old vs. new alignment test (direct import of old `__utils` function)
- [ ] `compute_univariate_event_return_periods` alignment test
- [ ] `compute_all_multivariate_return_period_combinations` alignment test
- [ ] Bootstrap event return period functions alignment test (at minimum `bs_samp_of_univar_event_return_period`)
- [ ] All tests pass
- [ ] `sys.exit()` inventory (Phase 4 rows): confirm `raise SSFHAError` for `compute_univariate_event_return_periods` (`__utils.py:2217`, `2219`), `compute_all_multivariate_return_period_combinations` (`__utils.py:2352`), `bs_samp_of_univar/multivar_event_return_period` (`__utils.py:2460`); mark `__utils.py:2507` N/A (dev scaffolding); fill in inventory table columns in master.md
- [ ] Lessons Learned section filled in
- [ ] Move this doc to `implemented/`

## Lessons Learned

_(fill in after implementation)_
