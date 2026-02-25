# Full Codebase Refactor: Interactive Scripts to System-Agnostic Library

## Task Understanding

### Requirements

1. Refactor `_old_code_to_refactor/` (~18,000 lines across 4 modules + 17 scripts) into a system-agnostic Python library (`ss_fha`)
2. Use Pydantic models + YAML configs for all user-defined inputs
3. Implement Snakemake-based workflow orchestration (`ssfha.run()` entry point)
4. Support HPC execution (particularly SLURM) for executing Snakemake
5. Create case studies using data hosted on HydroShare
6. Follow patterns from TRITON-SWMM_toolkit (config, validation, runner scripts, workflow generation, examples/test infrastructure)
    - **NOTE**: This library IS in the current environment at `/home/dcl3nd/dev/TRITON-SWMM_toolkit`. If any functions or classes can be used as-is, they should be imported rather than duplicated here.
7. Phased implementation with each phase independently testable

### Assumptions

1. The Norfolk study area is the primary (and initially only) case study
2. TRITON model outputs (zarr files) are the primary large binary inputs -- these are generated upstream by TRITON-SWMM_toolkit
3. Visualization is important but should be decoupled from the main computation pipeline. QAQC plots are an exception: they are generated as part of each runner script when `toggle_qaqc_plots=True` (the default). Tests always set `toggle_qaqc_plots=False`.
4. **Low risk**: We will use `hatchling` build system (already configured in pyproject.toml)
5. Package distribution name is `ss-fha` (PyPI/GitHub); import name is `ss_fha` (Python convention)

### Success Criteria

- `pip install ss-fha` works; `ssfha.run()` executes the full pipeline via Snakemake
- A new user can download case study data from HydroShare, configure a YAML, and reproduce the core flood hazard + uncertainty analysis
- Bootstrap sampling runs on SLURM-based HPC with configurable resource allocation
- Each phase has passing tests that validate outputs against known-good reference values
- Old scripts are fully superseded and can be archived

---

## Four Core Workflows

The software supports four somewhat independent workflows, each toggleable and independently runnable. They don't all require the same inputs.

| # | Workflow | Description | Key Inputs | Key Outputs | Dependencies |
|---|----------|-------------|------------|-------------|--------------|
| 1 | **Flood Hazard Assessment** | Empirically derived flood hazard return periods for each gridcell | TRITON simulated peak flood depth outputs, event summaries | Flood probability zarrs (return-period-indexed flood depths per gridcell) | None (foundation) |
| 2 | **Flood Hazard Uncertainty** | Bootstrap-derived flood depth confidence intervals for a range of return periods per gridcell | Flood probability outputs from Workflow 1, event-to-flood mappings | Bootstrap samples, combined CI zarrs (0.05, 0.5, 0.95 quantiles) | Workflow 1 |
| 3 | **PPCCT Validation** | Probability Plot Correlation Coefficient Test -- validates stochastically generated peak flood depth time series against observed | TRITON simulated + observed peak flood depth outputs | Pass/fail maps, p-values, PPCCT correlation grids | None (independent of Workflow 1; uses raw TRITON outputs directly) |
| 4 | **Flood Risk Assessment** | Impact assessment of flooding on buildings and roads at various depths | Flood probability outputs from Workflow 1 (optionally CIs from Workflow 2), building/road/parcel shapefiles | Impact return periods by feature type and AOI | Workflow 1 (optionally 2) |
| 5 | **FHA Comparison** | Compares flood hazard and flood risk outputs across multiple FHA approaches (e.g., ss_fha ensemble vs. design storm vs. MCDS) | Flood probability outputs from two or more FHA analyses | Difference maps, spatial statistics, ratio grids | At least two completed Workflow 1 outputs (one per approach) |

### Multi-FHA Analysis Design

A core use case is comparing flood hazard estimates across different methodologies. The design uses a **strategy pattern**: each FHA approach is defined as an independent analysis config with a unique `fha_id`, and a comparison config references the baseline and alternatives by their IDs.

**FHA approach types** (`fha_approach` field):
- `ssfha` — the full stochastic ensemble approach implemented here
- `bds` — basic design storm (single deterministic event per return period)
- `mcds` — Monte Carlo design storm (subsets of the ssfha ensemble, with its own uncertainty approach)

**Config structure:**

The primary `SSFHAConfig` YAML defines the baseline analysis. An optional `alt_fha_analyses` field accepts a list of paths to alternative FHA config YAMLs. Each alternative YAML has the same schema as the primary config but specifies different input datasets, a different `fha_approach`, and a unique `fha_id`.

```yaml
# Primary analysis YAML (defines the baseline)
fha_id: ssfha_compound
fha_approach: ssfha
triton_outputs:
  compound: path/to/compound.zarr
# ... rest of config ...

# Optional: list of alternative analyses to compare against baseline
alt_fha_analyses:
  - path/to/rainonly_config.yaml    # fha_id: ssfha_rainonly, fha_approach: ssfha
  - path/to/surgeonly_config.yaml   # fha_id: ssfha_surgeonly
  - path/to/design_storm_config.yaml  # fha_id: bds_100yr, fha_approach: bds
  - path/to/mcds_config.yaml          # fha_id: mcds, fha_approach: mcds
```

Alternative config YAMLs **inherit** all fields from the primary config except: `fha_id`, `fha_approach`, `triton_outputs`, and approach-specific parameters. Validation ensures all `fha_id` values are unique across primary and alternatives.

**Snakemake wildcard design:**

The `{fha_id}` wildcard drives all flood hazard and uncertainty rules, enabling all analyses to run in parallel. Comparison rules depend on two or more `{fha_id}` outputs and run after the independent analyses complete.

```
# All FHA analyses run in parallel via wildcard
rule flood_hazard:
    input: lambda w: fha_configs[w.fha_id].triton_outputs.compound
    output: "{output_dir}/{fha_id}/flood_probabilities/compound.zarr"

# Comparison only runs after both baseline and alternative are done
rule fha_comparison:
    input:
        baseline="{output_dir}/{baseline_id}/flood_probabilities/compound.zarr",
        alternative="{output_dir}/{alt_id}/flood_probabilities/compound.zarr"
    output: "{output_dir}/comparisons/{baseline_id}_vs_{alt_id}/difference.zarr"
```

This design does not lock in any specific set of comparisons — any combination of FHA approaches can be added by providing additional config YAMLs.

### Snakemake Architecture: Single Workflow with Modular Includes

One master Snakefile composes all four workflows using `include:` directives. This is the canonical Snakemake 9.x approach:

