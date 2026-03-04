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
8. When functions are ported, permanent test functions should be created to ensure that the new refactored functions produce the same results as the old functions. 
    - Ideally, old functions will be imported directly from an old script for comparison. If that is not possible, old functions can be ported to the new code base. Those functions should not be public (preceded with '_') and the docstring should include "PORTED FUNCTION FOR TESTING THE REFACTORING" so those functions can be easily found later. These represent an exception to the no cruft philosphy, but the intention is to eventually delete them once the refactor has been satisfactorly completed.
    - If discrepencies are found, consider the possibility that the old code has an error. This is unlikely, but possible. If you suspect an error in the old code, report to the developer what you suspect the error is and why your error is correct. Include any relevant code chunk(s) and mathematical proofs.

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

**MCDS (Monte Carlo design storm)** is not a separate `fha_approach`. Because MCDS subsets design storms directly from the stochastic ensemble (no independent model inputs), it is implemented as `toggle_mcds: bool` on the primary SSFHA combined config. Enabling it triggers additional analysis steps within Phase 3E. A standalone MCDS method (independent stochastic event generation) is a shelved future improvement — it would require a new weather model run and simulation ensemble. See work chunk 00 Decision 3.

**Config structure:**

The primary `SSFHAConfig` YAML defines the baseline analysis. An optional `alt_fha_analyses` field accepts a list of paths to alternative FHA config YAMLs. Each alternative YAML has the same schema as the primary config but specifies different input datasets, a different `fha_approach`, and a unique `fha_id`.

```yaml
# Primary analysis YAML (defines the baseline)
fha_id: ssfha_combined
fha_approach: ssfha
triton_outputs:
  combined: path/to/combined.zarr     # "combined" = rain + surge drivers
  observed: path/to/observed.zarr     # required when toggle_ppcct: true
toggle_mcds: true                     # MCDS subsets from this ensemble — no separate fha_id

# Optional: list of alternative analyses to compare against baseline
alt_fha_analyses:
  - path/to/rainonly_config.yaml    # fha_id: ssfha_rainonly, fha_approach: ssfha
  - path/to/surgeonly_config.yaml   # fha_id: ssfha_surgeonly
  - path/to/design_storm_config.yaml  # fha_id: bds_combined_24hr, fha_approach: bds
```

Alternative config YAMLs **inherit** all fields from the primary config except: `fha_id`, `fha_approach`, `triton_outputs`, and approach-specific parameters. Validation ensures all `fha_id` values are unique across primary and alternatives.

**Snakemake wildcard design:**

The `{fha_id}` wildcard drives all flood hazard and uncertainty rules, enabling all analyses to run in parallel. Comparison rules depend on two or more `{fha_id}` outputs and run after the independent analyses complete.

