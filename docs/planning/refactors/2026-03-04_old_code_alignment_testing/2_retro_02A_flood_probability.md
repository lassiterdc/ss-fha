---
created: 2026-03-04
last_edited: 2026-03-04 — initial draft
---

# Phase 2: Retroactive — 02A Flood Probability

## Dependencies

**Upstream**: Phase 1 (package + mock) must be complete.
**Downstream**: None within this plan.

## Task Understanding

Add old-code alignment tests for `core.flood_probability.compute_emp_cdf_and_return_pds`, which replaced the equivalent function in `_old_code_to_refactor/__utils.py`. The old function has additional I/O and debug parameters (`qaqc_plots`, `export_intermediate_outputs`, etc.) that were stripped in the refactor. The core computation — stacking events, computing empirical CDF, computing return periods — is what must be aligned.

## Old Function Signature (from `__utils.py`)

```python
def compute_emp_cdf_and_return_pds(da_wlevel, alpha, beta, qaqc_plots,
                                    export_intermediate_outputs, dir_temp_zarrs,
                                    f_out_zarr, testing, print_benchmarking):
```

The I/O and debug params (`qaqc_plots`, `export_intermediate_outputs`, `dir_temp_zarrs`, `f_out_zarr`, `testing`, `print_benchmarking`) are not present in the refactored version. For alignment testing, call the old function with these set to `False`/`None` so no I/O occurs.

Also test: `stack_wlevel_dataset()` — this was absorbed into `compute_emp_cdf_and_return_pds` in the refactor; verify that the stacking behavior is equivalent.

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `tests/test_old_code_alignment/test_align_flood_probability.py` | Old-code alignment tests for 02A |

## Implementation Notes

Import strategy:
```python
import sys
sys.path.insert(0, str(Path(__file__).parents[2] / "_old_code_to_refactor"))
from __utils import compute_emp_cdf_and_return_pds as _old_compute_emp_cdf_and_return_pds
from __utils import stack_wlevel_dataset as _old_stack_wlevel_dataset
```

The `mock_inputs_module` fixture from `conftest.py` must be active (it is, as a session autouse fixture).

Test structure: generate a small synthetic `da_wlevel` DataArray with `(x, y, event_iloc)` dimensions, call both old and new functions on the same input, assert `np.allclose(old_result, new_result, rtol=1e-10)`.

Watch for: the old function writes zarr files to disk by default — pass `export_intermediate_outputs=False`, `qaqc_plots=False`, `f_out_zarr=None` to disable I/O in the old function.

If the old function internally calls other `__utils` functions (e.g., `calculate_positions`, `calculate_return_period`, `sort_last_dim`), those will also be imported via the `from __inputs import *` mock path — they should work as-is.

## Validation Plan

```bash
conda run -n ss-fha pytest tests/test_old_code_alignment/test_align_flood_probability.py -v
conda run -n ss-fha pytest tests/ -v
```

## QAQC Notes

The QAQC report for this phase must include a **Lessons Learned** section summarizing any insights from implementation — particularly surprises, obstacles, or deviations from plan. Move observations into the Lessons Learned section below as they arise during implementation so the QAQC report can pull from it directly. Phase 8 synthesizes all phase lessons learned into the master refactor plan appendix.

## Definition of Done

- [ ] `test_align_flood_probability.py` written with direct import of old `compute_emp_cdf_and_return_pds`
- [ ] Test asserts numerical equivalence between old and new on synthetic data (multiple configurations of alpha/beta and n_years)
- [ ] `stack_wlevel_dataset` behavior verified via comparison on stacked vs. unstacked input
- [ ] Tests pass
- [ ] Lessons Learned section filled in
- [ ] Move this doc to `implemented/`

## Lessons Learned

_(fill in after implementation)_
