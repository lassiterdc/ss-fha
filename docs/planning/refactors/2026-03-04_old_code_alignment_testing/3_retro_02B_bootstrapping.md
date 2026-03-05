---
created: 2026-03-04
last_edited: 2026-03-04 — initial draft
---

# Phase 3: Retroactive — 02B Bootstrapping

## Dependencies

**Upstream**: Phase 1.
**Downstream**: None.

## Task Understanding

Add old-code alignment tests for bootstrap functions in `core.bootstrapping`. The old code is in `__utils.py`. The critical functions:

- `bootstrapping_return_period_estimates()` — assembles a bootstrap sample and computes return-period-indexed depths. This is the core bootstrap computation. Replaced by `assemble_bootstrap_sample()` + `compute_return_period_indexed_depths()` in the refactor.
- `sort_last_dim()` — simple numpy sort along last axis.
- `prepare_for_bootstrapping()` — determines bootstrap start ID and whether to resume/delete. Replaced by `prepare_bootstrap_run()` in `analysis.uncertainty`.

Note: `bootstrapping_return_period_estimates()` in old code has I/O (`dir_bootstrap_sample_destination` — writes per-sample zarr). For alignment testing, call with a tmp dir to capture output, or patch the write. The new code separates computation from I/O — alignment test should compare just the computed flood depths.

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `tests/test_old_code_alignment/test_align_bootstrapping.py` | Alignment tests for 02B |

## Implementation Notes

The old `bootstrapping_return_period_estimates()` writes a zarr to `dir_bootstrap_sample_destination`. To test without side effects, use a `tmp_path` fixture for the directory. Then read the written zarr and compare its `return_pd_yrs`-indexed depths against what the new `compute_return_period_indexed_depths()` produces given the same inputs.

The old function also calls `compute_emp_cdf_and_return_pds()` internally. If the Phase 2 alignment test passes, this is already validated. The bootstrap alignment test focuses on the year-resampling and assembly logic.

Key input shape: `ds_sim_flood_probs` must have `event_iloc` dimension. Provide a small synthetic dataset (e.g., 20 events, 3x3 grid) and a known seed for reproducibility.

## Validation Plan

```bash
conda run -n ss-fha pytest tests/test_old_code_alignment/test_align_bootstrapping.py -v
conda run -n ss-fha pytest tests/ -v
```

## Definition of Done

- [ ] `test_align_bootstrapping.py` written
- [ ] `sort_last_dim` old vs. new equivalence test
- [ ] `bootstrapping_return_period_estimates` old vs. `assemble_bootstrap_sample` + `compute_return_period_indexed_depths` pipeline equivalence test
- [ ] Tests use fixed seeds for reproducibility
- [ ] Tests pass
- [ ] Move this doc to `implemented/`

## Lessons Learned

_(fill in after implementation)_
