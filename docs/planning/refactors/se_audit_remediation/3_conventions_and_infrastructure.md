---
impact: High
urgency: Medium
loe: Medium
risk: Low
priority: 2.18
priority-label: "Core priority"
created: 2026-03-14
description: "Phase 3 — conventions and infrastructure: dimension name constants, zarr dtype pinning, config hash in output attrs, full_config fixture fix, test anti-patterns"
master: docs/planning/refactors/se_audit_remediation/master.md
dependencies:
  - docs/planning/refactors/se_audit_remediation/2_reproducibility_and_correctness.md  # config model changes
---

# Phase 3: Conventions and Infrastructure

## Dependencies

**Upstream**: Phase 2 (config model changes — this phase references `config.assign_dup_vals_max_return` in threading; also adds config hash which uses the model's `model_dump()`).
**Downstream**: Phase 4 (test speed convention applies marks to tests created/modified here).

## Task Understanding

### Requirements

Address audit findings: Section 2 item 5 (dimension name constants), Section 4 items on `full_config` fixture and test anti-patterns, Section 5 items 1–2 (zarr dtype pinning, config hash).

### Success Criteria

- Canonical dimension name constants in `constants.py`, used at module boundaries
- `default_zarr_encoding` pins explicit dtypes
- Every `write_zarr` call writes `config_sha256` to output attrs
- `full_config` fixture passes Pydantic validation
- Test anti-patterns in `test_event_stats_workflow.py` fixed
- All tests pass

## File-by-File Change Plan

### Modified Files

| File | Change |
|------|--------|
| `src/ss_fha/constants.py` | Add dimension name constants section: `DIM_EVENT_ILOC = "event_iloc"`, `DIM_X = "x"`, `DIM_Y = "y"`, `DIM_RETURN_PD_YRS = "return_pd_yrs"`, `DIM_QUANTILE = "quantile"`, `DIM_SAMPLE_ID = "sample_id"`. Include a docstring block explaining the convention and when to add new names. |
| `src/ss_fha/io/zarr_io.py` | (1) Update `default_zarr_encoding` to accept an optional `dtypes: dict[str, str]` parameter that pins dtype per variable. Add a `DEFAULT_DTYPES` constant mapping common variable patterns to dtypes: flood depth → float64, return period → float64, CDF → float64, boolean masks → uint8. (2) Add a `write_zarr_with_provenance` function (or modify `write_zarr`) that accepts an optional `config` parameter, computes `hashlib.sha256(json.dumps(config.model_dump(), sort_keys=True, default=str).encode()).hexdigest()`, and writes it to the zarr's root `attrs["config_sha256"]`. |
| `src/ss_fha/analysis/flood_hazard.py` | Pass config to `write_zarr` for provenance (if `write_zarr` API is modified) or call the provenance function after writing. |
| `src/ss_fha/analysis/uncertainty.py` | Same — pass config for provenance on bootstrap sample and combined zarr writes. |
| `src/ss_fha/analysis/event_comparison.py` | Same — pass config for provenance on event statistics output. |
| `tests/conftest.py` | Fix `full_config` fixture: add `"bootstrap_quantiles": [0.05, 0.50, 0.95]` to uncertainty dict, add `"alpha": 0.375, "beta": 0.375`, add `"assign_dup_vals_max_return": False` (from Phase 2), add required fields for non-comparative SsfhaConfig (`"weather_event_indices"`, `"event_statistic_variables"`). Verify the fixture actually instantiates without error by adding a simple assertion at the end. |
| `tests/test_event_stats_workflow.py` | (1) `test_runner_cli_end_to_end`: add `SystemConfig.model_validate(system_dict)` before writing system YAML to `tmp_path`. (2) `test_missing_timeseries_rejected`: refactor to use `test_case_builder` infrastructure instead of inline synthetic data construction. |

## Implementation Notes

### Dimension name constants — scope of adoption

This phase adds the constants and uses them in module-level documentation. Full adoption (replacing string literals throughout all source files) is a separate, lower-priority task that can be done incrementally as modules are touched by future work. The constants serve as a reference contract even before all call sites use them.

### Config hash — write_zarr API design

Two approaches:

**Option A (preferred)**: Add an optional `config` parameter to `write_zarr`. If provided, write the hash to `ds.attrs["config_sha256"]` before calling `ds.to_zarr()`. Minimal API change, no new function.

**Option B**: Create a `stamp_provenance(zarr_path, config)` function that opens the zarr store and writes the hash to `attrs` after the initial write. More composable but adds an extra open/close cycle.

Choose Option A during implementation unless there is a reason to decouple.

### Zarr dtype pinning — scope

The `default_zarr_encoding` function returns a dict of `{var: {"compressor": ...}}` entries. Adding dtype is straightforward: `{var: {"compressor": ..., "dtype": "float64"}}`. The dtype should be determined by variable name pattern matching or an explicit mapping.

A reasonable default mapping:
- Variables containing "depth", "wlevel", "cdf", "return_pd" → `float64`
- Variables named "mask" or boolean → `uint8`
- Everything else → caller must specify or default to `float64`

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| Config hash changes when adding new config fields | This is correct behavior — the hash should change when the config changes. Document that the hash covers all config fields. |
| `full_config` fixture fix requires adding fields that Phase 2 introduced | Yes — this phase depends on Phase 2 being complete. The `assign_dup_vals_max_return` field must be in the dict. |
| Dtype pinning may cause precision issues if a variable is unexpectedly float32 | `float64` is strictly more precise than `float32`. Pinning to float64 will never lose precision — it may use more storage. Document the tradeoff. |

## Validation Plan

```bash
# Verify dimension constants are importable
conda run -n ss-fha python -c "from ss_fha.constants import DIM_EVENT_ILOC, DIM_RETURN_PD_YRS; print('OK')"

# Verify full_config fixture works
conda run -n ss-fha pytest tests/conftest.py --co -q  # collection should not error

# Full test suite
conda run -n ss-fha pytest tests/ -v

# Verify config hash in output
conda run -n ss-fha python -c "
import zarr
# (only works after a test run that produces output zarrs)
"
```

## Definition of Done

- [ ] Dimension name constants added to `constants.py` with docstring
- [ ] `default_zarr_encoding` pins dtype explicitly
- [ ] `write_zarr` writes `config_sha256` to output attrs when config is provided
- [ ] All 3 analysis modules pass config to `write_zarr` for provenance
- [ ] `full_config` fixture instantiates without `ValidationError`
- [ ] `test_runner_cli_end_to_end` validates system YAML against `SystemConfig`
- [ ] `test_missing_timeseries_rejected` uses `test_case_builder`
- [ ] All tests pass
- [ ] Move this doc to `implemented/`
