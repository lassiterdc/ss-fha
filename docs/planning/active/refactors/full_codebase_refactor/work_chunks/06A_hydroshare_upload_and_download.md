# Work Chunk 06A: HydroShare Upload and Download Infrastructure

**Phase**: 6A — HydroShare gate before HPC testing
**Last edited**: 2026-02-25

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan.
- [`.prompts/philosphy.md`](../../../../../.prompts/philosphy.md) — project development philosophy.

**Prerequisite**: All Phases 1–5 complete and `test_end_to_end.py` passing locally with synthetic data. This work chunk is the gate between local development and HPC testing.

---

## Task Understanding

### Requirements

1. **Finalize and upload data to HydroShare** from the local staging directory at `/mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data`. Before uploading, verify that every file matches the schema expected by the library's I/O layer. If any file is incorrectly formatted, **fix the file** — do not add workarounds in the code.

2. **Implement `src/ss_fha/examples/examples.py`**:
   - `SSFHAExample` class: downloads from HydroShare, validates checksums, fills config template, returns `SSFHAConfig`
   - `download_norfolk_case_study(target_dir: Path) -> SSFHAConfig`

3. **Populate `NORFOLK_HYDROSHARE_RESOURCE_ID`** in `case_study_catalog.py` with the real resource ID once the HydroShare resource is created.

4. **Add integration test** `tests/fixtures/test_case_catalog.py::retrieve_norfolk_case_study` marked `@pytest.mark.slow` and `skip_if_no_hydroshare`.

### Data Staging Policy

- The staging directory may be incomplete or contain files that need reformatting. Audit every file against the expected schema before uploading.
- The canonical format is what the library expects, not the original source format. Reformat source files as needed.
- Do not write code that silently tolerates malformed input — fix the data.

### Success Criteria

- `ssfha download norfolk <dir>` downloads data and returns a valid `SSFHAConfig`
- Downloaded config passes `preflight_validate()`
- Integration test passes with real HydroShare data
- Ready to hand off to Phase 6 (full Norfolk HPC run)

---

## Evidence from Codebase

Before implementing, inspect:

1. `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/examples.py` — `SSFHAExample` pattern
2. `src/ss_fha/examples/case_study_catalog.py` (01G) — populate resource ID
3. `src/ss_fha/examples/config_templates/norfolk_default.yaml` (01G) — verify template is complete against all required config fields
4. `/mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data` — audit staged files against library I/O schemas

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/examples/examples.py` | `SSFHAExample` + `download_norfolk_case_study()` |

### Modified Files

| File | Change |
|------|--------|
| `src/ss_fha/examples/case_study_catalog.py` | Replace `PLACEHOLDER` with real HydroShare resource ID |
| `tests/fixtures/test_case_catalog.py` | Implement `retrieve_norfolk_case_study()` integration test |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| Staged data is incomplete | Audit all files before upload; document any gaps in this work chunk before proceeding |
| Staged data format doesn't match library I/O schema | Fix the data files, not the code |
| HydroShare resource not yet created | Block this work chunk until resource ID is available |

---

## Definition of Done

- [ ] All staged data files audited and verified against library I/O schemas (or fixed)
- [ ] HydroShare resource created and resource ID populated in `case_study_catalog.py`
- [ ] `src/ss_fha/examples/examples.py` implemented
- [ ] `ssfha download norfolk <dir>` works end-to-end
- [ ] Integration test passes with real HydroShare data
- [ ] Ready to hand off to Phase 6 (Norfolk HPC run)
- [ ] **Move this document to `../implemented/` once all boxes above are checked**
