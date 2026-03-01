# Norfolk SSFHA Comparison Case Study

Case study configs for the Norfolk, VA flood hazard assessment comparing four
SSFHA driver configurations against three Basic Design Storm (BDS) variants.

All configs in this directory point to staged data at:
`/mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data/`

**Schema status**: All YAMLs are PROVISIONAL — written to the intended `SSFHAConfig`
schema (01B), which is not yet implemented. Each YAML has a header comment noting
this. When 01B is implemented, its Definition of Done must include loading all YAMLs
here as smoke tests.

**Design principle**: Each analysis YAML defines exactly one FHA result with one set of
meteorological inputs. Geospatial inputs are defined once in `system.yaml` — they are
a property of the study area (the system), not of the analysis method.
Naming follows TRITON-SWMM_toolkit convention: `system.yaml` for the geographic context,
`analysis_<id>.yaml` for each specific computation.

---

## YAML Inventory

| File | `fha_id` | `fha_approach` | Purpose |
|------|----------|----------------|---------|
| `system.yaml` | — | — | System config: CRS and all geospatial input files |
| `analysis_ssfha_combined.yaml` | `ssfha_combined` | `ssfha` | **Primary config**. Combined drivers (rain + surge), SWMM-coupled. `toggle_mcds: true`. References all alternatives via `alt_fha_analyses`. |
| `analysis_ssfha_rainonly.yaml` | `ssfha_rainonly` | `ssfha` | Rain-only driver, SWMM-coupled |
| `analysis_ssfha_surgeonly.yaml` | `ssfha_surgeonly` | `ssfha` | Surge-only driver, SWMM-coupled |
| `analysis_ssfha_triton_only_combined.yaml` | `ssfha_triton_only_combined` | `ssfha` | Combined drivers, TRITON-only (no SWMM coupling) |
| `analysis_bds_combined.yaml` | `bds_combined_24hr` | `bds` | BDS combined drivers, 24-hr rain duration |
| `analysis_bds_rainonly.yaml` | `bds_rainonly_24hr` | `bds` | BDS rain-only, 24-hr duration |
| `analysis_bds_surgeonly.yaml` | `bds_surgeonly_6hr` | `bds` | BDS surge-only, 6-hr duration |

**Entry point**: pass `norfolk_ssfha_combined.yaml` to `ssfha.run()`. The primary
config references all alternative configs via `alt_fha_analyses`.

---

## Data Inventory

Staged data location: `/mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data/`
Inspected and confirmed: 2026-02-25.

### Model results (`model_results/`)

| File | Description | Dims | Status |
|------|-------------|------|--------|
| `ss_tritonswmm_combined.zarr` | SS combined (rain + surge) peak flood depths | `(x:526, y:513, event_iloc:3798)` | ✓ Present |
| `ss_tritonswmm_rainonly.zarr` | SS rain-only peak flood depths | `(x:526, y:513, event_iloc:3798)` | ✓ Present |
| `ss_tritonswmm_surgeonly.zarr` | SS surge-only peak flood depths | `(x:526, y:513, event_iloc:3798)` | ✓ Present |
| `ss_triton_only_combined.zarr` | SS TRITON-only (no SWMM), combined drivers | `(x:526, y:513, event_iloc:3798)` | ✓ Present |
| `obs_tritonswmm_combined.zarr` | Observed event peak flood depths (PPCCT) | `(x:526, y:513, event_iloc:71)` | ✓ Present |
| `design_storm_tritonswmm_combined.zarr` | BDS combined peak flood depths | `(return_pd_yrs:4, x:526, y:513)` | ✓ Present |
| `design_storm_tritonswmm_rainonly.zarr` | BDS rain-only peak flood depths | `(return_pd_yrs:4, x:526, y:513)` | ✓ Present |
| `design_storm_tritonswmm_surgeonly.zarr` | BDS surge-only peak flood depths | `(return_pd_yrs:4, x:526, y:513)` | ✓ Present |

All SS zarrs: `return_pd_yrs = [1, 2, 10, 100]`. All zarrs share `(x:526, y:513)` grid.
Data variable: `max_wlevel_m`. Scalar metadata coords dropped from zarrs.

### Events (`events/`)