```
workflow/
    Snakefile                      # Master: rule all with conditional targets
    rules/
        flood_hazard.smk           # Workflow 1 rules
        uncertainty.smk            # Workflow 2 rules (bootstrap parallelization)
        ppcct.smk                  # Workflow 3 rules
        flood_risk.smk             # Workflow 4 rules
```

**`rule all:`** dynamically assembles targets based on config toggles:
```python
rule all:
    input:
        # Always: flood hazard
        expand("{output}/flood_probs/{sim_type}.zarr", ...),
        # Conditional: uncertainty
        expand("{output}/bootstrap/cis.zarr", ...) if config["toggle_uncertainty"] else [],
        # Conditional: PPCCT
        expand("{output}/ppcct/results.zarr", ...) if config["toggle_ppcct"] else [],
        # Conditional: flood risk
        expand("{output}/risk/impact_rps.zarr", ...) if config["toggle_flood_risk"] else [],
```

**Why single Snakefile:**
- Snakemake's DAG naturally resolves cross-workflow dependencies (Workflow 2 depends on 1's outputs)
- Users can still run subsets: `snakemake --until flood_hazard_complete` or specific target files
- Config toggles control what runs -- disabled workflows simply produce no targets
- No manual orchestration or file-existence checks at workflow boundaries

**Why `include:` modules:** Each workflow's rules live in their own `.smk` file for clean code organization, but are composed into one DAG.

---

## Evidence from Codebase

### Old Code Structure (`_old_code_to_refactor/`)

- **`__inputs.py`** (369 lines): Central config -- all file paths, constants, return periods, depth thresholds, CRS. This becomes the Pydantic config model.
- **`__utils.py`** (3,072 lines, 50+ functions): Core computation -- CDF/return periods, bootstrapping, geospatial operations, multivariate statistics, I/O. Needs splitting into domain modules.
- **`__plotting.py`** (4,423 lines, 40+ functions): Visualization suite. Can be migrated largely intact as its own subpackage.
- **15 scripts** (alphabetically ordered phases B through H; A-phase design storm scripts excluded): Sequential workflow from flood probability, bootstrapping, event statistics, through comparison analyses.

### Key Observations

- **Hardcoded paths everywhere**: `__inputs.py` defines paths using string concatenation from a root directory. Needs full replacement with Pydantic path management.
- **No separation of I/O from computation**: Functions in `__utils.py` mix data loading, computation, and writing. These need separation for testability.
- **Bootstrap loop is the HPC bottleneck**: `c1` generates 500 bootstrap samples, each computing return periods across the full spatial grid. This is the primary parallelization target.
- **Heavy xarray/dask dependency**: All spatial data uses xarray with zarr backing. Dask chunking is already used in places but not systematically.
- **Event-number mapping is fragile**: Several scripts depend on CSV files that map event indices between different datasets. This should be formalized.

### TRITON-SWMM_toolkit Patterns to Adopt

- **Pydantic config with toggle-based validation** (analysis.py pattern)
- **Two-layer validation**: Pydantic for types + separate `validation.py` for business logic
- **Runner scripts as subprocess entry points** with argparse, memory profiling, log-based verification
- **`SnakemakeWorkflowBuilder`** class for dynamic Snakefile generation
- **`examples.py` + `case_study_catalog.py`** pattern for HydroShare data download and case study management. Keep as two separate files: `examples.py` handles *how* to download; `case_study_catalog.py` is the *registry* of what is available. This clean boundary is worth maintaining from the start even with one case study.
- **`paths.py` dataclasses** for organized file path management
- **`execution.py`** strategy pattern for LocalConcurrent/SLURM execution (no Serial mode -- Snakemake handles serialization via available resources when `max_workers=1`)
- **Deferred validation** with `ValidationResult` accumulating all issues before raising

### Current Repo State

- Skeleton project with hatchling build, typer CLI, empty `utils.py`, placeholder test
- Sphinx docs scaffolding (could migrate to mkdocs later but not a priority now)
- `src/ss_fha/` layout already established
- Snakemake 9.15.0 with `snakemake-executor-plugin-slurm` 2.1.0 in environment

---

## Implementation Strategy

### Chosen Approach: Bottom-Up Module Extraction with Snakemake Wrapping

Build the library from the foundation up: config/paths first, then pure computation modules, then runner scripts, then Snakemake orchestration. Each layer is testable independently before the next is added.

### Alternatives Considered

1. **Top-down (Snakemake first, fill in rules)**: Rejected -- hard to test without working computation modules
2. **Script-by-script port (convert each old script)**: Rejected -- perpetuates the monolithic structure; each script mixes I/O, computation, and plotting
3. **Parallel module development**: Rejected -- too many interdependencies to develop simultaneously without a stable config/paths foundation

### Trade-offs

- Bottom-up means the end-to-end workflow isn't runnable until later phases, but each intermediate phase produces testable, useful artifacts
- We invest heavily in config/paths/test infrastructure upfront, which delays "visible" computation work but pays off in every subsequent phase

---

## Target Architecture

