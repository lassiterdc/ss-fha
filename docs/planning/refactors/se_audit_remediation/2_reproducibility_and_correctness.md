---
impact: High
urgency: High
loe: Medium
risk: Medium
priority: 2.47
priority-label: "Core priority"
created: 2026-03-14
description: "Phase 2 — reproducibility and correctness fixes: unseeded RNG, join='exact', ASSIGN_DUP_VALS_MAX_RETURN promotion, Pydantic physical bounds validators"
master: docs/planning/refactors/se_audit_remediation/master.md
dependencies:
  - docs/planning/refactors/se_audit_remediation/1_quick_wins.md  # SSFHAConfig consolidation
---

# Phase 2: Reproducibility and Correctness

## Dependencies

**Upstream**: Phase 1 (SSFHAConfig consolidation — this phase adds a field to `SsfhaConfig`).
**Downstream**: Phase 3 (zarr dtype pinning + config hash use the config model modified here); alignment testing Phase 4 (event statistics) is blocked until the RNG fix lands.

## Task Understanding

### Requirements

Address audit findings: Section 1 item 2 (unseeded RNG), Section 2 items 1–3 (join="outer", ASSIGN_DUP_VALS_MAX_RETURN, physical bounds validators).

### Success Criteria

- `bs_samp_of_univar_event_return_period` and `bs_samp_of_multivar_event_return_period` accept a `rng: np.random.Generator` parameter (no default)
- Callers in `analysis/event_comparison.py` thread a seeded generator
- `combine_and_quantile` uses `join="exact"`
- `ASSIGN_DUP_VALS_MAX_RETURN` removed from `constants.py` and replaced with `assign_dup_vals_max_return: bool` on `SsfhaConfig`
- Pydantic validators reject: `alpha` or `beta` outside [0, 1], `alpha + beta > 1`, `return_periods` containing non-positive values, `n_years_synthesized <= 0`, `bootstrap_quantiles` outside (0, 1)
- All tests pass (updating test fixtures that violate new validators)

## File-by-File Change Plan

### Modified Files

| File | Change |
|------|--------|
| `src/ss_fha/core/event_statistics.py` | (1) Add `rng: np.random.Generator` param to `bs_samp_of_univar_event_return_period` and `bs_samp_of_multivar_event_return_period`. Replace `np.random.choice(...)` with `rng.choice(...)` at lines 603 and 745. (2) Add `assign_dup_vals_max_return: bool` param to `compute_univariate_event_return_periods` and `compute_all_multivariate_return_period_combinations`. Remove `from ss_fha.constants import ASSIGN_DUP_VALS_MAX_RETURN`. Pass the param through to internal call sites. |
| `src/ss_fha/analysis/event_comparison.py` | Thread `rng=np.random.default_rng(config.uncertainty.bootstrap_base_seed + sample_offset)` to the two bootstrap functions. Thread `assign_dup_vals_max_return=config.assign_dup_vals_max_return` to `compute_univariate_event_return_periods` and `compute_all_multivariate_return_period_combinations`. The exact `sample_offset` mechanism needs to be determined during implementation by reading how bootstrap iteration is structured in `run_event_comparison`. |
| `src/ss_fha/core/geospatial.py` | Replace `from ss_fha.constants import ASSIGN_DUP_VALS_MAX_RETURN` with a function parameter `assign_dup_vals_max_return: bool` on `compute_min_return_period_of_feature_impact`. Thread from caller. |
| `src/ss_fha/analysis/uncertainty.py` | Change `join="outer"` to `join="exact"` on line 327. Update the comment to explain: "All bootstrap samples must have the same return_pd_yrs axis. If they differ, this indicates varying event counts across samples — investigate the bootstrap resampling logic." |
| `src/ss_fha/config/model.py` | (1) Add `assign_dup_vals_max_return: bool = False` to `SsfhaConfig`. (2) Add `@field_validator` for: `alpha` in [0, 1], `beta` in [0, 1], model validator `alpha + beta <= 1`, all `return_periods > 0`, `n_years_synthesized > 0`. (3) Add `@field_validator` to `UncertaintyConfig` for: all `bootstrap_quantiles` in (0, 1). (4) Add `@field_validator` to `BdsConfig` for: all `return_periods > 0`. |
| `src/ss_fha/constants.py` | Remove `ASSIGN_DUP_VALS_MAX_RETURN: bool = False` and its docstring/comment. |
| `src/ss_fha/runners/event_stats_runner.py` | Thread `assign_dup_vals_max_return=config.assign_dup_vals_max_return` through to `run_event_comparison`. |
| `src/ss_fha/analysis/flood_hazard.py` | If `compute_min_return_period_of_feature_impact` is called here, thread `assign_dup_vals_max_return`. (Verify during implementation.) |

