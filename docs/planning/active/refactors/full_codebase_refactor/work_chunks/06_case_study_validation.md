# Work Chunk 06: Case Study Validation and Documentation

**Phase**: 6 — Norfolk Case Study End-to-End Validation
**Last edited**: 2026-02-25

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`.prompts/philosphy.md`](../../../../../.prompts/philosphy.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: All Phases 1–5 complete.

---

## Task Understanding

### Requirements

Validate the full pipeline reproduces known-good results from the old codebase using the real Norfolk case study data. Then prepare user-facing documentation.

**This work chunk is a validation and documentation sprint, not a feature sprint.**

### Validation Steps

1. **Download Norfolk case study from HydroShare** using `ssfha download norfolk <dir>` (requires HydroShare resource ID to be populated in `case_study_catalog.py`)
2. **Run all workflows** with the Norfolk YAML config: `ssfha run norfolk_config.yaml`
3. **Compare outputs against reference values** from the old codebase:
   - Flood probability zarrs: compare return period grids against old script outputs
   - Bootstrap CIs: compare 0.05/0.5/0.95 quantile grids
   - PPCCT: compare correlation grids
   - Event return periods: compare against `d0` script outputs
4. **Fix any discrepancies** — if outputs differ, investigate root cause (algorithm port error vs. legitimate design change)
5. **Run on UVA HPC** with SLURM executor to validate HPC path

### Documentation

- Installation and quickstart guide (how to install, download data, run Norfolk case study)
- Configuration reference (all YAML fields, their types, and what they do)
- Case study notebook (Jupyter notebook showing key Norfolk results)
- Update CHANGELOG

### Tests to Add/Update

- `tests/test_end_to_end.py::test_full_pipeline` — runs with synthetic data; should already pass from Phase 4
- `tests/test_UVA_end_to_end.py` — HPC-specific full pipeline test with real data; marked to run on UVA only

### Success Criteria (from master plan Definition of Done)

- `pip install ss-fha` works in a fresh environment
- `ssfha run norfolk_config.yaml` reproduces Norfolk results (all 4 workflows)
- `ssfha run norfolk_config.yaml` works on SLURM (tested on UVA HPC)
- `pytest` passes (local and HPC, with platform-specific gating)
- Norfolk data downloadable from HydroShare
- Synthetic test case CI completes in <5 minutes
- Configuration reference documentation exists
- CHANGELOG updated

---

## Evidence from Codebase

Before implementing, inspect:

1. Old script outputs (if available) to establish reference values
2. `tests/test_UVA_end_to_end.py` — ensure it exists and is correctly gated with `skip_if_no_slurm`
3. `full_codebase_refactor.md` — review for any outstanding `#user:` comments before proceeding
4. `pyproject.toml` — verify all dependencies are listed and pinned appropriately

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `tests/test_UVA_end_to_end.py` | HPC-specific full pipeline test |
| `docs/` | User documentation (quickstart, configuration reference) |
| `notebooks/norfolk_case_study.ipynb` | Case study results notebook |
| `CHANGELOG.md` | Release notes |

### Modified Files

| File | Change |
|------|--------|
| `tests/fixtures/test_case_catalog.py` | Populate Norfolk HydroShare resource ID |
| `src/ss_fha/examples/case_study_catalog.py` | Populate `NORFOLK_HYDROSHARE_RESOURCE_ID` |
| `pyproject.toml` | Finalize all dependencies |
| `full_codebase_refactor.md` | Move to `docs/planning/completed/` when all done |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| Norfolk outputs differ from old codebase | Investigate carefully: math port error vs. intentional design change; document any intentional differences |
| HydroShare resource not yet created | Block HPC testing until resource is live; continue local testing with available data |
| UVA HPC environment differs (module versions, SLURM config) | Test on UVA; fix platform-specific issues in `platform_configs.py` |

---

## Validation Plan

```bash
# Fresh install test
pip install -e . && python -c "import ss_fha; print(ss_fha.__version__)"

# Full local run (synthetic)
pytest tests/test_end_to_end.py::test_full_pipeline -v

# Norfolk case study run
ssfha download norfolk ~/norfolk_case_study
ssfha run ~/norfolk_case_study/norfolk_config.yaml

# HPC test (on UVA Rivanna)
pytest tests/test_UVA_end_to_end.py -v

# Synthetic CI timing
time pytest tests/ -k "not slow and not UVA" -v
```

---

## Documentation and Tracker Updates

- After all outputs validated: move `full_codebase_refactor.md` from `docs/planning/active/refactors/full_codebase_refactor/` to `docs/planning/completed/`.
- Update CHANGELOG with release notes for v1.0.

---

## Definition of Done

- [ ] Norfolk case study downloads and runs end-to-end with all 4 workflows
- [ ] Outputs match old codebase reference values (or discrepancies documented and justified)
- [ ] `ssfha run norfolk_config.yaml` runs successfully on UVA SLURM
- [ ] All `pytest` tests pass (local, with platform gates)
- [ ] `tests/test_UVA_end_to_end.py` passes on UVA HPC
- [ ] Synthetic CI completes in <5 minutes
- [ ] Configuration reference documentation written
- [ ] Quickstart guide written
- [ ] CHANGELOG updated
- [ ] `full_codebase_refactor.md` moved to `docs/planning/completed/`
- [ ] All work chunk documents moved to `implemented/`
- [ ] **Move this document to `../implemented/` once all boxes above are checked**
