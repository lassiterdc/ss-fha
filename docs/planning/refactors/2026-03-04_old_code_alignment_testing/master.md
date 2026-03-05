---
created: 2026-03-04
last_edited: 2026-03-04 — initial draft
---

# Old-Code Alignment Testing Protocol — Master Plan

## Task Understanding

### Requirements

Establish a systematic, enforceable protocol for verifying that refactored functions produce identical outputs to the old code they replaced. The refactor's master plan (item 8) declares this a requirement, but it has only been enforced in one chunk (02C). All other implemented chunks lack direct old-code comparison tests.

This plan has three goals:
1. **Retroactive**: add old-code alignment tests for all implemented computation-bearing chunks (02A, 02B, 02C gaps, 02D, 03A, 03B, 03C)
2. **Prospective**: establish a hard DoD gate for all remaining chunks (03D onward)
3. **Skill strengthening**: improve the `refactor-plan` skill so future refactors automatically include this protocol

### Assumptions

- `_old_code_to_refactor/` stays in the repo throughout the refactor (it does — it's the source of truth)
- Every old script uses `from __inputs import *`; `__inputs.py` creates directories at import time — direct import requires mocking `sys.modules["__inputs"]`
- Infrastructure chunks (00, 01A–01G) ported no computation from old code — they are out of scope for alignment testing
- 02E (empirical frequency analysis) is validated against scipy, which is arguably a stronger reference than old code — low priority; include in inventory table as "scipy-validated, old-code comparison deferred"
- The existing `_empirical_multivariate_return_periods_reference` in `event_statistics.py` is the one ported reference function in the entire codebase. Its test will be migrated into the alignment test package (testing old functions in place is the preference)

### Success Criteria

- `tests/test_old_code_alignment/` package exists and passes `pytest tests/test_old_code_alignment/`
- Function inventory table in this master plan covers every function in every old script, with ported status, new function mapping, and test reference
- Every computation-bearing chunk (02A–02D, 03A–03C) has at least one direct old-function import test OR a committed notebook in `_old_code_to_refactor/demonstrating_functional_alignment/`
- All remaining work chunks (03D onward) include the alignment DoD checkbox and pass it before being marked complete
- `refactor-plan` skill updated with the alignment protocol

---

## Importability Strategy

All old scripts use `from __inputs import *`. `__inputs.py` creates directories at import time and defines hundreds of path constants. Direct import requires mocking `sys.modules["__inputs"]` before importing `__utils` or any script module.

**Implementation**: `tests/test_old_code_alignment/conftest.py` inserts a mock module into `sys.modules["__inputs"]` as a session-scoped fixture, making all named functions in `__utils.py` and the b2/b2b/b2c/b2d scripts importable via normal `import` statements.

Functions in `__utils.py` that have `sys.exit()` inside them must be tested carefully — if the test input triggers the `sys.exit()` path, pytest will catch it as `SystemExit`. Tests must use inputs that do not trigger those paths.

**Notebook fallback**: Used for main-section behaviors (code that lives outside named functions in b1, b2, c1, etc.). These behaviors are orchestration pipelines, not named functions — they cannot be "imported" and require a notebook demonstration showing input→output equivalence.

---

## Test Package Structure

```
tests/test_old_code_alignment/
    __init__.py
    conftest.py                           # sys.modules["__inputs"] mock, session fixture
    test_align_flood_probability.py       # 02A — compute_emp_cdf_and_return_pds
    test_align_bootstrapping.py           # 02B — draw_bootstrap_years, assemble_bootstrap_sample, compute_return_period_indexed_depths
    test_align_event_statistics.py        # 02C — empirical_multivariate_return_periods (migrate existing ref), univariate gaps
    test_align_geospatial.py              # 02D — return_impacted_features, compute_min_return_period_of_feature_impact
    test_align_empirical_freq.py          # 02E — calculate_positions, calculate_return_period (low priority; scipy-validated)
    test_align_flood_hazard_workflow.py   # 03A — notebook fallback (main-section orchestration)
    test_align_uncertainty_workflow.py    # 03B — notebook fallback (main-section orchestration)
    test_align_event_stats_workflow.py    # 03C — notebook fallback (main-section orchestration)
```

Can be skipped in clean environments via `pytest --ignore=tests/test_old_code_alignment/`. Once the refactor is complete and all tests pass, this package becomes optional for ongoing development.

---

## Function Inventory Table

Full inventory of all named functions and main-section behaviors in every old script. Updated as phases complete.

**Columns**: Old name | Old script | New function | Status | Test / notebook

### `__utils.py` — Computation Functions

| Old function | New function | Status | Test |
|---|---|---|---|
| `calculate_positions()` | `core.empirical_frequency_analysis.calculate_positions` | Ported (02E) | `test_empirical_frequency_analysis.py` (scipy ref); alignment test deferred — low priority |
| `calculate_return_period()` | `core.empirical_frequency_analysis.calculate_return_period` | Ported (02E) | Same |
| `compute_return_periods_for_series()` | `core.empirical_frequency_analysis.compute_return_periods_for_series` | Ported (02E) | Same |
| `compute_emp_cdf_and_return_pds()` | `core.flood_probability.compute_emp_cdf_and_return_pds` | Ported (02A) | **Gap** — needs alignment test |
| `sort_last_dim()` | `core.bootstrapping.sort_last_dim` | Ported (02B) | **Gap** |
| `bootstrapping_return_period_estimates()` | `core.bootstrapping.assemble_bootstrap_sample` + `compute_return_period_indexed_depths` | Ported (02B) | **Gap** |
| `write_bootstrapped_samples_to_single_zarr()` | `analysis.uncertainty.combine_and_quantile` (partial) | Ported (02B/03B) | **Gap** |
| `prepare_for_bootstrapping()` | `analysis.uncertainty.prepare_bootstrap_run` | Ported (03B) | **Gap** |
| `compute_univariate_event_return_periods()` | `core.event_statistics.compute_univariate_event_return_periods` | Ported (02C) | Partial — hand-computed values only; no direct old-function import |
| `compute_all_multivariate_return_period_combinations()` | `core.event_statistics.compute_all_multivariate_return_period_combinations` | Ported (02C) | **Gap** |
| `empirical_multivariate_return_periods()` | `core.event_statistics.empirical_multivariate_return_periods` | Ported (02C) | Covered — `_empirical_multivariate_return_periods_reference` in source; **migrate test to alignment package** |
| `compute_AND_multivar_return_period_for_sample()` | Part of `empirical_multivariate_return_periods` internals | Ported (02C) | Covered via reference function |
| `compute_OR_multivar_return_period_for_sample()` | Same | Ported (02C) | Same |
| `bs_samp_of_univar_event_return_period()` | `core.event_statistics.bs_samp_of_univar_event_return_period` | Ported (02C/03C) | **Gap** |
| `bs_samp_of_multivar_event_return_period()` | `core.event_statistics.bs_samp_of_multivar_event_return_period` | Ported (02C/03C) | **Gap** |
| `analyze_bootstrapped_samples()` | `core.event_statistics.return_df_of_events_within_ci` (partial) | Ported (02C/03C) | **Gap** |
| `return_df_of_evens_within_ci_including_event_stats()` | `core.event_statistics.return_df_of_events_within_ci` | Ported (02C/03C) | **Gap** |
| `create_mask_from_shapefile()` | `io.gis_io.create_mask_from_polygon` | Ported (02D) | I/O — not computation; excluded from alignment scope |
| `create_flood_metric_mask()` | `io.gis_io.rasterize_features` | Ported (02D) | I/O wrapper — excluded |
| `return_impacted_features()` | `core.geospatial.return_impacted_features` | Ported (02D) | **Gap** |
| `return_number_of_impacted_features()` | `core.geospatial.return_number_of_impacted_features` | Ported (02D) | **Gap** |
| `compute_min_rtrn_pd_of_impact_for_unique_features()` | `core.geospatial.compute_min_return_period_of_feature_impact` | Ported (02D) | **Gap** |
| `write_zarr()` | `io.zarr_io.write_zarr` | Ported (01D) | I/O — excluded |
| `delete_zarr()` / `delete_directory()` | `io.zarr_io.delete_zarr` | Ported (01D) | I/O — excluded |
| `write_compressed_netcdf()` | `io.netcdf_io.write_compressed_netcdf` | Ported (01D) | I/O — excluded |
| `return_dic_zarr_encodingds()` | `io.zarr_io.default_zarr_encoding` | Ported (01D) | I/O — excluded |
| `return_ds_gridsize()` | `core.geospatial.grid_cell_size_m` | Ported (02D) | **Gap** (simple but should be verified) |
| `isel_first_and_slice_longest()` | Not ported — internal utility used only in old test section | Not ported | N/A |
| `stack_wlevel_dataset()` | Internal to `compute_emp_cdf_and_return_pds` | Absorbed | Covered via compute_emp_cdf alignment test |
| `compute_volume_at_max_flooding()` | Not yet ported | Deferred (3F) | N/A |
| `compute_flooded_area_by_depth_threshold()` | Not yet ported | Deferred (3F) | N/A |
| `analyze_baseline_flooded_area_vs_design_storm_flooded_areas()` | Not yet ported | Deferred (3E/3F) | N/A |
| `compute_floodarea_retrn_pds()` | Not yet ported | Deferred (3F) | N/A |
| `compute_flood_impact_return_periods()` | Not yet ported | Deferred (3F) | N/A |
| `retrieve_unique_feature_indices()` | Internal to `return_impacted_features` | Absorbed | Covered via geospatial alignment test |
| `retrieve_event_statistic_return_periods_indexed_by_event_number()` | Not yet ported | Deferred (3C output) | N/A |
| `return_event_ids_for_all_events_in_ssfha_CI()` | Not yet ported | Deferred | N/A |
| `return_event_ids_for_each_ssfha_quantile()` | Not yet ported | Deferred | N/A |
| `retrieve_ssfha_bootstrapped_CIs()` | Not yet ported | Deferred | N/A |
| `write_netcdf_of_ensemble_based_return_period_floods()` | Not yet ported | Deferred (3E) | N/A |
| `write_netcdf_of_mcds_return_period_floods()` | Not yet ported | Deferred (3E) | N/A |
| `return_ds_sim_flood_probs()` | Not yet ported | Deferred | N/A |
| `sort_dimensions()` | Not yet ported | Deferred | N/A |
| `convert_ob_datavars_to_dtype()` | Not yet ported | Deferred | N/A |
| `identify_missing_events()` | Not ported (QAQC only in old code) | Deferred / excluded | N/A |
| `make_sure_all_event_outputs_are_present()` | Not ported | Deferred / excluded | N/A |
| `eCDF_wasserman()` / `eCDF_stendinger()` | Not ported — superseded by `calculate_positions` | Excluded | N/A |
| `compute_corrs_in_2col_df()` / `compute_sse_and_mse_in_2col_df()` | Not yet ported | Deferred (3F) | N/A |
| `interpolate_return_pd()` | Not yet ported | Deferred | N/A |
| `compute_mean_high_high_tide_from_NOAA_tide_gage()` | Not ported — plotting only in old code | Excluded | N/A |
| `create_bar_label()` / `create_bar_label_one_line()` | Not ported — plotting labels | Excluded (visualization) | N/A |
| `return_current_datetime_string()` | Not ported — utility | Deferred / excluded | N/A |
| `estimate_chunk_memory()` | Not ported — dev utility | Excluded | N/A |
| `get_decimal_places()` | Not ported — utility | Excluded | N/A |
| `return_indices_of_series_geq_lb_and_leq_ub()` | Not ported | Deferred | N/A |
| `check_for_na_in_combined_bs_zarr()` | Not ported | Deferred | N/A |
| `reindex_df_with_event_numbers()` | Not ported | Deferred | N/A |
| `plot_event_constituent_return_periods()` | Not ported — plotting | Deferred (Phase 5) | N/A |

### `__plotting.py` — Deferred to Phase 5

All plotting functions deferred. Any computation embedded in plotting functions (see list below) must be extracted and tested when Phase 5 is implemented.

Computations embedded in plotting functions (must be separated at Phase 5):
- `return_emp_cdf_of_single_loc_in_ensemble()` — computes CDF at a single location (not just plotting)
- `reindex_df_with_event_numbers()` — reindexing computation
- `retreive_design_storm_stats()` — extracts statistics from dataset
- `tidy_hydro_varnames_for_plots()` — string formatting (minor)
- `process_stat_for_hexbin_plot()` — prepares data for plotting
- `retrieve_event_data_for_plotting()` — retrieves and formats event data

### `b1_analyze_triton_outputs_fld_prob_calcs.py`

| Behavior | Status | Notes |
|---|---|---|
| MAIN: Load and validate event data | Ported (03A) | Part of `run_flood_hazard` orchestration |
| MAIN: Compute flood probs for all sim types | Ported (03A) | `run_flood_hazard` with `--sim-type` flag |
| MAIN: Write flood prob zarrs | Ported (03A) | Part of orchestration |
| MAIN: Combine into single dataset | Partially ported | Not explicit in 03A — investigate |

No named functions. Alignment: notebook fallback in `_old_code_to_refactor/demonstrating_functional_alignment/`.

### `b2_sim_vs_obs_fld_ppct.py`

| Behavior | Status | Notes |
|---|---|---|
| MAIN: Bootstrap sim CDFs for PPCCT | Not yet ported | 03D |

No named functions. Will be part of PPCCT implementation (03D). Alignment: notebook or test after 03D implementation.

### `b2b_sim_vs_obs_flod_ppct.py`

| Old function | New function | Status | Test |
|---|---|---|---|
| `interpolate_quantile_function()` | Part of `core.ppcct.calc_ppcc` (03D) | Not yet ported | 03D |
| `calc_emp_vs_fit_corr()` | `core.ppcct.calc_ppcc` (03D) | Not yet ported | 03D |
| `create_data_array_of_ppct_stats()` | `analysis.ppcct` (03D) | Not yet ported | 03D |
| `compute_ppf()` / `compute_cdf()` / `compute_emp_vs_ftd_corr()` | Internal / superseded | Not yet ported | 03D |
| MAIN: Compute observed PPCC | Not yet ported | 03D — orchestration |
| MAIN: Bootstrap PPCC | Not yet ported | 03D — orchestration |

### `b2c_sim_vs_obs_fld_ppct.py`

| Old function | New function | Status | Test |
|---|---|---|---|
| `interpolate_cdf()` | Part of `analysis.ppcct` (03D) | Not yet ported | 03D |
| MAIN: Combine bootstrap correlations | Not yet ported | 03D — orchestration |
| MAIN: Compute rejection threshold | Not yet ported | 03D — computation |
| MAIN: Compute empirical CDF of correlations | Not yet ported | 03D — computation |
| MAIN: Compute p-values | Not yet ported | 03D — computation |

### `b2d_sim_vs_obs_fld_ppct.py`

| Old function / behavior | New function | Status | Test |
|---|---|---|---|
| `plot_PPCT_result()` | `visualization/` (Phase 5) | Deferred | Phase 5 |
| MAIN: Multiple-testing correction | `analysis.ppcct` (03D) | Not yet ported | 03D |
| MAIN: Bootstrap distribution of rejection rates | `analysis.ppcct` (03D) | Not yet ported | 03D |

### `c1_fpm_confidence_intervals_bootstrapping.py`

| Behavior | Status | Notes |
|---|---|---|
| MAIN: Loop bootstrap samples, call `bootstrapping_return_period_estimates` | Ported (03B) | `run_bootstrap_sample` orchestration |

No named functions. Alignment: notebook fallback.

### `c1b_fpm_confidence_intervals_bootstrapping.py`

| Old function | New function | Status | Test |
|---|---|---|---|
| `compute_bootstrapped_flood_depth_cis()` | `analysis.uncertainty.combine_and_quantile` | Ported (03B) | **Gap** — needs alignment test |
| `analyze_1_loc()` | Deferred (Phase 5 / QAQC) | Deferred | Phase 5 |
| MAIN: Combine bootstrap samples | Ported (03B) | `combine_and_quantile` orchestration |
| MAIN: Compute CIs | Ported (03B) | Same |

### `c2_fpm_confidence_intervals.py`

All main-section behaviors. No named functions. Visualization/QAQC only — deferred to Phase 5.

### `d0_computing_event_statistic_probabilities.py`

| Behavior | Status | Notes |
|---|---|---|
| MAIN: Compute univariate return periods | Ported (03C) | `run_event_comparison` orchestration |
| MAIN: Compute multivariate return periods | Ported (03C) | Same |
| MAIN: Bootstrap univariate return periods | Ported (03C) | Same |
| MAIN: Bootstrap multivariate return periods | Ported (03C) | Same |
| MAIN: Compute confidence intervals | Ported (03C) | Same |
| MAIN: Create events-in-CI CSV | Ported (03C) | Same |

No named functions. Alignment: notebook fallback.

### `d2_compare_ensemble-based_with_design_storms.py`

| Old function | Status | Notes |
|---|---|---|
| `spatial_resampling()` | Not yet ported | Deferred (3E) |
| All MAIN behaviors | Not yet ported | Deferred (3E) |

### `e2_investigating_flood_depth_area_probability.py`

All deferred to 3F (flood risk). No named functions — all main-section.

### `f1_box_and_whiskers_event_rtrn_vs_fld_rtrn.py`

| Old function | Status | Notes |
|---|---|---|
| `classify_events_for_targeted_return_period()` | Not yet ported | Deferred (3F) |
| `return_impact_varname_from_list()` | Not yet ported | Deferred (3F) |
| `return_flood_impact_ci_bounds()` | Not yet ported | Deferred (3F) |
| `create_box_and_whiskers()` | Not yet ported — plotting | Deferred (Phase 5) |
| All MAIN behaviors | Not yet ported | Deferred (3F) |

### `f2_comparing_event_and_flood_prob_by_aoi.py`

| Old function | Status | Notes |
|---|---|---|
| `hexbin_wrapper()` | Deferred — plotting | Phase 5 |
| `pearson_corr()` | Partially computation (computes corr before annotating) — note for Phase 5 | Phase 5 |
| `flood_impact_vs_return_pd()` | Deferred — plotting | Phase 5 |
| `label_xticks_target_return_pd()` | Deferred — plotting utility | Phase 5 |
| `label_yticks_target_return_pd()` | Deferred — plotting utility | Phase 5 |
| All MAIN behaviors | Not yet ported | Deferred (3F) |

### `h_experiment_design_figures.py`

| Old function | Status | Notes |
|---|---|---|
| `plot_experimental_design()` | Deferred — plotting | Phase 5 (low priority) |
| All MAIN behaviors | Deferred | Phase 5 (low priority) |

### `_qaqc_verifying_function_of_bndry_cndtn.py`

No named functions. All QAQC / plotting — deferred to Phase 5 or excluded.

---

## Phase Status Table

| Phase | Title | Status | Doc |
|-------|-------|--------|-----|
| 1 | Setup: package structure + `__inputs` mock | Pending | `1_setup.md` |
| 2 | Retroactive: 02A flood probability | Pending | `2_retro_02A_flood_probability.md` |
| 3 | Retroactive: 02B bootstrapping | Pending | `3_retro_02B_bootstrapping.md` |
| 4 | Retroactive: 02C event statistics gaps | Pending | `4_retro_02C_event_statistics.md` |
| 5 | Retroactive: 02D geospatial | Pending | `5_retro_02D_geospatial.md` |
| 6 | Retroactive: 03A/03B/03C orchestration notebooks | Pending | `6_retro_03ABC_notebooks.md` |
| 7 | Prospective: DoD gate on 03D onward | Pending | `7_prospective_dod.md` |
| 8 | Skill strengthening: `refactor-plan` + lessons learned appendix | Pending | `8_skill_strengthening.md` |

---

## Dependencies

**Upstream**: None — this plan is a prerequisite for all other remaining work chunks.

**Downstream**:
- `docs/planning/refactors/2026-02-25_full_codebase_refactor/work_chunks/03D_workflow3_ppcct.md` — blocked until Phase 1–7 of this plan are complete (or at minimum Phase 1 is complete and the prospective DoD gate is established)

---

## Known Bug Found During Audit

During test audit, `assert_event_comparison_valid` was found to be imported in `tests/test_event_stats_workflow.py` but is **not defined** in `tests/utils_for_testing.py`. This will cause an `ImportError` at test collection. This is a bug introduced during 03C implementation. It must be fixed in Phase 1 of this plan (as part of package setup — investigate and either implement the missing function or remove the import).

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| `__inputs` mock doesn't expose all required attributes | Build the mock comprehensively from `__inputs.py` attribute list; use `unittest.mock.MagicMock()` with `spec` to catch missing attributes |
| Old function hits `sys.exit()` during test | Use inputs that don't trigger error branches; document which branches trigger `sys.exit` |
| Old function reads from real file paths set by `__inputs` | If a function opens a file, use a fixture that provides a real test zarr; prefer testing pure computation paths only |
| Bug found in old code — what's "correct"? | When discrepancy found, document in `_old_code_to_refactor/bugs_fixed_during_refactor/` with proof of incorrectness before resolving |
| 02E alignment deprioritized — old code never compared | Mark explicitly in inventory table as "scipy-validated"; treat as low risk |

---

## Definition of Done

- [ ] `tests/test_old_code_alignment/` package created with `conftest.py` `__inputs` mock
- [ ] `assert_event_comparison_valid` bug investigated and resolved
- [ ] Alignment tests written for 02A, 02B, 02C (gaps), 02D — all using direct old-function import
- [ ] `_empirical_multivariate_return_periods_reference` test migrated to alignment package
- [ ] Orchestration notebooks committed for 03A, 03B, 03C in `_old_code_to_refactor/demonstrating_functional_alignment/`
- [ ] Function inventory table complete — all old scripts covered, all gaps resolved or explicitly deferred
- [ ] Prospective DoD gate documented in `full_codebase_refactor.md` and added to all incomplete work chunk plans (03D onward)
- [ ] `refactor-plan` skill updated with alignment protocol language and DoD checkbox template
- [ ] Lessons learned appendix added to `full_codebase_refactor.md`
- [ ] `pytest tests/test_old_code_alignment/ -v` passes
- [ ] `pytest tests/ -v` passes (no regressions)
- [ ] Architecture.md not changed (no module structure changes in this plan)
- [ ] `docs/planning/ideas.md` entry removed (copied to Appendix below)
- [ ] If performance or memory risks surfaced, entries added to `docs/planning/tech_debt_known_risks.md`

---

## Appendix: Originating Idea

### Old-code alignment testing protocol

**Surfaced**: 2026-03-04
**Priority**: High
**Dependency**: `docs/planning/refactors/2026-02-25_full_codebase_refactor/full_codebase_refactor.md`
**Description**: The refactor lacks a systematic, enforceable protocol for verifying that new functions produce identical outputs to the old code they replaced. The master plan mentions ported-function testing (item 8) but this is not enforced at the work chunk level — only chunk 02C implemented it via a ported reference function. All other implemented chunks (02A, 02B, 02D, 02E, 03A, 03B) have gaps: tests validate schema, mathematical properties, or scipy reference values but do not directly compare outputs against the old code. This idea formalizes the protocol and closes those gaps retroactively and prospectively.
**Approach notes**:
- **Direct import preferred**: Where old scripts can be imported without side effects (no `sys.exit`, no global writes, no GUI), import the old function directly in pytest and assert output equivalence. This is the gold standard.
- **Notebook fallback (hard gate)**: When direct import is impossible (script-level globals, `from __inputs import *`, side effects), require a Jupyter notebook in `_old_code_to_refactor/demonstrating_functional_alignment/` that shows: (a) an explanation of why direct import was not feasible, (b) the entire old function, (c) the entire new function, and (d) a side-by-side math comparison on representative inputs. The notebook must be self-contained and serve as a standalone document — a reader should understand the full context without referring to any other file. The notebook must be committed alongside the plan. A brief comment in the test file must also note why direct import was not feasible and point to the notebook path.
- **Dedicated test file/folder**: All old-vs-new comparison tests live in `tests/test_old_code_alignment/` (package with `__init__.py`) or a single `tests/test_old_code_alignment.py`. Separate from unit/integration tests so they can be skipped when old code import fails in a clean environment.
- **Function inventory table**: The plan must produce and maintain a table of every function (and named `main`-section behavior) in every old script, with columns: old function/section name, old script, new function(s), what was ported vs. deferred (e.g., plotting deferred to Phase 5), and the test(s) that confirm output equivalence.
- **Deferred portions**: Plotting-only functions are exempt from output comparison (they produce figures, not data). But if a plotting function performs any computation before plotting, that computation must be separated and tested. Note all deferred portions explicitly in the table.
- **Risk 1 — missed functionality**: If a core behavior exists only in the `main` section of an old script (not in any named function), it may be silently dropped in the refactor. The inventory must catalog all `main`-section behaviors explicitly, not just named functions.
- **Risk 2 — old code errors**: Blindly asserting output equivalence against old code bakes in any old-code bugs. Where mathematical correctness can be verified independently (e.g., via scipy, hand calculation, or domain reasoning), include an independent correctness assertion alongside the equivalence assertion. If a discrepancy between old and new is found, investigate and document which is correct before resolving. When a bug in the old code is confirmed and fixed in the refactor, generate a Jupyter notebook report in `_old_code_to_refactor/bugs_fixed_during_refactor/` documenting: the old code, the error, the proof of incorrectness, and the corrected implementation.
- **Retroactive scope**: All implemented work chunks (00, 01A–01G, 02A–02E, 03A–03C) must be audited and addressed in their original work chunk order — dependencies were captured in that ordering, so no reordering is needed.
- **Prospective scope**: Every remaining work chunk (03D onward) gets a hard DoD checkbox: `- [ ] Old-code alignment test: direct import or committed notebook in _old_code_to_refactor/demonstrating_functional_alignment/ for all core computation functions`. No chunk is marked complete without this gate.
- **`refactor-plan` skill strengthening (final phase)**: Each work chunk in this plan must record lessons learned in a dedicated appendix of the master refactor plan (`full_codebase_refactor.md`), capturing insights about verifying refactors against old code. The final phase of this multi-phase plan is to comprehensively strengthen `refactor-plan` using that accumulated appendix. That phase should note that the volume of lessons learned may warrant generating a set of instructional documents injected into `refactor-plan`, and should consider creating a subdirectory (e.g., `~/.claude/skills/refactor-plan/protocols/`) if the number of documents is high. This phase runs last — only after all retroactive and prospective alignment work is complete.
- **Blocking gate**: Implementation of 03D (and all subsequent work chunks) is blocked until this plan is written, reviewed, and the retroactive audit scope is agreed upon.
**Related ideas**: `docs/planning/refactors/2026-02-25_full_codebase_refactor/full_codebase_refactor.md` (master plan item 8 is the seed of this idea)
