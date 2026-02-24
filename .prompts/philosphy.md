## Development Philosophy

### Let's do things right, even if it takes more effort

- Assume the user is a relatively inexperience software developer
- The user wants to leverage this development project to learn software development best practices
- Always be on the lookout for better ways of achieving development goals and raise these ideas to the user 
- Look for opportunities to provide more information about programming or software-specific best practices to help guide the user's decision making
- Raise concerns when you suspect the user is making design decisions that diverge with best practices

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

## Architecture

### Key Modules

| Module | Purpose |
|--------|---------|
| `config/` | Pydantic-based configuration package (different config scripts may be needed for different parts of the process) |
| `workflow.py` | Dynamic Snakefile generation for parallel execution |
| `execution.py` | Execution strategies: SerialExecutor, LocalConcurrentExecutor, SlurmExecutor |
| `resource_management.py` | CPU/GPU/memory allocation for HPC |
| `sensitivity_analysis.py` | Parameter sweep orchestration with sub-analyses |
| `paths.py` | Dataclasses: SysPaths, AnalysisPaths, ScenarioPaths |
| `log.py` | JSON-persisted logging with LogField[T] pattern |

### Sources of inspiration

- TRITON-SWMM_toolkit
    - This is a repository for running large ensembles of hydrodynamic models. The current code base, ss-fha, is for flood hazard quantificaiton using the model outputs from that code. It deploys approaches that we can emulate and/or improve upon.
    - Examples for reference:
        - Pydantic usage: 
            - Example configuration: "D:\Dropbox\_GradSchool\repos\TRITON-SWMM_toolkit\src\TRITON_SWMM_toolkit\config\analysis.py"
            - Validation: "D:\Dropbox\_GradSchool\repos\TRITON-SWMM_toolkit\src\TRITON_SWMM_toolkit\validation.py"
        - Custom error messages: "D:\Dropbox\_GradSchool\repos\TRITON-SWMM_toolkit\src\TRITON_SWMM_toolkit\exceptions.py"
        - Example runner script: "D:\Dropbox\_GradSchool\repos\TRITON-SWMM_toolkit\src\TRITON_SWMM_toolkit\process_timeseries_runner.py"
        - Snakemake support: 
            - Snakefile generation: "D:\Dropbox\_GradSchool\repos\TRITON-SWMM_toolkit\src\TRITON_SWMM_toolkit\workflow.py"
            - Snakefile reporting: 
                - Reporting dry runs: "D:\Dropbox\_GradSchool\repos\TRITON-SWMM_toolkit\src\TRITON_SWMM_toolkit\snakemake_dry_run_report.py"
                - Parsing Snakemake rules: "D:\Dropbox\_GradSchool\repos\TRITON-SWMM_toolkit\src\TRITON_SWMM_toolkit\snakemake_snakefile_parsing.py"
        - Defining execution strategies on different systems: "D:\Dropbox\_GradSchool\repos\TRITON-SWMM_toolkit\src\TRITON_SWMM_toolkit\execution.py"
        - For creating case studies (full scale implementation) and test cases (for small scale testing):
            - For working with case data downloaded from Hydroshare: "D:\Dropbox\_GradSchool\repos\TRITON-SWMM_toolkit\src\TRITON_SWMM_toolkit\examples.py"
            - Case study creator: "D:\Dropbox\_GradSchool\repos\TRITON-SWMM_toolkit\src\TRITON_SWMM_toolkit\case_study_catalog.py"
            - Test case builder: "D:\Dropbox\_GradSchool\repos\TRITON-SWMM_toolkit\tests\fixtures\test_case_builder.py"
            - Test case catalog: "D:\Dropbox\_GradSchool\repos\TRITON-SWMM_toolkit\tests\fixtures\test_case_catalog.py"
        - Specifying system specific parameters for HPC implementation: "D:\Dropbox\_GradSchool\repos\TRITON-SWMM_toolkit\src\TRITON_SWMM_toolkit\platform_configs.py"
        - Data classes for controlling filepaths in classes: "D:\Dropbox\_GradSchool\repos\TRITON-SWMM_toolkit\src\TRITON_SWMM_toolkit\paths.py"

## Testing strategy

### Platform-Organized Tests
- This workflow is meant to be system agnostic. Toggles should be implemented in system-specific tests to ensure that running pytest on any given system only triggers tests designed to work on that system.
- `test_*.py` - Local machine tests (e.g., "D:\Dropbox\_GradSchool\repos\TRITON-SWMM_toolkit\tests\test_PC_04_multisim_with_snakemake.py")
- `test_UVA_*.py` - UVA HPC cluster tests (e.g., "D:\Dropbox\_GradSchool\repos\TRITON-SWMM_toolkit\tests\test_UVA_03_sensitivity_analysis_with_snakemake.py")
- See here for creating helper functions for running tests on specific systems: "D:\Dropbox\_GradSchool\repos\TRITON-SWMM_toolkit\tests\utils_for_testing.py"

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
- See here for examples of more complex assertion functions: "D:\Dropbox\_GradSchool\repos\TRITON-SWMM_toolkit\tests\utils_for_testing.py""