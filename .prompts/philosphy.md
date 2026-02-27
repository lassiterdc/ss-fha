## Terminology

Consistent vocabulary is critical for clear communication between developer, AI, and future readers. The following terms have precise meanings in this codebase.

### System vs. Analysis vs. Comparative Analysis

These terms align with TRITON-SWMM_toolkit's `system_config` / `analysis_config` distinction, extended with a third tier for multi-FHA comparison workflows:

| Term | Meaning | Config file pattern |
|------|---------|---------------------|
| **System** | The fixed physical and geographic context for a case study — the spatial domain, CRS, and all geospatial input files. Shared across all analyses of the same study area. | `system.yaml` |
| **Analysis** | The primary flood hazard computation for a study area — the FHA method, model output inputs, weather record parameters, event statistics configuration, workflow toggles, and execution settings. Owns the event return period calculations and may reference comparative analyses. | `analysis_<id>.yaml` |
| **Comparative analysis** | An alternative FHA approach referenced from the analysis config via `alt_fha_analyses`. Uses the same system but different model outputs, `fha_approach`, or driver configuration. Does not own event statistics or list further comparative analyses. Marked explicitly with `is_comparative_analysis: true`. | `analysis_<id>.yaml` (lighter schema) |

**Rule**: Parameters that belong to the geographic domain go in the system config. Parameters that describe a specific computation go in the analysis config. When in doubt: if two analyses of the same study area would always share the value, it's often a system parameter; if they could differ, it's an analysis parameter.

**Analysis vs. comparative analysis rules:**
- Event return period calculations (`event_statistic_variables`, `weather_event_indices`) belong to the **analysis**, never the comparative analysis. Event statistics are computed once and shared.
- A comparative analysis sets `is_comparative_analysis: true`. Validation raises an error if a comparative analysis config includes `event_statistic_variables`, `alt_fha_analyses`, or other analysis-only fields.
- An analysis with `fha_approach: ssfha` and `is_comparative_analysis: false` (the default) **requires** `event_statistic_variables` and `weather_event_indices`, regardless of whether `alt_fha_analyses` is empty.
- The distinction is explicit (`is_comparative_analysis` toggle), not inferred from schema content. This avoids silent misuse of a comparative config as a standalone analysis.

| Term | Meaning | Usage |
|------|---------|-------|
| **Combined** | A simulation that includes *both* rainfall and storm tide as flood drivers | Simulation type label — zarr filenames, `fha_id`, config fields, code variables |
| **Compound** | Flooding that is *worsened* by the simultaneous presence of multiple drivers — a phenomenon, not a simulation type | Scientific/descriptive use only (e.g., "compound flood hazard", "compound flooding") |
| **Rain-only** | A simulation that includes only the rainfall driver (surge set to a constant background level) | Simulation type label |
| **Surge-only** | A simulation that includes only the storm tide driver (rainfall excluded) | Simulation type label |
| **TRITON-only** | A simulation using the TRITON 2D model without SWMM coupling for urban drainage | Simulation type label |
| **BDS** | Basic Design Storm — a deterministic flood hazard approach using one event per return period | `fha_approach` value |
| **MCDS** | Monte Carlo Design Storm — subsets design storms from the stochastic ensemble within a CI band around a target return period | Implemented as `toggle_mcds` on SSFHA config, not as a separate `fha_approach` |
| **SSFHA** | Semicontinuous Simulation-based Flood Hazard Assessment — the primary method implemented here | `fha_approach: ssfha` |
| **event_iloc** | The canonical flat integer index uniquely identifying a single simulated event within the zarr model output. Connects simulation results to meteorological inputs via the iloc mapping CSV (e.g. `ss_event_iloc_mapping.csv`). Used as an xarray dimension name (`event_iloc`) and as a CSV column name. Not to be confused with `event_id` (the 3D sub-index within a year/event_type slice) or `event_number` (deprecated term — always use `event_iloc`). | xarray dim, CSV column, code variables |
| **ss** | When a boolean flag or branch distinguishes the semicontinuous simulation ensemble from design storms, use `ss`  — never `ensemble`. The SSFHA output *is* an ensemble, but `ensemble` is too generic and obscures the distinction from BDS. Example: `is_ss: bool` rather than `is_ensemble: bool`. Legacy uses of `ensemble` as a branch variable in ported functions should be renamed to `is_ss` during porting. | function arguments, branch variable names |

