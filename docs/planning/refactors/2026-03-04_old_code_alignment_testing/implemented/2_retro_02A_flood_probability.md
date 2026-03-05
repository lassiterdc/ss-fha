---
created: 2026-03-04
last_edited: 2026-03-05 — implementation complete
---

# Phase 2: Retroactive — 02A Flood Probability

## Dependencies

**Upstream**: Phase 1 (package + mock) must be complete.
**Downstream**: None within this plan.

## Task Understanding

Add old-code alignment tests for `core.flood_probability.compute_emp_cdf_and_return_pds`, which replaced the equivalent function in `_old_code_to_refactor/__utils.py`. The old function has additional I/O and debug parameters (`qaqc_plots`, `export_intermediate_outputs`, etc.) that were stripped in the refactor. The core computation — stacking events, computing empirical CDF, computing return periods — is what must be aligned.

## Old Function Signature (from `__utils.py`)

```python
def compute_emp_cdf_and_return_pds(da_wlevel, alpha, beta, qaqc_plots=False,
                                    export_intermediate_outputs=False, dir_temp_zarrs=None,
                                    f_out_zarr=None, testing=False, print_benchmarking=True,
                                    n_years=None, f_event_number_mapping=None):
```

For alignment testing, call with: `qaqc_plots=False`, `export_intermediate_outputs=False`, `dir_temp_zarrs=None`, `f_out_zarr=None`, `testing=False`, `print_benchmarking=False`, `f_event_number_mapping=None`, and `n_years=<explicit value>`.

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

### Key differences between old and new (from preflight)

1. **Dimension name**: old uses `event_number`, new uses `event_iloc`. Construct test inputs with the appropriate dimension name for each function.
2. **Variable name typo**: old names the CDF variable `emprical_cdf` (missing 'i'); new uses `empirical_cdf`. Compare values by role, not variable name.
3. **`fillna_val`**: old `compute_emp_cdf_and_return_pds` calls `calculate_positions` without `fillna_val` (so `None`); new passes `fillna_val=0.0`. For non-NaN inputs, both produce identical results. **Use non-NaN data only** for the alignment test. NaN handling was intentionally improved in the refactor.
4. **`n_years`**: old defaults to `len(da_wlevel.year.values)` if `None`; new requires it explicitly. Always pass `n_years` explicitly to both.
5. **Lazy vs. eager**: old calls `.copy().load()` when `f_out_zarr=None`; new returns lazy. Compare after `.compute()`.

### Error-path test (sys.exit() inventory)

`calculate_positions` has a `sys.exit()` at `__utils.py:1567` for the NaN-with-no-fillna case. The new `core.empirical_frequency_analysis.calculate_positions` raises `SSFHAError` for the same condition. Add an error-path test that verifies the new function raises `SSFHAError` when given NaN input with `fillna_val=np.nan`.

## Validation Plan

```bash
conda run -n ss-fha pytest tests/test_old_code_alignment/test_align_flood_probability.py -v
conda run -n ss-fha pytest tests/ -v
```

## QAQC Notes

The QAQC report for this phase must include a **Lessons Learned** section summarizing any insights from implementation — particularly surprises, obstacles, or deviations from plan. Move observations into the Lessons Learned section below as they arise during implementation so the QAQC report can pull from it directly. Phase 8 synthesizes all phase lessons learned into the master refactor plan appendix.

## Definition of Done

- [x] `test_align_flood_probability.py` written with direct import of old `compute_emp_cdf_and_return_pds`
- [x] Test asserts numerical equivalence between old and new on synthetic data (multiple configurations of alpha/beta and n_years)
- [x] `stack_wlevel_dataset` behavior verified via comparison on stacked vs. unstacked input
- [x] Tests pass (212 passed, 0 failed)
- [x] `sys.exit()` inventory (Phase 2 rows): `raise SSFHAError` confirmed for `calculate_positions` NaN path (`__utils.py:1567`); `__utils.py:1853` marked N/A (test-only guard); master.md inventory table updated
- [x] Lessons Learned section filled in
- [x] Move this doc to `implemented/`

## Lessons Learned

1. **Module-level mocking is required, not fixture-level.** Old code imports (`from __utils import ...`) happen at pytest collection time, before any fixture runs. The conftest.py mock must execute at module level, not inside a session-scoped fixture. This was the single biggest obstacle.

2. **`local.__inputs` must also be mocked.** The old code uses both `from __inputs import *` and `from local.__inputs import (...)`. Three `sys.modules` entries are needed: `__inputs`, `local`, and `local.__inputs`.

3. **Python 3.11 vs 3.12 f-string nesting.** Old code at `__utils.py:2186` uses a nested f-string (`f"...{col.split(f'...')[-1]}"`) that only works on Python 3.12+ (PEP 701). Required extracting the inner f-string to a variable for 3.11 compatibility.

4. **Missing dependencies.** `tzlocal` and `tqdm` are not in the ss-fha environment but are imported by `__utils.py`. Required `pip install` before tests could run.

5. **Plan's import strategy was inaccurate.** The plan specified `sys.path.insert(0, ...)` inside the test file, but this is better handled once in `conftest.py` (already done by Phase 1). The plan's `mock_inputs_module` fixture reference was also outdated — it had already been restructured to module-level code.