### Test Files to Update

| File | Change |
|------|--------|
| `tests/conftest.py` | Add `"alpha": 0.375, "beta": 0.375` and `"assign_dup_vals_max_return": false` to `full_config` analysis dict. Add `"bootstrap_quantiles": [0.05, 0.50, 0.95]` to the uncertainty section. Verify all test fixture configs pass the new validators. |
| `tests/test_event_stats_workflow.py` | Update inline config dicts to include `assign_dup_vals_max_return`. Verify alpha/beta values are within [0, 1]. |
| `tests/test_old_code_alignment/test_align_flood_probability.py` | Verify alpha/beta test values are within [0, 1] — they should already be since they test real plotting position parameters. |

## Implementation Notes

### RNG threading strategy

The event statistics bootstrap functions are called inside loops in `analysis/event_comparison.py::run_event_comparison`. Each iteration should get a deterministic, unique seed derived from the config's `bootstrap_base_seed` and the loop iteration index. Pattern:

```python
rng = np.random.default_rng(config.uncertainty.bootstrap_base_seed + i)
result = bs_samp_of_univar_event_return_period(..., rng=rng)
```

This matches the convention in `core/bootstrapping.py`.

### ASSIGN_DUP_VALS_MAX_RETURN call chain

```
SsfhaConfig.assign_dup_vals_max_return
  → runners/event_stats_runner.py
    → analysis/event_comparison.py::run_event_comparison
      → core/event_statistics.py::compute_univariate_event_return_periods
      → core/event_statistics.py::compute_all_multivariate_return_period_combinations
        → core/empirical_frequency_analysis.py::compute_return_periods_for_series (already accepts it as a parameter)
  → analysis/flood_hazard.py (verify)
    → core/geospatial.py::compute_min_return_period_of_feature_impact
      → core/empirical_frequency_analysis.py::compute_return_periods_for_series
```

### Validator test audit

Before adding validators, search all test files for config dict construction and verify the values will pass. Key patterns to search:
- `"alpha":` — must be in [0, 1]
- `"beta":` — must be in [0, 1]
- `"return_periods":` — must all be > 0
- `"n_years_synthesized":` — must be > 0
- `"bootstrap_quantiles":` — must all be in (0, 1)

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| New validators break existing test fixtures | Audit all test config dicts before adding validators. Fix any violations in the same commit. |
| `alpha + beta > 1` fails for some legitimate plotting position schemes | The Hazen formula uses alpha=beta=0.5 (sum=1.0), which is within bounds. The Weibull formula uses alpha=beta=0 (sum=0). Cunnane uses alpha=0.4, beta=0.4 (sum=0.8). No common scheme exceeds 1.0. The constraint `alpha + beta <= 1` is safe. |
| RNG threading changes the numerical output of event statistics | This is intentional — the current output is non-deterministic and non-reproducible. The new output will be deterministic for any given seed. Alignment tests (Phase 4 of alignment plan) should use the seeded interface. |
| `join="exact"` causes immediate failure on existing data | Only fails if bootstrap samples have different `return_pd_yrs` lengths. If this occurs on the Norfolk data, it indicates a real bug in the bootstrap pipeline that was previously hidden. |

## Validation Plan

```bash
# Verify validators work
conda run -n ss-fha python -c "
from ss_fha.config.model import SsfhaConfig
try:
    SsfhaConfig(alpha=-0.1, beta=0.5, ...)
    print('FAIL: should have rejected negative alpha')
except Exception as e:
    print(f'OK: {e}')
"

# Full test suite
conda run -n ss-fha pytest tests/ -v

# Smoke test: event stats runner with seeded RNG produces deterministic output
conda run -n ss-fha pytest tests/test_event_stats_workflow.py -v
```

## Definition of Done

- [ ] `bs_samp_of_univar_event_return_period` and `bs_samp_of_multivar_event_return_period` accept `rng: np.random.Generator` — no global RNG usage
- [ ] Callers thread seeded generators
- [ ] `join="outer"` → `join="exact"` in `combine_and_quantile`
- [ ] `ASSIGN_DUP_VALS_MAX_RETURN` removed from `constants.py`
- [ ] `assign_dup_vals_max_return: bool = False` added to `SsfhaConfig`
- [ ] All 6 call sites thread the config value (verify count during implementation)
- [ ] Pydantic validators: alpha ∈ [0,1], beta ∈ [0,1], alpha+beta ≤ 1, return_periods > 0, n_years_synthesized > 0, bootstrap_quantiles ∈ (0,1)
- [ ] All test fixture configs pass new validators
- [ ] All tests pass
- [ ] Move this doc to `implemented/`