```
# All FHA analyses run in parallel via wildcard
rule flood_hazard:
    input: lambda w: fha_configs[w.fha_id].triton_outputs.combined
    output: "{output_dir}/{fha_id}/flood_probabilities/combined.zarr"

# Comparison only runs after both baseline and alternative are done
rule fha_comparison:
    input:
        baseline="{output_dir}/{baseline_id}/flood_probabilities/combined.zarr",
        alternative="{output_dir}/{alt_id}/flood_probabilities/combined.zarr"
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
    paths.py                       # Path dataclasses: ProjectPaths (output dirs only; input paths live on config model)
    constants.py                   # All project-wide UPPER_SNAKE_CASE constants (not case-study-specific values)

    io/
        __init__.py
        zarr_io.py                 # Zarr read/write with encoding configs
        netcdf_io.py               # NetCDF read/write with compression
        gis_io.py                  # Geospatial file loading (load_geospatial_data_from_file) and masking/rasterization (create_mask_from_polygon, rasterize_features)

    core/
        __init__.py
        flood_probability.py       # Spatial flood-depth CDF and return period computation via xr.apply_ufunc (compute_emp_cdf_and_return_pds)
        bootstrapping.py           # Bootstrap sampling, combining, quantile analysis
        empirical_frequency_analysis.py  # Domain-agnostic empirical frequency/return period primitives (calculate_positions, calculate_return_period, compute_return_periods_for_series — split from flood_probability.py and event_statistics.py in work chunk 02E)
        event_statistics.py        # Univariate/multivariate event return periods (was return_periods.py in earlier plan drafts)
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
    norfolk_ssfha_comparison/      # Norfolk-specific parameters not on HydroShare
        system.yaml    # e.g., crs_epsg: 32147, study area bounds

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
| `__inputs.py` | PARTIAL (01A + 01B done — constants and Pydantic config model migrated; paths pending 01C) | `config/model.py`, `config/defaults.py`, `paths.py` | 1 |
| `__utils.py` | IN PROGRESS — I/O (1D, updated 2D: canonical loader + mask rename), flood probability (2A), bootstrap kernel (2B), event statistics (2C), geospatial primitives (2D), empirical frequency primitives (2E) migrated; orchestration functions (flood impact/area return periods) deferred to 3F; combine/QA deferred to 3B | `core/*`, `io/*` | 1D, 2A–2E, 3B, 3F |
| `__plotting.py` | NOT STARTED | `visualization/*` | 5 |
| `b1_analyze_triton_outputs_fld_prob_calcs.py` | COMPLETE | `analysis/flood_hazard.py` | 3A |
| `b2b_sim_vs_obs_flod_ppct.py` | NOT STARTED | `analysis/ppcct.py` | 3D |
| `b2c_sim_vs_obs_fld_ppct.py` | NOT STARTED | `analysis/ppcct.py` | 3D |
| `b2d_sim_vs_obs_fld_ppct.py` | NOT STARTED | `analysis/ppcct.py` + `visualization/` | 3D, 5 |
| `c1_fpm_confidence_intervals_bootstrapping.py` | COMPLETE — `analysis/uncertainty.py`, `runners/bootstrap_runner.py` | `analysis/uncertainty.py` | 3B |
| `c1b_fpm_confidence_intervals_bootstrapping.py` | COMPLETE — `analysis/uncertainty.py`, `runners/bootstrap_combine_runner.py` | `analysis/uncertainty.py` | 3B |
| `c2_fpm_confidence_intervals.py` | NOT STARTED | `analysis/uncertainty.py` + `visualization/` | 3B, 5 |
| `d0_computing_event_statistic_probabilities.py` | COMPLETE — `analysis/event_comparison.py`, `runners/event_stats_runner.py` | `analysis/event_comparison.py` | 3C |
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

**Goal**: Identify every external input file, stage it locally, and write case study config YAMLs that make data gaps and design decisions explicit before implementation begins.

**Work chunk**: `00_case_study_yaml_setup.md` — **complete this before 01A**.

**Local staging directory**: `/mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data`

This directory holds data *intended* for eventual HydroShare upload. It may be incomplete or require reformatting as implementation progresses — this is expected. **Do not create compatibility shims or workarounds to accommodate poorly formatted input data.** If a file's format needs to change, change the file. The canonical input format is whatever the library's I/O layer expects, not whatever was convenient at the time the data was originally produced.

**All case-study-specific data will eventually go to HydroShare** (nothing committed to git). Synthetic test data is generated programmatically in tests and must match the HydroShare data structure. During local development, configs point directly to the local staging directory; on HPC, they point to the downloaded HydroShare data.

**Staged Data Inventory** (inspected 2026-02-25; see `00_case_study_yaml_setup.md` for full detail):

| File (in staging dir) | Type | Staged Name | Used By | Status |
|------|------|-------------|---------|--------|
| SS combined (rain+surge) TRITON+SWMM peak flood depths | Zarr | `model_results/ss_tritonswmm_combined.zarr` | 1, 2, 4 | ✓ Present |
| SS rain-only TRITON+SWMM peak flood depths | Zarr | `model_results/ss_tritonswmm_rainonly.zarr` | 1, 2 | ✓ Present |
| SS surge-only TRITON+SWMM peak flood depths | Zarr | `model_results/ss_tritonswmm_surgeonly.zarr` | 1, 2 | ✓ Present |
| SS TRITON-only (no SWMM) peak flood depths | Zarr | `model_results/ss_triton_only_combined.zarr` | 1, 2 | ✓ Present |
| Design storm combined peak flood depths | Zarr | `model_results/design_storm_tritonswmm_combined.zarr` | Comparison, BDS | ✓ Present |
| Design storm rain-only peak flood depths | Zarr | `model_results/design_storm_tritonswmm_rainonly.zarr` | Comparison, BDS | ✓ Present |
| Design storm surge-only peak flood depths | Zarr | `model_results/design_storm_tritonswmm_surgeonly.zarr` | Comparison, BDS | ✓ Present |
| Observed event peak flood depths | Zarr | `model_results/obs_tritonswmm_combined.zarr` | 3 (PPCCT) | ✓ Present |
| SS simulation event summaries | CSV | `events/ss_simulation_summaries.csv` | 1, 2, 3 | ✓ Present |
| SS event iloc mapping | CSV | `events/ss_event_iloc_mapping.csv` | 1, 2, 3 | ✓ Present |
| SS simulation time series | NetCDF | `events/ss_simulation_time_series.nc` | Event stats | ✓ Present (~4 GB) |
| Observed event summaries | CSV | `events/obs_event_summaries_from_yrs_with_complete_coverage.csv` | 3 | ✓ Present |
| Observed event iloc mapping | CSV | `events/obs_event_iloc_mapping.csv` | 3 | ✓ Present |
| Observed event time series | NetCDF | `events/obs_event_tseries_from_yrs_with_complete_coverage.nc` | 3, Event stats | ✓ Present |
| Design storm event time series (combined) | NetCDF | `events/design_storm_combined.nc` | Comparison | ✓ Present |
| Design storm event time series (rain-only) | NetCDF | `events/design_storm_rainonly.nc` | Comparison | ✓ Present |
| Design storm event time series (surge-only) | NetCDF | `events/design_storm_surgeonly.nc` | Comparison | ✓ Present |
| NOAA tide gage data | CSV | N/A — not a pipeline input | Plotting only | Not required |
| Empirical rainfall/water level return period curves | CSV | N/A — pipeline outputs, not inputs | Written by event stats runner | Not required as inputs |
| Watershed boundary shapefile | Shapefile | `geospatial/norfolk_wshed_epsg32147_state_plane_m.shp` | 1, 2, 3, 4 | ✓ Present (EPSG:32147) |
| Roads (raw, city-wide) | Shapefile | `geospatial/Street_Centerline_-_City_of_Norfolk.shp` | 4 | ✓ Present (unclipped) |
| Sidewalks (raw, city-wide) | Shapefile | `geospatial/Sidewalk_-_City_of_Norfolk.shp` | 4 | ✓ Present (unclipped) |
| Buildings (raw, statewide) | Shapefile | `geospatial/buildings_from_ms_github/va_buildings.shp` | 4 | ✓ Present (unclipped) |
| Parcels | Shapefile | `geospatial/Parcel_Boundaries/Parcel_Boundaries.shp` | 4 | ✓ Present (clip status unknown) |
| FEMA 100-yr flood depth raster | GeoTIFF | `geospatial/fema/100yr_depths_m.tif` | Comparison | ✓ Present |
| AOI shapefile | Shapefile | N/A — not used; watershed used directly | 4 | Not required |

**Key structural notes on staged data**:
- All SS zarrs: dims `(x: 526, y: 513, event_iloc: 3798)`, variable `max_wlevel_m`, coords `x, y, event_iloc` only — scalar metadata coordinates (e.g., `ensemble_type`) have been removed; simulation type is encoded in the filename
- Observed zarr: dims `(x: 526, y: 513, event_iloc: 71)` — same spatial grid as SS zarrs; 71 observed events
- Design storm zarrs: dims `(return_pd_yrs: 4, x: 526, y: 513)` — indexed by return period `[1,2,10,100 yr]`, not event number; rain duration metadata dropped from zarr (encoded in filename / documented in YAML)
- SS time series NetCDF: `(event_type=3, year=954, event_id=5, timestep=3261)` — 954 years have ≥1 event (out of 1000 synthesized)
- Integer variables `156, 171, 170, 155, 140, 141` in time series NetCDFs are rain gage/SWMM node IDs — meaning must be confirmed before I/O layer is designed (see `00_case_study_yaml_setup.md` checklist)
- Roads, buildings, and sidewalks are raw (unclipped); **decision made**: clip on load via `read_shapefile(clip_to=watershed_gdf)` — see `00_case_study_yaml_setup.md` Decision 1
- **Terminology**: "combined" = simulation with rain + surge drivers (filename convention); "compound" = phenomenon of flooding worsened by multiple simultaneous drivers (scientific term). These are not interchangeable — see `CLAUDE.md` Terminology section

**HydroShare Resource Organization** (target — will be finalized in Phase 6A):
```
ss-fha-norfolk-case-study/
    model_results/
        ss_tritonswmm_combined.zarr
        ss_tritonswmm_rainonly.zarr
        ss_tritonswmm_surgeonly.zarr
        ss_triton_only_combined.zarr
        obs_tritonswmm_combined.zarr
        design_storm_tritonswmm_combined.zarr
        design_storm_tritonswmm_rainonly.zarr
        design_storm_tritonswmm_surgeonly.zarr
    events/
        ss_simulation_summaries.csv
        ss_event_iloc_mapping.csv
        ss_simulation_time_series.nc
        obs_event_summaries_from_yrs_with_complete_coverage.csv
        obs_event_iloc_mapping.csv
        obs_event_tseries_from_yrs_with_complete_coverage.nc
        design_storm_combined.nc
        design_storm_rainonly.nc
        design_storm_surgeonly.nc
        # NOTE: empirical return period CSVs are pipeline OUTPUTS, not HydroShare inputs.
        # They are written to output_dir/event_statistics/ by the event stats runner.
    geospatial/
        norfolk_wshed_epsg32147_state_plane_m.shp (+ companions)
        Street_Centerline_-_City_of_Norfolk.shp (+ companions)  # raw city-wide; clipped on load
        Sidewalk_-_City_of_Norfolk.shp (+ companions)           # raw city-wide; clipped on load
        buildings_from_ms_github/va_buildings.shp (+ companions) # raw statewide; clipped on load
        Parcel_Boundaries/Parcel_Boundaries.shp (+ companions)
        fema/100yr_depths_m.tif
        # No aoi.shp — spatial subsetting uses the watershed shapefile directly
```

**Test data strategy**: Synthetic test data is generated programmatically in `tests/fixtures/test_case_builder.py`. The builder creates xarray Datasets, DataFrames, and GeoDataFrames that match the structure (dimensions, variables, dtypes, coordinate names) of the real HydroShare data. This ensures that code tested against synthetic data will also work with real case study data. Suggested test dimensions: 10x10 grid, 10 events, 5 bootstrap samples.

---

### Phase 1: Foundation (Config, Paths, Exceptions, I/O, Test Infrastructure)

**Goal**: Establish the project skeleton so that every subsequent phase has a stable config system, path management, I/O layer, and test infrastructure to build on.

#### Phase 1A: Exceptions and Constants — **COMPLETE** (2026-02-25)

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
  - **Not included**: `DEFAULT_CRS_EPSG` (case-study-specific; goes in `cases/norfolk_ssfha_comparison/`) and `synthetic_years` (derived from weather data record length, not user-configured)
- `cases/norfolk_ssfha_comparison/system.yaml` -- Norfolk-specific parameters not in HydroShare (e.g. `crs_epsg: 32147`). This directory is the home for anything case-study-specific that isn't committed to HydroShare. Created in work chunk 00.

**Tests:**
- `test_config.py::test_defaults_are_accessible` -- import and verify defaults exist with expected types

#### Phase 1B: Pydantic Configuration Model — **COMPLETE** (2026-02-25)

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
    fha_id: str                          # Unique ID for this FHA approach (e.g. "ssfha_combined")
    fha_approach: Literal["ssfha", "bds"]

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

    # MCDS toggle — only valid when fha_approach="ssfha"; subsets design storms from this ensemble
    toggle_mcds: bool = False            # See work chunk 00 Decision 3

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
    combined: Path                         # Always required — rain+surge combined simulation
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

#### Phase 1C: Path Management — **COMPLETE** (2026-02-25)

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

#### Phase 1D: I/O Layer — **COMPLETE** (2026-02-25)

Before writing any I/O function, check `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/` for reusable utilities to import rather than duplicate. Any function identified as project-agnostic (useful beyond ss_fha and TRITON-SWMM_toolkit) should be noted in `docs/planning/utility_package_candidates.md` for potential extraction into a shared pip-installable package.

**Files created:**
- `src/ss_fha/io/__init__.py`
- `src/ss_fha/io/zarr_io.py`:
  - `write_zarr(ds, path, encoding, overwrite, compression_level=5)`
  - `read_zarr(path, chunks) -> xr.Dataset`
  - `delete_zarr(path, timeout_s)`
  - `default_zarr_encoding(ds, compression_level=5) -> dict`
- `src/ss_fha/io/netcdf_io.py`:
  - `write_compressed_netcdf(ds, path, encoding, compression_level=5)`
  - `read_netcdf(path) -> xr.Dataset`
- `src/ss_fha/io/gis_io.py`:
  - `read_shapefile(path, clip_to) -> gpd.GeoDataFrame`
  - `create_mask_from_shapefile(shapefile_path, reference_ds, crs_epsg) -> xr.DataArray`
  - `rasterize_features(gdf, reference_ds, field) -> xr.DataArray`

Note: TRITON-SWMM_toolkit analogues exist but were not imported — they violate this project's no-defaults philosophy. Fresh implementations documented in `docs/planning/utility_package_candidates.md`.

**Tests (21 passing):**
- `test_io.py` — zarr roundtrip, netcdf roundtrip, zarr encoding, overwrite protection, delete, shapefile read, clip_to, create_mask, rasterize_features, all DataError cases

#### Phase 1E: Validation Layer — **COMPLETE** (2026-02-25)

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

#### Phase 1F: Test Infrastructure — **COMPLETE** (2026-02-25)

**Files to create:**
- `tests/conftest.py` -- Shared fixtures:
  - `tmp_project_dir` -- Temporary directory with expected structure
  - `minimal_config` -- Smallest valid SSFHAConfig using synthetic data (Workflow 1 only)
  - `full_config` -- Config with all workflows enabled
  - `synthetic_flood_dataset` -- Small xarray Dataset mimicking TRITON output structure
- `tests/fixtures/__init__.py`
- `tests/fixtures/test_case_builder.py`:
  - `build_synthetic_triton_output(n_events: int, nx: int, ny: int) -> xr.Dataset` -- Matches real zarr structure (no defaults; schema: dims x/y/event_iloc, var max_wlevel_m)
  - `build_synthetic_observed_output(n_events: int, nx: int, ny: int) -> xr.Dataset`
  - `build_synthetic_event_summaries(n_events: int, include_obs_cols: bool) -> pd.DataFrame` -- cols: event_type, year, event_id (index), precip_depth_mm; obs variant adds event_start
  - `build_synthetic_watershed(nx: int, ny: int, crs_epsg: int) -> gpd.GeoDataFrame`
  - `build_minimal_test_case(tmp_path: Path) -> SSFHAConfig` -- Creates config + all synthetic data files on disk (no defaults)
- `tests/fixtures/test_case_catalog.py`:
  - `retrieve_norfolk_case_study(start_from_scratch: bool)` -- HydroShare download (deferred; raises NotImplementedError until HPC phase)
- `tests/utils_for_testing.py`:
  - `uses_slurm() -> bool` -- checks `shutil.which("sbatch")`; correct for login-node detection (not `SLURM_JOB_ID`)
  - `skip_if_no_slurm` -- pytest mark decorator
  - `skip_if_no_hydroshare` -- for integration tests
  - `assert_zarr_valid(path, expected_vars)` -- Check zarr is readable and has expected vars
  - `assert_flood_probs_valid(ds)` -- Domain-specific validation

**Tests:**
- `test_config.py::test_synthetic_test_case_builds` -- Builder produces valid config + data

#### Phase 1G: Case Study Config Infrastructure (local only) — **COMPLETE** (2026-02-25)

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

#### Phase 2A: `core/flood_probability.py` — **COMPLETE** (2026-02-26)
Migrated from `__utils.py`:
- `calculate_positions()` — plotting positions via `scipy.stats.mstats.plotting_positions(alpha, beta)`
- `calculate_return_period()` — position-to-return-period conversion
- `compute_emp_cdf_and_return_pds()` — empirical CDF and return period computation across spatial grid

Also created `src/ss_fha/core/utils.py`:
- `sort_dimensions()` — generic xarray dimension ordering utility (also added to utility_package_candidates.md)

Deferred: `compute_return_periods_for_series()` — 1D series wrapper for univariate event-level analysis; not needed by the gridded CDF pipeline; deferred to Phase 2C.

Plotting position interface: `alpha`/`beta` float parameters passed directly to scipy. Named method mappings (Weibull=0,0; Cunnane=0.4,0.4 etc.) are documented in the module docstring and config field descriptions.

**Tests**: `tests/test_flood_probability.py` — 22 tests; validates against scipy reference, hand-derived examples, and algebraic properties.

#### Phase 2B: `core/bootstrapping.py` — **COMPLETE** (2026-02-26)
**Scope: single-sample computation only.** Combining N samples, computing CIs, and post-combine QA are Phase 3B runner responsibilities — see Phase 3B below.

New functions (not direct ports — old code was I/O-coupled and had no named equivalents for combine/quantile):
- `draw_bootstrap_years(n_years_synthesized, base_seed, sample_id)` — seeded year resampling via `np.random.default_rng(base_seed + sample_id)`; draws from `np.arange(n_years_synthesized)` (all years, including event-free)
- `assemble_bootstrap_sample(resampled_years, years_with_events, event_number_mapping, da_flood_probs)` — filter to valid years, reassign sequential event numbers, return stacked DataArray; raises `SSFHAError` on NaN
- `compute_return_period_indexed_depths(da_stacked, alpha, beta, n_years)` — sort flood depths and assign return period coordinate (calls `core/flood_probability` functions internally)
- `sort_last_dim(arr)` — helper: `np.sort(arr, axis=-1)`

Also: add `bootstrap_base_seed: int` as a required field in `SsfhaConfig` uncertainty block.

Deferred to Phase 3B runner: combining per-sample zarrs, computing quantile CIs, post-combine NaN QA.

**Tests**: Reproducibility, year-pool correctness (event-free years), NaN guard, return period accuracy.

#### Phase 2C: `core/event_statistics.py` — **COMPLETE** (2026-02-26)
Extract from `__utils.py`:
- `compute_univariate_event_return_periods()`
- `compute_all_multivariate_return_period_combinations()`
- `empirical_multivariate_return_periods()`
- Bootstrap sampling functions for event return periods

**Tests**: Known event sets with pre-computed return periods.

#### Phase 2D: `core/geospatial.py` + `io/gis_io.py` updates — **COMPLETE** (2026-02-26)

**`io/gis_io.py` changes (prerequisite to the core module):**
- Rename `read_shapefile()` → superseded by `load_geospatial_data_from_file(path, clip_to)`, the canonical loader for any OGR-readable vector format (`.shp`, `.geojson`, `.json`, `.gpkg`). Validates file extension.
- Rename `create_mask_from_shapefile()` → `create_mask_from_polygon()`. Accepts a file path (calls `load_geospatial_data_from_file` internally), or a `gpd.GeoDataFrame`, or a `gpd.GeoSeries`/Shapely geometry — no filetype-specific name in non-I/O functions.
- Validation layer: any `SsfhaConfig` geospatial file path field must validate that the extension is a recognized OGR format (`.shp`, `.geojson`, `.json`, `.gpkg`).
- **Rule**: Function names must not include filetype strings (`shapefile`, `geojson`, etc.) unless the function is exclusively a file-reading/writing operation.

**New `core/geospatial.py` — pure spatial computation on in-memory objects:**
Extract from `__utils.py` (spatial primitives only — orchestration functions deferred to Phase 3F):
- `return_mask_dataset_from_polygon()` — wraps `create_mask_from_polygon()` to return a boolean xr.DataArray; superseded by the new gis_io function but ported as a thin adapter if still needed
- `retrieve_unique_feature_indices()` — helper for `return_impacted_features()`
- `return_impacted_features()` — identifies features within flood depth threshold via xarray ufunc
- `compute_number_of_unique_indices()` — helper
- `return_number_of_impacted_features()` — helper
- `compute_min_rtrn_pd_of_impact_for_unique_features()` — per-feature minimum return period
- `return_ds_gridsize()` — grid cell size utility (2-line spatial utility; needed by flood volume/area functions)

**Deferred to Phase 3F** (orchestration — combine spatial primitives with return period computation):
- `compute_flood_impact_return_periods()` — ported to `analysis/flood_risk.py`
- `compute_floodarea_retrn_pds()` — ported to `analysis/flood_risk.py`
- `compute_volume_at_max_flooding()` — uses domain constant `LST_KEY_FLOOD_THRESHOLDS`; ported to Phase 3F
- `compute_flooded_area_by_depth_threshold()` — uses domain constant `LST_KEY_FLOOD_THRESHOLDS`; ported to Phase 3F

**Already migrated in Phase 1D (not to be re-ported):**
- `create_mask_from_shapefile()` → `gis_io.create_mask_from_polygon()` (renamed above)
- `create_flood_metric_mask()` → `gis_io.rasterize_features()`

**Vocabulary note**: The `ensemble` flag in the old `compute_flood_impact_return_periods()` and `compute_floodarea_retrn_pds()` distinguishes SSFHA (semicontinuous simulation) from BDS (design storm) branches. When porting to Phase 3F, rename `ensemble` → `is_ss` per philosophy.md terminology.

**Tests**: Synthetic geometries with known overlap areas; verify `create_mask_from_polygon` with file path, GeoDataFrame, and geometry inputs.

#### Phase 2E: `core/empirical_frequency_analysis.py` — **COMPLETE** (2026-02-26)

**Goal**: Extract three domain-agnostic empirical frequency primitives into a new `core/empirical_frequency_analysis.py`. These functions contain no flood hydrology, no SWMM, and no project-specific context.

**Functions moved**:
- `calculate_positions()` — from `flood_probability.py`; numpy-level empirical CDF plotting positions via Hazen family formula
- `calculate_return_period()` — from `flood_probability.py`; arithmetic conversion of plotting positions to return periods
- `_compute_return_periods_for_series()` — from `event_statistics.py`; pandas-level pipeline combining both above for a Series. Renamed to `compute_return_periods_for_series()` (public) and gains an explicit required `assign_dup_vals_max_return: bool` argument (replacing the implicit read of the `ASSIGN_DUP_VALS_MAX_RETURN` constant)

**Import sites updated**: `flood_probability.py`, `event_statistics.py`, `geospatial.py`, `tests/test_flood_probability.py`

**Fixes**: `geospatial.py` previously imported a `_private` function from `event_statistics` — a cross-module private import code smell. Now imports the public function from `empirical_frequency_analysis`.

**Not moved**: `compute_emp_cdf_and_return_pds()` stays in `flood_probability.py` — its inputs (`da_wlevel`, spatial `x`/`y` dims, NaN-fill for dry cells) are flood-specific.

**Timing**: Pure internal refactor with no new functionality. Single dedicated commit. Run full test suite before and after to confirm no regressions (165 → 171 tests, 6 new tests for `compute_return_periods_for_series`).

**Work chunk**: `work_chunks/02E_empirical_frequency_analysis.md`

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
- Compute flood probabilities by simulation type (combined, surge-only, rain-only, triton-only)
- Produce flood probability zarrs indexed by return period

Runner script: accepts `--config`, `--sim-type` (combined/surgeonly/rainonly/triton_only) args.

#### Phase 3B: Workflow 2 -- `analysis/uncertainty.py` + bootstrap runners — **COMPLETE** (2026-03-02)
Replaces: `c1_*` and `c1b_*`
- `runners/bootstrap_runner.py`: Compute single bootstrap sample (Snakemake parallelizes across sample IDs)
  - Args: `--config`, `--sample-id`, `--sim-type` (combined/surgeonly/rainonly/triton_only)
- `runners/bootstrap_combine_runner.py`: Combine all samples and compute quantiles
  - Args: `--config`, `--sim-type`
- `bootstrap_quantiles` added to `UncertaintyConfig` as a required user config field (not hardcoded)
- `fha_id` namespacing added to `ProjectPaths` (all workflow dirs under `output_dir/fha_id/`)

This is the primary HPC parallelization target -- 500 independent bootstrap samples.

#### Phase 3C: Event Statistics -- `analysis/event_comparison.py` + `runners/event_stats_runner.py` — **COMPLETE** (2026-03-02)
Replaces: `d0_computing_event_statistic_probabilities.py`
- Compute univariate and multivariate event return periods
- Output is `xr.DataTree` with `/univariate` and `/multivariate` nodes; dual zarr/NetCDF format via `--output-format` CLI arg
- `event_iloc` always sourced from `sim_event_iloc_mapping`; weather indexers stored as 1D non-index coordinates
- Bootstrap event return period uncertainty deferred to future chunk `03C-ext`
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
- **Pre-ported from Phase 2D** (moved here because they are orchestration, not pure computation):
  - `compute_flood_impact_return_periods()` from `__utils.py`
  - `compute_floodarea_retrn_pds()` from `__utils.py`
  - `compute_volume_at_max_flooding()` from `__utils.py`
  - `compute_flooded_area_by_depth_threshold()` from `__utils.py`
- **Vocabulary**: The old `ensemble` parameter in these functions indicates SSFHA (semicontinuous simulation) vs. BDS (design storm). Rename to `is_ss: bool` on porting. A single analysis run is always one approach; branching on `is_ss` is fine if the two paths share substantial logic, otherwise split into separate functions. Recommend seeking agent input on the best structure when Phase 3F planning begins.

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
| Multivariate return period combinations explode combinatorially with many event statistics | Memory/time issues | No hard cap enforced; runner scripts emit per-rule wall-clock timings to CSV (see Cross-Cutting: Timing Infrastructure below) so bottlenecks are observable before decisions are made |
| TRITON output zarr structure varies between TRITON versions | Data loading fails | Validate zarr schema against expected variables/dimensions in config validation |
| Plotting positions (Weibull vs Stendinger) produce subtly different results | Silent mathematical errors | Test both methods against analytical distributions with known CDF |
| HydroShare download may be slow or unavailable | Case study tests fail | Cache downloaded data; mock HydroShare in unit tests; only require download for integration tests |
| SLURM environments vary significantly | Workflow fails on untested HPC | Platform configs with explicit validation; document tested platforms |
| Snakemake 9.x API differs from examples in older TRITON-SWMM_toolkit | Workflow generation code incompatible | Target 9.15.0 specifically; use `--executor slurm` plugin API, not legacy `--cluster` |
| **Full-scale memory allocation in `run_flood_hazard()`** | OOM at ~3700 events x 550x550 grid (~25 GB for 3 float64 arrays). The `.compute()` before `write_zarr()` materializes the entire result into RAM — a workaround for zarr V3's inability to serialize dask masked arrays from `.where(mask)`. This was a known pain point in the original development. | **Must be profiled during Phase 6 case study validation.** Options: (a) chunk the `.compute()` along event_iloc in slices, writing incrementally; (b) apply mask via `np.where(mask, data, np.nan)` on computed chunks instead of xarray `.where()` to avoid masked arrays; (c) switch to zarr V2 which handles masked arrays natively. The synthetic test data (8 events, 10x10 grid) does not exercise this path. |

---

## Cross-Cutting Concerns

### Timing Infrastructure (applies to all runner scripts, Phase 3+)

Every runner script must emit structured timing records to stdout in a consistent, parseable format. Snakemake collects stdout into per-rule log files; a post-processing utility reads those log files and compiles them into a summary CSV. Writing timing data directly to a shared CSV from concurrent runners would cause race conditions and is explicitly prohibited.

**Runner invocation convention:**

Every runner accepts a `--rule` CLI argument containing the Snakemake rule name (a string literal in the `shell:` directive — not inferrable from inside the runner). `fha_id` is read from the loaded analysis config (not passed as a redundant CLI arg). Runner name is derived from `Path(__file__).stem`.

```
# Snakefile shell directive:
python event_statistics_runner.py --config {input.config} --rule compute_event_stats
```

**Required format (emitted to stdout by every runner):**

```
TIMING runner=<Path(__file__).stem> rule=<--rule arg> fha_id=<from config> elapsed_s=<float> start_utc=<ISO8601> end_utc=<ISO8601>
```

The `TIMING` prefix makes records grep-able across all log files. All fields are space-separated key=value pairs on a single line.

**Post-processing:** A utility (to be implemented when runners are written) scans `{output_dir}/logs/` for all Snakemake log files, extracts `TIMING` lines, and writes `{output_dir}/timing/runner_timings.csv` with columns: `runner`, `rule`, `fha_id`, `elapsed_s`, `start_utc`, `end_utc`.

**Rationale:** Multivariate bootstrapping and other combinatorial steps have unknown wall-clock costs on full-scale data. Timing records allow informed decisions about Snakemake parallelization (e.g., whether multivariate bootstrap samples should be distributed as individual sbatch jobs). No hard limits on combination counts are imposed; the timing data provides the empirical basis for future optimization decisions.

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
python -m ss_fha.runners.flood_hazard_runner --config test_config.yaml --sim-type combined
python -m ss_fha.runners.bootstrap_runner --config test_config.yaml --sample-id 0 --sim-type combined

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
| `architecture.md` | Update Key Modules section with finalized module list after Phase 1 |
| `docs/planning/refactors/2026-02-25_full_codebase_refactor/full_codebase_refactor.md` (this file) | Update tracking table after each phase; move to `docs/planning/refactors/completed/` when done |
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
