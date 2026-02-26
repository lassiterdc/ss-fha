# Work Chunk 04B: Execution Strategies, Platform Configs, and CLI

**Phase**: 4B–4D — Snakemake Workflow Integration (Execution + CLI)
**Last edited**: 2026-02-25

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`.prompts/philosphy.md`](../../../../../.prompts/philosphy.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: Work chunk 04A complete (Snakemake workflow builder and rules).

---

## Task Understanding

### Requirements

Implement execution strategy classes, platform presets, and the CLI that ties everything together.

**Files to create:**

1. `src/ss_fha/workflow/execution.py`:
   - `LocalConcurrentExecutor` — runs Snakemake with `-j N` (auto-detect or config-specified N)
   - `SlurmExecutor` — runs with `--executor slurm` (Snakemake 9.x SLURM plugin)
   - **Note**: `SerialExecutor` is removed (per master plan `#user:` decision — Snakemake handles serialization via available resources; `local_concurrent` with 1 worker is equivalent)

2. `src/ss_fha/workflow/platform_configs.py`:
   - HPC platform presets: local machine defaults, UVA Rivanna preset
   - Each preset defines default SLURM partition, memory, CPUs, etc.

3. `src/ss_fha/workflow/resource_management.py`:
   - CPU/memory allocation logic (translates config resources to Snakemake `--resources` flags)

4. `src/ss_fha/cli.py` — Typer CLI commands:
   - `ssfha run <config.yaml>` — validate config, generate Snakefile, execute
   - `ssfha validate <config.yaml>` — preflight validation only
   - `ssfha download norfolk <target_dir>` — HydroShare case study download
   - `ssfha run <config.yaml> --dry-run` — Snakemake dry run

5. `src/ss_fha/__init__.py` — update to expose `run(config_path)` programmatic API

6. `src/ss_fha/__main__.py` — CLI entry point (if not already present)

### Key Design Decisions

- **`SerialExecutor` is omitted** — the config model's `ExecutionConfig` already has `mode: Literal["local_concurrent", "slurm"]` (no `serial`). The execution module must match this.
- **`max_workers: None` → auto-detect**: use `os.cpu_count()` as the default for `local_concurrent`.
- **`ssfha run` runs `preflight_validate` before generating the Snakefile** — no silent failures.
- **SLURM plugin API**: Use `--executor slurm` (Snakemake 9.x); never use `--cluster` (legacy).
- Check `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/execution.py` for patterns.

### Success Criteria

- `ssfha run config.yaml` executes the full pipeline locally (synthetic test case)
- `ssfha validate config.yaml` reports all validation issues before execution
- `ssfha download norfolk <dir>` calls the HydroShare download infrastructure (01G)
- `ssfha run config.yaml --dry-run` reports expected rules without executing

---

## Evidence from Codebase

Before implementing, inspect:

1. `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/execution.py` — execution strategy pattern
2. `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/platform_configs.py` — platform preset pattern
3. `src/ss_fha/cli.py` — existing CLI skeleton (if any)
4. `src/ss_fha/workflow/builder.py` (04A) — `SnakemakeWorkflowBuilder.generate()` API

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/workflow/execution.py` | Executor classes |
| `src/ss_fha/workflow/platform_configs.py` | HPC platform presets |
| `src/ss_fha/workflow/resource_management.py` | Resource allocation logic |

### Modified Files

| File | Change |
|------|--------|
| `src/ss_fha/cli.py` | Add `run`, `validate`, `download` commands |
| `src/ss_fha/__init__.py` | Expose `run(config_path)` programmatic API |
| `src/ss_fha/__main__.py` | Ensure CLI entry point exists |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| SLURM plugin not installed in local environment | Guard `SlurmExecutor` construction with a check; raise clear error if plugin missing |
| `max_workers=None` on a machine where `os.cpu_count()` returns `None` | Default to `1` in that case; log a warning |
| CLI `download` command without HydroShare resource ID | Raise `ConfigurationError` with fix hint pointing to `case_study_catalog.py` |

---

## Validation Plan

```bash
# Full local pipeline run (synthetic test case)
ssfha run /tmp/ssfha_test/config.yaml

# Validation only
ssfha validate /tmp/ssfha_test/config.yaml

# Dry run
ssfha run /tmp/ssfha_test/config.yaml --dry-run

# Phase 4 validation tests
pytest tests/test_workflow.py -v

# Full end-to-end (Phase 4 definition of done)
pytest tests/test_end_to_end.py::test_full_pipeline -v
```

---

## Documentation and Tracker Updates

- Update `pyproject.toml` to add all dependencies introduced across Phases 1–4 if not already done.
- Update `full_codebase_refactor.md` Phase 4 definition of done checklist.

---

## Definition of Done

- [ ] `src/ss_fha/workflow/execution.py` implemented (no `SerialExecutor`)
- [ ] `src/ss_fha/workflow/platform_configs.py` with local and UVA presets
- [ ] `src/ss_fha/workflow/resource_management.py` implemented
- [ ] `ssfha run config.yaml` executes full pipeline on local machine
- [ ] `ssfha validate config.yaml` reports all issues before execution
- [ ] `ssfha run config.yaml --dry-run` shows rule execution plan
- [ ] `ssfha.run(config_path)` programmatic API works
- [ ] All Phase 4 tests pass
- [ ] `test_end_to_end.py::test_full_pipeline` passes locally
- [ ] **Move this document to `../implemented/` once all boxes above are checked**