**Rule**: Never use "compound" to describe a simulation type (e.g., "compound simulation", "compound zarr"). Use "combined" instead. Use "compound" only when describing the *phenomenon* of compound flooding.

---

## About this code base:

- The primary purpose of this code base is computing flood hazard and flood hazard uncertainty using bootstrapping from 2D flood model results
- There is also ground work laid for deeper analyses into shape-file defined subareas and flood risk quantification (using road and building shapefiles) that is currently a lower priority, but the base functionality is here
- Visualizing flood hazard and flood hazard uncertainty is also a core functionality
- **Critical context**: This code base is in the middle of a refactoring documented in docs/planning/active/refactors/full_codebase_refactor.md. All code decisions and plans should:
    - Reference full_codebase_refactor.md in decisions
    - Propose changes to full_codebase_refactor.md if appropriate
    - Keep full_codebase_refactor.md up to date if any changes are made that are relevant to the document

## Development Philosophy

### Never commit without explicit permission

- All commits require prior approval from the developer

### Raise questions rather than make assumptions

- When you encounter uncertainty or discrepencies, especially when implementing a prewritten plan that my stale components, err on the side of caution and ask the developer how to proceed

### Plan, then implement

- The developer has a strong preference for a plan-then-implement strategy as outlined in .prompts/implementation_plan.md
- RISK: sometimes planning documents can become stale because of other changes, especially for larger refactors. Each plan should therefore be validated prior to implementation. If there is uncertainty or discrepancies, raise questions.
- **Sometimes implementing the plan uncovers needs to change it and/or its success criteria. This is okay but raise any discrepencies or opportunities for improvement to the developer before implementing.**

### ''#user:' prefixed statements mark developer comments that must be addressed before plan implementation

- In planning documents, all comments followed by "#user:" are meant as feedback for the AI and must ALL be addressed before any implementation can take place
    - The comments should be removed once they are addressed
    - In addressing these comments, impliciations for the entire planning document should be considered since they can yield major changes
    - The user comments can only be removed with written confirmation from the developer that the comment has been sufficiently addressed 

### Let's do things right, even if it takes more effort

- Assume the user is a relatively inexperience software developer
- The user wants to leverage this development project to learn software development best practices
- Always be on the lookout for better ways of achieving development goals and raise these ideas to the user 
- Look for opportunities to provide more information about programming or software-specific best practices to help guide the user's decision making
- Raise concerns when you suspect the user is making design decisions that diverge with best practices
- Look for opportunities to make the code more efficient (e.g., vectorize operations, be careful with loops involving pandas operations, etc.)
- Be alert for mathematical errors in probability and return period calculations

### Most function arguments should not have defaults

- Default function arguments can lead to very difficult to debug unexpected patterns so I prefer that we avoid default argument values unless a default is almost always going to be the desired choice, e.g., verbose = True. 
- This is especially true for the config files that users will populate. The user should have to make an intentional choice about every input.

### Backward compatibility is NOT a priority for this project

Rationale:
- Single developer codebase
- Better to have clean code than maintain deprecated APIs
- Refactoring should remove old patterns, not preserve them
- Git history provides access to old implementations if needed

When refactoring:
- ❌ Don't add deprecation warnings
- ❌ Don't keep old APIs "for compatibility"
- ❌ Don't create compatibility shims or aliases
- ✅ Do update all usage sites immediately
- ✅ Do delete obsolete code completely
- ✅ Do use git history if old patterns are needed later

