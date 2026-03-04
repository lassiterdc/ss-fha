# Work Chunk 03C: Event Statistics Analysis and Runner

**Phase**: 3C — Analysis Modules + Runner Scripts (Event Statistics)
**Last edited**: 2026-03-02

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/refactors/2026-02-25_full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`CONTRIBUTING.md`](../../../../CONTRIBUTING.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: Work chunks 02C (event_statistics core) and 03A complete.

---

## Step 0: xarray-specialist findings ✅ COMPLETE

Specialist consulted 2026-03-02. Findings written to `.scratch/2026-03-02_16-38_zarr-output-structure-findings.md`. Decision C is now resolved — see below.

---

## Task Understanding

### Requirements

Implement the event statistics analysis module and runner script.

**Replaces**: `_old_code_to_refactor/d0_computing_event_statistic_probabilities.py`

**Files to create:**

1. `src/ss_fha/analysis/event_comparison.py`:
   - Loads weather event time series NetCDF (via `ss_fha.io.netcdf_io.read_netcdf`)
   - Calls `ss_fha.core.event_statistics` functions (`compute_univariate_event_return_periods`, `compute_all_multivariate_return_period_combinations`)
   - Assembles an `xr.DataTree` with `/univariate` and `/multivariate` child nodes (see Decision C)
   - Writes output as `event_comparison.zarr` (primary) or `event_comparison.nc` (secondary) to `paths.event_stats_dir`
   - Supports Workflows 1 and 4

2. `src/ss_fha/runners/event_stats_runner.py`:
   - CLI args: `--config <yaml>`, `--system-config <yaml>`, `--output-format <zarr|netcdf>` (required, no default), `--overwrite`
   - Logs completion marker: `"COMPLETE: event_stats"`
   - Fail-fast with `ConfigurationError` for missing/invalid config

### Scope

**In scope**: Univariate event return periods + multivariate event return periods only.

**Out of scope** (deferred to future chunk `03C-ext` or `03G`): Bootstrap event statistic uncertainty (CI on return period estimates and on statistic values such as "1-year 24-hr rainfall depth"). Future chunk should be toggle-guarded. Note: bootstrap samples from `bs_samp_of_univar_event_return_period` already include statistic values, so CIs on both return periods and statistic values are derivable from the same bootstrap run.

### Key Design Decisions

#### Decision A — `n_years` source ✅ RESOLVED
Use `config.n_years_synthesized` (a required field on `SsfhaConfig`). Do **not** derive `n_years` from record length — the synthesized record has 1000 years but only 954 have events; deriving from `len(ds.year)` would give the wrong value. Log the value at run start.

#### Decision B — Bootstrap scope ✅ RESOLVED
Bootstrap event statistics are **out of scope** for 03C. Implement univariate + multivariate only. A future chunk will add bootstrap support, toggle-guarded via config. The master refactor plan has been updated accordingly.

#### Decision C — Output format ✅ RESOLVED (xarray-specialist 2026-03-02)

**Container: `xr.DataTree` with two child nodes.**

```
/                    (root — empty Dataset; global attrs: fha_id, description)
├── univariate/      (Dataset indexed by flat event_iloc)
└── multivariate/    (Dataset indexed by flat event_iloc × event_stats)
```

**Why DataTree, not raw zarr groups:**
`DataTree.to_zarr` / `DataTree.to_netcdf` write one zarr/HDF5 group per tree node. `xr.open_datatree(engine="zarr")` and `xr.open_datatree(engine="h5netcdf")` both discover all groups via `root.groups()` or `_iter_nc_groups` — **no hardcoded group name strings required by the caller.** Both APIs are symmetric; the same DataTree can be written to either format and read back identically.

**h5netcdf group support confirmed**: `DataTree.to_netcdf` supports `engine="h5netcdf"` and writes genuine HDF5 subgroups. `format="NETCDF4"` is enforced (classic NetCDF3 has no groups). `xr.open_datatree(engine="h5netcdf")` discovers groups identically to zarr.

**Write / read pattern:**

```python
# Write zarr (primary)
dt.to_zarr(paths.event_stats_dir / "event_comparison.zarr", mode="w-", consolidated=True)

# Write NetCDF (secondary, user-configurable)
dt.to_netcdf(paths.event_stats_dir / "event_comparison.nc", mode="w", engine="h5netcdf")

# Read (zarr)
dt = xr.open_datatree(path, engine="zarr", chunks={"event_iloc": 500})
ds_uni   = dt["univariate"].ds
ds_multi = dt["multivariate"].ds
```

**Gotcha**: `DataTree.to_zarr` does not support the `group=` argument — the DataTree must be the root of its own store. This is fine for a dedicated per-analysis output file.

**Gotcha**: Writing consolidated zarr v3 metadata emits a `ZarrUserWarning` ("Consolidated metadata is currently not part of the Zarr format 3 specification"). Suppress during writes or accept in logs; it is correct to use.

**Dead space**: Does not apply. Both nodes are dense over their own flat `event_iloc` dimension. The dead-space concern only arises when a sparse multi-index is forced into a dense array. Using a flat integer `event_iloc` dimension (with `event_type`, `year`, `event_id` as non-index 1D coordinates) avoids this entirely.

**`event_stats` string dimension encoding:**
Keep `event_stats` as a flat string dimension with a structured companion coordinate:

```python
# event_stats dim: ["5min,24hr", "5min,w", "24hr,w", "5min,24hr,w"]
# event_stats_vars: 2D string array (event_stats × component_slot)
combo_components = np.array([
    ["max_5min_mm",      "max_24hr_0min_mm", ""],
    ["max_5min_mm",      "max_waterlevel_m", ""],
    ["max_24hr_0min_mm", "max_waterlevel_m", ""],
    ["max_5min_mm",      "max_24hr_0min_mm", "max_waterlevel_m"],
], dtype=object)
```

Callers can filter without parsing strings:
```python
ds.event_stats_vars.sel(event_stats="5min,24hr").values  # → component names
```

**Univariate Dataset structure:**
```python
ds_uni = xr.Dataset(
    {
        "max_24hr_0min_mm":               ("event_iloc", ...),
        "emp_cdf_max_24hr_0min_mm":       ("event_iloc", ...),
        "return_pd_yrs_max_24hr_0min_mm": ("event_iloc", ...),
        # ... one block per driver stat ...
    },
    coords={
        "event_iloc":  ("event_iloc", event_iloc_arr),   # int64, primary dim
        "event_type":  ("event_iloc", event_type_arr),   # str, non-index coord
        "year":        ("event_iloc", year_arr),          # int, non-index coord
        "event_id":    ("event_iloc", event_id_arr),      # int, non-index coord
    },
)
```

**Multivariate Dataset structure:**
```python
ds_multi = xr.Dataset(
    {
        "empirical_multivar_cdf_AND":      (["event_iloc", "event_stats"], ...),
        "empirical_multivar_cdf_OR":       (["event_iloc", "event_stats"], ...),
        "empirical_multivar_rtrn_yrs_AND": (["event_iloc", "event_stats"], ...),
        "empirical_multivar_rtrn_yrs_OR":  (["event_iloc", "event_stats"], ...),
    },
    coords={
        "event_iloc":       ("event_iloc", event_iloc_arr),
        "event_type":       ("event_iloc", event_type_arr),
        "year":             ("event_iloc", year_arr),
        "event_id":         ("event_iloc", event_id_arr),
        "event_stats":      ("event_stats", combo_labels),
        "event_stats_vars": (["event_stats", "component_slot"], combo_components),
        "component_slot":   ("component_slot", ["var_0", "var_1", "var_2"]),
    },
)
```

**Output file naming**: `event_comparison.zarr` (zarr primary) or `event_comparison.nc` (NetCDF secondary). Both in `paths.event_stats_dir`.

#### Decision D — `event_iloc` assignment and multi-indexer EDA ✅ RESOLVED (xarray-specialist 2026-03-02)

`event_iloc` must always be sourced from `config.event_data.sim_event_iloc_mapping`. This is the canonical mapping from flat integer index to all weather event indexers. **If `sim_event_iloc_mapping` is `None`, fail-fast with `ConfigurationError`.** Never assign `event_iloc` as a bare positional integer.

**Real iloc mapping schema** (confirmed from `hydroshare_data/events/ss_event_iloc_mapping.csv`):
- Columns: `event_number` (= `event_iloc`), `year`, `event_type`, `event_id`
- Note: the sim mapping uses `event_number` (deprecated) — rename to `event_iloc` on load. The obs mapping already uses `event_iloc`.
- 3798 rows for Norfolk; `event_type` values: `compound`, `surge`, `rain`

**Join logic**: Merge the event statistics DataFrames (indexed by `(event_type, year, event_id)`) with the iloc mapping on all three indexer columns. The join is clean because the mapping has all four columns. Raise `DataError` if any event in the time series has no corresponding iloc mapping entry.

**Multi-indexer EDA** (xarray-specialist 2026-03-02, findings at `.scratch/2026-03-02_17-24_multiindex-eda-findings.md`):

Store each weather event indexer as a **1D non-index coordinate** on the `event_iloc` dimension. `event_iloc` is the sole index coord (backed by a `PandasIndex`). This pattern:
- Avoids dead space (no multi-index serialization issues)
- Supports `ds.where(ds.event_type == "compound", drop=True)` cleanly — xarray's `where(drop=True)` propagates through all coords and data vars simultaneously
- Is EDA-discoverable: all coords appear in the Dataset repr; the indexer names are stored in `ds.attrs["weather_event_indices"]`

```python
ds_uni = xr.Dataset(
    data_vars={
        "max_24hr_0min_mm":               ("event_iloc", ...),
        "emp_cdf_max_24hr_0min_mm":       ("event_iloc", ...),
        "return_pd_yrs_max_24hr_0min_mm": ("event_iloc", ...),
    },
    coords={
        "event_iloc":  ("event_iloc", event_iloc_arr),    # int64, index coord
        # weather event indexers — from iloc mapping, dynamic per config:
        "year":        ("event_iloc", year_arr),           # int, non-index coord
        "event_type":  ("event_iloc", event_type_arr),     # str, non-index coord
        "event_id":    ("event_iloc", event_id_arr),       # int, non-index coord
        # ... any additional weather_event_indices from config ...
    },
    attrs={"weather_event_indices": list(config.weather_event_indices)},
)
```

**String coordinate encoding** (zarr v3): Set `dtype=str` encoding for all string indexer coordinates to use zarr v3's native variable-length string dtype:
```python
for name in config.weather_event_indices:
    if ds[name].dtype.kind in ("U", "O", "S"):
        ds[name].encoding["dtype"] = str
```

**Do not** store the iloc mapping as a 2D variable in the DataTree — it is fully redundant with the 1D coords and creates a sync burden.

Log the `event_iloc` source and indexer columns at run start.

#### CF metadata — ✅ RESOLVED
No CF compliance. Use descriptive `attrs` only (`long_name`, `units`, `description`) on xarray variables. Do not install or use `cf_xarray`.

- Event-to-flood mapping (the "fragile CSV" noted in the master plan) must be formalized. Define the expected column schema for event CSV files clearly and validate on load.

### Success Criteria

- Runner executes end-to-end with synthetic event summaries
- Event return periods written to output; output passes basic sanity checks (no NaN, return periods > 0)

---

## Evidence from Codebase

Before implementing, inspect:

1. `_old_code_to_refactor/d0_computing_event_statistic_probabilities.py`
2. `src/ss_fha/core/event_statistics.py` (02C)
3. `_old_code_to_refactor/__inputs.py` — event CSV column name conventions

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/analysis/event_comparison.py` | Event statistics orchestration |
| `src/ss_fha/runners/event_stats_runner.py` | CLI runner |
| `tests/fixtures/test_case_builder.py` (new function) | `build_event_stats_test_case()` — primary analysis with event_statistic_variables, synthetic time series NetCDF, and synthetic iloc mapping CSV with full `(event_iloc, year, event_type, event_id)` schema |
| `tests/test_event_stats_workflow.py` | Integration test |

### Modified Files

| File | Change |
|------|--------|
| `tests/utils_for_testing.py` | Add `assert_event_comparison_valid(dt: xr.DataTree)` assertion helper |
| `_old_code_to_refactor/d0_*.py` | Add refactoring status block |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| Event time series NetCDF missing required variables | Validate `precip_varname` and `stage_varname` (if not None) are present; raise `DataError` with clear message |
| `n_years` derived from data instead of config | Always use `config.n_years_synthesized`; log the value at run start |
| `DataTree.to_zarr` emits `ZarrUserWarning` re: consolidated metadata | Expected and harmless — suppress with `warnings.filterwarnings` during write or accept in logs |
| `DataTree.to_zarr` does not accept `group=` argument | Not needed here — the DataTree is always the root of its own store |
| Rain-only analysis: `stage_varname=None` → no stage return periods | Handled by `compute_univariate_event_return_periods` returning `(df_rain, None)`; `compute_all_multivariate_return_period_combinations` handles `None` stage |
| iloc mapping join fails | Merge on all of `(event_type, year, event_id)` — raise `DataError` with unmatched rows listed if any event has no iloc mapping entry |
| Sim iloc mapping uses deprecated column name `event_number` | Rename to `event_iloc` on load; obs mapping already uses `event_iloc` |

---

## Validation Plan

```bash
# Integration test (primary validation — uses synthetic data via build_event_stats_test_case)
conda run -n ss-fha pytest tests/test_event_stats_workflow.py -v

# Existing tests still pass
conda run -n ss-fha pytest tests/ -v

# Ruff check (before commit)
conda run -n ss-fha ruff check src/ tests/
conda run -n ss-fha ruff format --check src/ tests/
```

---

## Documentation and Tracker Updates

- Update `full_codebase_refactor.md` tracking table: `d0_*` → `COMPLETE`.
- Update master plan bootstrap event stats note (future chunk).

---

## Definition of Done

- [x] xarray-specialist consulted; Decision C resolved and this plan updated
- [x] `src/ss_fha/analysis/event_comparison.py` implemented
- [x] `src/ss_fha/runners/event_stats_runner.py` implemented
- [x] `n_years` sourced from `config.n_years_synthesized`; logged at run start
- [x] Runner rejects `is_comparative_analysis=True` configs with `ConfigurationError`
- [x] Runner rejects configs with `event_data.sim_event_timeseries` absent (`None`) with `ConfigurationError`
- [x] Runner rejects configs with `event_data.sim_event_iloc_mapping` absent (`None`) with `ConfigurationError`
- [x] `event_iloc` always sourced from `sim_event_iloc_mapping`; `event_number` column renamed to `event_iloc` on load; runner raises `DataError` if any event has no mapping entry
- [x] Weather indexers stored as 1D non-index coords; `ds.attrs["weather_event_indices"]` set on all child Datasets; string coords use `encoding={"dtype": str}`
- [x] `--output-format zarr|netcdf` is a required CLI argument (no default)
- [x] Output is a `DataTree` with `/univariate` and `/multivariate` nodes written to `event_comparison.zarr` or `event_comparison.nc`
- [x] `build_event_stats_test_case()` added to `tests/fixtures/test_case_builder.py`
- [x] `assert_event_comparison_valid()` added to `tests/utils_for_testing.py`
- [x] Integration test in `tests/test_event_stats_workflow.py` passes (206/206 across full suite)
- [x] `full_codebase_refactor.md` tracking table updated (`d0_*` → COMPLETE)
- [x] Refactoring status block added to `_old_code_to_refactor/d0_*.py`
- [x] **Move this document to `../implemented/`** — done (2026-03-02)
