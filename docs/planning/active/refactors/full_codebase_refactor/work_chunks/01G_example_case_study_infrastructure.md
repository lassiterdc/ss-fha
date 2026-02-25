# Work Chunk 01G: Case Study Config Infrastructure (Local Only)

**Phase**: 1G — Foundation (Case Study Config Infrastructure)
**Last edited**: 2026-02-25

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`.prompts/philosphy.md`](../../../../../.prompts/philosphy.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: Work chunks 01A–01F complete (all Phase 1 modules importable, test infrastructure in place).

**Scope note**: HydroShare upload and the `examples.py` download infrastructure are deferred to work chunk `06A`, just before HPC testing. This chunk only creates the registry stub and config template so local development can proceed using the staging directory directly.

---

## Task Understanding

### Requirements

1. `src/ss_fha/examples/__init__.py` — package stub

2. `src/ss_fha/examples/case_study_catalog.py`:
   - Registry of available case studies with HydroShare resource IDs
   - Norfolk entry with `NORFOLK_HYDROSHARE_RESOURCE_ID = "PLACEHOLDER"` — raises a clear error if called before the ID is populated. Do not allow silent no-ops.

3. `src/ss_fha/examples/config_templates/norfolk_default.yaml` — complete YAML template with `{{placeholder}}` syntax for paths. During local development, placeholders are filled with paths into `/mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data`. On HPC, they point to the HydroShare-downloaded paths.

4. `cases/norfolk_ssfha_comparison/` — **already created in work chunk 00**. The README and all YAML files (including `norfolk_study_area.yaml`) exist. This chunk does not re-create them. Verify they are present; if any are missing, chunk 00 was not completed.

### Key Design Decisions

- **`examples.py` is not created here** — deferred to 06A. The `__init__.py` should not attempt to re-export `download_norfolk_case_study` yet.
- **Local development configs** point directly to `/mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data`. No abstraction layer is needed for this — local configs are just configs with absolute paths.
- **Staged data may be incomplete or need reformatting** — this is expected. Do not write code to tolerate malformed data; fix the data when the issue is encountered.

### Success Criteria

- `from ss_fha.examples.case_study_catalog import NORFOLK_HYDROSHARE_RESOURCE_ID` works and raises clearly if called
- `config_templates/norfolk_default.yaml` is complete and passes template filling with a test path substitution
- `cases/norfolk_ssfha_comparison/norfolk_study_area.yaml` exists (created in chunk 00) with EPSG and other Norfolk-specific parameters
- Unit tests for template filling pass without network access

---

## Evidence from Codebase

Before implementing, inspect:

1. `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/case_study_catalog.py` — registry pattern
2. `src/ss_fha/config/model.py` (01B) — verify the template YAML covers all required `SSFHAConfig` fields
3. `src/ss_fha/config/loader.py` (01B) — template filling logic; the config template uses this

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/examples/__init__.py` | Package stub (no re-exports yet — `examples.py` deferred to 06A) |
| `src/ss_fha/examples/case_study_catalog.py` | Registry with placeholder Norfolk resource ID |
| `src/ss_fha/examples/config_templates/norfolk_default.yaml` | Complete YAML template with `{{placeholder}}` syntax |

**Note**: `cases/norfolk_ssfha_comparison/README.md` and all case study YAMLs were created in work chunk 00. Do not re-create them here.

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| Config template is incomplete (missing required fields) | Verify against `SSFHAConfig` field list from 01B; a template load test will catch this |
| Template placeholder syntax clashes with YAML or Pydantic | Use `{{double_brace}}` syntax; test filling logic from 01B handles this |

---

## Validation Plan

```bash
# Template filling unit test (no network)
pytest tests/ -k "template" -v

# Smoke test: catalog imports correctly
python -c "from ss_fha.examples.case_study_catalog import NORFOLK_HYDROSHARE_RESOURCE_ID; print('OK')"

# Smoke test: cases/norfolk_ssfha_comparison config is valid YAML
python -c "import yaml; yaml.safe_load(open('cases/norfolk_ssfha_comparison/norfolk_study_area.yaml')); print('OK')"
```

---

## Documentation and Tracker Updates

- No tracking table changes (all new files).

---

## Definition of Done

- [ ] `src/ss_fha/examples/case_study_catalog.py` with Norfolk placeholder entry that raises clearly if called
- [ ] `src/ss_fha/examples/config_templates/norfolk_default.yaml` complete and verified against `SSFHAConfig`
- [ ] `cases/norfolk_ssfha_comparison/` directory and YAMLs confirmed present (created in chunk 00; this chunk does not re-create them)
- [ ] Template filling unit tests pass
- [ ] **Move this document to `implemented/` once all boxes above are checked**