Exception: Configuration file formats should maintain backward compatibility
where practical, since they may be versioned separately from code.

### Error handling 
- **Fail-fast**: Critical paths must raise exceptions, never silently return False
- **Preserve context**: Exceptions include file paths, return codes, log locations for actionable debugging
- Where appropriate, **Raise custom exceptions** from `exceptions.py` with full contextual attributes

### Completion Status: Log-Based Checks over File Existence

- Prefer log-based checks over file existence checks for determining processing completion
- A file may exist but be corrupt, incomplete, or from a previous failed run
- File existence checks are redundant when log checks are available and can mask errors
- Exception: File existence is appropriate for verifying *input* files before reading them

### Use Pydantic models and user-defined YAMLs for controlling inputs

### To accomodate Snakemake implementation, outputs should be generated from executing 'runner' scripts that take command line arguments to control their operation

### Robust logging in runner scripts should be directed to the stdout which will be collected by Snakemake and recorded in logfiles

### Identify project-agnostic utility candidates

- When writing or porting a function that has no domain-specific logic (no flood hydrology, no SWMM, no specific project context), add it to `docs/planning/utility_package_candidates.md` as a candidate for a future shared pip-installable package.
- This prevents the "copy from TRITON-SWMM_toolkit" anti-pattern and encourages clean reuse across projects.

### Snakemake rule generation in workflow.py should use wildcards as much as possible to keep the Snakefiles a reasonable human readable length

- It may be necessary to write loops that generate many different rules, but that should only be done if there isn't cleaner more canonical Snakemake approach to designing the rules

### No cruft

### No shims for working with poorly formatted inputs

- If the case study data in the hydroshare data folder is formatted in a way that is inconvenient for analysis, the AI should make a recommendation to the developer on how to best format the data for the process. This is helpful because it could inform improvements to other prior processes, mainly stochastic weather generation and ensemble simulatoin result processing.

### Avoid aliases whenever possible

### data type preferences

- for point, line, and polygon geospatial data, prefer geojson
- for multidimensional outputs, prefer zarr (v3) with support for netcdf

### System agnostic software

- In the codebase, there should be minimal system-specific functions
- The only exception currently to the system-agnostic philosphy is in the development testing structure that may reference hard coded local files which will likely be removed in the future once we've implemented the Hydroshare download functionality
- All system-specific information should be in user defined yaml files

### All hardcoded constants will be housed in one script

- All module-level constants (named `UPPER_SNAKE_CASE`) belong in `src/ss_fha/constants.py`
- Case-study-specific values (e.g. `n_years_synthesized`, `return_periods`, rain windows) are user YAML config values, not constants
- Do not define constants in individual modules; import from `constants.py` instead

### Type checking is handled by pyright/Pylance via `pyrightconfig.json` and `.vscode/settings.json`

- The type checking configuration lives in two files:
    - `pyrightconfig.json` — controls the pyright CLI and is also read by Pylance
    - `.vscode/settings.json` — controls Pylance-specific overrides via `python.analysis.diagnosticSeverityOverrides` (required because some Pylance settings are not exposed through `pyrightconfig.json`)
- Do not use `ty` (removed from project; too immature for production use as of early 2026)
- Resolve type errors with code changes where possible:
    - Use `.to_numpy()` instead of `.values` when `ndarray` is required (not `ExtensionArray | ndarray`)
    - Use `str(s.name)` or `str(n) for n in index.names` to narrow `Hashable | None` → `str` for Index names
    - Use `int(series.idxmin())` to narrow `int | str` when the index is guaranteed integer
    - Use `cast(pd.DataFrame, ...)` to narrow `Series | DataFrame` return types from `.loc` when the result is always a DataFrame
