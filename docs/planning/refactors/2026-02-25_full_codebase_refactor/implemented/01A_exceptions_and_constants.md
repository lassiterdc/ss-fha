# Work Chunk 01A: Exceptions and Constants

**Phase**: 1A — Foundation (Exceptions and Constants)
**Last edited**: 2026-02-25

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/refactors/2026-02-25_full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`CONTRIBUTING.md`](../../../../CONTRIBUTING.md) — project development philosophy; all implementation decisions must align with it.

---

## Task Understanding

### Requirements

Create the foundational exception hierarchy and constants module for `ss_fha`. These are the lowest-level building blocks that every other module depends on.

1. `src/ss_fha/exceptions.py` — custom exception hierarchy:
   - `SSFHAError` (base)
   - `ConfigurationError(field, config_path, message)`
   - `DataError(operation, filepath, reason)`
   - `BootstrapError(sample_id, reason)`
   - `WorkflowError(phase, stderr)`
   - `ValidationError(issues: list)`

2. `src/ss_fha/config/defaults.py` — extract constants from `_old_code_to_refactor/__inputs.py`:
   - `DEFAULT_RETURN_PERIODS`
   - `DEFAULT_DEPTH_THRESHOLDS_M`
   - `DEFAULT_N_BOOTSTRAP_SAMPLES`
   - `DEFAULT_PLOTTING_POSITION_METHOD`
   - Variable name mappings and other non-case-study-specific constants

   **Important**: Do NOT include a `DEFAULT_CRS_EPSG` or any other parameter that is case-study-specific. Per philosophy.md, users must make intentional choices about such parameters. Hard-coded case-study values (e.g., EPSG for Norfolk) belong in `cases/norfolk_ssfha_comparison/` YAML files, not in defaults.

   **Important**: Do NOT include `DEFAULT_SYNTHETIC_YEARS`. `n_years_synthesized` is a required field on `SSFHAConfig` (set in 01B) — it is a property of the weather model run (1000 for Norfolk), not an analysis-method default. It must be explicitly provided by the user because it is the denominator for all return period calculations. Using the wrong value silently biases every return period estimate.

### Assumptions

- **Low risk**: TRITON-SWMM_toolkit exception patterns are the primary design inspiration; check `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/exceptions.py` before designing.
- **Low risk**: Only constants that are truly analysis-method defaults (not case-study-specific) belong in `defaults.py`.
- **Low risk**: `config/` directory and `__init__.py` stubs will be created as part of this chunk.

### Success Criteria

- `from ss_fha.exceptions import SSFHAError, ConfigurationError, DataError, BootstrapError, WorkflowError, ValidationError` works
- `from ss_fha.config.defaults import DEFAULT_RETURN_PERIODS` works
- All exception classes carry the expected contextual attributes
- `pytest tests/test_config.py::test_defaults_are_accessible` passes

---

## Evidence from Codebase

Before implementing, inspect:

1. `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/exceptions.py` — patterns to adopt or import
2. `_old_code_to_refactor/__inputs.py` — identify which constants are truly generic defaults vs. Norfolk-specific
3. `src/ss_fha/` — current skeleton state
4. `pyproject.toml` — confirm `ss_fha` package is correctly configured

---

## Implementation Strategy

### Chosen Approach

Direct extraction: read the TRITON-SWMM_toolkit exception module and the old `__inputs.py`, then write `exceptions.py` and `defaults.py` from scratch following those patterns. Do not import from TRITON-SWMM_toolkit for these files (exception hierarchies and constants are trivially duplicated and having a cross-package dependency for base exceptions is poor design).

### Alternatives Considered

- **Re-export from TRITON-SWMM_toolkit**: Rejected — creates a hard runtime dependency for what should be self-contained base classes.
- **Single `constants.py` instead of `config/defaults.py`**: Rejected — `config/` is already the planned home per the master plan; `defaults.py` signals that these are overridable defaults, not fixed constants.

### Trade-offs

- This chunk has no computation logic, so it is fast to implement but critical to get right — every subsequent chunk imports from here.

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/exceptions.py` | Custom exception hierarchy |
| `src/ss_fha/config/__init__.py` | Makes `config` a package (can be empty or re-export key symbols) |
| `src/ss_fha/config/defaults.py` | Analysis-method-level defaults (return periods, depth thresholds, bootstrap count, plotting position method) |

### Modified Files

| File | Change |
|------|--------|
| `src/ss_fha/__init__.py` | Verify package imports cleanly; no substantive change expected |
| `tests/test_config.py` | Add `test_defaults_are_accessible` and `test_exceptions_have_attributes` |

### Notes

- Add a refactoring status comment block to `_old_code_to_refactor/__inputs.py` indicating which constants have been migrated (format defined in master plan).

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| Constants mistakenly pulled from Norfolk-specific config | Cross-check every constant against the question: "would a user with a different study area want a different value?" If yes, it's not a default. |
| `ValidationError` name clashes with Pydantic's own `ValidationError` | Name the ss_fha version `SSFHAValidationError` in the internal hierarchy, or alias carefully in `__init__.py`. Check what TRITON-SWMM_toolkit does. |

---

## Validation Plan

```bash
# Confirm package imports cleanly
python -c "from ss_fha.exceptions import SSFHAError, ConfigurationError, DataError, BootstrapError, WorkflowError, SSFHAValidationError; print('OK')"

# Confirm defaults importable
python -c "from ss_fha.config.defaults import DEFAULT_RETURN_PERIODS, DEFAULT_DEPTH_THRESHOLDS_M; print(DEFAULT_RETURN_PERIODS)"

# Run tests
pytest tests/test_config.py::test_defaults_are_accessible tests/test_config.py::test_exceptions_have_attributes -v
```

---

## Documentation and Tracker Updates

- Update the tracking table in `full_codebase_refactor.md` to mark `__inputs.py` as `PARTIAL` (constants migrated, config model not yet).
- Add refactoring status block to `_old_code_to_refactor/__inputs.py`.

---

## Definition of Done

- [ ] `src/ss_fha/exceptions.py` created with full exception hierarchy
- [ ] `src/ss_fha/config/__init__.py` created
- [ ] `src/ss_fha/config/defaults.py` created with only truly generic defaults (no Norfolk-specific values)
- [ ] All exceptions carry contextual attributes (not just a message string)
- [ ] Tests pass: `pytest tests/test_config.py::test_defaults_are_accessible`
- [ ] Refactoring status block added to `_old_code_to_refactor/__inputs.py`
- [ ] `full_codebase_refactor.md` tracking table updated
- [ ] **Move this document to `implemented/` once all boxes above are checked**
