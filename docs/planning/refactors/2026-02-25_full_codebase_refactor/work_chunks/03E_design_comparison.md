# Work Chunk 03E: FHA Comparison Analysis

**Phase**: 3E — Analysis Modules (FHA Comparison)
**Last edited**: 2026-02-25

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/refactors/2026-02-25_full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; pay particular attention to the **Multi-FHA Analysis Design** section under "Four Core Workflows".
- [`CONTRIBUTING.md`](../../../../CONTRIBUTING.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: Workflow 1 outputs from all participating FHA approaches must be complete (i.e., 03A must have run for each `fha_id` being compared).

---

## Task Understanding

### Requirements

Implement Workflow 5 (FHA Comparison) — comparing flood hazard outputs across two or more FHA approaches defined by their `fha_id`.

**Replaces**: `_old_code_to_refactor/d2_compare_ensemble-based_with_design_storms.py`

**Config design** (resolved in master plan):

- Each FHA approach is a separate `SSFHAConfig` YAML with a unique `fha_id` and `fha_approach` field.
- The primary (baseline) config includes `alt_fha_analyses: list[Path]` pointing to the alternative configs.
- Validation ensures all `fha_id` values are unique.
- This workflow only runs when `toggle_fha_comparison=True`.

**FHA approach types**: `ssfha`, `bds`, `mcds`

**Files to create:**

1. `src/ss_fha/analysis/fha_comparison.py`:
   - Load Workflow 1 flood probability zarrs for baseline and each alternative
   - Compute difference maps, ratios, and spatial statistics
   - Output comparison zarrs/CSVs indexed by `(baseline_id, alt_id)` pairs

2. `src/ss_fha/runners/fha_comparison_runner.py`:
   - CLI args: `--config <primary_yaml>`, `--baseline-id <fha_id>`, `--alt-id <fha_id>`
   - Invoked once per comparison pair by Snakemake (wildcard-driven)
   - Logs completion marker

### Snakemake Design

All FHA analyses (flood hazard + uncertainty) run in parallel via the `{fha_id}` wildcard. Comparison rules depend on pairs of completed Workflow 1 outputs:

```
rule fha_comparison:
    input:
        baseline="{output_dir}/{baseline_id}/flood_probabilities/compound.zarr",
        alternative="{output_dir}/{alt_id}/flood_probabilities/compound.zarr"
    output: "{output_dir}/comparisons/{baseline_id}_vs_{alt_id}/difference.zarr"
    shell: "python -m ss_fha.runners.fha_comparison_runner --config {config} --baseline-id {wildcards.baseline_id} --alt-id {wildcards.alt_id}"
```

### MCDS Special Case

MCDS (Monte Carlo design storm) subsets from the ss_fha ensemble rather than running an independent simulation. Its bootstrap infrastructure reuses `ss_fha.core.bootstrapping` from 02B — do not duplicate.

### Success Criteria

- Comparison runner executes with two synthetic FHA outputs (different zarr values)
- Output difference maps have correct sign and magnitude (verified against hand-computed examples)
- Toggle guard prevents execution when `toggle_fha_comparison=False`
- All `fha_id` uniqueness validated at config load time

---

## Evidence from Codebase

Before implementing, inspect:

1. `_old_code_to_refactor/d2_compare_ensemble-based_with_design_storms.py` — understand what comparisons were computed
2. `src/ss_fha/config/model.py` (01B) — `SSFHAConfig.alt_fha_analyses`, `fha_id`, `fha_approach` fields
3. `src/ss_fha/analysis/flood_hazard.py` (03A) — output zarr schema that comparisons load from
4. `src/ss_fha/core/bootstrapping.py` (02B) — MCDS reuse

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/analysis/fha_comparison.py` | Multi-FHA comparison computation |
| `src/ss_fha/runners/fha_comparison_runner.py` | CLI runner (one invocation per comparison pair) |

### Modified Files

| File | Change |
|------|--------|
| `_old_code_to_refactor/d2_*.py` | Add refactoring status block |
| `src/ss_fha/workflow/rules/` | Add `fha_comparison.smk` rule file |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| Comparing zarrs with different spatial grids | Validate matching dimensions before computing differences; raise `DataError` if mismatched |
| MCDS subsetting reuses bootstrap logic | Import from `ss_fha.core.bootstrapping`; do not copy |
| Comparison pair count grows quadratically | Validate `alt_fha_analyses` count is reasonable; warn if >5 alternatives |

---

## Validation Plan

```bash
# Single comparison pair
python -m ss_fha.runners.fha_comparison_runner --config /tmp/ssfha_test/config.yaml --baseline-id ssfha_compound --alt-id ssfha_rainonly

# Integration test
pytest tests/test_end_to_end.py::test_fha_comparison -v
```

---

## Documentation and Tracker Updates

- Update `full_codebase_refactor.md` tracking table: `d2_*` → `COMPLETE`.

---

## Definition of Done

- [ ] `src/ss_fha/analysis/fha_comparison.py` implemented
- [ ] `src/ss_fha/runners/fha_comparison_runner.py` implemented (wildcard-driven, one pair per invocation)
- [ ] `fha_comparison.smk` rule file added
- [ ] Toggle guard (`toggle_fha_comparison`) in place
- [ ] `fha_id` uniqueness validated at config load
- [ ] Integration test with two synthetic FHA outputs passes
- [ ] `full_codebase_refactor.md` tracking table updated
- [ ] **Move this document to `../implemented/` once all boxes above are checked**