| File | Shape | Status |
|------|-------|--------|
| `ss_simulation_summaries.csv` | (3798, ~40) | ✓ Present |
| `ss_event_iloc_mapping.csv` | (3798, 4) | ✓ Present |
| `ss_simulation_time_series.nc` | (event_type=3, year=954, event_id=5, timestep=3261) ~4 GB | ✓ Present |
| `obs_event_summaries_from_yrs_with_complete_coverage.csv` | (71, ~61) | ✓ Present |
| `obs_event_iloc_mapping.csv` | (71, 4) | ✓ Present |
| `obs_event_tseries_from_yrs_with_complete_coverage.nc` | (year=18, event_type=3, event_id=5, timestep=2174) ~47 MB | ✓ Present |
| `design_storm_combined.nc` | (year=4, timestep=336) | ✓ Present |
| `design_storm_rainonly.nc` | (year=4, timestep=336) | ✓ Present |
| `design_storm_surgeonly.nc` | (year=4, timestep=336) | ✓ Present |

### Geospatial (`geospatial/`) — defined in `norfolk_study_area.yaml`

| File | CRS | Clipped? | Status |
|------|-----|----------|--------|
| `norfolk_wshed_epsg32147_state_plane_m.shp` | EPSG:32147 ✓ | N/A | ✓ Present |
| `Street_Centerline_-_City_of_Norfolk.shp` | TODO | No — clip on load | ✓ Present (raw) |
| `Sidewalk_-_City_of_Norfolk.shp` | TODO | No — clip on load | ✓ Present (raw) |
| `buildings_from_ms_github/va_buildings.shp` | TODO | No — clip on load | ✓ Present (raw, statewide) |
| `Parcel_Boundaries/Parcel_Boundaries.shp` | TODO | Unknown | ✓ Present |
| `fema/100yr_depths_m.tif` | TODO | N/A | ✓ Present |

---

## Data Gap Tracking

Items below must be resolved before Phase 6 (case study validation).

### Resolved gaps

- [x] `obs_tritonswmm_combined.zarr` — staged and confirmed 2026-02-25.
- [x] Design storm `rain_duration_h` — combined/rain-only use 24-hr; surge-only uses 6-hr.
      Dropped from zarr metadata; documented in BDS YAML comments.
- [x] MCDS scope — implemented as `toggle_mcds` on combined config (Decision 3).
- [x] Raw vs. pre-clipped geospatial files — clip on load (Decision 1).
- [x] `ppct_alpha` / `FLD_RTRN_PD_ALPHA` classification — both generic defaults
      → `config/defaults.py` (Decision 5).
- [x] `fha_id` naming convention — see Decision 2.
- [x] Combined vs. compound terminology — see Decision 6.

### Open gaps — must resolve before Phase 6

- [ ] **Confirm CRS of all geospatial files** (roads, sidewalks, buildings, parcels,
      FEMA raster). Watershed confirmed EPSG:32147. All others need verification.
      Action: `geopandas.read_file(...).crs` / `rasterio.open(...).crs`.

- [ ] **Confirm meaning of integer variable names** (156, 171, 170, 155, 140, 141)
      in time series NetCDFs. Appear in both SS and observed NetCDFs. Likely NOAA
      rain gage station IDs or SWMM node IDs. Check TRITON-SWMM_toolkit outputs.
      Decision point for 01D I/O layer.

- [ ] **Confirm `n_years_synthesized: 1000`** against weather model run metadata.
      Legacy `__inputs.py` has `N_YEARS_SYNTHESIZED = 1000`; SS time series has
      year dim = 954 (years with ≥1 event only). The 1000 vs. 954 distinction must
      be verified and handled correctly in empirical return period calculations.

- [ ] **Confirm `RETURN_PERIODS` constraint** — [1, 2, 10, 100] is locked by upstream
      tide gage data. Confirm and document constraint clearly in 01B/01D.

---

## Decisions Made

All decisions are recorded in detail in:
`docs/planning/refactors/2026-02-25_full_codebase_refactor/implemented/00_case_study_yaml_setup.md`

Summary:

| # | Decision | Outcome |
|---|----------|---------|
| 1 | Raw vs. pre-clipped geospatial | Clip on load via `gis_io.read_shapefile(clip_to=...)` |
| 2 | `fha_id` naming convention | See YAML inventory table above |
| 3 | MCDS scope | `toggle_mcds` on combined SSFHA config; not a separate `fha_approach` |
| 4 | `constant_head_bndry_cndtn` | Not an ss-fha input; belongs to TRITON-SWMM simulation config |
| 5 | `ppct_alpha` / `FLD_RTRN_PD_ALPHA` | Both generic defaults → `config/defaults.py` |
| 6 | Combined vs. compound terminology | "Combined" = simulation type; "compound" = phenomenon only |
| 7 | Geospatial at study area level | Geospatial inputs defined in `norfolk_study_area.yaml`; not repeated per FHA config |
| 8 | One zarr per BDS config | Each BDS YAML defines exactly one design storm output and one timeseries |