- Suppress whole diagnostic categories globally rather than scattering `# type: ignore` in source files
    - `pyrightconfig.json`: `reportIndexIssue = "none"`, `reportUnreachable = "none"`, `reportUnusedFunction = "none"`
    - `.vscode/settings.json` `python.analysis.diagnosticSeverityOverrides`: `reportIndexIssue: "none"`, `reportUnreachable: "none"`, `reportUnusedFunction: "none"`
    - `reportIndexIssue` covers simple pandas `.loc` / `[]` subscript overload false positives
    - `reportUnreachable` is set but does **not** fix "unreachable code" cascade hints — see cast/annotation fix below
    - `reportUnusedFunction` suppresses the "not accessed" hint on intentionally-kept private reference functions
- Fix "unreachable code" cascade hints with code changes, not suppression settings:
    - Explicitly annotate accumulator lists: `lst: list[pd.DataFrame] = []` instead of `lst = []`. Pylance infers `list[Never]` from an untyped empty list, which propagates `Never` through `pd.concat(lst)` and makes post-loop code unreachable.
    - Wrap `.loc[]` / `.apply()` calls that return `Never` with `cast(pd.DataFrame, ...)` to break the propagation chain.
- Use `# type: ignore[index]` for isolated pandas `.loc` / `pd.IndexSlice` calls where the global suppression doesn't apply. The global `reportIndexIssue: "none"` covers simple subscript complaints but **not** overload resolution failures — these still require inline suppression:
    - `groupby(cols)[col_name]` — fires `Hashable | None` overload error, not `reportIndexIssue`
    - `.loc[pd.IndexSlice[...]]` with complex tuples — fires `_IndexSliceUnion` assignment error
    - `.loc[event_idx, col_list]` where `event_idx` is a tuple — fires `tuple[...]` overload error
    - Verify each `# type: ignore[index]` is load-bearing by removing it and checking diagnostics; remove redundant ones.
- Use `# type: ignore[union-attr]` when iterating over `Hashable` (e.g., `for v in idx`) guarded by a `hasattr` check — Pylance doesn't narrow `Hashable` based on `hasattr`.
- Use `# type: ignore` without a code only as a last resort; require developer approval before adding any inline suppression

### All variables, imports, and function arguments should be used

- If you come across unused variables, imports, or function arguments, consider the possibility that implementation is incomplete. If you are uncertain, try to find the planning document(s) that touched that script and function and investigate whether implementation is complete. If you are still uncertain, raise the concern with the developer. Include references to any relevant planning documents and present hypotheses about why those unused elements are present. Make a recommendation about how to proceed.
- The only exception that will allow unused elements is if those elements are part of a currently-planned implementation. If the variable is included for a planned implementation, add a comment near the unused variable, import, or argument that includes the relative path to the planning document and the reason for its inclusion. If no planning document exists but you suspect those elements are present for future compatability, raise this with the developer and work out the details of a planning document that will leverage those variables.

### Functions all have helpful docstrings, type hints, and type checking

## Architecture

### Key Modules

| Module | Purpose |
|--------|---------|
| `constants.py` | All project-wide `UPPER_SNAKE_CASE` constants; import from here, never define constants in individual modules |
| `config/` | Pydantic-based configuration package (different config scripts may be needed for different parts of the process) |
| `workflow.py` | Dynamic Snakefile generation for parallel execution |
| `execution.py` | Execution strategies: LocalConcurrentExecutor, SlurmExecutor (no Serial -- set max_workers=1 to serialize) |
| `resource_management.py` | CPU/GPU/memory allocation for HPC |
| `sensitivity_analysis.py` | Parameter sweep orchestration with sub-analyses |
| `paths.py` | Dataclasses for organized output path management (e.g., `ProjectPaths`). Class names should reflect ss-fha's domain, not TRITON-SWMM_toolkit's names (`SysPaths`, `AnalysisPaths`, `ScenarioPaths` are reference patterns only). |
| `log.py` | JSON-persisted logging with LogField[T] pattern |

### Sources of inspiration