```
src/ss_fha/
    __init__.py                    # Public API: run(), version
    __main__.py                    # CLI entry point
    cli.py                         # Typer CLI (run, validate, download-data, etc.)
    exceptions.py                  # Custom exception hierarchy

    config/
        __init__.py
        model.py                   # Pydantic config model (replaces __inputs.py)
        defaults.py                # Default constants (return periods, thresholds, CRS, etc.)
        loader.py                  # YAML loading, template filling, config instantiation

    validation.py                  # Business logic validation (beyond Pydantic type checks)
    paths.py                       # Path dataclasses: ProjectPaths, AnalysisPaths, BootstrapPaths

    io/
        __init__.py
        zarr_io.py                 # Zarr read/write with encoding configs
        netcdf_io.py               # NetCDF read/write with compression
        gis_io.py                  # Shapefile/raster loading and masking

    core/
        __init__.py
        flood_probability.py       # CDF computation, return periods, plotting positions
        bootstrapping.py           # Bootstrap sampling, combining, quantile analysis
        return_periods.py          # Univariate/multivariate event return periods
        geospatial.py              # Masking, rasterization, feature impact computation

    analysis/
        __init__.py
        flood_hazard.py            # Workflow 1: flood probability from TRITON outputs
        uncertainty.py             # Workflow 2: bootstrap confidence intervals
        ppcct.py                   # Workflow 3: probability plot correlation coefficient test
        flood_risk.py              # Workflow 4: impact assessment (buildings, roads, AOIs)
        event_comparison.py        # Event return period statistics (supports Workflows 1, 4)
        design_comparison.py       # Ensemble vs design storm comparison (optional analysis)

    runners/
        __init__.py
        flood_hazard_runner.py     # Snakemake-invoked: compute flood probabilities
        bootstrap_runner.py        # Snakemake-invoked: single bootstrap sample (parallelizable)
        bootstrap_combine_runner.py  # Snakemake-invoked: combine bootstrap results
        ppcct_runner.py            # Snakemake-invoked: PPCCT validation
        flood_risk_runner.py       # Snakemake-invoked: impact analysis
        event_stats_runner.py      # Snakemake-invoked: compute event return periods

    workflow/
        __init__.py
        builder.py                 # SnakemakeWorkflowBuilder (dynamic Snakefile generation)
        rules/                     # Modular Snakemake rule files
            flood_hazard.smk       # Workflow 1 rules
            uncertainty.smk        # Workflow 2 rules (bootstrap fan-out/fan-in)
            ppcct.smk              # Workflow 3 rules
            flood_risk.smk         # Workflow 4 rules
        execution.py               # SerialExecutor, LocalConcurrentExecutor, SlurmExecutor
        platform_configs.py        # HPC platform presets (local, UVA, etc.)
        resource_management.py     # CPU/memory allocation logic

    visualization/
        __init__.py
        flood_maps.py              # Spatial flood depth/probability maps
        probability_curves.py      # CDF, return period, depth-probability curves
        comparison_plots.py        # Ensemble vs design, event vs flood return
        impact_plots.py            # Feature impact, AOI analysis plots
        helpers.py                 # Colorbars, tick formatting, subplot labels

    examples/
        __init__.py
        examples.py                # HydroShare download, case study loading
        case_study_catalog.py      # Available case studies registry
        config_templates/          # YAML templates with {{placeholders}}
            norfolk_default.yaml

cases/
    norfolk/                       # Norfolk-specific parameters not on HydroShare
        norfolk_study_area.yaml    # e.g., crs_epsg: 32147, study area bounds

tests/
    conftest.py                    # Shared fixtures, platform detection
    fixtures/
        __init__.py
        test_case_builder.py       # Synthetic test data generation (matches HydroShare structure)
        test_case_catalog.py       # Test case registry
        reference_data/            # Small known-good reference outputs for validation
    test_config.py                 # Config loading, validation, defaults
    test_paths.py                  # Path resolution, directory creation
    test_flood_probability.py      # Core CDF/return period math
    test_bootstrapping.py          # Bootstrap sampling logic
    test_event_statistics.py       # Event return period computation
    test_geospatial.py             # Masking, rasterization
    test_io.py                     # Zarr/NetCDF/shapefile I/O
    test_workflow.py               # Snakefile generation, validation
    test_end_to_end.py             # Full pipeline test (local only)
    test_UVA_end_to_end.py         # HPC-specific tests
    utils_for_testing.py           # Platform detection, assertion helpers
```

---

## Tracking Refactored Code in Old Codebase

As modules are extracted from the old code, we track progress by adding a comment block at the top of each old file indicating refactoring status. This provides a clear audit trail and prevents accidentally re-porting already-migrated code.

