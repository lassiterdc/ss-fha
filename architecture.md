# Architecture

Reference document for the SS-FHA codebase. Load this alongside `CONTRIBUTING.md` at the start of any AI-assisted session.

---

## Project Overview

The primary purpose of this codebase is computing flood hazard and flood hazard uncertainty using bootstrapping from 2D flood model results. There is also groundwork laid for deeper analyses into shapefile-defined subareas and flood risk quantification (using road and building shapefiles) that is currently a lower priority. Visualizing flood hazard and flood hazard uncertainty is also a core functionality.

---

## Key Modules

| Module | Purpose |
|--------|---------|
| `constants.py` | All project-wide `UPPER_SNAKE_CASE` constants; import from here, never define constants in individual modules |
| `config/` | Pydantic-based configuration package (different config scripts may be needed for different parts of the process) |
| `workflow.py` | Dynamic Snakefile generation for parallel execution |
| `execution.py` | Execution strategies: LocalConcurrentExecutor, SlurmExecutor (no Serial — set max_workers=1 to serialize) |
| `resource_management.py` | CPU/GPU/memory allocation for HPC |
| `sensitivity_analysis.py` | Parameter sweep orchestration with sub-analyses |
| `paths.py` | Dataclasses for organized output path management (e.g., `ProjectPaths`). Class names should reflect ss-fha's domain, not TRITON-SWMM_toolkit's names. |
| `log.py` | JSON-persisted logging with LogField[T] pattern |

---

## Configuration System

- **System config** (`system.yaml`): CRS and geospatial file paths only — shared across all analyses of the same study area
- **Analysis config** (`analysis_<id>.yaml`): FHA method, model inputs, weather params, toggles, execution settings
- Config flow: YAML → Pydantic model validation → typed config objects used throughout the pipeline

---

## Workflow Phases

The full pipeline is orchestrated by Snakemake via `workflow.py`:
1. Load and validate configuration (system + analysis YAMLs)
2. Compute flood hazard (event statistics, return periods)
3. Compute uncertainty via bootstrapping
4. PPCCT analysis
5. Visualization and QAQC plots
6. Flood risk quantification (future)

---

## Sources of Inspiration

### TRITON-SWMM_toolkit

This is a repository for running large ensembles of hydrodynamic models. The current codebase (ss-fha) is for flood hazard quantification using the model outputs from that code. It deploys approaches that we can emulate and/or improve upon.

**NOTE**: This library IS in the current environment at `/home/dcl3nd/dev/TRITON-SWMM_toolkit/`, so if any functions or classes can be used as-is, they should be imported rather than duplicated here.

**When a TRITON-SWMM_toolkit function violates this project's design philosophy** (e.g., has default arguments that should be explicit, doesn't raise `DataError` on failure, or doesn't match the expected signature), write a fresh ss-fha implementation instead of importing. When doing so:
1. Note the new function in `docs/planning/utility_package_candidates.md`, including which TRITON-SWMM_toolkit function it is analogous to
2. Do not add a comment in the source code referencing the toolkit — the utility candidates list is the canonical record

This codebase should not be considered representative of best practices, rather a representation of a design approach that worked. **The codebase should be considered a source to mine for good ideas.**

Reference files for patterns:
- Pydantic configuration: `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/config/analysis.py`
- Validation: `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/validation.py`
- Custom exceptions: `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/exceptions.py`
- Runner script example: `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/process_timeseries_runner.py`
- Snakefile generation: `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/workflow.py`
- Execution strategies: `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/execution.py`
- Case study/test infrastructure: `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/examples.py`, `case_study_catalog.py`
- Path management: `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/paths.py`

---

## Testing Strategy

### Platform-Organized Tests
- This workflow is meant to be system-agnostic. Toggles should be implemented in system-specific tests to ensure that running pytest on any given system only triggers tests designed to work on that system.
- `test_*.py` — Local machine tests
- `test_HPC_slurm_*.py` — HPC cluster tests (really 3 Snakemake patterns: local runs, SLURM executor runs, and local mode in a large sbatch job)

### Test Fixtures
- Test fixtures are stored in `tests/conftest.py`
- Use custom assertion functions where appropriate (e.g., end-to-end workflow tests should call a single function that verifies many things)

---

## Gotchas

- `n_years_synthesized` is 1000 for Norfolk but must never be inferred from `len(ds.year)` (which gives 954)
- `n_years_observed` (18 for Norfolk) lives inside `PPCCTConfig`, not top-level on `SsfhaConfig`
- Integer variables 156, 171, 170, 155, 140, 141 in time series NetCDFs are SWMM subcatchment IDs; ss-fha uses `mm_per_hr` (domain-wide avg rainfall intensity)
