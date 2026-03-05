---
created: 2026-03-04
last_edited: 2026-03-04 — initial draft
---

# Phase 6: Retroactive — 03A/03B/03C Orchestration Notebooks

## Dependencies

**Upstream**: Phase 1. Phases 2–5 should be complete first (they validate the core functions these workflows orchestrate).
**Downstream**: None.

## Task Understanding

03A, 03B, and 03C replaced main-section script code (b1, c1/c1b, d0) — there are no named functions to directly import and compare. The alignment strategy is notebook fallback: demonstrate that given the same inputs, the new pipeline produces equivalent outputs to the old script.

Each notebook must be self-contained — a reader should understand the full context without reading any other file.

## Notebooks to Create

| Notebook | Old script | New code | Location |
|---|---|---|---|
| `03A_flood_hazard_workflow_alignment.ipynb` | `b1_analyze_triton_outputs_fld_prob_calcs.py` | `analysis.flood_hazard.run_flood_hazard` | `_old_code_to_refactor/demonstrating_functional_alignment/` |
| `03B_uncertainty_workflow_alignment.ipynb` | `c1_fpm_confidence_intervals_bootstrapping.py`, `c1b_fpm_confidence_intervals_bootstrapping.py` | `analysis.uncertainty.run_bootstrap_sample`, `combine_and_quantile` | Same |
| `03C_event_stats_workflow_alignment.ipynb` | `d0_computing_event_statistic_probabilities.py` | `analysis.event_comparison.run_event_comparison` | Same |

## Required Notebook Structure (each notebook)

1. **Title cell**: notebook name, date, what is being demonstrated
2. **Why direct import is not feasible**: explain that all old scripts use `from __inputs import *` and all logic lives in the main section (not named functions), making function-level pytest import impossible for orchestration-level behavior
3. **Old code**: show the relevant main-section logic verbatim, with the path to the original file
4. **New code**: show the equivalent new function(s) and their call signatures
5. **Inputs**: construct or load the smallest possible real or synthetic input that exercises the core computation path (avoid loading multi-GB real data — use synthetic fixtures from `tests/fixtures/test_case_builder.py`)
6. **Side-by-side comparison**: run both old (mocked/adapted) and new code on the same inputs; show outputs and assert equivalence numerically
7. **Conclusion**: state explicitly whether alignment holds, and note any intentional differences (e.g., output file format changes, dimension renames)

## Special Note: `compute_bootstrapped_flood_depth_cis` (03B)

`c1b_fpm_confidence_intervals_bootstrapping.py` has one named function: `compute_bootstrapped_flood_depth_cis()`. This function computes quantile-based flood depth CIs from a combined bootstrap zarr and is a true computation function. It should be:
- Directly imported using the `__inputs` mock (not notebook fallback)
- Tested in `tests/test_old_code_alignment/test_align_uncertainty_workflow.py`

Add this to the test file even though the rest of 03B is covered by notebook.

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `_old_code_to_refactor/demonstrating_functional_alignment/03A_flood_hazard_workflow_alignment.ipynb` | 03A alignment notebook |
| `_old_code_to_refactor/demonstrating_functional_alignment/03B_uncertainty_workflow_alignment.ipynb` | 03B alignment notebook |
| `_old_code_to_refactor/demonstrating_functional_alignment/03C_event_stats_workflow_alignment.ipynb` | 03C alignment notebook |
| `tests/test_old_code_alignment/test_align_uncertainty_workflow.py` | Direct import test for `compute_bootstrapped_flood_depth_cis` |

### New Directories

| Directory | Purpose |
|-----------|---------|
| `_old_code_to_refactor/demonstrating_functional_alignment/` | All alignment notebooks |

## Validation Plan

```bash
# Test file
conda run -n ss-fha pytest tests/test_old_code_alignment/test_align_uncertainty_workflow.py -v

# Notebooks — run and verify no errors
conda run -n ss-fha jupyter nbconvert --to notebook --execute _old_code_to_refactor/demonstrating_functional_alignment/03A_flood_hazard_workflow_alignment.ipynb
# Repeat for 03B and 03C
```

## QAQC Notes

The QAQC report for this phase must include a **Lessons Learned** section summarizing any insights from implementation — particularly surprises, obstacles, or deviations from plan. Move observations into the Lessons Learned section below as they arise during implementation so the QAQC report can pull from it directly. Phase 8 synthesizes all phase lessons learned into the master refactor plan appendix.

## Definition of Done

- [ ] `_old_code_to_refactor/demonstrating_functional_alignment/` directory created
- [ ] 03A alignment notebook written, executed cleanly, committed
- [ ] 03B alignment notebook written, executed cleanly, committed
- [ ] 03C alignment notebook written, executed cleanly, committed
- [ ] `compute_bootstrapped_flood_depth_cis` direct import test added to `test_align_uncertainty_workflow.py`
- [ ] All tests pass
- [ ] `sys.exit()` inventory (Phase 6 rows): no `sys.exit()` calls in named functions for 03A/03B/03C scope — mark all Phase 6 rows N/A in master.md inventory table
- [ ] Lessons Learned section filled in
- [ ] Move this doc to `implemented/`

## Lessons Learned

_(fill in after implementation)_
