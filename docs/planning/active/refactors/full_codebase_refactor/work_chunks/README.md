# Work Chunks: Full Codebase Refactor

Each file in this directory is a self-contained implementation prompt for one chunk of the refactor. To implement a chunk, pass the file to Claude as context.

Files are alphabetically sorted in implementation order. Complete them in order — each chunk lists its prerequisites.

When a chunk is fully implemented and all checklist items are checked, move it to `../implemented/`.

## Status Overview

| File | Phase | Status |
|------|-------|--------|
| `00_case_study_yaml_setup.md` | 0 | Pending — create case study YAMLs and data inventory before any code |
| `01A_exceptions_and_constants.md` | 1A | Pending |
| `01B_pydantic_config_model.md` | 1B | Pending |
| `01C_path_management.md` | 1C | Pending |
| `01D_io_layer.md` | 1D | Pending |
| `01E_validation_layer.md` | 1E | Pending |
| `01F_test_infrastructure.md` | 1F | Pending |
| `01G_example_case_study_infrastructure.md` | 1G | Pending — local config/registry only; HydroShare download deferred to 06A |
| `02A_core_flood_probability.md` | 2A | Pending |
| `02B_core_bootstrapping.md` | 2B | Pending |
| `02C_core_event_statistics.md` | 2C | Pending |
| `02D_core_geospatial.md` | 2D | Pending |
| `03A_workflow1_flood_hazard.md` | 3A | Pending |
| `03B_workflow2_uncertainty.md` | 3B | Pending |
| `03C_event_statistics_runner.md` | 3C | Pending |
| `03D_workflow3_ppcct.md` | 3D | Pending |
| `03E_design_comparison.md` | 3E | Pending |
| `03F_workflow4_flood_risk.md` | 3F | Pending |
| `04A_snakemake_workflow_builder.md` | 4A | Pending |
| `04B_execution_and_cli.md` | 4B–4D | Pending |
| `05_visualization.md` | 5 | Pending |
| `06A_hydroshare_upload_and_download.md` | 6A | Pending — gate before HPC; audit staged data + implement download |
| `06_case_study_validation.md` | 6 | Pending |
