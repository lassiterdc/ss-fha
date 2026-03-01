# Work Chunk 04A: Snakemake Workflow Builder and Rule Files

**Phase**: 4A — Snakemake Workflow Integration (Builder + Rules)
**Last edited**: 2026-02-25

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`CONTRIBUTING.md`](../../../../CONTRIBUTING.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: All Phase 3 runner scripts must be complete and tested before Snakemake rules invoke them.

---

## Task Understanding

### Requirements

Implement the Snakemake workflow builder and modular rule files. This wires all Phase 3 runners into an orchestrated, DAG-resolved pipeline.

**Snakemake version**: 9.15.0 with `snakemake-executor-plugin-slurm` 2.1.0

**Files to create:**

1. `src/ss_fha/workflow/__init__.py`
2. `src/ss_fha/workflow/builder.py` — `SnakemakeWorkflowBuilder`:
   - Generates a master Snakefile that `include:`s per-workflow rule files
   - `rule all:` assembles targets conditionally based on config toggles
   - Bootstrap fan-out: one rule per `sample_id` (0..N-1), then combine rule
   - Resource blocks for SLURM via Snakemake 9.x `resources:` directive
   - Writes Snakefile to a temporary/output directory

3. `src/ss_fha/workflow/rules/` (Snakemake rule files):
   - `flood_hazard.smk` — Workflow 1 rules (one rule per sim-type)
   - `uncertainty.smk` — Bootstrap fan-out (N sample rules) + combine rule
   - `ppcct.smk` — Workflow 3 rules (only included when `toggle_ppcct=True`)
   - `flood_risk.smk` — Workflow 4 rules (only included when `toggle_flood_risk=True`)

### Key Design Decisions

- **Single master Snakefile** with `include:` directives — canonical Snakemake 9.x approach.
- **Conditional `rule all:` targets** based on config toggles (not conditional `include:`).
- **Bootstrap fan-out**: Snakemake `expand()` generates one rule per sample_id. The combine rule depends on all sample outputs.
- **Runner script invocation pattern**: Each Snakemake rule calls `python -m ss_fha.runners.<runner> --config {config_path} [--sim-type {sim_type}] [--sample-id {sample_id}]`.
- **Log-based completion**: Snakemake rules should use `log:` directive; rules check for the completion marker in the log.
- **No `--cluster` flag** (legacy) — use `--executor slurm` plugin (Snakemake 9.x API).

Before implementing, check `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/workflow.py` for the `SnakemakeWorkflowBuilder` pattern to adopt or improve.

### Success Criteria

- `SnakemakeWorkflowBuilder(config).generate()` produces a valid master Snakefile
- `snakemake -n` (dry run) from the generated Snakefile shows correct rule execution order
- Bootstrap fan-out rules are generated correctly for `n_bootstrap_samples` samples
- Conditional targets: `toggle_ppcct=False` → no PPCCT targets in `rule all:`

---

## Evidence from Codebase

Before implementing, inspect:

1. `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/workflow.py` — builder pattern
2. Snakemake 9.15.0 documentation for `include:`, `expand()`, `resources:`, `--executor slurm` plugin
3. All Phase 3 runner script CLI signatures — these define the exact `shell:` commands in rules

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/workflow/__init__.py` | Package stub |
| `src/ss_fha/workflow/builder.py` | `SnakemakeWorkflowBuilder` |
| `src/ss_fha/workflow/rules/flood_hazard.smk` | Workflow 1 Snakemake rules |
| `src/ss_fha/workflow/rules/uncertainty.smk` | Workflow 2 (bootstrap) Snakemake rules |
| `src/ss_fha/workflow/rules/ppcct.smk` | Workflow 3 Snakemake rules |
| `src/ss_fha/workflow/rules/flood_risk.smk` | Workflow 4 Snakemake rules |
| `tests/test_workflow.py` | Snakefile generation and dry-run tests |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| Snakemake 9.x API differs from older versions used in TRITON-SWMM_toolkit | Target 9.15.0 specifically; do not use `--cluster` flag |
| Bootstrap fan-out for 500 samples generates 500 rules — Snakemake DAG may be slow to build | Test with 5 samples in unit tests; 500 is production-only |
| `include:` paths must be relative to master Snakefile location | Write rules relative to the generated Snakefile path |
| Race conditions in bootstrap fan-in | Snakemake's DAG handles this; verify with dry run |

---

## Validation Plan

```bash
# Generate Snakefile
python -c "
from ss_fha.config.loader import load_config_from_dict
from ss_fha.workflow.builder import SnakemakeWorkflowBuilder
# ... build config, generate Snakefile, print path
"

# Dry run
snakemake -n --snakefile /tmp/ssfha_test/Snakefile

# Workflow generation tests
pytest tests/test_workflow.py -v
pytest tests/test_workflow.py::test_rule_all_respects_toggles -v
pytest tests/test_workflow.py::test_bootstrap_fanout_count -v
```

---

## Documentation and Tracker Updates

- No tracking table changes (new files).
- If significant deviations from TRITON-SWMM_toolkit builder pattern are made, document in `full_codebase_refactor.md`.

---

## Definition of Done

- [ ] `src/ss_fha/workflow/builder.py` implemented
- [ ] All four `.smk` rule files created
- [ ] Generated Snakefile passes `snakemake -n` dry run
- [ ] `rule all:` correctly gates on config toggles
- [ ] Bootstrap fan-out generates correct number of rules
- [ ] `tests/test_workflow.py` passes
- [ ] **Move this document to `../implemented/` once all boxes above are checked**
