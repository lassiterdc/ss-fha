## Terminology

Consistent vocabulary is critical for clear communication between developer, AI, and future readers. The following terms have precise meanings in this codebase.

### System vs. Analysis

These terms align with TRITON-SWMM_toolkit's `system_config` / `analysis_config` distinction:

| Term | Meaning | Config file pattern |
|------|---------|---------------------|
| **System** | The fixed physical and geographic context for a case study — the spatial domain, CRS, and all geospatial input files. Shared across all analyses of the same study area. | `system.yaml` |
| **Analysis** | A specific flood hazard computation layered on top of a system — the FHA method, model output inputs, weather record parameters, workflow toggles, and execution settings. Multiple analyses can share one system. | `analysis_<id>.yaml` |

**Rule**: Parameters that belong to the geographic domain go in the system config. Parameters that describe a specific computation go in the analysis config. When in doubt: if two analyses of the same study area would always share the value, it's often a system parameter; if they could differ, it's an analysis parameter.

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

### Developer-AI Communication

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

### No cruft to accomodate poorly formatted inputs

- If the case study data in the hydroshare data folder is formatted in a way that is inconvenient for analysis, the AI should make a recommendation to the developer on how to best format the data for the process. This is helpful because it could inform improvements to other prior processes, mainly stochastic weather generation and ensemble simulatoin result processing.

## Architecture

### Key Modules

| Module | Purpose |
|--------|---------|
| `config/` | Pydantic-based configuration package (different config scripts may be needed for different parts of the process) |
| `workflow.py` | Dynamic Snakefile generation for parallel execution |
| `execution.py` | Execution strategies: LocalConcurrentExecutor, SlurmExecutor (no Serial -- set max_workers=1 to serialize) |
| `resource_management.py` | CPU/GPU/memory allocation for HPC |
| `sensitivity_analysis.py` | Parameter sweep orchestration with sub-analyses |
| `paths.py` | Dataclasses: SysPaths, AnalysisPaths, ScenarioPaths |
| `log.py` | JSON-persisted logging with LogField[T] pattern |

### Sources of inspiration

- TRITON-SWMM_toolkit
    - This is a repository for running large ensembles of hydrodynamic models. The current code base, ss-fha, is for flood hazard quantificaiton using the model outputs from that code. It deploys approaches that we can emulate and/or improve upon.
    - **NOTE**: This library IS in the current environment, so if any functions or classes can be used as-is, they should be imported rather than duplicated here.
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
- `test_UVA_*.py` - UVA HPC cluster tests (e.g., "/home/dcl3nd/dev/TRITON-SWMM_toolkit/tests/test_UVA_03_sensitivity_analysis_with_snakemake.py")
- See here for creating helper functions for running tests on specific systems: "/home/dcl3nd/dev/TRITON-SWMM_toolkit/tests/utils_for_testing.py"

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