# Work Chunk 01E: Validation Layer

**Phase**: 1E — Foundation (Validation Layer)
**Last edited**: 2026-02-25

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`.prompts/philosphy.md`](../../../../../.prompts/philosphy.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: Work chunks 01A–01B complete (exceptions and config model importable).

---

## Task Understanding

### Requirements

Create `src/ss_fha/validation.py` — business logic validation that goes beyond Pydantic's type checks. This is the "does the config make sense for a real run?" layer: files exist, workflow inputs are complete for enabled toggles, etc.

Follows the TRITON-SWMM_toolkit pattern of a `ValidationResult` that accumulates all issues before raising, so users see every problem at once rather than fixing them one at a time.

**Functions to implement:**

- `ValidationResult` dataclass: `is_valid: bool`, `issues: list[ValidationIssue]`, `raise_if_invalid()`, `merge(other: ValidationResult) -> ValidationResult`
- `ValidationIssue` dataclass: `field: str`, `message: str`, `current_value: Any`, `fix_hint: str`
- `validate_config(config: SSFHAConfig) -> ValidationResult` — structural/logical checks
- `validate_input_files(config: SSFHAConfig) -> ValidationResult` — checks that referenced files exist
- `validate_workflow_inputs(config: SSFHAConfig) -> ValidationResult` — per-workflow input completeness
- `preflight_validate(config: SSFHAConfig) -> ValidationResult` — combines all checks; this is the primary entry point called before any workflow execution

### Key Design Decisions

- **Accumulate all issues before raising** — `raise_if_invalid()` collects everything into a single `ss_fha.exceptions.ValidationError` with the full `issues` list.
- **File existence checks live here**, not in the Pydantic model (Pydantic validates types; validation.py validates reality).
- **Fix hints are required** on every `ValidationIssue` — the user must be told what to do to fix the problem, not just what is wrong.
- Per philosophy.md: fail-fast at execution start (call `preflight_validate` before any computation), but accumulate within the validation pass.

### Success Criteria

- `preflight_validate` with a config pointing to missing files returns a `ValidationResult` listing all missing files with fix hints
- Multiple issues are reported together, not one at a time
- Per-workflow validation catches missing inputs for enabled workflows
- All Phase 1E tests pass

---

## Evidence from Codebase

Before implementing, inspect:

1. `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/validation.py` — pattern to adopt (ValidationResult, ValidationIssue, accumulation)
2. `src/ss_fha/exceptions.py` (from 01A) — use `ValidationError` for raising accumulated results
3. `src/ss_fha/config/model.py` (from 01B) — understand all config fields and toggle dependencies

---

## Implementation Strategy

### Chosen Approach

Mirror the TRITON-SWMM_toolkit `ValidationResult` pattern, adapting field names and issue types to ss_fha's domain. Each `validate_*` function returns a `ValidationResult`; `preflight_validate` merges them all and calls `raise_if_invalid()`.

### Alternatives Considered

- **Raise immediately on first error**: Rejected — philosophy.md and master plan both explicitly require accumulation.
- **Put validation in the Pydantic model**: Rejected — file existence checks don't belong in Pydantic; Pydantic runs at model instantiation, before the user has set up the environment.

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/validation.py` | `ValidationResult`, `ValidationIssue`, all `validate_*` functions |
| (add tests to) `tests/test_config.py` | Phase 1E test cases |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| Paths in config may be relative — existence check fails | Resolve paths against `project_dir` before checking existence (same logic as `ProjectPaths.from_config`) |
| Zarr "files" are actually directories — `Path.exists()` works but `Path.is_file()` doesn't | Use `Path.exists()` for all path checks; add a note in `fix_hint` if the expected type is a directory |
| `toggle_ppcct=False` but observed data path is provided — should this warn? | No warning — silently ignored is fine; only validate what's required for enabled workflows |

---

## Validation Plan

```bash
# Missing input files reported with fix hints
pytest tests/test_config.py::test_validation_missing_input_files -v

# Multiple issues accumulate
pytest tests/test_config.py::test_validation_accumulates_errors -v

# Per-workflow validation (PPCCT enabled, observed data missing)
pytest tests/test_config.py::test_validation_per_workflow -v

# Full suite
pytest tests/test_config.py -v
```

---

## Documentation and Tracker Updates

- No tracking table changes required (validation.py is a new file).
- If patterns differ significantly from TRITON-SWMM_toolkit, note the ss_fha-specific approach in `full_codebase_refactor.md`.

---

## Definition of Done

- [ ] `src/ss_fha/validation.py` implemented with `ValidationResult`, `ValidationIssue`, and all `validate_*` functions
- [ ] `preflight_validate` is the single entry point that combines all checks
- [ ] Every `ValidationIssue` has a non-empty `fix_hint`
- [ ] File existence checks resolve relative paths against `project_dir` before checking
- [ ] All Phase 1E tests pass
- [ ] **Move this document to `../implemented/` once all boxes above are checked**