**Format** (added to top of each old file as it's refactored):

```python
# =============================================================================
# REFACTORING STATUS: [COMPLETE | PARTIAL | NOT STARTED]
#
# Migrated to:
#   - ss_fha.core.flood_probability (functions: compute_emp_cdf_and_return_pds, ...)
#   - ss_fha.core.bootstrapping (functions: prepare_for_bootstrapping, ...)
#
# Remaining (not yet migrated):
#   - compute_flood_impact_return_periods() → planned for Phase 3F
#
# Last updated: YYYY-MM-DD
# =============================================================================
```

Additionally, maintain a tracking table in this planning document (updated after each phase):

| Old File | Status | Migrated To | Phase |
|----------|--------|------------|-------|
| `__inputs.py` | NOT STARTED | `config/model.py`, `config/defaults.py`, `paths.py` | 1 |
| `__utils.py` | NOT STARTED | `core/*`, `io/*` | 2 |
| `__plotting.py` | NOT STARTED | `visualization/*` | 5 |
| `b1_analyze_triton_outputs_fld_prob_calcs.py` | NOT STARTED | `analysis/flood_hazard.py` | 3A |
| `b2b_sim_vs_obs_flod_ppct.py` | NOT STARTED | `analysis/ppcct.py` | 3D |
| `b2c_sim_vs_obs_fld_ppct.py` | NOT STARTED | `analysis/ppcct.py` | 3D |
| `b2d_sim_vs_obs_fld_ppct.py` | NOT STARTED | `analysis/ppcct.py` + `visualization/` | 3D, 5 |
| `c1_fpm_confidence_intervals_bootstrapping.py` | NOT STARTED | `analysis/uncertainty.py` | 3B |
| `c1b_fpm_confidence_intervals_bootstrapping.py` | NOT STARTED | `analysis/uncertainty.py` | 3B |
| `c2_fpm_confidence_intervals.py` | NOT STARTED | `analysis/uncertainty.py` + `visualization/` | 3B, 5 |
| `d0_computing_event_statistic_probabilities.py` | NOT STARTED | `analysis/event_comparison.py` | 3C |
| `d2_compare_ensemble-based_with_design_storms.py` | NOT STARTED | `analysis/design_comparison.py` | 3E |
| `e2_investigating_flood_depth_area_probability.py` | NOT STARTED | `analysis/flood_hazard.py` + `visualization/` | 3A, 5 |
| `f1_box_and_whiskers_event_rtrn_vs_fld_rtrn.py` | NOT STARTED | `analysis/flood_risk.py` | 3F |
| `f2_comparing_event_and_flood_prob_by_aoi.py` | NOT STARTED | `analysis/flood_risk.py` | 3F |
| `h_experiment_design_figures.py` | NOT STARTED | `visualization/` (low priority) | 5 |
| `b2_sim_vs_obs_fld_ppct.py` | NOT STARTED | Minor QA/QC, likely absorbed into ppcct.py | 3D |
| `_qaqc_verifying_function_of_bndry_cndtn.py` | NOT STARTED | Minor QA/QC utility | TBD |

---

## Phased Implementation Plan

### Phase 0: Input Data Inventory and Local Data Staging

**Goal**: Identify every external input file and stage it locally. HydroShare upload and download infrastructure are deferred until just before HPC testing (see Phase 6A).

**Local staging directory**: `/mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data`

This directory holds data *intended* for eventual HydroShare upload. It may be incomplete or require reformatting as implementation progresses — this is expected. **Do not create compatibility shims or workarounds to accommodate poorly formatted input data.** If a file's format needs to change, change the file. The canonical input format is whatever the library's I/O layer expects, not whatever was convenient at the time the data was originally produced.

**All case-study-specific data will eventually go to HydroShare** (nothing committed to git). Synthetic test data is generated programmatically in tests and must match the HydroShare data structure. During local development, configs point directly to the local staging directory; on HPC, they point to the downloaded HydroShare data.

**External Input Files Required** (based on `__inputs.py` and script analysis, design storm scripts excluded):

| File | Type | Size Category | Source | Used By Workflow(s) |
|------|------|--------------|--------|---------------------|
| TRITON simulation peak flood depth outputs (compound) | Zarr | Large (multi-GB) | TRITON-SWMM_toolkit | 1, 2, 4 |
| TRITON simulation peak flood depth outputs (surge-only) | Zarr | Large | TRITON-SWMM_toolkit | 1, 2 |
| TRITON simulation peak flood depth outputs (rain-only) | Zarr | Large | TRITON-SWMM_toolkit | 1, 2 |
| TRITON-only simulation peak flood depth outputs | Zarr | Large | TRITON-SWMM_toolkit | 1, 2 |
| TRITON observed event peak flood depth outputs | Zarr | Large | TRITON-SWMM_toolkit | 3 |
| TRITON design storm peak flood depth outputs | Zarr | Large | TRITON-SWMM_toolkit | Design comparison |
| Simulation event summaries CSV | CSV | Small (~100KB) | TRITON-SWMM_toolkit | 1, 2, 3 |
| Observed event summaries CSV | CSV | Small (~100KB) | TRITON-SWMM_toolkit | 3 |
| Simulation time series (per-event rainfall, water level) | NetCDF/Zarr | Medium-Large | TRITON-SWMM_toolkit | Event statistics |
| NOAA tide gage data (water level + surge) | CSV | Small-Medium | NOAA Tides & Currents | Event statistics |
| Empirical rainfall return period curves | CSV | Small | Computed from ensemble | Event statistics |
| Empirical water level return period curves | CSV | Small | Computed from ensemble | Event statistics |
| Watershed boundary shapefile | Shapefile | Small | User-defined | 1, 2, 3, 4 |
| AOI (area of interest) shapefile | Shapefile | Small | User-defined | 4 |
| Roads shapefile (clipped to study area) | Shapefile | Small-Medium | User-defined | 4 |
| Buildings shapefile | Shapefile | Small-Medium | User-defined | 4 |
| Parcels shapefile | Shapefile | Small-Medium | User-defined | 4 |
| Sidewalks shapefile | Shapefile | Small-Medium | User-defined | 4 |
| FEMA 100-yr flood depth raster | GeoTIFF | Medium | FEMA NFHL | 4 (comparison) |
| Event classification table | CSV | Small-Medium | Computed from event summaries | Event statistics |
| Constant head boundary condition value | Scalar (in config) | N/A | From TRITON-SWMM_toolkit | Config |

**HydroShare Resource Organization** (suggested):
```
ss-fha-norfolk-case-study/
    triton_outputs/
        triton_tritonswmm_allsims_compound.zarr/
        triton_tritonswmm_allsims_surgeonly.zarr/
        triton_tritonswmm_allsims_rainonly.zarr/
        triton_allsims.zarr/
        triton_observed.zarr/
        triton_design_storms.zarr/
    event_data/
        event_summaries_sim.csv
        event_summaries_obs.csv
        event_classification.csv
        simulation_timeseries/  (or a single consolidated NetCDF)
        tide_gage_data.csv
        empirical_rainfall_return_periods.csv
        empirical_water_level_return_periods.csv
    geospatial/
        watershed.shp (+ .shx, .dbf, .prj)
        aoi.shp (+ companions)
        roads_clipped.shp (+ companions)
        buildings.shp (+ companions)
        parcels.shp (+ companions)
        sidewalks.shp (+ companions)
        fema_100yr_depths_m.tif
```

**Test data strategy**: Synthetic test data is generated programmatically in `tests/fixtures/test_case_builder.py`. The builder creates xarray Datasets, DataFrames, and GeoDataFrames that match the structure (dimensions, variables, dtypes, coordinate names) of the real HydroShare data. This ensures that code tested against synthetic data will also work with real case study data. Suggested test dimensions: 10x10 grid, 10 events, 5 bootstrap samples.

---

### Phase 1: Foundation (Config, Paths, Exceptions, I/O, Test Infrastructure)

**Goal**: Establish the project skeleton so that every subsequent phase has a stable config system, path management, I/O layer, and test infrastructure to build on.

#### Phase 1A: Exceptions and Constants

**Files to create:**
- `src/ss_fha/exceptions.py` -- Custom exception hierarchy following TRITON-SWMM_toolkit pattern:
  - `SSFHAError` (base)
  - `ConfigurationError` (field, config_path, message)
  - `DataError` (operation, filepath, reason) -- for missing/corrupt data
  - `BootstrapError` (sample_id, reason) -- bootstrap-specific failures
  - `WorkflowError` (phase, stderr) -- Snakemake failures
  - `ValidationError` (issues list) -- accumulated validation failures
- `src/ss_fha/config/defaults.py` -- Analysis-method defaults only (no case-study-specific values):
  - `DEFAULT_RETURN_PERIODS = [1, 2, 10, 100]`
  - `DEFAULT_DEPTH_THRESHOLDS_M = [0.03, 0.10, 0.30, 1.00]`
  - `DEFAULT_N_BOOTSTRAP_SAMPLES = 500`
  - `DEFAULT_PLOTTING_POSITION_METHOD = "weibull"`
  - Variable name mappings, etc.
  - **Not included**: `DEFAULT_CRS_EPSG` (case-study-specific; goes in `cases/norfolk/`) and `synthetic_years` (derived from weather data record length, not user-configured)
- `cases/norfolk/norfolk_study_area.yaml` -- Norfolk-specific parameters not in HydroShare (e.g. `crs_epsg: 32147`). This directory is the home for anything case-study-specific that isn't committed to HydroShare.

**Tests:**
- `test_config.py::test_defaults_are_accessible` -- import and verify defaults exist with expected types

#### Phase 1B: Pydantic Configuration Model

**Files to create:**
- `src/ss_fha/config/model.py` -- Main Pydantic config model

The config model captures everything from `__inputs.py` in a structured, validated form. The toggle pattern controls which workflows are enabled and which input sections are required.

```python
class SSFHAConfig(BaseModel):
    """Top-level configuration for ss-fha analysis.

    Each config defines one FHA approach (one fha_id). To compare multiple
    approaches, set alt_fha_analyses to a list of paths to additional configs.
    The config that defines alt_fha_analyses is treated as the baseline.
    """

    # Analysis identity
    fha_id: str                          # Unique ID for this FHA approach (e.g. "ssfha_compound")
    fha_approach: Literal["ssfha", "bds", "mcds"]

    # Project identification
    project_name: str
    description: str = ""

    # Core paths
    project_dir: Path                    # Root working directory
    data_dir: Path | None = None         # Optional: override default data location
    output_dir: Path | None = None       # Optional: override default output location

    # Study area parameters (no default -- must be specified explicitly per study area)
    crs_epsg: int

    # Analysis parameters
    return_periods: list[float] = DEFAULT_RETURN_PERIODS
    depth_thresholds_m: list[float] = DEFAULT_DEPTH_THRESHOLDS_M
    n_bootstrap_samples: int = DEFAULT_N_BOOTSTRAP_SAMPLES
    # NOTE: n_years (synthetic record length) is derived from event data, not user-specified
    plotting_position_method: Literal["weibull", "stendinger"] = DEFAULT_PLOTTING_POSITION_METHOD

    # Input file references (relative to data_dir or absolute)
    triton_outputs: TritonOutputsConfig
    event_data: EventDataConfig
    geospatial: GeospatialConfig

    # Workflow toggles
    # Workflow 1 (flood hazard) is always enabled -- it's the foundation
    toggle_uncertainty: bool = True        # Workflow 2
    toggle_ppcct: bool = False             # Workflow 3
    toggle_flood_risk: bool = False        # Workflow 4
    toggle_qaqc_plots: bool = True         # Generate QAQC plots during runner execution (set False in tests)

    # Conditional config sections (required when toggle is True)
    ppcct: PPCCTConfig | None = None
    flood_risk: FloodRiskConfig | None = None

    # Optional: compare this (baseline) analysis against alternative FHA approaches
    toggle_fha_comparison: bool = False
    alt_fha_analyses: list[Path] | None = None   # Required when toggle_fha_comparison=True

    # Execution configuration
    execution: ExecutionConfig
```

With sub-models:

```python
class TritonOutputsConfig(BaseModel):
    """Paths to TRITON peak flood depth outputs for one FHA approach."""
    compound: Path                         # Always required (primary simulation type)
    observed: Path | None = None           # Required when toggle_ppcct=True

class EventDataConfig(BaseModel):
    sim_event_summaries: Path
    obs_event_summaries: Path | None = None   # Required when toggle_ppcct=True
    event_classification: Path | None = None
    sim_timeseries_dir: Path | None = None    # Required when toggle_event_comparison=True

class GeospatialConfig(BaseModel):
    watershed: Path                            # Always required (spatial mask)
    aoi: Path | None = None                    # Required when toggle_flood_risk=True

class PPCCTConfig(BaseModel):
    """Configuration specific to PPCCT validation (Workflow 3)."""
    n_bootstrap_samples: int = 500             # Can differ from main bootstrap count
    alpha: float = 0.05                        # Significance level

class FloodRiskConfig(BaseModel):
    """Configuration specific to flood risk assessment (Workflow 4)."""
    roads: Path | None = None
    buildings: Path | None = None
    parcels: Path | None = None
    sidewalks: Path | None = None
    fema_raster: Path | None = None

class ExecutionConfig(BaseModel):
    mode: Literal["local_concurrent", "slurm"] = "local_concurrent"
    max_workers: int | None = None     # None = auto-detect CPU count
    slurm: SlurmConfig | None = None

class SlurmConfig(BaseModel):
    partition: str
    account: str
    time_limit: str = "02:00:00"
    mem_per_cpu: str = "4G"
    cpus_per_task: int = 1
    nodes: int = 1
```

**Toggle validation** (via `@model_validator`): When `toggle_ppcct=True`, validates that `ppcct` config is provided AND `triton_outputs.observed` is set AND `event_data.obs_event_summaries` is set. Similar for other toggles. Errors accumulate before raising.

- `src/ss_fha/config/loader.py` -- YAML loading with template support:
  - `load_config(yaml_path: Path) -> SSFHAConfig`
  - `load_config_from_dict(d: dict) -> SSFHAConfig`
  - Template placeholder filling (like TRITON-SWMM_toolkit `examples.py`)

**Tests:**
- `test_config.py::test_minimal_config_loads` -- Load a minimal valid YAML (Workflow 1 only)
- `test_config.py::test_config_validates_required_fields` -- Missing required fields raise `ConfigurationError`
- `test_config.py::test_toggle_dependencies` -- When `toggle_ppcct=True`, `ppcct` config + observed data paths must be provided
- `test_config.py::test_path_resolution` -- Relative paths resolve against `project_dir`/`data_dir`
- `test_config.py::test_defaults_applied` -- Unspecified optional fields get default values
- `test_config.py::test_workflow1_only_minimal_inputs` -- Verify minimal config for just flood hazard

**Note on end-to-end tests**: Phase 1F (test infrastructure) builds `build_minimal_test_case()` which is the synthetic fixture for all integration tests. Phase 6 (case study validation) runs the full Norfolk pipeline and compares against old-codebase reference outputs. Passing `test_end_to_end.py` with synthetic data is the gate before HPC testing; passing `test_UVA_end_to_end.py` with real data is the gate before publication.

#### Phase 1C: Path Management

**Files to create:**
- `src/ss_fha/paths.py` -- Path dataclasses:

```python
@dataclass
class ProjectPaths:
    """Resolved paths for the entire project."""
    project_dir: Path
    data_dir: Path
    output_dir: Path
    logs_dir: Path

    # Workflow 1: Flood hazard
    flood_probs_dir: Path         # output_dir / "flood_probabilities"

    # Workflow 2: Uncertainty
    bootstrap_dir: Path           # output_dir / "bootstrap"
    bootstrap_samples_dir: Path   # bootstrap_dir / "samples"

    # Workflow 3: PPCCT
    ppcct_dir: Path               # output_dir / "ppcct"

    # Workflow 4: Flood risk
    flood_risk_dir: Path          # output_dir / "flood_risk"

    # Shared
    event_stats_dir: Path         # output_dir / "event_statistics"
    figures_dir: Path             # output_dir / "figures"

    @classmethod
    def from_config(cls, config: SSFHAConfig) -> "ProjectPaths":
        ...

    def ensure_dirs_exist(self) -> None:
        """Create all output directories."""
        ...
```

**Tests:**
- `test_paths.py::test_paths_from_config` -- Paths resolve correctly from config
- `test_paths.py::test_ensure_dirs_creates_directories` -- Directories created in temp dir

#### Phase 1D: I/O Layer

Before writing any I/O function, check `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/` for reusable utilities to import rather than duplicate. Any function identified as project-agnostic (useful beyond ss_fha and TRITON-SWMM_toolkit) should be noted in `docs/planning/utility_package_candidates.md` for potential extraction into a shared pip-installable package.

**Files to create:**
- `src/ss_fha/io/__init__.py`
- `src/ss_fha/io/zarr_io.py` -- Extract from `__utils.py`:
  - `write_zarr(ds, path, encoding=None, overwrite=False)`
  - `read_zarr(path, chunks=None) -> xr.Dataset`
  - `delete_zarr(path, timeout_s=30)`
  - `default_zarr_encoding(ds) -> dict`
- `src/ss_fha/io/netcdf_io.py`:
  - `write_compressed_netcdf(ds, path, encoding=None)`
  - `read_netcdf(path) -> xr.Dataset`
- `src/ss_fha/io/gis_io.py`:
  - `read_shapefile(path) -> gpd.GeoDataFrame`
  - `create_mask_from_shapefile(shapefile_path, reference_ds, crs_epsg) -> xr.DataArray`
  - `rasterize_features(gdf, reference_ds, field=None) -> xr.DataArray`

**Tests:**
- `test_io.py::test_zarr_roundtrip` -- Write and read back an xarray Dataset
- `test_io.py::test_netcdf_roundtrip` -- Same for NetCDF
- `test_io.py::test_zarr_encoding_defaults` -- Verify encoding dict structure
- Tests use synthetic xarray datasets (no HydroShare data needed)

#### Phase 1E: Validation Layer

**Files to create:**
- `src/ss_fha/validation.py` -- Following TRITON-SWMM_toolkit pattern:
  - `ValidationResult` dataclass with `is_valid`, `raise_if_invalid()`, `merge()`
  - `ValidationIssue` with field, message, current_value, fix_hint
  - `validate_config(config: SSFHAConfig) -> ValidationResult`
  - `validate_input_files(config: SSFHAConfig) -> ValidationResult` -- check that referenced files exist
  - `validate_workflow_inputs(config: SSFHAConfig) -> ValidationResult` -- per-workflow input completeness
  - `preflight_validate(config: SSFHAConfig) -> ValidationResult` -- all checks combined

**Tests:**
- `test_config.py::test_validation_missing_input_files` -- Reports missing files with fix hints
- `test_config.py::test_validation_accumulates_errors` -- Multiple issues reported together
- `test_config.py::test_validation_per_workflow` -- Workflow 3 validation catches missing observed data

#### Phase 1F: Test Infrastructure

**Files to create:**
- `tests/conftest.py` -- Shared fixtures:
  - `tmp_project_dir` -- Temporary directory with expected structure
  - `minimal_config` -- Smallest valid SSFHAConfig using synthetic data (Workflow 1 only)
  - `full_config` -- Config with all workflows enabled
  - `synthetic_flood_dataset` -- Small xarray Dataset mimicking TRITON output structure
- `tests/fixtures/__init__.py`
- `tests/fixtures/test_case_builder.py`:
  - `build_synthetic_triton_output(n_events=10, nx=10, ny=10) -> xr.Dataset` -- Matches real zarr structure
  - `build_synthetic_observed_output(n_events=5, nx=10, ny=10) -> xr.Dataset`
  - `build_synthetic_event_summaries(n_events) -> pd.DataFrame`
  - `build_synthetic_watershed(nx, ny, crs_epsg) -> gpd.GeoDataFrame`
  - `build_minimal_test_case(tmp_path) -> SSFHAConfig` -- Creates config + all synthetic data files on disk
- `tests/fixtures/test_case_catalog.py`:
  - `retrieve_norfolk_case_study(start_from_scratch=True)` -- Downloads from HydroShare (integration test only)
- `tests/utils_for_testing.py`:
  - `uses_slurm() -> bool`
  - `on_UVA_HPC() -> bool`
  - `skip_if_no_slurm` -- pytest mark decorator
  - `skip_if_no_hydroshare` -- for integration tests
  - `assert_zarr_valid(path, expected_vars=None)` -- Check zarr is readable and has expected vars
  - `assert_flood_probs_valid(ds)` -- Domain-specific validation

**Tests:**
- `test_config.py::test_synthetic_test_case_builds` -- Builder produces valid config + data

#### Phase 1G: Case Study Config Infrastructure (local only)

HydroShare upload and download logic are deferred to Phase 6A, just before HPC testing. This phase only creates the config registry and template so local development can proceed using the staging directory directly.

**Files to create:**
- `src/ss_fha/examples/__init__.py`
- `src/ss_fha/examples/case_study_catalog.py`:
  - Registry of available case studies with HydroShare resource IDs (Norfolk ID is a placeholder until resource is created)
- `src/ss_fha/examples/config_templates/norfolk_default.yaml` -- Template YAML with `{{placeholder}}` paths; during local development these are filled with paths into the local staging directory

**Deferred to Phase 6A:**
- `src/ss_fha/examples/examples.py` (`SSFHAExample` class, `download_norfolk_case_study()`)
- HydroShare upload of staged data
- BagIt checksum validation

**Tests:**
- Unit tests for template filling logic (no network needed)

#### Phase 1 Definition of Done

- [ ] `SSFHAConfig` loads from YAML and validates all fields
- [ ] Toggle validation works: enabling Workflow 3 without observed data raises clear error
- [ ] `ProjectPaths.from_config()` resolves all paths correctly
- [ ] Zarr and NetCDF I/O round-trips work with synthetic data
- [ ] GIS masking works with synthetic geometries
- [ ] Validation reports accumulate errors with fix hints
- [ ] Test case builder creates valid synthetic data + config matching HydroShare structure
- [ ] `pytest tests/` passes with all Phase 1 tests green
- [ ] A reference minimal YAML config exists in `src/ss_fha/examples/config_templates/`

---

### Phase 2: Core Computation Modules

**Goal**: Extract and test the pure computational functions from `__utils.py` into domain-specific modules. All functions are pure computation -- no I/O.

#### Phase 2A: `core/flood_probability.py`
Extract from `__utils.py`:
- `compute_emp_cdf_and_return_pds()` -- empirical CDF and return period computation
- `calculate_positions()` -- Weibull/Stendinger plotting positions
- `calculate_return_period()` -- position-to-return-period conversion
- `compute_return_periods_for_series()` -- series-level return period computation
- `sort_dimensions()` -- xarray dimension ordering utility

**Tests**: Verify against hand-computed examples and numpy/scipy reference implementations.

#### Phase 2B: `core/bootstrapping.py`
Extract from `__utils.py`:
- `prepare_for_bootstrapping()` -- setup sampling indices
- `bootstrapping_return_period_estimates()` -- single bootstrap sample computation
- `combine_bootstrap_samples()` -- stack samples along new dimension
- `compute_bootstrap_quantiles()` -- quantile computation across samples
- `check_for_na_in_combined_bs_zarr()` -- validation

**Tests**: Small synthetic dataset, verify bootstrap distribution properties (mean converges, CI coverage).

#### Phase 2C: `core/event_statistics.py`
Extract from `__utils.py`:
- `compute_univariate_event_return_periods()`
- `compute_all_multivariate_return_period_combinations()`
- `empirical_multivariate_return_periods()`
- Bootstrap sampling functions for event return periods

**Tests**: Known event sets with pre-computed return periods.

#### Phase 2D: `core/geospatial.py`
Extract from `__utils.py`:
- `create_mask_from_shapefile()`
- `return_mask_dataset_from_polygon()`
- `return_impacted_features()`
- `create_flood_metric_mask()`
- `compute_floodarea_retrn_pds()`
- `compute_flood_impact_return_periods()`

**Tests**: Synthetic geometries with known overlap areas.

#### Phase 2 Definition of Done

- [ ] All computational functions from `__utils.py` are migrated to typed, documented module functions
- [ ] Each function has unit tests with synthetic data
- [ ] Mathematical correctness validated against reference values (especially return period calculations)
- [ ] No function performs I/O directly -- I/O is handled by callers using `ss_fha.io`
- [ ] `__utils.py` functions are fully superseded (tracking table updated)

---

### Phase 3: Analysis Modules and Runner Scripts

**Goal**: Implement the workflow steps as analysis modules called by runner scripts. Each runner is a subprocess entry point invocable by Snakemake.

#### Phase 3A: Workflow 1 -- `analysis/flood_hazard.py` + `runners/flood_hazard_runner.py`
Replaces: `b1_analyze_triton_outputs_fld_prob_calcs.py`
- Load TRITON outputs, validate event completeness
- Compute flood probabilities by simulation type (compound, surge-only, rain-only, triton-only)
- Produce flood probability zarrs indexed by return period

Runner script: accepts `--config`, `--sim-type` (compound/surge/rain/triton) args.

#### Phase 3B: Workflow 2 -- `analysis/uncertainty.py` + bootstrap runners
Replaces: `c1_*` and `c1b_*`
- `runners/bootstrap_runner.py`: Compute single bootstrap sample (Snakemake parallelizes across sample IDs)
  - Args: `--config`, `--sample-id`, `--sim-type`
- `runners/bootstrap_combine_runner.py`: Combine all samples and compute quantiles
  - Args: `--config`, `--sim-type`

This is the primary HPC parallelization target -- 500 independent bootstrap samples.

#### Phase 3C: Event Statistics -- `analysis/event_comparison.py` + `runners/event_stats_runner.py`
Replaces: `d0_computing_event_statistic_probabilities.py`
- Compute univariate and multivariate event return periods
- Bootstrap event return period uncertainty
- Supports Workflows 1 and 4

#### Phase 3D: Workflow 3 -- `analysis/ppcct.py` + `runners/ppcct_runner.py`
Replaces: `b2b`, `b2c`, `b2d` scripts
- Probability Plot Correlation Coefficient Test
- Only runs when `toggle_ppcct=True`
- Independent of Workflow 1 -- uses raw TRITON outputs directly

#### Phase 3E: Design Comparison -- `analysis/design_comparison.py` (optional)
Replaces: `d2_compare_ensemble-based_with_design_storms.py`
- Only runs when `toggle_design_comparison=True`

#### Phase 3F: Workflow 4 -- `analysis/flood_risk.py` + `runners/flood_risk_runner.py`
Replaces: `f1_*`, `f2_*` scripts
- Impact assessment on buildings, roads, parcels by AOI
- Only runs when `toggle_flood_risk=True`
- Depends on Workflow 1 outputs; optionally uses Workflow 2 CIs

#### Phase 3 Definition of Done

- [ ] Each analysis module can be called programmatically with a config object
- [ ] Each runner script is invocable from command line with `--config` + phase-specific args
- [ ] Runner scripts log to stdout (Snakemake captures), use log-based completion checks
- [ ] Integration tests using synthetic test case (from Phase 1F builder) pass
- [ ] End-to-end chain works: flood_hazard_runner -> bootstrap_runner (x N) -> bootstrap_combine_runner
- [ ] PPCCT runner works independently of flood hazard runner
- [ ] Tracking table in old code updated for all migrated scripts

---

### Phase 4: Snakemake Workflow Integration

**Goal**: Wire everything together so `ssfha.run()` generates and executes a Snakefile.

**Snakemake version**: 9.15.0 with `snakemake-executor-plugin-slurm` 2.1.0

#### Phase 4A: `workflow/builder.py` + `workflow/rules/*.smk`
- `SnakemakeWorkflowBuilder` class:
  - Generates master Snakefile that `include:`s per-workflow rule files
  - `rule all:` with conditional targets based on config toggles
  - Bootstrap fan-out/fan-in pattern: one rule per `sample_id` (0..N-1), then combine rule
  - Resource blocks for SLURM (via Snakemake 9.x `resources:` directive)
- Modular rule files:
  - `flood_hazard.smk`: Rules for Workflow 1 (per sim-type)
  - `uncertainty.smk`: Bootstrap sample rules (parallelized) + combine rule
  - `ppcct.smk`: PPCCT rules (only included when toggled on)
  - `flood_risk.smk`: Impact analysis rules (only included when toggled on)

#### Phase 4B: `workflow/execution.py`
- `LocalConcurrentExecutor` -- run with `-j N` (auto-detect N; set N=1 to serialize)
- `SlurmExecutor` -- run with `--executor slurm` (Snakemake 9.x plugin API)

#### Phase 4C: `workflow/platform_configs.py`
- Presets for known HPC systems (UVA, etc.)

#### Phase 4D: CLI and `ssfha.run()`
- `cli.py`: `ssfha run config.yaml` -- validate config, generate Snakefile, execute
- `cli.py`: `ssfha validate config.yaml` -- dry run validation
- `cli.py`: `ssfha download norfolk` -- download case study data from HydroShare
- `__init__.py`: `ssfha.run(config_path)` -- programmatic API

#### Phase 4 Definition of Done

- [ ] `ssfha run config.yaml` executes full pipeline on local machine (local_concurrent mode)
- [ ] `ssfha run config.yaml` executes on SLURM with bootstrap parallelization
- [ ] `ssfha validate config.yaml` reports all issues before execution
- [ ] Snakefile correctly expresses dependencies (no race conditions)
- [ ] Dry run (`snakemake -n`) shows expected rule execution order
- [ ] Disabled workflows produce no targets and no errors

---

### Phase 5: Visualization

**Goal**: Migrate plotting functions, integrated with the new data structures.

- Split `__plotting.py` into domain-specific modules under `visualization/`
- Update to use new path conventions and config
- Add CLI command: `ssfha plot config.yaml --figures all|flood_maps|probability_curves|...`
- Optionally add Snakemake rules for figure generation

#### Phase 5 Definition of Done

- [ ] All critical visualizations from `__plotting.py` migrated
- [ ] Figures generate from pipeline outputs without manual intervention
- [ ] Optional: Snakemake rules for figure generation

---

### Phase 6: Case Study Validation and Documentation

**Goal**: Validate the full pipeline reproduces published results.

- Run Norfolk case study end-to-end (download from HydroShare, run all workflows)
- Compare outputs against reference values from old codebase
- Write user documentation (installation, quickstart, configuration reference)
- Prepare case study notebook showing key results

---

## Risks and Edge Cases

| Risk | Impact | Mitigation |
|------|--------|------------|
| Bootstrap zarr files are multi-GB; 500 samples creates massive I/O | Pipeline fails or is extremely slow on local machines | Implement chunked I/O, configurable sample count, and test with small counts (5-10) |
| Multivariate return period combinations explode combinatorially | Memory/time issues | Validate combination count before execution; warn user |
| TRITON output zarr structure varies between TRITON versions | Data loading fails | Validate zarr schema against expected variables/dimensions in config validation |
| Plotting positions (Weibull vs Stendinger) produce subtly different results | Silent mathematical errors | Test both methods against analytical distributions with known CDF |
| HydroShare download may be slow or unavailable | Case study tests fail | Cache downloaded data; mock HydroShare in unit tests; only require download for integration tests |
| SLURM environments vary significantly | Workflow fails on untested HPC | Platform configs with explicit validation; document tested platforms |
| Snakemake 9.x API differs from examples in older TRITON-SWMM_toolkit | Workflow generation code incompatible | Target 9.15.0 specifically; use `--executor slurm` plugin API, not legacy `--cluster` |

---

## Validation Plan

### Phase 1 Validation
```bash
# Run all Phase 1 tests
pytest tests/test_config.py tests/test_paths.py tests/test_io.py -v

# Smoke test: load config from YAML
python -c "from ss_fha.config.loader import load_config; c = load_config('examples/norfolk_default.yaml'); print(c)"
```

### Phase 2 Validation
```bash
# Run core computation tests
pytest tests/test_flood_probability.py tests/test_bootstrapping.py tests/test_event_statistics.py tests/test_geospatial.py -v

# Numerical validation: compare return period computation against scipy reference
pytest tests/test_flood_probability.py::test_return_periods_match_scipy -v
```

### Phase 3 Validation
```bash
# Runner script smoke tests
python -m ss_fha.runners.flood_hazard_runner --config test_config.yaml --sim-type compound
python -m ss_fha.runners.bootstrap_runner --config test_config.yaml --sample-id 0 --sim-type compound

# Integration test
pytest tests/test_end_to_end.py -v
```

### Phase 4 Validation
```bash
# Snakemake dry run
ssfha run config.yaml --dry-run

# Full local execution
ssfha run config.yaml

# Validate outputs
pytest tests/test_end_to_end.py::test_full_pipeline -v
```

---

## Documentation and Tracker Updates

| Document | Update Condition |
|----------|-----------------|
| `.prompts/philosophy.md` | Update Architecture section with finalized module list after Phase 1 |
| `docs/planning/active/refactors/full_codebase_refactor.md` (this file) | Update tracking table after each phase; move to `docs/planning/completed/` when done |
| `pyproject.toml` | Add dependencies after Phase 1 (xarray, dask, pydantic, geopandas, snakemake, etc.) |
| Example YAML configs | Create during Phase 1B; update as config model evolves |
| Old code files | Add refactoring status comment blocks as each module is migrated |

---

## Decisions Needed from User

All previously open decisions have been resolved:

| # | Decision | Resolution |
|---|----------|------------|
| 1 | HydroShare resource structure | User will create resource while plan is finalized. Organization as proposed. |
| 2 | Test data sizing | 10x10 grid, 10 events, 5 bootstrap samples. Synthetic only (not from HydroShare). |
| 3 | Small files git vs HydroShare | All case study data goes to HydroShare. No data files committed to git. |
| 4 | Design storm scripts | Excluded from ss-fha. Belong in TRITON-SWMM_toolkit. |
| 5 | PPCCT and impact analysis priority | Neither deferred. Impact analysis (Workflow 4) is last in Phase 3 but within scope. |
| 6 | Package name | `ss-fha` (distribution) / `ss_fha` (import). Confirmed. |
| 7 | Snakemake version | 9.15.0 with `snakemake-executor-plugin-slurm` 2.1.0. |
| 8 | Snakemake architecture | Single Snakefile with modular `include:` directives and conditional targets. |

**Remaining open question (non-blocking):**
- HydroShare resource ID: will be provided when resource is created. The `case_study_catalog.py` will reference this ID.

---

## Definition of Done (Full Project)

- [ ] All old scripts in `_old_code_to_refactor/` are fully superseded by library modules
- [ ] `pip install ss-fha` works in a fresh environment
- [ ] `ssfha run norfolk_config.yaml` reproduces the Norfolk case study results (all 4 workflows)
- [ ] `ssfha run norfolk_config.yaml` works on SLURM (tested on UVA HPC)
- [ ] `pytest` passes on local machine and HPC (platform-specific tests gated appropriately)
- [ ] Norfolk case study data downloadable from HydroShare
- [ ] Synthetic test case runs in <5 minutes for CI
- [ ] Configuration reference documentation exists
- [ ] CHANGELOG updated

---

## Self-Check Results

1. **Header/body alignment check**: All required sections present and content matches headers. The "File-by-File Change Plan" is integrated into the phased plan (each phase lists files to create) rather than as a standalone section -- this is more readable given the scope of the refactor.

2. **Section necessity check**: All sections carry actionable content. The "Four Core Workflows" section was added to clearly define the independent workflows and their dependencies, which is critical for the Snakemake architecture and toggle design.

3. **Alignment with philosophy.md check**:
   - Fail-fast exceptions: Addressed via `exceptions.py` design (Phase 1A)
   - Log-based completion: Addressed in runner script design (Phase 3)
   - Pydantic + YAML: Central to Phase 1B
   - Snakemake runner scripts with CLI args: Phase 3 + 4
   - No backward compatibility concerns: Confirmed (clean break from old scripts)
   - Platform-organized tests: Addressed in Phase 1F test infrastructure
   - TRITON-SWMM_toolkit patterns: Explicitly referenced throughout
   - PPCCT (not PPCT): Corrected throughout