- TRITON-SWMM_toolkit
    - This is a repository for running large ensembles of hydrodynamic models. The current code base, ss-fha, is for flood hazard quantificaiton using the model outputs from that code. It deploys approaches that we can emulate and/or improve upon.
    - This codebase should not be considered representative of best practices, rather a representation of a design approach that worked for the user. Therefore nothing in the code base should be automatically considered 'correct'. Rather, **the code base should be considered a source to mine for good ideas**
    - **NOTE**: This library IS in the current environment, so if any functions or classes can be used as-is, they should be imported rather than duplicated here.
    - **When a TRITON-SWMM_toolkit function violates this project's design philosophy** (e.g., has default arguments that should be explicit, doesn't raise `DataError` on failure, or doesn't match the expected signature), write a fresh ss-fha implementation instead of importing. When doing so:
        1. Note the new function in `docs/planning/utility_package_candidates.md`, including which TRITON-SWMM_toolkit function it is analogous to (so the two implementations can be consolidated when a shared utility package is created).
        2. Do not add a comment in the source code referencing the toolkit — the utility candidates list is the canonical record of this relationship.
    - Examples for reference:
        - Pydantic usage: 
            - Example configuration: "/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/config/analysis.py"
            - Validation: "/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/validation.py"
        - Custom error messages: "/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/exceptions.py"
        - Example runner script: "/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/process_timeseries_runner.py"
        - Snakemake support: 
            - Snakefile generation: "/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/workflow.py"
            - Snakefile reporting: 
                - Reporting dry runs: "/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/snakemake_dry_run_report.py"
                - Parsing Snakemake rules: "/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/snakemake_snakefile_parsing.py"
        - Defining execution strategies on different systems: "/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/execution.py"
        - For creating case studies (full scale implementation) and test cases (for small scale testing):
            - For working with case data downloaded from Hydroshare: "/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/examples.py"
            - Case study creator: "/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/case_study_catalog.py"
            - Test case builder: "/home/dcl3nd/dev/TRITON-SWMM_toolkit/tests/fixtures/test_case_builder.py"
            - Test case catalog: "/home/dcl3nd/dev/TRITON-SWMM_toolkit/tests/fixtures/test_case_catalog.py"
        - Specifying system specific parameters for HPC implementation: "/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/platform_configs.py"
        - Data classes for controlling filepaths in classes: "/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/paths.py"

## Testing strategy

### Platform-Organized Tests
- This workflow is meant to be system agnostic. Toggles should be implemented in system-specific tests to ensure that running pytest on any given system only triggers tests designed to work on that system.
- `test_*.py` - Local machine tests (e.g., "/home/dcl3nd/dev/TRITON-SWMM_toolkit/tests/test_PC_04_multisim_with_snakemake.py")
- `test_HPC_slurm_*.py` - HPC cluster tests (e.g., "/home/dcl3nd/dev/TRITON-SWMM_toolkit/tests/test_UVA_03_sensitivity_analysis_with_snakemake.py") **Tests should not require a specific system. There are really 3 Snakemake patterns - local runs and slurm executor runs. Generally HPC runs will use the slurm executor, but sometimes the local run mode will be used in a large sbatch job. See TRITON-SWMM_toolkit workflow.py for more information on the 1 big job approach on HPC systems.**

### Test Fixtures

- Test fixtures should be stored in tests/conftest.py

Fixtures use `GetTS_TestCases` from `examples.py`:
```python
@pytest.fixture
def norfolk_multi_sim_analysis():
    case = tst.retrieve_norfolk_multi_sim_test_case(start_from_scratch=True)
    return case.system.analysis

@pytest.fixture
def norfolk_multi_sim_analysis_cached():
    case = tst.retrieve_norfolk_multi_sim_test_case(start_from_scratch=False)
    return case.system.analysis
```

### Use custom assertion functions where appropriate

- e.g., tests of the end-to-end workflow should be able to call a single function that asserts many things that verifies that everything has been run successfully
- See here for examples of more complex assertion functions: "/home/dcl3nd/dev/TRITON-SWMM_toolkit/tests/utils_for_testing.py""