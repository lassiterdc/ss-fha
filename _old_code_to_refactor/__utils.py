# %%
# =============================================================================
# REFACTORING STATUS (ss-fha full_codebase_refactor)
# Last updated: 2026-02-26 (updated for 02B)
#
# I/O FUNCTIONS — migrated to src/ss_fha/io/ (Phase 1D, complete)
#   write_zarr()                  → ss_fha.io.zarr_io.write_zarr
#   delete_zarr()                 → ss_fha.io.zarr_io.delete_zarr
#   return_dic_zarr_encodingds()  → ss_fha.io.zarr_io.default_zarr_encoding
#   write_compressed_netcdf()     → ss_fha.io.netcdf_io.write_compressed_netcdf
#   create_mask_from_shapefile()  → ss_fha.io.gis_io.create_mask_from_shapefile
#   create_flood_metric_mask()    → ss_fha.io.gis_io.rasterize_features
#   (read_zarr, read_netcdf, read_shapefile are new — no old equivalent)
#
# CORE COMPUTATION FUNCTIONS — partially migrated in Phase 2A
#   calculate_positions()             → ss_fha.core.flood_probability.calculate_positions
#   calculate_return_period()         → ss_fha.core.flood_probability.calculate_return_period
#   compute_emp_cdf_and_return_pds()  → ss_fha.core.flood_probability.compute_emp_cdf_and_return_pds
#   sort_dimensions()                 → ss_fha.core.utils.sort_dimensions
#
#
# BOOTSTRAP FUNCTIONS — partially migrated in Phase 2B
#   sort_last_dim()                   → ss_fha.core.bootstrapping.sort_last_dim
#   (bootstrapping_return_period_estimates — pure computation kernel extracted into:)
#     draw_bootstrap_years()          → ss_fha.core.bootstrapping.draw_bootstrap_years  [new]
#     assemble_bootstrap_sample()     → ss_fha.core.bootstrapping.assemble_bootstrap_sample  [new]
#     compute_return_period_indexed_depths() → ss_fha.core.bootstrapping.compute_return_period_indexed_depths  [new]
#
#   NOT MIGRATED (deferred to Phase 3B runner):
#   prepare_for_bootstrapping()           — orchestration/file-management; runner layer
#   bootstrapping_return_period_estimates() — fully replaced by the three new functions above
#   write_bootstrapped_samples_to_single_zarr() — combine step; runner layer
#   check_for_na_in_combined_bs_zarr()    — post-combine QA; runner layer
#
#   NOT YET MIGRATED (remaining Phase 2+):
#   compute_return_periods_for_series() — deferred to later phase (univariate event-level analysis)
#   All other functions in this file are not yet migrated.
# =============================================================================

import xarray as xr
import dask.array as da
from pathlib import Path
from scipy.stats.mstats import plotting_positions
import numpy as np
import pandas as pd
import time
import sys
import matplotlib.pyplot as plt
import shutil
import matplotlib.colors as mcolors
from local.__inputs import (
    COMPRESSION_LEVEL,
    COORD_EPSG,
    MIN_THRESH_FLDING,
    FPATH_ENSEMBLE_DESIGN_FLOODS,
    F_SIM_FLOOD_PROBS,
    F_SIM_FLOOD_PROBS_SURGEONLY,
    F_SIM_FLOOD_PROBS_RAINONLY,
    F_SIM_FLOOD_PROBS_TRITON,
    LST_KEY_FLOOD_THRESHOLDS,
    TIMESERIES_BUFFER_BEFORE_FIRST_RAIN_H,
    LST_KEY_FLOOD_THRESHOLDS_FOR_SENSITIVITY_ANALYSIS,
    ALPHA,
    BETA,
    N_YEARS_SYNTHESIZED,
    ASSIGN_DUP_VALS_MAX_RETURN,
    MC_QUANTS_FOR_FLOOD_MAPPING,
    FPATH_MC_DESIGN_FLOODS_MULTIVAR_AND,
    DIC_DPTH_DSC_LOOKUP,
    F_BS_UNCERTAINTY_EVENTS_IN_CI,
    F_WSHED_SHP,
    LST_FLOOD_DEPTH_BIN_EDGES,
    F_SIM_TSERIES,
    F_RTRN_PDS_SEA_WATER_LEVEL,
    F_RTRN_PDS_RAINFALL,
    F_SIM_FLOOD_PROBS_EVENT_NUMBER_MAPPING,
    F_SIM_MULTIVAR_RETURN_PERIODS,
    RAIN_WINDOWS_MIN,
    F_TRITON_OUTPUTS_DSGN,
    FLD_RTRN_PD_ALPHA,
    PATTERN_EVENT_NUMBER_MAPPING,
    F_SIM_FLOOD_PROBS_BOOTSTRAPPED_CIS,
    LST_RTRNS,
)


from datetime import datetime, timezone
import tzlocal  # pip install tzlocal
from tqdm import tqdm


def analyze_baseline_flooded_area_vs_design_storm_flooded_areas(
    ds_baseline,
    da_sim_flood_probs_bs_rtrn,
    ds_alt_ensemble,
    lst_ds_mcds,
    ds_triton_dsgn,
    ds_dsgn_tseries,
    dsgn_rain_dur: int,
    target_return_pd,
    ensemble_type_ordering=[
        "2D_compound",
        "surge_only",
        "rain_only",
        "1driver_max",
    ],  # from ds_alt_ensemble
    design_storm_type_ordering=["compound", "surge", "rain"],
    verbose=True,
):
    df_flood_volumes = pd.DataFrame(
        columns=[
            "year",
            "simtype",
            "rainfall_mm",
            "event_duration_hr",
            "flooded_volume",
        ]
    )
    lst_df_flooded_volumes = []
    # if "quantile" in da_baseline_og.coords:
    #     quants = da_baseline_og["quantile"].to_series()
    #     baseline_nonzero_flood_mask = da_baseline_og.sel(quantile=quants.min()) > 0

    #     lst_ds_rtrn = []
    #     lst_titles = []
    #     pattern = "ensemble-based, q={}"
    #     for quant in quants:
    #         lst_ds_rtrn.append(da_baseline_og.sel(quantile=quant))
    #         lst_titles.append(pattern.format(quant))
    #     print("using median flood hazard estimate as comparison baseline")
    #     da_baseline = da_baseline_og.sel(quantile=0.5)
    # else:
    # n_events_contributing = int(da_baseline.n_unique_events.values)
    da_baseline = ds_baseline["max_wlevel_m"]
    baseline_nonzero_flood_mask = da_baseline > 0
    lst_ds_rtrn = [da_baseline.where(baseline_nonzero_flood_mask)]
    lst_titles = [
        f"ensemble-based"  # ({int(n_events_contributing)} unique events contributing)"
    ]

    if da_sim_flood_probs_bs_rtrn is not None:
        quants = da_sim_flood_probs_bs_rtrn["quantile"].to_series()
        pattern = "SS-FHA, q={}"
        for quant in quants:
            baseline_nonzero_flood_mask_quant = (
                da_sim_flood_probs_bs_rtrn.sel(quantile=quant) > 0
            )
            lst_ds_rtrn.append(
                da_sim_flood_probs_bs_rtrn.sel(quantile=quant).where(
                    baseline_nonzero_flood_mask_quant
                )
            )
            lst_titles.append(pattern.format(quant))

    lst_ds_rtrn_diff = []
    lst_titles_diff = []
    grid_size = return_ds_gridsize(da_baseline)
    ensemble_flooded_area_by_threshold = compute_flooded_area_by_depth_threshold(
        da_baseline, output_series_name="ensemble_compound"
    )
    max_dsgn_wlevel = ds_triton_dsgn.max_wlevel_m.sel(
        data_source="dsgn", model="tritonswmm"  #  simtype="compound"
    )
    # process design storms
    lst_s_dsgn_flooded_area_by_threshold = []
    # pull design storm datasets
    for event_type in design_storm_type_ordering:
        max_dsgn_wlevel_subset = (
            max_dsgn_wlevel.sel(event_type=event_type, year=target_return_pd)
            .dropna(dim="event_id", how="all")
            .reset_coords(drop=True)
        )
        for event_id in max_dsgn_wlevel_subset["event_id"].values:
            if event_type == "1driver_max":
                df_dsgn_tseries = (
                    ds_dsgn_tseries.sel(
                        year=target_return_pd, event_id=event_id, event_type="rain"
                    )
                    .to_dataframe()
                    .dropna()
                    .reset_index()
                    .set_index("timestep")
                )
            else:
                df_dsgn_tseries = (
                    ds_dsgn_tseries.sel(
                        year=target_return_pd, event_id=event_id, event_type=event_type
                    )
                    .to_dataframe()
                    .dropna()
                    .reset_index()
                    .set_index("timestep")
                )
            idx_event = df_dsgn_tseries.index
            tstep = pd.Series(idx_event).diff().mode().iloc[0]
            rain_depth_mm = (
                df_dsgn_tseries["mm_per_hr"] * (tstep / np.timedelta64(1, "h"))
            ).sum()
            event_dur_h = (
                int(
                    (idx_event.max() - idx_event.min() + tstep) / np.timedelta64(1, "h")
                )
                - 2 * TIMESERIES_BUFFER_BEFORE_FIRST_RAIN_H
            )
            if event_type in ["rain", "compound"]:
                if event_dur_h != dsgn_rain_dur:
                    continue
                if event_type == "rain":
                    simtype = "rainonly"
                if event_type == "compound":
                    simtype = "compound"
                # sys.exit("work")
                title = f"{event_dur_h}hr SCS Type II design rain event ({rain_depth_mm:.0f}mm)\n"
                if event_type == "compound":
                    title += f" with {target_return_pd} year boundary water levels"
                else:
                    title += f" with median boundary water levels"
            if event_type == "surge":
                title = (
                    f"{target_return_pd} year boundary water levels\nwith no rainfall"
                )
                simtype = "surgeonly"
            if event_type == "1driver_max":
                title = f"max of {target_return_pd} year water level and {event_dur_h}hr rainfall"
                simtype = "surgeonly"
            if verbose:
                print("design storm simulations used for comparison:")
                sim_idx = dict(
                    event_id=event_id,
                    event_type=event_type,
                    year=target_return_pd,
                    simtype=simtype,
                )
                print(f"designs storm sim: {sim_idx}")
            max_dsgn_wlevel_subset = (
                max_dsgn_wlevel_subset.sel(event_id=event_id, simtype=simtype)
                .reset_coords(drop=True)
                .load()
            )

            lst_titles.append(title)
            lst_titles_diff.append(title)
            if "median boundary water levels" in title:
                short_title = "rain-only"
            elif "no rainfall" in title:
                short_title = "water level-only"
            else:
                short_title = "compound"
            # if "mm)" in title:
            #     short_title = f"{short_title} {rain_depth_mm:.0f}mm"
            dsgn_mask_nonzero_flooding = max_dsgn_wlevel_subset > 0
            lst_ds_rtrn.append(
                max_dsgn_wlevel_subset.where(
                    dsgn_mask_nonzero_flooding | baseline_nonzero_flood_mask
                )
            )  # .where(max_dsgn_wlevel_subset>MIN_THRESH_FLDING)
            # diff_sim_minus_design = (da_baseline - max_dsgn_wlevel_subset)
            diff_alt_minus_baseline = max_dsgn_wlevel_subset - da_baseline
            # diff_sim_minus_design = diff_sim_minus_design.where(~np.isclose(diff_sim_minus_design, 0), np.nan)
            lst_ds_rtrn_diff.append(
                diff_alt_minus_baseline.where(
                    dsgn_mask_nonzero_flooding | baseline_nonzero_flood_mask
                )
            )
            # lst_titles_diff.append(f"ensemble_minus_design_strm_{event_type}_{event_dur_h}_hr")
            thresh0 = LST_KEY_FLOOD_THRESHOLDS[0]
            dsgn_flooded_area_by_threshold = pd.Series().astype(float)
            for thresh1 in LST_KEY_FLOOD_THRESHOLDS[1::]:
                dsgn_area_flooded_m2 = (
                    len(
                        max_dsgn_wlevel_subset.where(
                            (max_dsgn_wlevel_subset >= thresh0)
                            & (max_dsgn_wlevel_subset < thresh1)
                        )
                        .to_dataframe()["max_wlevel_m"]
                        .dropna()
                    )
                    * grid_size**2
                )
                dsgn_flooded_area_by_threshold[
                    f"{thresh0} $\\le$ depth (m) $<$ {thresh1}"
                ] = dsgn_area_flooded_m2
                thresh0 = thresh1
            dsgn_flooded_area_by_threshold.name = short_title
            lst_s_dsgn_flooded_area_by_threshold.append(dsgn_flooded_area_by_threshold)
            dsgn_total_flood_volume = (
                max_dsgn_wlevel_subset.to_dataframe()["max_wlevel_m"].sum()
                * grid_size**2
            )
            idx = len(df_flood_volumes)
            df_flood_volumes.loc[idx, "simtype"] = short_title
            df_flood_volumes.loc[idx, "flooded_volume"] = dsgn_total_flood_volume
            df_flood_volumes.loc[idx, "rainfall_mm"] = rain_depth_mm
            df_flood_volumes.loc[idx, "event_duration_hr"] = event_dur_h
    # process ensemble alternatives
    lst_s_alt_flooded_area_by_threshold = []
    for ensemble_type in ensemble_type_ordering:
        ds_alt_ensemble_subset = ds_alt_ensemble.sel(ensemble_type=ensemble_type)
        da_alt_ensemble_subset = ds_alt_ensemble_subset["max_wlevel_m"]
        # n_events_contributing = int(ds_alt_ensemble_subset.n_unique_events.values)
        title = f"ensemble-based {ensemble_type}"  # ({int(n_events_contributing)} unique events contributing)"
        lst_titles.append(title)
        lst_titles_diff.append(title)
        alt_mask_nonzero_flooding = da_alt_ensemble_subset > 0
        lst_ds_rtrn.append(
            da_alt_ensemble_subset.where(
                alt_mask_nonzero_flooding | baseline_nonzero_flood_mask
            )
        )
        diff_alt_minus_baseline = da_alt_ensemble_subset - da_baseline
        lst_ds_rtrn_diff.append(
            diff_alt_minus_baseline.where(
                alt_mask_nonzero_flooding | baseline_nonzero_flood_mask
            )
        )

        # PROCESSING BELOW HERE
        thresh0 = LST_KEY_FLOOD_THRESHOLDS[0]
        alt_flooded_area_by_threshold = pd.Series().astype(float)
        for thresh1 in LST_KEY_FLOOD_THRESHOLDS[1::]:
            alt_area_flooded_m2 = (
                len(
                    da_alt_ensemble_subset.where(
                        (da_alt_ensemble_subset >= thresh0)
                        & (da_alt_ensemble_subset < thresh1)
                    )
                    .to_dataframe()["max_wlevel_m"]
                    .dropna()
                )
                * grid_size**2
            )
            alt_flooded_area_by_threshold[
                f"{thresh0} $\\le$ depth (m) $<$ {thresh1}"
            ] = alt_area_flooded_m2
            thresh0 = thresh1
        short_title = f"ensemble {ensemble_type}"
        alt_flooded_area_by_threshold.name = short_title
        lst_s_alt_flooded_area_by_threshold.append(alt_flooded_area_by_threshold)
        alt_total_flood_volume = (
            da_alt_ensemble_subset.to_dataframe()["max_wlevel_m"].sum() * grid_size**2
        )
        idx = len(df_flood_volumes)
        df_flood_volumes.loc[idx, "simtype"] = short_title
        df_flood_volumes.loc[idx, "flooded_volume"] = alt_total_flood_volume
        df_flood_volumes.loc[idx, "rainfall_mm"] = rain_depth_mm
        df_flood_volumes.loc[idx, "event_duration_hr"] = event_dur_h

    # process mcds alternatives
    lst_s_mcds_flooded_area_by_threshold = []
    for ds_mcds in lst_ds_mcds:
        mcds_formulation = ds_mcds.attrs["event_formulation"]
        mcds_event_stat = ds_mcds.attrs["event_stat"]
        for ensemble_type in ds_mcds.ensemble_type.to_series():
            for quant in ds_mcds["quantile"].to_series():
                ds_mcds_subset = ds_mcds.sel(
                    ensemble_type=ensemble_type, quantile=quant
                )
                da_alt_ensemble_subset = ds_mcds_subset["max_wlevel_m"]
                title = f"MCDS {ensemble_type} {mcds_formulation} {mcds_event_stat} (quantile = {quant})"
                lst_titles.append(title)
                lst_titles_diff.append(title)
                alt_mask_nonzero_flooding = da_alt_ensemble_subset > 0

                if da_sim_flood_probs_bs_rtrn is not None:
                    baseline_nonzero_flood_mask_quant = (
                        da_sim_flood_probs_bs_rtrn.sel(quantile=quant) > 0
                    )
                else:
                    baseline_nonzero_flood_mask_quant = baseline_nonzero_flood_mask

                lst_ds_rtrn.append(
                    da_alt_ensemble_subset.where(
                        alt_mask_nonzero_flooding | baseline_nonzero_flood_mask_quant
                    )
                )
                if da_sim_flood_probs_bs_rtrn is not None:
                    diff_alt_minus_baseline = (
                        da_alt_ensemble_subset
                        - da_sim_flood_probs_bs_rtrn.sel(quantile=quant)
                    )
                    print(
                        "MCDS is being compared to ensemble estimate for the SAME quantile (i.e., 0.05 quantile MCDS is compared to 0.05 SS)"
                    )
                else:
                    diff_alt_minus_baseline = da_alt_ensemble_subset - da_baseline
                lst_ds_rtrn_diff.append(
                    diff_alt_minus_baseline.where(
                        alt_mask_nonzero_flooding | baseline_nonzero_flood_mask_quant
                    )
                )

                thresh0 = LST_KEY_FLOOD_THRESHOLDS[0]
                alt_flooded_area_by_threshold = pd.Series().astype(float)
                for thresh1 in LST_KEY_FLOOD_THRESHOLDS[1::]:
                    alt_area_flooded_m2 = (
                        len(
                            da_alt_ensemble_subset.where(
                                (da_alt_ensemble_subset >= thresh0)
                                & (da_alt_ensemble_subset < thresh1)
                            )
                            .to_dataframe()["max_wlevel_m"]
                            .dropna()
                        )
                        * grid_size**2
                    )
                    alt_flooded_area_by_threshold[
                        f"{thresh0} $\\le$ depth (m) $<$ {thresh1}"
                    ] = alt_area_flooded_m2
                    thresh0 = thresh1
                short_title = f"mcds q={quant}"
                alt_flooded_area_by_threshold.name = short_title
                lst_s_mcds_flooded_area_by_threshold.append(
                    alt_flooded_area_by_threshold
                )
                alt_total_flood_volume = (
                    da_alt_ensemble_subset.to_dataframe()["max_wlevel_m"].sum()
                    * grid_size**2
                )
                idx = len(df_flood_volumes)
                df_flood_volumes.loc[idx, "simtype"] = short_title
                df_flood_volumes.loc[idx, "flooded_volume"] = alt_total_flood_volume
    df_flood_volumes.loc[:, "year"] = target_return_pd
    lst_df_flooded_volumes.append(df_flood_volumes)
    lst_flooded_areas_by_threshold = (
        [ensemble_flooded_area_by_threshold]
        + lst_s_dsgn_flooded_area_by_threshold
        + lst_s_alt_flooded_area_by_threshold
        + lst_s_mcds_flooded_area_by_threshold
    )
    df_flooded_areas = pd.concat(lst_flooded_areas_by_threshold, axis=1) / (1000**2)
    return (
        df_flood_volumes,
        lst_ds_rtrn,
        lst_titles,
        lst_titles_diff,
        lst_ds_rtrn_diff,
        lst_df_flooded_volumes,
        df_flooded_areas,
    )


def return_ds_gridsize(ds):
    grid_size = ds.x.to_dataframe()["x"].sort_values().diff().mode()[0]
    return grid_size


def compute_volume_at_max_flooding(ds_flood_depths):
    grid_size = return_ds_gridsize(ds_flood_depths)
    total_flood_volume = (
        ds_flood_depths.to_dataframe()["max_wlevel_m"].sum() * grid_size**2
    )
    return total_flood_volume


def compute_flooded_area_by_depth_threshold(ds_flood_depths, output_series_name: str):
    grid_size = return_ds_gridsize(ds_flood_depths)
    thresh0 = LST_KEY_FLOOD_THRESHOLDS[0]
    ensemble_flooded_area_by_threshold = pd.Series().astype(float)
    for thresh1 in LST_KEY_FLOOD_THRESHOLDS[1::]:
        ensemble_area_flooded_m2 = (
            len(
                ds_flood_depths.where(
                    (ds_flood_depths >= thresh0) & (ds_flood_depths < thresh1)
                )
                .to_dataframe()["max_wlevel_m"]
                .dropna()
            )
            * grid_size**2
        )
        ensemble_flooded_area_by_threshold[
            f"{thresh0} $\\le$ depth (m) $<$ {thresh1}"
        ] = ensemble_area_flooded_m2
        thresh0 = thresh1
    ensemble_flooded_area_by_threshold.name = output_series_name
    return ensemble_flooded_area_by_threshold


def return_ds_sim_flood_probs():

    ds_sim_flood_probs_compound = xr.open_dataset(
        F_SIM_FLOOD_PROBS, engine="zarr", chunks="auto"
    ).expand_dims(ensemble_type=["compound"])
    ds_sim_flood_probs_surge = xr.open_dataset(
        F_SIM_FLOOD_PROBS_SURGEONLY, engine="zarr", chunks="auto"
    ).expand_dims(ensemble_type=["surge_only"])
    ds_sim_flood_probs_rain = xr.open_dataset(
        F_SIM_FLOOD_PROBS_RAINONLY, engine="zarr", chunks="auto"
    ).expand_dims(ensemble_type=["rain_only"])
    ds_sim_flood_probs_trition = xr.open_dataset(
        F_SIM_FLOOD_PROBS_TRITON, engine="zarr", chunks="auto"
    ).expand_dims(ensemble_type=["2D_compound"])

    ds_sim_flood_probs = xr.concat(
        [
            ds_sim_flood_probs_compound,
            ds_sim_flood_probs_surge,
            ds_sim_flood_probs_rain,
            ds_sim_flood_probs_trition,
        ],
        dim="ensemble_type",
    )

    return ds_sim_flood_probs


# within the function
def retrieve_event_statistic_return_periods_indexed_by_event_number():
    ds_sim_tseries = xr.open_dataset(F_SIM_TSERIES).chunk(
        dict(timestep=-1, year=-1, event_type=1, event_id=-1)
    )
    sim_idx_names = ds_sim_tseries.coords.to_index().names
    event_idx_names = [name for name in sim_idx_names if name != "timestep"]

    df_wlevel_return_pds = pd.read_csv(
        F_RTRN_PDS_SEA_WATER_LEVEL, index_col=event_idx_names
    ).filter(like="return_pd_yrs")
    df_rain_return_pds = pd.read_csv(
        F_RTRN_PDS_RAINFALL, index_col=event_idx_names
    ).filter(like="return_pd_yrs")

    # processing multivariate return periods

    ds_multivar_rtrn = xr.open_dataset(F_SIM_MULTIVAR_RETURN_PERIODS, engine="zarr")
    df_multivar_rtrn_AND = (
        ds_multivar_rtrn.to_dataframe()
        .dropna()["empirical_multivar_rtrn_yrs_AND"]
        .unstack(level="event_stats")
    )
    new_cols = [f"{col} (AND)" for col in df_multivar_rtrn_AND.columns]
    df_multivar_rtrn_AND.columns = new_cols

    df_multivar_rtrn_OR = (
        ds_multivar_rtrn.to_dataframe()
        .dropna()["empirical_multivar_rtrn_yrs_OR"]
        .unstack(level="event_stats")
    )
    new_cols = [f"{col} (OR)" for col in df_multivar_rtrn_OR.columns]
    df_multivar_rtrn_OR.columns = new_cols

    df_sim_flood_probs_event_num_mapping = pd.read_csv(
        F_SIM_FLOOD_PROBS_EVENT_NUMBER_MAPPING
    ).set_index(event_idx_names)

    df_event_return_periods = pd.concat(
        [
            df_sim_flood_probs_event_num_mapping,
            df_rain_return_pds,
            df_wlevel_return_pds,
            df_multivar_rtrn_AND,
            df_multivar_rtrn_OR,
        ],
        axis=1,
    ).set_index("event_number")
    return df_event_return_periods


def retrieve_ssfha_bootstrapped_CIs():
    if Path(F_SIM_FLOOD_PROBS_BOOTSTRAPPED_CIS).exists():
        ds_sim_flood_probs_bs = xr.open_dataset(
            F_SIM_FLOOD_PROBS_BOOTSTRAPPED_CIS, engine="zarr", chunks="auto"
        )
        print(f"Loaded ds_sim_flood_probs_bs from {F_SIM_FLOOD_PROBS_BOOTSTRAPPED_CIS}")
        ds_sim_flood_probs_bs = ds_sim_flood_probs_bs.sel(return_pd_yrs=LST_RTRNS)
    else:
        print(
            "Bootstrapped ensemble-based flood depths file does not exist so confidence intervals cannot be included in the plots of single location probability-depth curves."
        )
        print("############")
        ds_sim_flood_probs_bs = None
    return ds_sim_flood_probs_bs


def return_event_ids_for_all_events_in_ssfha_CI():
    da_sim_flood_probs_bs = retrieve_ssfha_bootstrapped_CIs()["max_wlevel_m"]
    ds_sim_flood_probs = return_ds_sim_flood_probs()
    da_sim_ssfha = ds_sim_flood_probs.sel(ensemble_type="compound")["max_wlevel_m"]
    lst_ds_events_in_ci = []

    mask_watershed = return_mask_dataset_from_polygon(
        ds_sim_flood_probs, shapefile_path=F_WSHED_SHP
    )
    for target_return_pd in tqdm(da_sim_flood_probs_bs["return_pd_yrs"]):
        # trying to figure out how to return all events within the CI
        ds_subset = da_sim_flood_probs_bs.sel(return_pd_yrs=target_return_pd)

        ds_subset_ul = ds_subset.sel(quantile=ds_subset["quantile"].max())
        ds_subset_ll = ds_subset.sel(quantile=ds_subset["quantile"].min())

        mask_events_in_ci = (da_sim_ssfha >= ds_subset_ll) & (
            da_sim_ssfha <= ds_subset_ul
        )
        mask_events_in_ci = mask_events_in_ci.expand_dims(
            {"return_pd_yrs": [target_return_pd]}
        ).where(mask_watershed)
        mask_events_in_ci.name = "event_ids_in_CI"

        mask_events_in_ci["notes"] = (
            "na values are assigned for gridcells outside the watershed boundary"
        )

        lst_ds_events_in_ci.append(mask_events_in_ci)

    ds_events_in_CI = xr.merge(lst_ds_events_in_ci)

    return ds_events_in_CI


def return_event_ids_for_each_ssfha_quantile(
    da_sim_flood_probs_bs=None, f_zarr_out=None
):
    if da_sim_flood_probs_bs is None:
        da_sim_flood_probs_bs = retrieve_ssfha_bootstrapped_CIs()["max_wlevel_m"]
    ds_sim_flood_probs = return_ds_sim_flood_probs()
    da_sim_ssfha = ds_sim_flood_probs.sel(ensemble_type="compound")["max_wlevel_m"]
    lst_ds_events_per_quant = []

    mask_watershed = return_mask_dataset_from_polygon(
        ds_sim_flood_probs, shapefile_path=F_WSHED_SHP
    )
    for target_return_pd in tqdm(da_sim_flood_probs_bs["return_pd_yrs"]):
        for quant in da_sim_flood_probs_bs["quantile"]:
            ds_subset = da_sim_flood_probs_bs.sel(
                return_pd_yrs=target_return_pd, quantile=quant
            )

            da_event_ids = abs(da_sim_ssfha - ds_subset).argmin(dim=["event_number"])[
                "event_number"
            ]
            da_event_ids.name = "contributing_event_id"
            da_event_ids = da_event_ids.where(mask_watershed).expand_dims(
                {"return_pd_yrs": [target_return_pd], "quantile": [quant]}
            )
            da_event_ids.attrs["notes"] = (
                "na values are assigned for gridcells outside the watershed boundary"
            )
            lst_ds_events_per_quant.append(da_event_ids)
    if f_zarr_out is None:
        ds_CI_event_ids = xr.combine_by_coords(lst_ds_events_per_quant)
    return ds_CI_event_ids


def write_netcdf_of_ensemble_based_return_period_floods(
    ds_sim_flood_probs, return_periods
):
    lst_ds = []
    mask_watershed = return_mask_dataset_from_polygon(
        ds_sim_flood_probs, shapefile_path=F_WSHED_SHP
    )
    for target_return_pd in tqdm(return_periods):
        # subset x-y locations with nearest return period
        for ensemble_type in ds_sim_flood_probs["ensemble_type"].to_series():
            # sys.exit('work')
            ds_subset = ds_sim_flood_probs.sel(ensemble_type=ensemble_type)
            ds_subset = ds_subset.expand_dims(
                {
                    "year": [int(target_return_pd)],
                    "ensemble_type": [ensemble_type],  # make sure this is a list
                }
            )

            da_event_ids = (
                abs(ds_subset["return_pd_yrs"] - target_return_pd)
                .argmin(dim=["event_number"])["event_number"]
                .load()
            )
            da_event_ids.name = "contributing_event_id"

            da_sim_rtrn_pd_flood = (
                ds_subset["max_wlevel_m"].sel(event_number=da_event_ids).load()
            )

            # mask_nonzero_flooding_in_watershed = (
            #     da_sim_rtrn_pd_flood > 0
            # ) & mask_watershed

            da_event_ids = da_event_ids.where(mask_watershed)
            da_event_ids.attrs["notes"] = (
                "na values are assigned for gridcells outside the watershed boundary"
            )
            da_sim_rtrn_pd_flood = da_sim_rtrn_pd_flood.where(mask_watershed)
            da_sim_rtrn_pd_flood.attrs["notes"] = (
                "na values are assigned for gridcells outside the watershed boundary"
            )

            lst_ds.append(da_event_ids)

            da_sim_rtrn_pd_flood = da_sim_rtrn_pd_flood.rio.write_crs(COORD_EPSG)

            lst_depths = [MIN_THRESH_FLDING] + LST_FLOOD_DEPTH_BIN_EDGES

            lst_da_event_ids = []
            for depth_threshold in lst_depths:
                df_events_contributing = da_event_ids.where(
                    (da_sim_rtrn_pd_flood >= depth_threshold) & mask_watershed
                ).to_dataframe()

                unique_events = pd.Series(
                    df_events_contributing[
                        ~df_events_contributing["contributing_event_id"].isna()
                    ]
                    .loc[:, "event_number"]
                    .unique()
                )

                unique_events.name = (
                    f"event_numbers_with_geq_{depth_threshold}m_flooding"
                )
                unique_events.index.name = f"int_contributing_event_idx"
                da_n_unique = xr.DataArray(data=unique_events)
                da_n_unique = da_n_unique.expand_dims(
                    {
                        "year": [int(target_return_pd)],
                        "ensemble_type": [ensemble_type],  # make sure this is a list
                    }
                )
                lst_da_event_ids.append(da_n_unique)

            ds_sim_rtrn_pd_flood = da_sim_rtrn_pd_flood.to_dataset()
            ds_sim_rtrn_pd_flood.attrs["notes"] = (
                "event counts are based are based on gridcells within the watershed boundary"
            )

            ds_sim_rtrn_pd_flood = xr.merge(lst_da_event_ids + [ds_sim_rtrn_pd_flood])
            lst_ds.append(ds_sim_rtrn_pd_flood)
    ds_ensemble_return_pds = xr.merge(lst_ds)

    # compute the max wlevel for surge only and rain only
    da_max_wlevel_rain_only = ds_ensemble_return_pds["max_wlevel_m"].sel(
        ensemble_type="rain_only"
    )
    da_max_wlevel_surge_only = ds_ensemble_return_pds["max_wlevel_m"].sel(
        ensemble_type="surge_only"
    )
    da_max_wlevel_1driver_max = da_max_wlevel_rain_only.where(
        da_max_wlevel_rain_only >= da_max_wlevel_surge_only, da_max_wlevel_surge_only
    )

    da_max_wlevel_1driver_max = da_max_wlevel_1driver_max.expand_dims(
        {
            "ensemble_type": ["1driver_max"],  # make sure this is a list
        }
    )

    ds_ensemble_return_pds = xr.merge(
        [ds_ensemble_return_pds, da_max_wlevel_1driver_max]
    )
    write_compressed_netcdf(ds_ensemble_return_pds, FPATH_ENSEMBLE_DESIGN_FLOODS)
    return


def write_netcdf_of_mcds_return_period_floods(
    ds_sim_flood_probs, mcds_formulation, mcds_event_stat, return_periods, fpath_save
):
    df_event_rtrns_with_CI = (
        pd.read_csv(F_BS_UNCERTAINTY_EVENTS_IN_CI, index_col=[0, 1, 2, 3, 4, 5])
        .loc[
            pd.IndexSlice[
                mcds_formulation,
                mcds_event_stat,
                :,
                :,
                :,
                :,
            ]
        ]
        .dropna(axis=1)
    )
    lst_ds = []
    for target_return_pd in return_periods:
        e_nums = (
            df_event_rtrns_with_CI.loc[pd.IndexSlice[target_return_pd, :, :, :]]
            .reset_index()["event_number"]
            .unique()
        )
        da_wlevels_mcds = ds_sim_flood_probs.sel(
            event_number=e_nums, ensemble_type="compound"
        )["max_wlevel_m"]

        da_wlevels_mcds_flood_map = da_wlevels_mcds.quantile(
            q=MC_QUANTS_FOR_FLOOD_MAPPING,
            dim="event_number",
            method="closest_observation",
        )
        da_wlevels_mcds_flood_map = da_wlevels_mcds_flood_map.expand_dims(
            {
                "year": [int(target_return_pd)],
                "ensemble_type": ["compound"],  # make sure this is a list
            }
        )
        lst_ds.append(da_wlevels_mcds_flood_map)
    ds_mcds_return_pds = xr.merge(lst_ds)

    ds_mcds_return_pds.attrs["event_formulation"] = mcds_formulation
    ds_mcds_return_pds.attrs["event_stat"] = mcds_event_stat

    write_compressed_netcdf(ds_mcds_return_pds, fpath_save)
    return


def return_current_datetime_string():
    local_tz = tzlocal.get_localzone()
    now = datetime.now(local_tz)
    current_datetime = now.strftime("%Y-%m-%d %H:%M %Z %z")
    return current_datetime


def write_compressed_netcdf(ds, f_out, verbose=True):
    comp = dict(zlib=True, complevel=COMPRESSION_LEVEL)
    encoding = {var: comp for var in ds.data_vars}
    ds.attrs["date_written"] = return_current_datetime_string()
    if verbose:
        print(f"writing file: {f_out}")
    ds.to_netcdf(f_out, encoding=encoding, engine="h5netcdf")
    ds = xr.open_dataset(f_out)
    return ds, f_out


def identify_missing_events(ds_test, df_input_event_summaries):
    x, y = ds_test.x.to_series().quantile(0.5), ds_test.y.to_series().quantile(0.5)
    s_simtypes = ds_test.simtype.to_series()
    s_models = ds_test.model.to_series()
    ds_test_1loc = ds_test.sel(x=x, y=y, method="nearest")
    lst_df_missing_events = []
    data_source = ds_test.data_source.to_series().iloc[0]
    for simtype in s_simtypes:
        for model in s_models:
            df_all_events = (
                ds_test_1loc.sel(simtype=simtype, model=model)
                .reset_coords()["max_wlevel_m"]
                .to_dataframe()
            )
            df_all_events = df_all_events.dropna()
            if len(df_all_events) == 0:
                print(
                    f"{data_source} {simtype} events in {model} were not simulated (this is most likely deliberate)"
                )
                continue
            df_all_events = df_all_events.reset_index().set_index(
                df_input_event_summaries.index.names
            )
            s_joined = df_input_event_summaries.join(df_all_events, how="left").loc[
                :, "max_wlevel_m"
            ]
            idx_events_missing = s_joined[s_joined.isna()].index
            df_missing_events = pd.DataFrame(
                index=idx_events_missing, columns=["simtype", "model", "data_source"]
            )
            df_missing_events["simtype"] = simtype
            df_missing_events["model"] = model
            df_missing_events["data_source"] = data_source
            lst_df_missing_events.append(df_missing_events.reset_index())
    df_missing_events = (
        pd.concat(lst_df_missing_events).reset_index(drop=True).drop_duplicates()
    )
    return df_missing_events


def make_sure_all_event_outputs_are_present(ds_triton, s_events, sim_smry_idx):
    df_1loc = ds_triton.isel(dict(x=0, y=0))["max_wlevel_m"].to_dataframe().dropna()
    dic_idx_missing_events = dict()
    for grp_id, df_group in df_1loc.groupby(level=["simtype", "model", "data_source"]):
        idx_missing_events = (
            s_events.to_frame().join(df_group, how="left")["max_wlevel_m"].isna()
        )
        idx_missing_events = idx_missing_events[idx_missing_events]
        dic_idx_missing_events[grp_id] = idx_missing_events
    lst_idx_missing = []
    for key in dic_idx_missing_events.keys():
        lst_idx_missing.append(dic_idx_missing_events[key])
    all_missing = (
        pd.concat(lst_idx_missing)
        .reset_index()
        .drop_duplicates()[sim_smry_idx]
        .sort_values(["year", "event_id"])
    )
    if len(all_missing) > 0:
        print(
            f"WARNING: One or more outputs for the following events are missing:\n{all_missing}"
        )
    else:
        print("No missing events in outputs")
    return all_missing


def write_zarr(ds, f_out, mode="w"):
    ds.attrs["date_written"] = return_current_datetime_string()
    delete_zarr(f_out, attempt_time_limit_s=10)
    ds.to_zarr(
        f_out,
        mode=mode,
        encoding=return_dic_zarr_encodingds(ds, clevel=5),
        consolidated=True,
    )
    ds_out = xr.open_zarr(f_out, consolidated=True)
    ds_out.attrs["success"] = "true"
    ds_out.to_zarr(f_out, mode="a", consolidated=True)
    return ds_out


def compute_mean_high_high_tide_from_NOAA_tide_gage(
    f_noaa_tide_gage_csv, feet_per_meter
):
    df_tide_gage = pd.read_csv(
        f_noaa_tide_gage_csv, parse_dates=["date_time"], index_col="date_time"
    )
    df_tide_gage["tide_prediction_m"] = df_tide_gage["predicted_wl"] / feet_per_meter
    # daily_max_tide_pred = df_tide_gage.groupby(df_tide_gage.index.date)['tide_prediction_m'].max()

    # counts per day (DatetimeIndex at midnight)
    counts_per_day = df_tide_gage.groupby(df_tide_gage.index.floor("D")).size()

    expected_count = counts_per_day.mode().iloc[0]

    # days with the expected (complete) number of records
    full_days = counts_per_day[counts_per_day == expected_count].index

    # filter first, then group using the *filtered* index
    filtered = df_tide_gage[df_tide_gage.index.floor("D").isin(full_days)]
    daily_max_tide_pred = filtered.groupby(filtered.index.floor("D"))[
        "tide_prediction_m"
    ].max()

    # make sure the index is a DatetimeIndex at midnight
    daily_max_tide_pred.index = pd.to_datetime(daily_max_tide_pred.index)

    # filter for full years
    # Step 1: identify first full day (already guaranteed by filtering)
    start_date = daily_max_tide_pred.index.min()

    # Step 2: define the end date to be exactly 1 year after start_date,
    # but truncated to the last full year that fits in the data
    full_years = (
        daily_max_tide_pred.index[-1] - start_date
    ).days // 365  # full years count
    end_date = start_date + pd.DateOffset(years=full_years)

    # Step 3: truncate the series to the full-year period only
    daily_max_tide_pred_years = daily_max_tide_pred.loc[
        start_date : end_date - pd.Timedelta(days=1)
    ]

    mean_high_high_tide = daily_max_tide_pred_years.mean()

    return mean_high_high_tide


def create_flood_metric_mask(gdf_impact_feature, ds_sim_flood_probs):
    from rasterio.features import rasterize

    shapes = [
        (row_tuple[1].geometry, row_tuple[0])
        for row_tuple in gdf_impact_feature.iterrows()
    ]

    existing_raster = ds_sim_flood_probs["max_wlevel_m"]
    transform = existing_raster.rio.transform()
    xs = existing_raster.x.to_series()
    ys = existing_raster.y.to_series()

    mask_shape = len(ys), len(xs)
    raster_array = np.zeros(mask_shape, dtype=np.int32)

    # Rasterize the polygon onto the existing grid
    raster_array = rasterize(
        shapes,
        out_shape=mask_shape,
        transform=transform,
        fill=-9999,  # Background value
        nodata=-9999,
        all_touched=True,
        dtype=np.int32,
    )

    ds_features = pd.DataFrame(raster_array, index=ys, columns=xs).stack().to_xarray()

    return ds_features


def create_mask_from_shapefile(
    da_to_mask, shapefile_path=None, series_single_row_of_gdf=None
):  # , COORD_EPSG):
    # da_to_mask, shapefile_path = da_sim_wlevel, f_mitigation_aois
    xs = da_to_mask.x.to_series()
    ys = da_to_mask.y.to_series()
    from shapely.geometry import mapping
    import geopandas as gpd
    import rasterio.features

    if shapefile_path is not None:
        gdf = gpd.read_file(shapefile_path)
        shapes = [
            mapping(geom) for geom in gdf.geometry
        ]  # Convert geometries to GeoJSON-like format
    if series_single_row_of_gdf is not None:
        shapes = [mapping(series_single_row_of_gdf.geometry)]
    mask = rasterio.features.geometry_mask(
        shapes,
        transform=da_to_mask.rio.transform(),
        invert=True,
        out_shape=(len(ys), len(xs)),
    )
    return mask


def return_mask_dataset_from_polygon(
    da_to_mask, shapefile_path=None, series_single_row_of_gdf=None
):
    xs = da_to_mask.x.to_series()
    ys = da_to_mask.y.to_series()
    ar_subarea_mask = create_mask_from_shapefile(
        da_to_mask,
        shapefile_path=shapefile_path,
        series_single_row_of_gdf=series_single_row_of_gdf,
    )
    ds_subarea_mask = (
        pd.DataFrame(ar_subarea_mask, index=ys, columns=xs).stack().to_xarray()
    )
    # ds_subarea_mask.plot(x = "x", y = "y")
    return ds_subarea_mask


def sort_last_dim(arr):
    return np.sort(arr, axis=-1)


def check_for_na_in_combined_bs_zarr(ds_combined):
    # x, y = (np.float64(3697992.8434817656), np.float64(1060829.6483268768))
    na_values_present = (
        ds_combined.isel(x=200, y=200).to_dataframe()["max_wlevel_m"].isna().any()
    )
    if na_values_present == True:
        print("WARNING: the following code snippet indicates there are missing values.")
        print(
            "ds_combined.isel(x = 200, y = 200).to_dataframe()['max_wlevel_m'].isna().any()"
        )
    return na_values_present


def write_bootstrapped_samples_to_single_zarr(
    lst_f,
    f_out,
    rewrite_if_file_already_exists,
    currently_running,
    rewrite_if_any_na=True,
    print_benchmarks=True,
):
    if rewrite_if_file_already_exists == False:
        if Path(f_out).exists():
            print(
                f"rewrite_if_file_already_exists={rewrite_if_file_already_exists} and the target output file already exists: {f_out}"
            )
            ds_combined = xr.open_dataset(f_out, engine="zarr").chunk("auto")
            na_values_present = check_for_na_in_combined_bs_zarr(ds_combined)
            if na_values_present == True:
                print("WARNING: there are NA values are present in the dataset....")
                if rewrite_if_any_na == False:
                    print("not reprocessing...")
                    return ds_combined
                else:
                    print("reprocessing...")
            else:
                print("not reprocessing...")
                return ds_combined

    bm_time = time.time()

    dic_files = dict(idx=[], file=[])
    for f in lst_f:
        idx = int(f.split("bs_")[-1].split("_")[0])
        dic_files["idx"].append(idx)
        dic_files["file"].append(f)

    s_files = pd.DataFrame(dic_files).sort_values("idx").set_index("idx")["file"]

    if currently_running:
        s_files = s_files.iloc[0:-1]

    # s_files = s_files.iloc[0:10]

    ds_combined = xr.open_mfdataset(s_files, engine="zarr").chunk(
        dict(return_pd_yrs=-1, x=10, y=10, bs_id=-1)
    )
    if print_benchmarks:
        print(f"{(time.time() - bm_time)/60:.2f} min to consolidate datasets")

    bm_time = time.time()
    delete_zarr(f_out, attempt_time_limit_s=10)
    Path(f_out).parent.mkdir(parents=True, exist_ok=True)
    ds_combined.to_zarr(
        f_out,
        mode="w",
        encoding=return_dic_zarr_encodingds(ds_combined, clevel=5),
        consolidated=True,
    )
    if print_benchmarks:
        print(f"{(time.time() - bm_time)/60:.2f} min to export {f_out}")
    # check for missing vlaues
    ds_combined = xr.open_dataset(f_out, engine="zarr").chunk("auto")
    check_for_na_in_combined_bs_zarr(ds_combined)
    return ds_combined


def prepare_for_bootstrapping(
    lst_files_processed,
    pickup_where_left_off,
    currently_running,
    n_bs_samples,
    split_string="_",
    delete_existing=None,
):
    from tqdm import tqdm

    move_forward_with_bootstrapping = True
    bs_id_start = 0
    if len(lst_files_processed) > 1:
        bs_ids_done = []
        for f in lst_files_processed:
            bs_ids_done.append(int(f.split("bs_")[-1].split(split_string)[0]))
        if pickup_where_left_off:
            bs_id_start = max(bs_ids_done) - int(currently_running)
        else:  # delete all files
            if delete_existing is None:
                delete_existing = False
                val = input(
                    f"write 'yes' to delete existing bootstrapped samples. Any other input will NOT delete. (you are being prompted because pickup_where_left_off={pickup_where_left_off})"
                )
                if val.lower() == "yes":
                    delete_existing = True
            if delete_existing:
                import os

                print("deleting existing bootstrapped samples")
                for f in tqdm(lst_files_processed):
                    if ".zarr" in f:
                        delete_zarr(f)
                    else:
                        os.remove(f)
    if pickup_where_left_off and (len(lst_files_processed) == n_bs_samples):
        print(
            f"Halting because pickup_where_left_off is set to {pickup_where_left_off} and len(lst_files_processed) == n_bs_samples = {len(lst_files_processed) == n_bs_samples}"
        )
        move_forward_with_bootstrapping = False
    return bs_id_start, move_forward_with_bootstrapping


def bootstrapping_return_period_estimates(
    resampled_years,
    years_with_at_least_1_event,
    df_sim_flood_probs_event_num_mapping,
    ds_sim_flood_probs,
    dir_bootstrap_sample_destination,
    alpha,
    beta,
    n_ensemble_years,
    bs_id,
    print_benchmarks=False,
):
    """
    dir_bootstrap_sample_destination is the destination for the bootstrapped samples
    """
    # create water level dataset with all the resampled years
    bm_time = time.time()
    da_wlevel_list = []
    next_first_event_idx = 0
    for year in resampled_years:
        if year not in years_with_at_least_1_event:
            # print(f"Skipping year {year} because there were no events in the stochastically generated dataset")
            continue
        lst_event_nums = df_sim_flood_probs_event_num_mapping[
            df_sim_flood_probs_event_num_mapping["year"] == year
        ].event_number.to_list()
        ds_wlevel_for_year = ds_sim_flood_probs.sel(event_number=lst_event_nums)  # [
        #     "max_wlevel_m"
        # ]
        da_wlevel_for_year = ds_wlevel_for_year["max_wlevel_m"]
        # ds_wlevel_for_year["event_id"]
        # da_event_id =
        # da_wlevel_for_year["event_number_og"] = da_wlevel_for_year["event_number"]
        og_event_nums = (
            da_wlevel_for_year["event_number"].to_dataframe().iloc[:, 0].values
        )

        da_wlevel_for_year["event_number"] = np.arange(
            next_first_event_idx,
            next_first_event_idx + len(og_event_nums),
        )

        next_first_event_idx = da_wlevel_for_year["event_number"].to_series().max() + 1
        da_wlevel_list.append(da_wlevel_for_year)

    stacked_data = xr.combine_by_coords(da_wlevel_list)
    # export stacked bootstrapped sample to zarr
    dir_temp_zarrs = f"{dir_bootstrap_sample_destination}/_scratch/bs_{bs_id}/"
    Path(dir_temp_zarrs).mkdir(parents=True, exist_ok=True)
    lst_zarr_tmp = []
    # write stacked data to file
    f_zar_temp = f"{dir_temp_zarrs}sim_wlevel_stacked.zarr"
    lst_zarr_tmp.append(f_zar_temp)
    chunk_sizes = dict(x=10, y=10, event_number=-1)
    delete_zarr(f_zar_temp)
    stacked_data.chunk(chunk_sizes).to_zarr(
        f_zar_temp,
        mode="w",
        encoding=return_dic_zarr_encodingds(stacked_data, clevel=5),
        consolidated=True,
    )
    stacked_data = xr.open_dataset(f_zar_temp, engine="zarr", chunks=chunk_sizes)
    if print_benchmarks:
        print(f"{(time.time() - bm_time)/60:.2f} min to write {f_zar_temp}")
    bm_time = time.time()

    n_events = len(stacked_data.event_number.to_series())
    # sort data (need to index it all by return period instead of event number)
    sorted_ds = xr.apply_ufunc(
        sort_last_dim,  # Function to apply
        stacked_data["max_wlevel_m"],  # Data variable to process
        input_core_dims=[["event_number"]],  # Core dimension to apply along
        output_core_dims=[["return_pd_yrs"]],  # Output dimension name
        dask_gufunc_kwargs={"output_sizes": dict(return_pd_yrs=n_events)},
        vectorize=True,  # Allow broadcasting over other dimensions
        dask="parallelized",  # Use Dask for parallel computation
        output_dtypes=[stacked_data["max_wlevel_m"].dtype],  # Data type of output
    )
    # write sorted data to file
    f_zar_temp = f"{dir_temp_zarrs}sim_wlevel_stacked_sorted.zarr"
    lst_zarr_tmp.append(f_zar_temp)
    chunk_sizes = dict(x=10, y=10, return_pd_yrs=-1)
    delete_zarr(f_zar_temp)
    sorted_ds.chunk(chunk_sizes).to_zarr(
        f_zar_temp,
        mode="w",
        encoding=return_dic_zarr_encodingds(sorted_ds, clevel=5),
        consolidated=True,
    )
    sorted_ds = xr.open_dataset(f_zar_temp, engine="zarr", chunks=chunk_sizes)
    if print_benchmarks:
        print(f"{(time.time() - bm_time)/60:.2f} min to write {f_zar_temp}")
    bm_time = time.time()
    # compute return periods for a single location
    ## extract 1 location with flooding to verify correct sorting and for calculating return periods
    df_max = stacked_data["max_wlevel_m"].max("event_number").to_dataframe()
    idx_higher_quant = df_max["max_wlevel_m"] == df_max["max_wlevel_m"].quantile(
        0.995, interpolation="nearest"
    )
    x_quant, y_quant = df_max["max_wlevel_m"][idx_higher_quant].index.values[0]
    x, y = x_quant, y_quant  # x_max, y_max
    s_sorted_ds_test = (
        sorted_ds.sel(x=x, y=y).to_dataframe()["max_wlevel_m"].sort_index()
    )
    if not (s_sorted_ds_test.diff().dropna() >= 0).all():
        sys.exit("issue with sorting")
    ar_pos = np.sort(
        plotting_positions(s_sorted_ds_test.values, alpha=alpha, beta=beta).data
    )

    ar_rtrn_pds = calculate_return_period(
        ar_pos, n_years=n_ensemble_years, n_events=n_events
    )

    # assign return period index
    sorted_ds["return_pd_yrs"] = ar_rtrn_pds
    # sorted_ds.sel(x=x, y=y).to_dataframe()["max_wlevel_m"].plot(logx=True)

    # subset quantized return periods based on index from the parent dataset
    og_rtrn_pds = (
        ds_sim_flood_probs["return_pd_yrs"]
        .isel(x=0, y=0)
        .to_series()
        .sort_values()
        .reset_index(drop=True)
    )
    og_rtrn_pds_reduced = og_rtrn_pds.round(1).drop_duplicates()[1:].values
    og_rtrn_pds_reduced_nearest0p5 = pd.Series(
        np.round(og_rtrn_pds_reduced * 2) / 2
    ).unique()

    sorted_ds = sorted_ds.sel(
        return_pd_yrs=og_rtrn_pds_reduced_nearest0p5, method="nearest"
    )
    sorted_ds["return_pd_yrs"] = og_rtrn_pds_reduced_nearest0p5
    sorted_ds.attrs["notes"] = (
        "bootstrapped dataset is subset to return periods quantized to 0.5 year intervals to save disk space"
    )

    # save flood depth by return period dataset to zarr
    f_out_zarr = f"{dir_bootstrap_sample_destination}bs_{bs_id}_rtrn_idxd.zarr"
    ## if the file already exists, delete it
    delete_zarr(f_out_zarr)
    chunk_sizes = dict(return_pd_yrs=-1, x=10, y=10, bs_id=-1)

    sorted_ds["bs_id"] = bs_id
    sorted_ds = sorted_ds.expand_dims(dict(bs_id=[bs_id])).chunk(chunk_sizes)
    sorted_ds.chunk(chunk_sizes).to_zarr(
        f_out_zarr,
        mode="w",
        encoding=return_dic_zarr_encodingds(sorted_ds, clevel=5),
        consolidated=True,
    )
    if print_benchmarks:
        print(f"{(time.time() - bm_time)/60:.2f} min to write {f_out_zarr}")
    s_retrn_yr = sorted_ds.return_pd_yrs.to_series()
    if (~(s_retrn_yr.sort_index() == s_retrn_yr.index)).sum() > 0:
        sys.exit("encountered problem")
    # clear memory
    lst_vars = [sorted_ds, stacked_data, df_max, idx_higher_quant]
    for var in lst_vars:
        try:
            del var
        except:
            pass
    for f_zar_temp in lst_zarr_tmp:
        delete_zarr(f_zar_temp)
    return


def compute_sse_and_mse_in_2col_df(df_2col_og):
    df_2col = df_2col_og.copy()
    df_diffs = df_2col_og.diff(axis=1).dropna(axis=1)
    mae = df_diffs.abs().mean().values[0]
    mse = (df_diffs**2).mean().values[0]
    s_mse_and_mae = pd.Series().astype(float)
    s_mse_and_mae.loc["mae"] = mae
    s_mse_and_mae.loc["mse"] = mse
    s_mse_and_mae.name = "loss_function"
    return s_mse_and_mae


def compute_corrs_in_2col_df(df_2col_og, pearson_on_log=False):
    df_2col = df_2col_og.copy()
    methods = ["pearson", "kendall", "spearman"]
    dic_cors = dict()
    for method in methods:
        if (method == "pearson") and (pearson_on_log == True):
            df_cor = df_2col.apply(np.log).corr(method=method)
        else:
            df_cor = df_2col.corr(method=method)
        cor = df_cor.iloc[0, 1]
        dic_cors[method] = cor
    s_corrs_by_method = pd.Series(dic_cors, name="correlation")
    s_corrs_by_method.index = methods
    s_corrs_by_method.index.name = "corr_method"
    return s_corrs_by_method


def estimate_chunk_memory(ds, input_chunk_sizes=None):
    """
    Estimate memory requirements for each chunk of an Xarray dataset.

    Parameters:
    -----------
    ds : xr.Dataset or xr.DataArray
        The Xarray dataset or data array.
    chunk_sizes : dict, optional
        A dictionary specifying the chunk sizes for each dimension (e.g., {'time': 100, 'latitude': 500}).
        If None, it uses the current chunk sizes in the dataset.

    Returns:
    --------
    float
        The estimated memory usage per chunk in megabytes (MB).
    """
    import numpy as np

    #
    # Use existing chunk sizes if none are provided
    if input_chunk_sizes is None:
        chunk_sizes = {dim: ds.chunks.get(dim, (len(ds[dim]),))[0] for dim in ds.dims}
    else:
        chunk_sizes = input_chunk_sizes.copy()
        # assume full chunking on all other datasets
        keys_to_skip = chunk_sizes.keys()
        for dim in ds.dims:
            if dim not in keys_to_skip:
                chunk_sizes[dim] = len(ds[dim])
    #
    # Estimate the total number of elements in one chunk
    total_elements = np.prod(list(chunk_sizes.values()))
    #
    # Get the dtype of the dataset (assuming homogeneous dtype across variables)
    # Get the dtype of the dataset, or assume float32 if no data variables
    if isinstance(ds, xr.DataArray):
        dtype = ds.dtype
    elif len(ds.data_vars) > 0:
        dtype = next(iter(ds.data_vars.values())).dtype
    else:
        # print("No data variables found. Assuming float32 for estimation.")
        dtype = np.float32
    #
    # Calculate the size of each element in bytes
    element_size = np.dtype(dtype).itemsize
    # Estimate the total memory for one chunk (in bytes)
    total_bytes = total_elements * element_size
    # Convert to megabytes (MB) for convenience
    total_mb = total_bytes / (1024**2)
    # print(f"Estimated memory per chunk: {total_mb:.2f} MB")
    return total_mb, chunk_sizes


def return_dic_zarr_encodingds(ds, clevel=5):
    # import zarr
    from numcodecs import Blosc

    # from numcodecs.zarr3 import Blosc as Zarr3Blosc
    # from zarr.codecs import BloscCodec

    encoding = {}
    # compressor = Zarr3Blosc(cname="zstd", clevel=clevel, shuffle="shuffle")
    # compressor = Zarr3Blosc(cname="zstd", clevel=clevel, shuffle=Zarr3Blosc)
    # compressor = Zarr3Blosc(cname="zstd", clevel=clevel, shuffle=1)
    compressor = {
        "compressor": Blosc(cname="zstd", clevel=clevel, shuffle=Blosc.SHUFFLE)
    }
    # compressor = {
    #     "compressors": {
    #         "name": "blosc",
    #         "configuration": {
    #             "cname": "zstd",
    #             "clevel": clevel,
    #             "shuffle": "shuffle"  # Use string instead of numcodecs.Blosc.SHUFFLE
    #         }
    #     }
    # }
    try:
        for var in ds.data_vars:
            if ds[var].dtype.kind in {
                "i",
                "u",
                "f",
            }:  # 'i'=int, 'u'=unsigned int, 'f'=float
                encoding[var] = compressor
    except:  # is a data array
        encoding[ds.name] = compressor
    # Handle coordinate encoding
    for coord in ds.coords:
        if (ds[coord].dtype.kind == "U") or (
            ds[coord].dtype.kind == "O"
        ):  # For Unicode string coordinates or object coordiantes
            # Compute the maximum string length if the data is backed by Dask
            # if isinstance(ds[coord].data, da.Array):
            max_len = ds[coord].str.len().values.max()
            # else:
            #     max_len = ds[coord].str.len().max().item()  # For non-Dask arrays (NumPy)
            encoding[coord] = {
                "dtype": f"<U{max_len}",  # Preserve max length
            }
            # encoding[coord] = {
            #             'dtype': 'object'  # Let Zarr handle it as an object
            #         }
    return encoding


######### WORK - debugging
# ds = stacked_data.to_dataset()
# print(return_dic_zarr_encodingds(ds, clevel=5))
# ds.to_zarr(f_zar_out, mode='w', encoding = return_dic_zarr_encodingds(ds, clevel=5), consolidated=True)
# #%%


# ds = xr.Dataset(
#     {"foo": (("x", "y"), np.random.rand(4, 5))},
#     coords={
#         "x": [10, 20, 30, 40],
#         "y": pd.date_range("2000-01-01", periods=5),
#         "z": ("x", list("abcd")),
#     },
# )
# print(return_dic_zarr_encodingds(ds, clevel=5))

# ds.to_zarr(f_zar_out, mode='w', encoding = return_dic_zarr_encodingds(ds, clevel=5), consolidated=True)
# #%%
# # ds = stacked_data.to_dataset()


# # stacked_data_zarr = stacked_data.to_zarr()
# import xarray as xr
# import numcodecs
# import zarr
# from numcodecs.zarr3 import Blosc as Zarr3Blosc
# # from numcodecs import Blosc

# print("Xarray version:", xr.__version__)
# print("Numcodecs version:", numcodecs.__version__)
# print("Zarr version:", zarr.__version__)


# ds = xr.Dataset(
#     {"foo": (("x", "y"), np.random.rand(4, 5))},
#     coords={
#         "x": [10, 20, 30, 40],
#         "y": pd.date_range("2000-01-01", periods=5),
#         "z": ("x", list("abcd")),
#     },
# )
# # ds.to_zarr(f_zar_out, mode='w')

# clevel = 5
# # compressor = Zarr3Blosc(cname="zstd", clevel=clevel, shuffle="shuffle")
# compressor = (Blosc(cname="zstd", clevel=clevel, shuffle=Blosc.SHUFFLE),)
# dic_encoding = {}
# dic_encoding["foo"] = {"compressors": compressor}

# print("Encoding dictionary:", dic_encoding)
# print("Compressor type:", type(compressor))
# print(ds)

# ds.to_zarr(f_zar_out, mode='w', encoding = dic_encoding, consolidated=True)

######### ENDWORK - debugging

# def calculate_positions(data, alpha, beta):
#     valid_data = data[~np.isnan(data)]
#     return plotting_positions(valid_data, alpha=alpha, beta=beta)


def calculate_positions(data_og, alpha, beta, fillna_val=None):
    """
    When n/a values are present, assign the maximum empirical cdf value computed for them
    """
    data = data_og.copy()
    if fillna_val is not None:
        idx_null = np.isnan(data)
        # idx_valid = ~idx_null
        data[idx_null] = fillna_val
        na_vals_present = idx_null.sum() > 0

    if np.isnan(data).sum() > 0:
        sys.exit(
            f"attempting to calculate plotting positions when there are {np.isnan(data).sum()} out of {len(data)} observations missing"
        )

    # valid_data = data[idx_valid]

    # If there's no valid data, return all NaNs
    # if len(valid_data) == 0:
    #     return np.full_like(data, np.nan)  # Return an array of NaNs with the same shape as input

    # Calculate the plotting positions for valid data
    result = plotting_positions(data, alpha=alpha, beta=beta)

    # Create an output array filled with NaN values, matching the original shape
    # result = np.full_like(data, np.nan, dtype=float)

    # Insert the calculated positions back into their original locations
    # result[idx_valid] = pos
    if (
        fillna_val is not None
    ) and na_vals_present:  # assign the maximum computed quantile for missing values
        result[idx_null] = result[idx_null].max()

    return result


# compute return periods
def calculate_return_period(positions, n_years, n_events):
    # does not require ordering
    # Ensure that CDF values are within the valid range (0 < F < 1)
    positions = positions.clip(min=1e-10, max=1 - 1e-10)
    events_per_year = n_events / n_years
    exceedance_prob = 1 - positions
    return_period_yrs = 1 / (
        exceedance_prob * events_per_year
    )  # 1/exceedance_prb_for_event * years/event = years
    return return_period_yrs


def isel_first_and_slice_longest(ds, n=5):
    """
    Select the first element for all dimensions, but slice the first `n` elements
    for the longest dimension.
    """
    # Find the longest dimension
    longest_dim = max(ds.dims, key=lambda d: ds.sizes[d])
    # Build the `isel` dictionary: first element for all dims, slice for the longest
    isel_dict = {dim: 0 for dim in ds.dims}  # Default to first index
    isel_dict[longest_dim] = slice(
        0, min(ds.sizes[longest_dim], n)
    )  # Slice longest dim
    # Apply the `isel` operation using the dictionary
    return ds.isel(isel_dict)


def convert_ob_datavars_to_dtype(
    ds, lst_dtypes_to_try=[int, str], lst_vars_to_convert=None
):
    # ds, lst_dtypes_to_try=[float, str]
    if lst_vars_to_convert is None:  # convert all variables
        lst_vars_to_convert = ds.data_vars
    for var in lst_vars_to_convert:
        if ds[var].dtype == object:
            converted = False
            first_attempt = True
            for dtype in lst_dtypes_to_try:
                # break if it alread is the resired data type
                if ds[var].dtype == dtype:
                    converted = True
                    break
                try:
                    # deal with common problem in SWMM results
                    if (dtype == float) or (dtype == int):
                        if ds[var].dtype == object:
                            # first coerce to string
                            ds[var] = ds[var].astype(str)
                            # convert "" to "0"
                            ds[var] = xr.where(ds[var] == "", "0", ds[var])
                        ds[var] = ds[var].astype(dtype)
                    # verify conversion
                    sample = isel_first_and_slice_longest(ds[var], n=10).values
                    test = np.array(sample, dtype=dtype)
                    ds[var] = ds[var].astype(dtype)
                    converted = True
                    if not first_attempt:
                        print(f"Converted variable to datatype = {var}, {dtype}")
                    break
                except Exception as e:
                    print(
                        f"Failed to convert variable to datatype = {var}, {dtype}. Trying next datatype. Error encountered: {e}"
                    )
                    first_attempt = False
                    pass
            if not converted:
                print(f"{var} unable to be converted to either {lst_dtypes_to_try}")
    return ds


def delete_zarr(f_zarr, attempt_time_limit_s=10):
    import gc

    if Path(f_zarr).exists():
        gc.collect()
        t_0 = time.time()
        t_elapse = 0
        deleted = False
        while t_elapse < attempt_time_limit_s:
            try:
                shutil.rmtree(f_zarr)
                deleted = True
                break
            except:
                pass
            t_elapse = time.time() - t_0
        if deleted == False:
            print(f"failed to delete file {f_zarr}")
    return


def delete_directory(dir, attempt_time_limit_s=10):
    delete_zarr(dir, attempt_time_limit_s=attempt_time_limit_s)
    return


def sort_dimensions(ds, lst_dims=None):
    if lst_dims is None:
        lst_dims = ds.dims
    for dim in lst_dims:
        ds = ds.sortby(variables=dim)
    return ds


def stack_wlevel_dataset(
    da_wlevel, f_zar_out=None, export_to_file=False, f_csv_mapping=None
):
    # chunk_sizes = dict(x=100, y=100)
    # total_mb, chunk_sizes = estimate_chunk_memory(stacked_data, input_chunk_sizes=chunk_sizes)
    bm_time = time.time()
    # da_wlevel = da_wlevel.dropna(dim="year", how="all").reset_coords(drop=True)
    stacked_data = da_wlevel.stack(
        event_number=["year", "event_type", "event_id"]
    )  # "simtype", "model"
    stacked_data = stacked_data.dropna(dim="event_number", how="all").reset_index(
        "event_number"
    )
    stacked_data = stacked_data.assign_coords(event_number=stacked_data["event_number"])
    if f_csv_mapping is not None:
        Path(f_csv_mapping).parent.mkdir(parents=True, exist_ok=True)
        df_event_number_mapping = stacked_data.isel(x=0, y=0).to_dataframe().dropna()
        df_event_number_mapping = df_event_number_mapping.drop(
            columns=["x", "y", "max_wlevel_m"]
        )
        df_event_number_mapping.to_csv(f_csv_mapping)
    stacked_data = stacked_data.reset_coords(drop=True)
    if export_to_file:
        delete_zarr(f_zar_out, attempt_time_limit_s=10)
        Path(f_zar_out).parent.mkdir(parents=True, exist_ok=True)
        #
        chunk_sizes = dict(x=100, y=100, event_number=-1)
        stacked_data.chunk(chunk_sizes).to_zarr(
            f_zar_out,
            mode="w",
            encoding=return_dic_zarr_encodingds(stacked_data, clevel=5),
            consolidated=True,
        )
        stacked_data = xr.open_dataset(f_zar_out, engine="zarr", chunks=chunk_sizes)
        # stacked_data.max("event_number").to_dataframe().dropna().max()
        print(f"Reshaped data ({(time.time() - bm_time)/60:.2f} min")
        return f_zar_out, stacked_data
    return stacked_data


def compute_emp_cdf_and_return_pds(
    da_wlevel,
    alpha,
    beta,
    qaqc_plots=False,
    export_intermediate_outputs=False,
    dir_temp_zarrs=None,
    f_out_zarr=None,
    testing=False,
    print_benchmarking=True,
    n_years=None,
    f_event_number_mapping=None,
):

    start_time = bm_time = time.time()
    lst_zar_tmp = []
    if "event_number" in da_wlevel.dims:  # already stacked
        stacked_data = da_wlevel
    else:
        f_zar_out = f"{dir_temp_zarrs}sim_wlevel_stacked.zarr"
        export_to_file = export_intermediate_outputs
        f_csv_mapping = f_event_number_mapping
        stacked_data = stack_wlevel_dataset(
            da_wlevel,
            f_zar_out=f_zar_out,
            export_to_file=export_to_file,
            f_csv_mapping=f_csv_mapping,
        )
        if len(stacked_data) > 1:
            f_zar_out, stacked_data = stacked_data
        if export_intermediate_outputs:
            lst_zar_tmp.append(f_zar_out)
    bm_time = time.time()
    # compute plotting positions (empirical CDF)
    positions = xr.apply_ufunc(
        calculate_positions,
        stacked_data,
        input_core_dims=[["event_number"]],
        output_core_dims=[["event_number"]],
        vectorize=True,
        dask="parallelized",  # Optional: Use Dask for large datasets
        output_dtypes=[float],
        keep_attrs=True,  # Preserve attributes if needed
        kwargs={"alpha": alpha, "beta": beta},
    )

    if export_intermediate_outputs:
        f_zar_temp_quants = f"{dir_temp_zarrs}sim_wlevel_emp_quantiles.zarr"
        total_mb, chunk_sizes = estimate_chunk_memory(
            stacked_data, input_chunk_sizes=dict(x=50, y=50)
        )
        delete_zarr(f_zar_temp_quants, attempt_time_limit_s=10)
        Path(f_zar_temp_quants).parent.mkdir(parents=True, exist_ok=True)
        positions.chunk(chunk_sizes).to_zarr(
            f_zar_temp_quants,
            mode="w",
            encoding=return_dic_zarr_encodingds(positions, clevel=5),
            consolidated=True,
        )
        print(
            f"Calculated plotting positions ({(time.time() - bm_time)/60:.2f} min, {(time.time() - start_time)/60:.2f} min total)"
        )
        lst_zar_tmp.append(f_zar_temp_quants)
        positions = xr.open_dataset(f_zar_temp_quants, engine="zarr", chunks="auto")

    bm_time = time.time()
    if n_years is None:
        n_years = len(da_wlevel.year.values)
    n_events = len(stacked_data.event_number.values)
    return_periods = xr.apply_ufunc(
        calculate_return_period,
        positions,
        input_core_dims=[["event_number"]],
        output_core_dims=[["event_number"]],
        vectorize=True,
        dask="parallelized",  # Enable Dask support
        output_dtypes=[float],  # Specify output dtype
        kwargs={"n_years": n_years, "n_events": n_events},
    )
    if export_intermediate_outputs:
        f_zar_temp_return_pds = f"{dir_temp_zarrs}sim_wlevel_emp_return_periods.zarr"
        # total_mb, chunk_sizes = estimate_chunk_memory(stacked_data, input_chunk_sizes=dict(x=50, y=50))
        delete_zarr(f_zar_temp_return_pds, attempt_time_limit_s=10)
        Path(f_zar_temp_return_pds).parent.mkdir(parents=True, exist_ok=True)
        return_periods.chunk(chunk_sizes).to_zarr(
            f_zar_temp_return_pds,
            mode="w",
            encoding=return_dic_zarr_encodingds(return_periods, clevel=5),
            consolidated=True,
        )
        lst_zar_tmp.append(f_zar_temp_return_pds)
        return_periods = xr.open_dataset(
            f_zar_temp_return_pds, engine="zarr", chunks="auto"
        )
        print(
            f"Calculated return periods ({(time.time() - bm_time)/60:.2f} min, {(time.time() - start_time)/60:.2f} min total)"
        )
    bm_time = time.time()
    # verify plotting positions
    if testing:
        max_event_idx_og = (
            stacked_data["max_wlevel_m"]
            .argmax(dim="event_number", skipna=True)
            .compute()
        )
        max_event_idx_plt_pos = (
            positions["max_wlevel_m"].argmax(dim="event_number", skipna=True).compute()
        )
        subset_w_og = stacked_data.isel(event_number=max_event_idx_og)
        subset_w_plt_pos = stacked_data.isel(event_number=max_event_idx_plt_pos)
        s_diffs2 = (
            subset_w_og["max_wlevel_m"] - subset_w_plt_pos["max_wlevel_m"]
        ).to_dataframe()["max_wlevel_m"]
        if (s_diffs2.max() != 0) or (s_diffs2.min() != 0):
            sys.exit("WARNING! THE PLOTTING POSITION CALCULATIONS HAVE AN ISSUE")
        # compare 1 x and y coordinate where max water level was observed
        if qaqc_plots:
            x_max, y_max = (
                subset_w_og["max_wlevel_m"].to_dataframe()["max_wlevel_m"].idxmax()
            )

            s_single_obs_wlevel = (
                stacked_data["max_wlevel_m"]
                .sel(x=x_max, y=y_max)
                .to_dataframe()["max_wlevel_m"]
            )
            idx_ordered = s_single_obs_wlevel.sort_values().index
            s_single_obs_wlevel = s_single_obs_wlevel.loc[idx_ordered].reset_index(
                drop=True
            )
            s_single_obs_emp_cdf = (
                positions["max_wlevel_m"]
                .sel(x=x_max, y=y_max)
                .to_dataframe()["max_wlevel_m"]
                .loc[idx_ordered]
                .reset_index(drop=True)
            )
            s_single_obs_trn_pds = (
                return_periods["max_wlevel_m"]
                .sel(x=x_max, y=y_max)
                .to_dataframe()["max_wlevel_m"]
                .loc[idx_ordered]
                .reset_index(drop=True)
            )

            s_single_obs_emp_cdf.index = s_single_obs_wlevel.values
            s_single_obs_trn_pds.index = s_single_obs_wlevel.values

            s_single_obs_emp_cdf.index.name = "max_wlevel_m"
            s_single_obs_trn_pds.index.name = "max_wlevel_m"

            fig, axes = plt.subplots(1, 3, figsize=(9, 3))

            s_single_obs_wlevel.plot(ax=axes[0])
            axes[0].set_ylabel("Max Water Level (m)", fontsize=9)
            axes[0].set_xlabel("Event Number")
            s_single_obs_emp_cdf.plot(ax=axes[1])
            axes[1].set_ylabel("Empirical CDF", fontsize=9)
            s_single_obs_trn_pds.plot(ax=axes[2], logy=True)
            axes[2].set_ylabel("Return Period Years", fontsize=9)
            fig.suptitle(
                "Comparing Ordered Water Levels with Empirical CDF and Return Periods for Single Gridcell",
                fontsize=11,
            )
            plt.tight_layout()
            plt.show()
    if export_intermediate_outputs:
        da_emp_cdf = positions["max_wlevel_m"]
        if type(da_wlevel) == xr.Dataset:
            da_wlevel = stacked_data["max_wlevel_m"]
        da_return_pds = return_periods["max_wlevel_m"]
    else:
        da_emp_cdf = positions
        da_wlevel = stacked_data
        da_return_pds = return_periods
    da_emp_cdf.name = "emprical_cdf"
    da_return_pds.name = "return_pd_yrs"
    # ds_mapping = df_event_number_mapping.to_xarray()
    # dic_idx_dtypes = df_event_number_mapping.dtypes.to_dict()
    # for var in dic_idx_dtypes:
    #     if dic_idx_dtypes[var] == object:
    #         ds_mapping[var] = ds_mapping[var].astype(np.str_)
    #     else:
    #         ds_mapping[var] = ds_mapping[var].astype(dic_idx_dtypes[var])
    # ds_mapping.attrs["notes"] = "this contains the mapping of event number to specific modeled events"
    ds_flood_prob = xr.merge([da_wlevel, da_emp_cdf, da_return_pds])
    # ds_flood_prob = ds_flood_prob.reset_index("event_number").set_index(event_number=["event_id", "event_type", "model", "simtype", "year"])
    # ds_flood_prob = ds_flood_prob.unstack("event_number")
    if f_out_zarr is not None:
        Path(f_out_zarr).parent.mkdir(parents=True, exist_ok=True)
        exported = False
        bm_time2 = time.time()
        while exported == False:
            try:
                delete_zarr(f_out_zarr, attempt_time_limit_s=10)
                chunk_sizes = dict(x=10, y=10, event_number=-1)
                ds_flood_prob.chunk(chunk_sizes).to_zarr(
                    f_out_zarr,
                    mode="w",
                    encoding=return_dic_zarr_encodingds(ds_flood_prob, clevel=5),
                    consolidated=True,
                )
                exported = True
                break
            except:
                t_elapsed_min = (time.time() - bm_time2) / 60
                if t_elapsed_min > 1:
                    print(
                        "The code has hung up on exporting the primary output. Returning the dataset that has NOT been saved to a file."
                    )
                    return ds_flood_prob
                continue
        # ds_flood_prob = xr.open_dataset(f_out_zarr, engine = "zarr", chunks = "auto")
        if print_benchmarking:
            print(
                f"Flood probability dataset created ({(time.time() - bm_time)/60:.2f} min, {(time.time() - start_time)/60:.2f} min total)"
            )
    else:
        ds_flood_prob = ds_flood_prob.copy().load()
    if export_intermediate_outputs:
        bm_time = time.time()
        import dask

        positions.close()
        return_periods.close()
        stacked_data.close()
        ds_flood_prob.close()
        dask.config.refresh()
        for f in lst_zar_tmp:
            delete_zarr(f, attempt_time_limit_s=10)
    return ds_flood_prob


def create_bar_label(event_formulation):
    label = (
        event_formulation.replace(".", "\n")
        .replace("max_0hr_", "")
        .replace("max_", "")
        .replace("_mm", "")
        .replace("_m", "")
        .replace("_0min", "")
    )
    return label


def create_bar_label_one_line(event_formulation):
    label = (
        event_formulation.replace(".", ", ")
        .replace("max_0hr_", "")
        .replace("max_", "")
        .replace("_mm", "")
        .replace("_m", "")
        .replace("_0min", "")
    )
    return label


def compute_return_periods_for_series(og_series, n_years, varname=None):
    # og_series, n_years, alpha, beta, assign_dup_vals_max_return, varname = s_flooded_area_by_event_sm, n_years_synthesized, alpha, beta, assign_dup_vals_max_return, s_flooded_area_by_event_sm.name
    series_to_analyze = og_series.copy()
    og_name = og_series.name
    if varname is None:
        varname = og_name
    series_to_analyze.name = varname
    df_result = compute_return_periods(series_to_analyze, n_years, ALPHA, BETA, varname)
    og_index = df_result.index
    df_result = df_result.reset_index(drop=True)
    if ASSIGN_DUP_VALS_MAX_RETURN:
        s_vals = df_result[varname]
        idx_max_rtrn_by_val = df_result.groupby(varname).idxmax().iloc[:, 0]
        df_result_maxrtrn = (
            df_result.loc[idx_max_rtrn_by_val, :]
            .reset_index(drop=True)
            .set_index(varname)
        )
        df_result = s_vals.to_frame().join(df_result_maxrtrn, how="left", on=varname)
    df_result.index = og_index
    df_result = df_result.rename(columns={varname: og_name})
    return df_result.sort_index()


def compute_univariate_event_return_periods(
    ds_sim_tseries,
):
    idx_valid_events = (
        ds_sim_tseries.isel(timestep=0)["mm_per_hr"].to_dataframe().dropna().index
    )
    lst_df_rain_return_pds = []
    for rain_window_min in RAIN_WINDOWS_MIN:
        rain_window_h = rain_window_min / 60
        # define variable name
        if rain_window_h >= 1:
            sfx = f"{int(rain_window_h)}hr_0min"
        else:
            sfx = f"0hr_{int(rain_window_min)}min"
        varname = f"max_{sfx}_mm"
        # compute max x hour rain depth in each event
        sim_tstep_hr = pd.Series(ds_sim_tseries.timestep.values).diff().mode().loc[
            0
        ] / np.timedelta64(1, "h")
        tsteps_per_target_window = int(rain_window_h / sim_tstep_hr)
        # create data array of moving precipitation sums over the target time window for the entire ensemble
        da_precip_max_depth_in_window = (
            (ds_sim_tseries["mm_per_hr"] * sim_tstep_hr)
            .fillna(0)
            .rolling(timestep=tsteps_per_target_window, min_periods=1)
            .sum()
            .max(dim="timestep")
        )

        s_max_rain_in_target_window = (
            da_precip_max_depth_in_window.to_dataframe()["mm_per_hr"]
            .reset_index()
            .drop_duplicates()
            .set_index(idx_valid_events.names)
            .loc[idx_valid_events]["mm_per_hr"]
        )
        # convert to a pandas series
        # s_max_rain_in_target_window = s_mm_per_hr.loc[idx_valid_events]
        s_max_rain_in_target_window.name = varname
        df_emp_rain_rtrn_pds = compute_return_periods_for_series(
            s_max_rain_in_target_window, N_YEARS_SYNTHESIZED
        )
        # assign events with zero rain to all have the same return period
        lst_df_rain_return_pds.append(df_emp_rain_rtrn_pds)
    df_rain_return_pds = pd.concat(lst_df_rain_return_pds, axis=1)
    # extract max sea water level per event
    s_max_sea_wlevel_per_event = (
        ds_sim_tseries["waterlevel_m"]
        .max("timestep")
        .to_dataframe()["waterlevel_m"]
        .dropna()
    )
    s_max_sea_wlevel_per_event.name = "max_waterlevel_m"
    df_wlevel_return_pds = compute_return_periods_for_series(
        s_max_sea_wlevel_per_event, N_YEARS_SYNTHESIZED
    )
    return df_wlevel_return_pds, df_rain_return_pds


def eCDF_wasserman(data, alpha=ALPHA):
    # alpha = 0 is the weibull plotting position
    # see wassermanAllStatisticsConcise2004
    n_obs = len(data)
    # data_ordered = np.sort(data)
    counts = np.searchsorted(np.sort(data), data, side="right")
    ecdfs = (counts - alpha) / (n_obs + 1 - 2 * alpha)
    return ecdfs


def eCDF_stendinger(data, alpha=ALPHA):
    # alpha = 0 is the weibull plotting position
    # see stedingerChapter18Frequency1993
    sorted_idx = data.argsort()
    ranks = np.arange(1, len(data) + 1)
    n_obs = len(data)
    ecdfs_sorted = (ranks - alpha) / (n_obs + 1 - 2 * alpha)
    inverse_idx = np.empty_like(sorted_idx)
    inverse_idx[sorted_idx] = np.arange(len(sorted_idx))
    # reorder ECDFs back to original data order
    ecdfs = ecdfs_sorted[inverse_idx]
    return ecdfs


def bs_samp_of_univar_event_return_period(
    bs_id,
    ds_sim_tseries,
    df_wlevel_return_pds_og,
    df_rain_return_pds_og,
):
    ar_sim_years = np.arange(N_YEARS_SYNTHESIZED)
    # draw a sample
    resampled_years = pd.Series(
        np.random.choice(ar_sim_years, size=N_YEARS_SYNTHESIZED, replace=True)
    )
    resampled_years = resampled_years[
        resampled_years.isin(ds_sim_tseries.year.to_series())
    ]
    ds_sim_tseries_bs = ds_sim_tseries.sel(year=resampled_years.values).load()
    # compute univariate return periods
    df_wlevel_return_pds_bs, df_rain_return_pds_bs = (
        compute_univariate_event_return_periods(
            ds_sim_tseries_bs,
        )
    )
    # create event stats column for bootstrap sample and original dataset
    df_event_all_stats = pd.concat(
        [df_wlevel_return_pds_bs, df_rain_return_pds_bs], axis=1
    )
    cols_vals = df_event_all_stats.columns[
        [
            ("emp_cdf" not in col) and ("return_pd" not in col)
            for col in df_event_all_stats.columns
        ]
    ]
    df_event_all_stats_og = pd.concat(
        [df_wlevel_return_pds_og, df_rain_return_pds_og], axis=1
    )
    ds_triton_dsgn = xr.open_dataset(F_TRITON_OUTPUTS_DSGN, engine="zarr").chunk("auto")
    target_design_storms_years = ds_triton_dsgn.year.values
    # for each stat and each target return period, pull all event statistics associated with the original computation
    lst_df_rtrn_pds = []
    for event_stat in cols_vals:
        relevant_cols = df_event_all_stats.columns[
            [(event_stat in col) for col in df_event_all_stats.columns]
        ]
        df_vals_rtrn_and_cdf = df_event_all_stats.loc[:, relevant_cols]
        for trgt_rtrn in target_design_storms_years:
            idx_rtrn_pd = (
                (df_vals_rtrn_and_cdf.filter(like="return_pd").iloc[:, 0] - trgt_rtrn)
                .reset_index(drop=True)
                .abs()
                .idxmin()
            )
            s_vals_rtrn_and_cdf_trgt = df_vals_rtrn_and_cdf.iloc[idx_rtrn_pd, :]
            event_idx = s_vals_rtrn_and_cdf_trgt.name
            event_idx_colname = ""
            event_idx_str = ""
            first = True
            for idx, name in enumerate(df_vals_rtrn_and_cdf.index.names):
                if first != True:
                    event_idx_colname += "."
                    event_idx_str += "."
                event_idx_colname += f"{name}"
                event_idx_str += f"{str(event_idx[idx])}"
                first = False
            # add relevant fields
            formulation = "empirical_univar_"
            s_vals_rtrn_and_cdf_trgt.loc[event_idx_colname] = event_idx_str
            s_vals_rtrn_and_cdf_trgt.loc["return_period_yrs"] = trgt_rtrn
            s_vals_rtrn_and_cdf_trgt.loc["formulation"] = f"{formulation}return_pd_yrs"
            s_vals_rtrn_and_cdf_trgt.loc["event_stat"] = event_stat
            # lookup original formulation return periods
            s_og_event = df_event_all_stats_og.loc[event_idx, relevant_cols]
            s_og_event = s_og_event.drop(event_stat)
            new_rows = [f"{idx}_og" for idx in s_og_event.index]
            s_og_event.index = new_rows

            df_output = (
                pd.concat([s_vals_rtrn_and_cdf_trgt, s_og_event], axis=0).to_frame().T
            )
            df_output = df_output.reset_index(drop=True).set_index(
                ["formulation", "event_stat", "return_period_yrs"]
            )
            # rename return pd and quantile columns
            colnames = [
                (
                    f"{formulation}{col.split(f"{event_stat}_")[-1]}"
                    if ("return" in col) or ("emp_cdf" in col)
                    else col
                )
                for col in df_output.columns
            ]
            df_output.columns = colnames
            colnames.sort()
            lst_df_rtrn_pds.append(df_output.loc[:, colnames])
    # combine bootstrapped samples into single dataframe
    df_bootstrapped_results = pd.concat(lst_df_rtrn_pds).sort_index()
    df_bootstrapped_results.loc[:, "bs_id"] = bs_id
    idx_cols = ["bs_id"] + df_bootstrapped_results.index.names
    lst_cols = list(df_bootstrapped_results.columns)
    lst_cols.sort()
    df_bootstrapped_results = (
        df_bootstrapped_results.loc[:, lst_cols].reset_index().set_index(idx_cols)
    )
    return df_bootstrapped_results


def compute_all_multivariate_return_period_combinations(
    df_rain_return_pds, df_wlevel_return_pds
):
    """
    Considers formulations with a single rain statistic and water level or two rain statistics and water level
    """
    # idx_events = ds_sim_tseries.isel(timestep=0)["mm_per_hr"].to_dataframe().dropna().index
    # df_rain_return_pds = df_rain_return_pds.loc[idx_events, :]
    # df_wlevel_return_pds = df_wlevel_return_pds.loc[idx_events, :]
    if df_rain_return_pds.isna().any().any():
        sys.exit("error: na values present")
    if df_wlevel_return_pds.isna().any().any():
        sys.exit("error: na values present")
    # cols_rain_cdf = df_rain_return_pds.columns[["emp_cdf" in col for col in df_rain_return_pds.columns]]
    # df_rain_cdf = df_rain_return_pds[cols_rain_cdf]
    cols_rain_vals = df_rain_return_pds.columns[
        [
            ("emp_cdf" not in col) and ("return_pd_yrs" not in col)
            for col in df_rain_return_pds.columns
        ]
    ]
    df_rain_vals = df_rain_return_pds[cols_rain_vals]
    s_wlevel_vals = df_wlevel_return_pds["max_waterlevel_m"]
    # dic_rain_stats = dict()
    dic_multivar_return_periods = dict()
    lst_processed_pairs = []
    # find every unique pair of rainfall statistics
    for first_stat in cols_rain_vals:
        # compute bivariate formulation
        first_stat_shortened = create_bar_label_one_line(first_stat)
        wlevel_statname_shortened = "w"
        combined_statnames = f"{first_stat_shortened},{wlevel_statname_shortened}"
        lst_processed_pairs.append(combined_statnames)
        df_multivar = pd.concat(
            [s_wlevel_vals, df_rain_vals.loc[:, first_stat]], axis=1
        )
        dic_multivar_return_periods[combined_statnames] = (
            empirical_multivariate_return_periods(df_multivar, n_years)
        )
        for second_stat in cols_rain_vals:
            if first_stat == second_stat:
                continue
            second_stat_shortened = create_bar_label_one_line(second_stat)
            lst_stats = [first_stat_shortened, second_stat_shortened]
            # order list of stats based on the duration represented
            lst_min = [
                (
                    int(stat.split("hr")[0]) * 60
                    if "hr" in stat
                    else int(stat.split("min")[0])
                )
                for stat in lst_stats
            ]
            df_stats = pd.DataFrame(dict(stat=lst_stats, minutes=lst_min))
            lst_stats = df_stats.sort_values("minutes")["stat"].to_list()
            combined_statnames = (
                f"{lst_stats[0]},{lst_stats[1]},{wlevel_statname_shortened}"
            )
            if combined_statnames in lst_processed_pairs:
                continue
            lst_processed_pairs.append(combined_statnames)
            df_multivar = pd.concat(
                [
                    s_wlevel_vals,
                    df_rain_vals.loc[:, first_stat],
                    df_rain_vals.loc[:, second_stat],
                ],
                axis=1,
            )
            dic_multivar_return_periods[combined_statnames] = (
                empirical_multivariate_return_periods(df_multivar, n_years)
            )
            # sys.exit("work")
    lst_df = []
    for event_combination in dic_multivar_return_periods.keys():
        df_return_periods = dic_multivar_return_periods[event_combination]
        df_return_periods["event_stats"] = event_combination
        df_return_periods = df_return_periods.reset_index().set_index(
            ["event_stats", "event_type", "year", "event_id"]
        )
        lst_df.append(df_return_periods)
    df_multivar_return_periods = pd.concat(lst_df)
    return df_multivar_return_periods


def bs_samp_of_multivar_event_return_period(
    bs_id,
    df_multivar_return_periods_og,
    ds_sim_tseries,
    df_rain_return_pds,
    df_wlevel_return_pds,
    target_design_storms_years,
):
    # draw a bootstrap sample
    ar_sim_years = np.arange(N_YEARS_SYNTHESIZED)
    # draw a sample
    resampled_years = pd.Series(
        np.random.choice(ar_sim_years, size=N_YEARS_SYNTHESIZED, replace=True)
    )
    resampled_years = resampled_years[
        resampled_years.isin(ds_sim_tseries.year.to_series())
    ]
    # extract event indices of bootstrapped sample and subset the water level and rain data
    ds_sim_tseries_bs = ds_sim_tseries.sel(year=resampled_years.values)
    idx_events = (
        ds_sim_tseries_bs.isel(timestep=0)["mm_per_hr"]
        .to_dataframe()
        .dropna()
        .sort_index()
        .index
    )  # work
    df_rain_return_pds_bs = df_rain_return_pds.loc[idx_events, :]
    df_wlevel_return_pds_bs = df_wlevel_return_pds.loc[idx_events, :]
    # compute multivariate
    df_multivar_return_periods = compute_all_multivariate_return_period_combinations(
        df_rain_return_pds_bs,
        df_wlevel_return_pds_bs,
    )
    # create dataframe with all event statistics
    cols_rain_vals = df_rain_return_pds.columns[
        ["emp_cdf" not in col for col in df_rain_return_pds.columns]
    ]
    df_rain_vals = df_rain_return_pds[cols_rain_vals]
    s_wlevel_vals = df_wlevel_return_pds["max_waterlevel_m"]
    df_event_statistics = pd.concat([s_wlevel_vals, df_rain_vals], axis=1)
    # compute target return period for every combination of event statistics
    lst_df_rtrn_pds = []
    for event_stat, df_eventstat_rtrns in df_multivar_return_periods.groupby(
        level="event_stats"
    ):
        # extract return period for event stats
        df_rtrn_pds = df_eventstat_rtrns.loc[pd.IndexSlice[event_stat]]
        # extract associated event data
        lst_s_vals = []
        for stat in event_stat.split(","):
            if stat == "w":
                lst_s_vals.append(df_event_statistics["max_waterlevel_m"])
            else:
                lst_col = df_event_statistics.columns[
                    [
                        (f"_{stat}" in col) and ("return" not in col)
                        for col in df_event_statistics.columns
                    ]
                ]
                if len(lst_col) != 1:
                    sys.exit("houston we have a problem")
                else:
                    lst_s_vals.append(df_event_statistics[lst_col[0]])
        df_vals = pd.concat(lst_s_vals, axis=1).loc[df_rtrn_pds.index]
        # combine return periods and event stats into single dataframe
        df_vals_and_rtrn_pds = pd.concat([df_rtrn_pds, df_vals], axis=1)
        # extract each formulation
        rtrn_pd_cols = df_vals_and_rtrn_pds.columns[
            ["rtrn_yrs" in col for col in df_vals_and_rtrn_pds.columns]
        ]
        # compute return period for every multivariate formulation
        for trgt_rtrn in target_design_storms_years:
            for rtrn_pd_form in rtrn_pd_cols:
                idx_rtrn_pd = (
                    (df_vals_and_rtrn_pds[rtrn_pd_form] - trgt_rtrn).abs().idxmin()
                )
                df_event_vals_for_target_return_pd = (
                    df_vals_and_rtrn_pds.loc[pd.IndexSlice[idx_rtrn_pd]]
                    .copy()
                    .drop_duplicates()
                )
                # df_event_vals_for_target_return_pd = row_rtrn.loc[val_names].to_frame().T
                # df_event_vals_for_target_return_pd.index.names = df_vals_and_rtrn_pds.index.names
                event_idx = df_event_vals_for_target_return_pd.index
                event_idx_colname = ""
                event_idx_str = ""
                first = True
                for idx, name in enumerate(event_idx.names):
                    if first != True:
                        event_idx_colname += "."
                        event_idx_str += "."
                    event_idx_colname += f"{name}"
                    event_idx_str += f"{str(event_idx.values[0][idx])}"
                    first = False
                df_event_vals_for_target_return_pd.loc[:, event_idx_colname] = (
                    event_idx_str
                )
                df_event_vals_for_target_return_pd.loc[:, "return_period_yrs"] = (
                    trgt_rtrn
                )
                df_event_vals_for_target_return_pd.loc[:, "formulation"] = rtrn_pd_form
                df_event_vals_for_target_return_pd.loc[:, "event_stat"] = event_stat
                # lookup original formulation return periods
                df_og = df_multivar_return_periods_og.loc[
                    pd.IndexSlice[event_stat, :, :, :]
                ].loc[event_idx, :]
                new_cols = [f"{col}_og" for col in df_og.columns]
                df_og.columns = new_cols
                # combine and properly index outputs
                df_output = pd.concat(
                    [df_event_vals_for_target_return_pd, df_og], axis=1
                )
                df_output = df_output.reset_index(drop=True).set_index(
                    ["formulation", "event_stat", "return_period_yrs"]
                )
                lst_df_rtrn_pds.append(df_output)
    # combine bootstrapped samples into single dataframe
    df_bootstrapped_results = pd.concat(lst_df_rtrn_pds).sort_index()
    df_bootstrapped_results.loc[:, "bs_id"] = bs_id
    idx_cols = ["bs_id"] + df_bootstrapped_results.index.names
    lst_cols = list(df_bootstrapped_results.columns)
    lst_cols.sort()
    df_bootstrapped_results = (
        df_bootstrapped_results.loc[:, lst_cols].reset_index().set_index(idx_cols)
    )
    return df_bootstrapped_results


# def assign_duplicates_emp_cdf_values_the_max_value(s_emp_cdf):
#     s_val_counts = s_emp_cdf.value_counts()
#     s_val_dups = s_val_counts[s_val_counts>1]
#     for dup_cdf in s_val_dups.index:
#         s_emp_cdf[s_emp_cdf==dup_cdf]
#         break
#     return
def return_vars_associated_with_event_stat(s_row_og, df_event_all_stats_og):
    # make sure that only hydrologic values are included in event stats dataframe
    cols_vals = df_event_all_stats_og.columns[
        [
            ("emp_cdf" not in col) and ("return_pd" not in col)
            for col in df_event_all_stats_og.columns
        ]
    ]
    df_event_all_stats = df_event_all_stats_og.loc[:, cols_vals].copy()
    s_row = s_row_og.copy()
    lst_of_stats = s_row.filter(like="event_stat").iloc[0].split(",")
    event_type, year, event_id = (
        s_row["event_type"],
        int(s_row["year"]),
        int(s_row["event_id"]),
    )
    s_event_stats = pd.Series(index=["q1", "q2", "q3"]).astype(float)
    for q_idx, substat in enumerate(lst_of_stats):
        if substat in df_event_all_stats.columns:
            val = df_event_all_stats.loc[
                pd.IndexSlice[event_type, year, event_id], substat
            ]
        else:
            if substat == "w":
                val = df_event_all_stats.loc[
                    pd.IndexSlice[event_type, year, event_id], "max_waterlevel_m"
                ]
            else:
                rain_stat = df_event_all_stats.columns[
                    [f"_{substat}" in col for col in df_event_all_stats.columns]
                ]
                if len(rain_stat) != 1:
                    print(rain_stat)
                    sys.exit("houston we have a problem")
                val = df_event_all_stats.loc[
                    pd.IndexSlice[event_type, year, event_id], rain_stat[0]
                ]
        s_event_stats.iloc[q_idx] = val
    return s_event_stats


def return_df_of_evens_within_ci_including_event_stats(
    all_event_return_pds,
    df_return_pd_cis,
    stat,
    form,
    lst_trgt_return_pds,
    df_event_all_stats,
):
    if "multivar" in form:
        df_events = (
            all_event_return_pds.sel(event_stats=stat)[form].to_dataframe().dropna()
        )
    else:
        df_events = all_event_return_pds.loc[:, stat]
        df_events.name = form
        df_events = df_events.to_frame()
        df_events.loc[:, "event_stats"] = stat
    s_bounds = (
        df_return_pd_cis.loc[pd.IndexSlice[:, stat, lst_trgt_return_pds]]
        .filter(like=form)
        .iloc[:, 0]
    )
    lst_dfs = []
    for rtrn in lst_trgt_return_pds:
        s_bounds_rtrn = s_bounds.loc[pd.IndexSlice[:, :, rtrn]]
        idx_events_in_ci = (df_events[form] >= s_bounds_rtrn.min()) & (
            df_events[form] <= s_bounds_rtrn.max()
        )
        df_events_in_ci = df_events[idx_events_in_ci]
        event_stats = df_events_in_ci.reset_index().apply(
            return_vars_associated_with_event_stat,
            **dict(df_event_all_stats_og=df_event_all_stats),
            axis=1,
        )
        event_stats = event_stats.set_index(df_events_in_ci.index)
        df_ci_with_stats = pd.concat([df_events_in_ci, event_stats], axis=1)
        df_ci_with_stats["return_period_yrs"] = rtrn
        lst_dfs.append(df_ci_with_stats)
        if len(df_ci_with_stats) == 0:
            sys.exit("work")
    df_events_in_ci_w_event_stats = pd.concat(lst_dfs).reset_index()
    return df_events_in_ci_w_event_stats


def analyze_bootstrapped_samples(
    lst_files_processed, colname_event_idx, lst_idx, df_event_all_stats
):
    df_bs_return_pds = pd.concat(
        [pd.read_csv(f, index_col=lst_idx) for f in lst_files_processed]
    )
    mask_non_dups = ~df_bs_return_pds.reset_index().duplicated()
    df_bs_return_pds = df_bs_return_pds[mask_non_dups.values]

    ds_bs_return_pds = df_bs_return_pds.to_xarray()
    formulations = ds_bs_return_pds["formulation"].values
    lst_df_cis = []
    lst_df_unique_events = []
    cols_vals = df_event_all_stats.columns[
        [
            ("emp_cdf" not in col) and ("return_pd" not in col)
            for col in df_event_all_stats.columns
        ]
    ]
    df_event_all_stats = df_event_all_stats.loc[:, cols_vals]

    for form in formulations:
        df_confidence_intervals = (
            ds_bs_return_pds.sel(formulation=form)[f"{form}_og"]
            .quantile(
                [FLD_RTRN_PD_ALPHA / 2, 0.5, (1 - FLD_RTRN_PD_ALPHA / 2)],
                dim="bs_id",
                method="linear",
            )
            .to_dataframe()
        )
        lst_df_cis.append(df_confidence_intervals)
        # create dataframe of all unique storms yielding each return period

        df_unique_events = (
            ds_bs_return_pds.sel(formulation=form)[colname_event_idx]
            .to_dataframe()
            .reset_index()
            .drop(columns=["bs_id"])
            .drop_duplicates()
            .reset_index(drop=True)
        )
        event_ids = df_unique_events[colname_event_idx].apply(
            lambda x: pd.Series(x.split("."), index=colname_event_idx.split("."))
        )
        df_unique_events = pd.concat(
            [df_unique_events.drop(columns=colname_event_idx), event_ids], axis=1
        )
        # add column with the value of the stats
        df_event_stats = df_unique_events.apply(
            return_vars_associated_with_event_stat,
            **dict(df_event_all_stats_og=df_event_all_stats),
            axis=1,
        )
        df_unique_events = pd.concat([df_unique_events, df_event_stats], axis=1)
        lst_df_unique_events.append(df_unique_events)
    df_return_pd_cis = pd.concat(lst_df_cis, axis=1).sort_index()
    df_unique_events = pd.concat(lst_df_unique_events, axis=0)
    df_unique_events = df_unique_events.set_index(
        ["formulation", "return_period_yrs", "event_stat"]
    ).sort_index()
    df_unique_events = df_unique_events.dropna(axis=1, how="all")
    return df_return_pd_cis, df_unique_events


def compute_AND_multivar_return_period_for_sample(
    sample_values, df_all_samples, n_samples, alpha, beta
):
    # (i-alpha)/(n+1-alpha-beta)
    df_exceedance = df_all_samples <= sample_values
    n_1_lessthan_or_equal_to = df_exceedance.any(axis=1).sum()
    emp_cdf_val_AND = (n_1_lessthan_or_equal_to - alpha) / (
        n_samples + 1 - alpha - beta
    )  # small non exceedance probability = larger exceedance probability
    return emp_cdf_val_AND


def compute_OR_multivar_return_period_for_sample(
    sample_values, df_all_samples, n_samples, alpha, beta
):
    df_exceedance = df_all_samples <= sample_values
    n_all_lessthan_or_equal_to = df_exceedance.all(axis=1).sum()
    emp_cdf_val_OR = (n_all_lessthan_or_equal_to - alpha) / (
        n_samples + 1 - alpha - beta
    )
    return emp_cdf_val_OR


def empirical_multivariate_return_periods(df_samples, n_years):
    n_samples = len(df_samples)
    s_emp_cdf_AND = df_samples.apply(
        compute_AND_multivar_return_period_for_sample,
        axis=1,
        **dict(df_all_samples=df_samples, n_samples=n_samples, alpha=ALPHA, beta=BETA),
    )
    s_emp_cdf_OR = df_samples.apply(
        compute_OR_multivar_return_period_for_sample,
        axis=1,
        **dict(df_all_samples=df_samples, n_samples=n_samples, alpha=ALPHA, beta=BETA),
    )
    s_emp_cdf_AND.name = "empirical_multivar_cdf_AND"
    s_emp_cdf_OR.name = "empirical_multivar_cdf_OR"

    if ASSIGN_DUP_VALS_MAX_RETURN:
        val_cols = list(df_samples.columns)
        df_result = pd.concat([df_samples, s_emp_cdf_AND, s_emp_cdf_OR], axis=1)
        idx_max_rtrn_by_val = df_result.groupby(val_cols).idxmax()
        df_result_maxcdf_OR = (
            df_result.loc[
                idx_max_rtrn_by_val[s_emp_cdf_OR.name], val_cols + [s_emp_cdf_OR.name]
            ]
            .reset_index(drop=True)
            .set_index(val_cols)
        )
        df_result_maxcdf_AND = (
            df_result.loc[
                idx_max_rtrn_by_val[s_emp_cdf_AND.name], val_cols + [s_emp_cdf_AND.name]
            ]
            .reset_index(drop=True)
            .set_index(val_cols)
        )
        s_emp_cdf_OR = df_samples.join(df_result_maxcdf_OR, how="left", on=val_cols)[
            s_emp_cdf_OR.name
        ]
        s_emp_cdf_AND = df_samples.join(df_result_maxcdf_AND, how="left", on=val_cols)[
            s_emp_cdf_AND.name
        ]

    rtrn_pds_AND = calculate_return_period(
        s_emp_cdf_AND.values, n_years, n_events=n_samples
    )
    rtrn_pds_OR = calculate_return_period(
        s_emp_cdf_OR.values, n_years, n_events=n_samples
    )

    df_multivar_return_periods = pd.concat([s_emp_cdf_AND, s_emp_cdf_OR], axis=1)
    df_multivar_return_periods["empirical_multivar_rtrn_yrs_AND"] = rtrn_pds_AND
    df_multivar_return_periods["empirical_multivar_rtrn_yrs_OR"] = rtrn_pds_OR

    return df_multivar_return_periods


def compute_return_periods(s_event_stat, n_years, alpha, beta, varname=None):
    # s_event_stat, n_years, alpha, beta, varname  = series_to_analyze, n_years, alpha, beta, varname
    if varname is None:
        varname = s_event_stat.name
    s_event_stat = s_event_stat.sort_values()
    og_idx = s_event_stat.index
    s_event_stat = s_event_stat.reset_index(drop=True)
    n_events = len(s_event_stat)
    plt_pos = calculate_positions(s_event_stat, alpha, beta)
    rtrn_pds = calculate_return_period(plt_pos, n_years, n_events)
    s_plt_pos = pd.Series(plt_pos)
    s_plt_pos.name = f"{varname}_emp_cdf"
    s_retrn_pd = pd.Series(rtrn_pds)
    s_retrn_pd.name = f"{varname}_return_pd_yrs"
    df_result = pd.concat([s_event_stat, s_plt_pos, s_retrn_pd], axis=1)
    df_result.index = og_idx
    return df_result


def interpolate_return_pd(
    s_stat, df_return_pds, na_fillval=0.01
):  # na_fillval is to not throw an error when taking the log
    colname_return_pd = df_return_pds.filter(regex="_return_pd_yrs").columns[0]
    s_rtrn = pd.Series(index=s_stat.index).astype(float)
    # interpolate return periods for events with stats that meet or exceed the threshold
    idx_valid = s_stat[s_stat >= df_return_pds[s_stat.name].min()].index
    rtrn_pds_interp = np.interp(
        s_stat.loc[idx_valid].values,
        df_return_pds[s_stat.name].values,
        df_return_pds[colname_return_pd].values,
    )
    s_rtrn.loc[idx_valid] = rtrn_pds_interp
    # for invalid locations, fill with 0
    s_rtrn[s_rtrn.isna()] = na_fillval
    s_rtrn.name = colname_return_pd
    return pd.concat([s_stat, s_rtrn], axis=1)


def plot_event_constituent_return_periods(
    dir_plot, df_event_stat_return_periods, ds_sim_tseries
):
    lst_stats_for_quantiles = [
        "max_0hr_5min_mm_return_pd_yrs",
        "max_0hr_30min_mm_return_pd_yrs",
        "max_1hr_0min_mm_return_pd_yrs",
        "max_6hr_0min_mm_return_pd_yrs",
        "max_12hr_0min_mm_return_pd_yrs",
        "max_24hr_0min_mm_return_pd_yrs",
        "max_48hr_0min_mm_return_pd_yrs",
        "max_waterlevel_m_return_pd_yrs",
    ]

    lst_stats_for_table = [
        "max_0hr_30min_mm_return_pd_yrs",
        "max_2hr_0min_mm_return_pd_yrs",
        "max_6hr_0min_mm_return_pd_yrs",
        "max_24hr_0min_mm_return_pd_yrs",
        "max_waterlevel_m_return_pd_yrs",
    ]
    # compute upper and lower bounds for time series plots
    rain_lims = (0, 100)
    wlevel_lims = (
        ds_sim_tseries["waterlevel_m"].min().values,
        ds_sim_tseries["waterlevel_m"].max().values,
    )
    for rtrn_pd_stat in lst_stats_for_quantiles:
        for quantile in [0.25, 0.5, 0.75, 1]:
            # sys.exit("Work")
            stat_quant_val = df_event_stat_return_periods[rtrn_pd_stat].quantile(
                quantile, interpolation="nearest"
            )
            event = df_event_stat_return_periods[rtrn_pd_stat][
                df_event_stat_return_periods[rtrn_pd_stat] == stat_quant_val
            ]
            event_type, year, event_id = event.index[0]
            # event = df_event_stat_return_periods.sort_values(rtrn_pd_stat, ascending = False).iloc[0,:]
            # event_type,	year, event_id = event.name

            fname_save_fig = (
                "{}event_constituent_return_pds_etype-{}_year-{}_eid-{}.png".format(
                    dir_plot, event_type, year, event_id
                )
            )
            event = df_event_stat_return_periods.loc[
                pd.IndexSlice[event_type, year, event_id], :
            ]
            constituent_return_periods = event[event.index.str.contains("return_pd")]

            df_weather = (
                ds_sim_tseries.sel(year=year, event_type=event_type, event_id=event_id)
                .to_dataframe()
                .loc[:, ["mm_per_hr", "waterlevel_m"]]
                .dropna()
            )
            s_mm_per_hr = df_weather["mm_per_hr"]
            s_wlevel = df_weather["waterlevel_m"]
            # define indices
            first_idx_wrain = s_mm_per_hr[s_mm_per_hr > 0].index.min()
            last_idx_wrain = s_mm_per_hr[s_mm_per_hr > 0].index.max()
            preceding_max_wlevel = s_wlevel.idxmax() - np.timedelta64(3, "h")
            proceding_max_wlevel = s_wlevel.idxmax() + np.timedelta64(3, "h")
            first_idx = min(first_idx_wrain, preceding_max_wlevel)
            last_idx = max(last_idx_wrain, proceding_max_wlevel)
            df_weather = df_weather.loc[first_idx:last_idx, :]
            df_weather.index = (
                df_weather.index - df_weather.index.min()
            ) / np.timedelta64(1, "h")
            s_mm_per_hr = df_weather["mm_per_hr"]
            s_wlevel = df_weather["waterlevel_m"]

            fig, axes = plt.subplots(2, 1, figsize=(4.5, 6), dpi=450)

            # s_mm_per_hr = s_mm_per_hr.loc[first_idx_wrain:last_idx_wrain]
            # s_mm_per_hr.index = (s_mm_per_hr.index - s_mm_per_hr.index.min())/np.timedelta64(1, "h")
            # s_mm_per_hr.plot(ax = ax)
            bar_width = (
                s_mm_per_hr.index[1] - s_mm_per_hr.index[0]
            )  # Assumes the index is evenly spaced
            axes[0].bar(
                s_mm_per_hr.index, s_mm_per_hr.values, width=bar_width, color="skyblue"
            )
            # Define evenly spaced ticks at 6-hour intervals starting from 0
            upper_bound = int(np.ceil(s_mm_per_hr.index.max() / 6) * 6)
            tick_positions = np.arange(0, upper_bound + 1, 6)  # 6-hour intervals
            axes[0].set_xlabel("")
            axes[0].set_ylabel("Rainfall (mm per hour)")
            axes[0].set_ylim(rain_lims)
            # axes[0].set_xticks(None)

            axes[1].plot(s_wlevel.index, s_wlevel.values, color="black")
            axes[1].set_ylabel("Sea water level (m)")
            axes[1].set_xticks(tick_positions)
            axes[1].set_xticklabels(
                [f"{int(t)}h" for t in tick_positions], rotation=45, ha="right"
            )
            axes[1].set_ylim(wlevel_lims)
            axes[0].set_xticklabels([])

            table_data = (
                []
            )  # list(zip(constituent_return_periods.index, constituent_return_periods.round(1).values))
            for stat, val in constituent_return_periods.items():
                if stat not in lst_stats_for_table:
                    continue
                stat_name = (
                    stat.split("_return")[0]
                    .replace("_", " ")
                    .replace(" 0hr ", " ")
                    .replace(" 0min ", " ")
                    .replace("mm", "intensity")
                )
                return_pd = str(round(val, 2))
                table_data.append((stat_name, return_pd))

            table_columns = ["Statistic", "Return Period (yr)"]

            # Create the table
            the_table = plt.table(
                cellText=table_data,
                colLabels=table_columns,
                loc="bottom",
                bbox=[0, -1.8, 1, 1.5],
            )
            the_table.auto_set_font_size(False)
            the_table.set_fontsize(12)

            # Center-align text in all cells
            for key, cell in the_table.get_celld().items():
                cell.set_text_props(ha="center")

            # Adjust layout to make space for the table
            plt.subplots_adjust(bottom=0.3)
            Path(fname_save_fig).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(fname_save_fig, bbox_inches="tight")
            plt.clf()


# mostly stuff for flood impact probability calculations
def retrieve_unique_feature_indices(x, sorted_unique_features_in_aoi):
    unique_impacted_feature = np.unique(x)
    return np.isin(
        sorted_unique_features_in_aoi, unique_impacted_feature, assume_unique=True
    )


def return_impacted_features(
    da_features_impacted, sorted_unique_features_in_aoi, event_number_chunksize=100
):
    n_features_in_aoi = len(sorted_unique_features_in_aoi)
    feature_id_name = da_features_impacted.name
    d_chnk = dict(x=-1, y=-1, event_number=event_number_chunksize)
    da_features_impacted = da_features_impacted.chunk(d_chnk)
    da_unique_features_impacted = xr.apply_ufunc(
        retrieve_unique_feature_indices,
        da_features_impacted,
        input_core_dims=[["x", "y"]],
        output_core_dims=[[feature_id_name]],
        vectorize=True,
        dask="parallelized",  # Optional: Use Dask for large datasets
        output_dtypes=bool,
        keep_attrs=True,  # Preserve attributes if needed
        kwargs={"sorted_unique_features_in_aoi": sorted_unique_features_in_aoi},
        dask_gufunc_kwargs=dict(output_sizes={feature_id_name: n_features_in_aoi}),
    )
    da_unique_features_impacted[feature_id_name] = sorted_unique_features_in_aoi.astype(
        int
    )
    da_unique_features_impacted.name = f"{feature_id_name}_impacted"
    return da_unique_features_impacted


def compute_number_of_unique_indices(x):
    return np.array([x.sum()], dtype=int)


def return_number_of_impacted_features(
    da_unique_features_impacted, feature_type
):  # , event_number_chunksize=-1):
    da_unique_features_impacted_loaded = da_unique_features_impacted.load()
    da_n_impacted_features = xr.apply_ufunc(
        compute_number_of_unique_indices,
        da_unique_features_impacted_loaded,
        input_core_dims=[[da_unique_features_impacted_loaded.dims[1]]],
        output_core_dims=[[]],
        vectorize=True,
        dask="parallelized",  # Optional: Use Dask for large datasets
        output_dtypes=[int],
        keep_attrs=True,  # Preserve attributes if needed
    )
    da_n_impacted_features.name = f"n_{feature_type}_impacted"
    return da_n_impacted_features


def compute_min_rtrn_pd_of_impact_for_unique_features(s_grp, n_years):
    varname = "group_feature_impacted"
    s_grp.name = varname
    df_rtrn_pds = compute_return_periods_for_series(s_grp, n_years, varname=varname)
    if (df_rtrn_pds[varname] == False).all():
        rtrn_pd_of_impact = np.nan  # feature was never impacted
    else:
        rtrn_pd_of_impact = (
            df_rtrn_pds.groupby(varname).min().loc[True, f"{varname}_return_pd_yrs"]
        )
    return rtrn_pd_of_impact


def compute_flood_impact_return_periods(
    da_features_impacted,
    sorted_unique_features_in_aoi,
    feature_type,
    sdf_subarea,
    lower_depth_threshold,
    upper_depth_threshold,
    N_YEARS_SYNTHESIZED,
    ALPHA,
    BETA,
    ASSIGN_DUP_VALS_MAX_RETURN,
    ensemble,
):
    # n_features_in_aoi = len()
    da_unique_features_impacted = return_impacted_features(
        da_features_impacted, sorted_unique_features_in_aoi
    ).chunk({"event_number": 100, feature_type: 100})

    da_n_impacted_features = return_number_of_impacted_features(
        da_unique_features_impacted, feature_type
    )

    s_n_features_impacted = da_n_impacted_features.to_series()
    varname = s_n_features_impacted.name
    if ensemble:
        df_impacted_features = compute_return_periods_for_series(
            s_n_features_impacted,
            N_YEARS_SYNTHESIZED,
            varname=varname,
        )
    else:
        s_return_periods = pd.Series(s_n_features_impacted.index)
        s_return_periods.index = s_return_periods.values
        s_return_periods.name = varname + "_return_pd_yrs"
        df_impacted_features = pd.concat(
            [s_n_features_impacted, s_return_periods], axis=1
        )
        df_impacted_features.index.name = "event_number"
    # df_impacted_features["flooded_area_sqkm"] = s_flooded_area_by_event_sm / (1000*1000)

    df_impacted_features["subarea_name"] = sdf_subarea["name"]
    df_impacted_features[f"fraction_of_{feature_type}_impacted"] = (
        s_n_features_impacted / len(sorted_unique_features_in_aoi)
    )
    df_impacted_features["depth_range_m"] = (
        f"[{lower_depth_threshold},{upper_depth_threshold})"
    )
    df_impacted_features = df_impacted_features.reset_index().set_index(
        ["subarea_name", "depth_range_m", "event_number"]
    )
    ds_impacted_features = df_impacted_features.to_xarray()

    # compute return period of impacts for individual buildings ids
    df_unique_features_impacted = da_unique_features_impacted.to_dataframe()
    feature_idx_name = da_features_impacted.name
    feature_impacted_column = da_unique_features_impacted.name
    s_name = f"min_return_period_{feature_impacted_column}"
    if ensemble:
        s_min_rtrn_pd_of_feature_impact = (
            df_unique_features_impacted.loc[:, feature_impacted_column]
            .groupby(feature_idx_name)
            .apply(
                compute_min_rtrn_pd_of_impact_for_unique_features,
                **dict(n_years=N_YEARS_SYNTHESIZED),
            )
        )
        s_min_rtrn_pd_of_feature_impact.name = s_name
    else:
        df_unique_features_impacted = df_unique_features_impacted.reset_index()
        s_rtrn = df_unique_features_impacted["event_number"]
        df_unique_features_impacted[s_name] = s_rtrn
        # subset where impacted is True
        s_min_rtrn_pd_of_feature_impact = (
            df_unique_features_impacted[
                df_unique_features_impacted.loc[:, feature_impacted_column]
            ]
            .groupby(feature_idx_name)
            .min(s_name)[s_name]
        )
        # for any feature that is not impacted, insert NA
        s_min_rtrn_pd_of_feature_impact = s_min_rtrn_pd_of_feature_impact.reindex(
            da_unique_features_impacted[feature_idx_name].to_series()
        )
    df_min_rtrn_pd_of_feature_impact = s_min_rtrn_pd_of_feature_impact.to_frame()
    df_min_rtrn_pd_of_feature_impact["subarea_name"] = sdf_subarea["name"]
    df_min_rtrn_pd_of_feature_impact["depth_range_m"] = (
        f"[{lower_depth_threshold},{upper_depth_threshold})"
    )
    ds_min_rtrn_pd_of_feature_impact = (
        df_min_rtrn_pd_of_feature_impact.reset_index()
        .set_index(["subarea_name", "depth_range_m", feature_idx_name])
        .to_xarray()
    )
    return ds_impacted_features, ds_min_rtrn_pd_of_feature_impact


def compute_floodarea_retrn_pds(
    da_sim_wlevel,
    ds_features,
    gdf_mitigation_aois,
    N_YEARS_SYNTHESIZED,
    ALPHA,
    BETA,
    ASSIGN_DUP_VALS_MAX_RETURN,
):
    # prepare lists to populate with datasets
    lst_ds_flooded_areas_by_event_and_aoi = []
    lst_feature_count_rtrn_pds = []
    lst_min_rtrn_pd_of_impact_by_feature = []
    lst_key_flood_thresholds_and_beyond = (
        LST_KEY_FLOOD_THRESHOLDS_FOR_SENSITIVITY_ANALYSIS.copy()
    )
    lst_key_flood_thresholds_and_beyond.append(np.inf)
    for shp_row_iloc, sdf_subarea in gdf_mitigation_aois.iterrows():
        # create mask for the AOI
        xs = da_sim_wlevel.x.to_series()
        ys = da_sim_wlevel.y.to_series()
        # define gridsize
        x_size_m = xs.diff().dropna().mean()
        y_size_m = ys.diff().dropna().mean()
        if not np.isclose(x_size_m, y_size_m):
            print("warning: the x size and y size of the gridcells aren't the same")
        grid_area_m = x_size_m * y_size_m
        # generate subarea mask from the shapefile
        ensemble = True
        if da_sim_wlevel.attrs["design_storms"]:
            ensemble = False
        da_to_mask = da_sim_wlevel.isel(event_number=1)
        series_single_row_of_gdf = sdf_subarea
        ds_subarea_mask = return_mask_dataset_from_polygon(
            da_to_mask,
            shapefile_path=None,
            series_single_row_of_gdf=series_single_row_of_gdf,
        )

        # subset waterlevel dataset
        da_sim_wlevel_subarea = da_sim_wlevel.where(ds_subarea_mask, drop=True).chunk(
            x=5, y=5, event_number=-1
        )
        da_sim_wlevel_subarea = da_sim_wlevel_subarea.rio.write_crs(COORD_EPSG)
        # analyze impacts by depth range
        for idx_upper_depth_threshold, upper_depth_threshold in enumerate(
            lst_key_flood_thresholds_and_beyond
        ):
            # skip the first one; i don't care what's below the minimum nuisance flood boundary
            if idx_upper_depth_threshold == 0:
                continue
            lower_depth_threshold = lst_key_flood_thresholds_and_beyond[
                idx_upper_depth_threshold - 1
            ]
            # subset events within depth range
            mask_depths_within_range = (
                da_sim_wlevel_subarea >= lower_depth_threshold
            ) & (da_sim_wlevel_subarea < upper_depth_threshold)
            da_sim_wlevel_subarea_target_depths = da_sim_wlevel_subarea.where(
                mask_depths_within_range
            )
            da_ngridcells_in_depth_range = (
                ~da_sim_wlevel_subarea_target_depths.isnull()
            ).sum(["x", "y"])
            s_ncells_flooded_by_event = da_ngridcells_in_depth_range.to_series()
            s_flooded_area_by_event_sm = s_ncells_flooded_by_event * grid_area_m
            s_flooded_area_by_event_sm.name = "flooded_area_sqm"
            if ensemble:
                df_flooded_area_by_event = compute_return_periods_for_series(
                    s_flooded_area_by_event_sm,
                    N_YEARS_SYNTHESIZED,
                    varname=s_flooded_area_by_event_sm.name,
                )
            else:
                s_return_periods = pd.Series(s_flooded_area_by_event_sm.index)
                s_return_periods.index = s_return_periods.values
                s_return_periods.name = (
                    s_flooded_area_by_event_sm.name + "_return_pd_yrs"
                )
                df_flooded_area_by_event = pd.concat(
                    [s_flooded_area_by_event_sm, s_return_periods], axis=1
                )
                df_flooded_area_by_event.index.name = "event_number"
            # df_flooded_area_by_event["flooded_area_sqkm"] = s_flooded_area_by_event_sm / (1000*1000)
            str_depth_range = f"[{lower_depth_threshold},{upper_depth_threshold})"
            df_flooded_area_by_event["subarea_name"] = sdf_subarea["name"]
            df_flooded_area_by_event["depth_range_m"] = str_depth_range
            df_flooded_area_by_event = df_flooded_area_by_event.reset_index().set_index(
                ["subarea_name", "depth_range_m", "event_number"]
            )
            ds_flooded_area_by_event = df_flooded_area_by_event.to_xarray()
            # compute feature impact return periods
            for var in ds_features.data_vars:
                da_features = ds_features[var]
                feature_type = da_features.name
                # da_features = dic_features[feature_type]
                # subset for the sub area
                da_features_in_aoi = da_features.where(ds_subarea_mask, drop=True)
                # subset for features that experience flooding
                da_features_impacted = da_features_in_aoi.where(
                    mask_depths_within_range
                )
                # da_features_impacted_og.sel(event_number = 3748).plot(x = "x", y = "y")
                sorted_unique_features_in_aoi = np.sort(
                    da_features_in_aoi.to_dataframe().dropna().iloc[:, 0].unique()
                )
                # sys.extit('work')
                ds_impacted_features, ds_min_rtrn_pd_of_feature_impact = (
                    compute_flood_impact_return_periods(
                        da_features_impacted,
                        sorted_unique_features_in_aoi,
                        feature_type,
                        sdf_subarea,
                        lower_depth_threshold,
                        upper_depth_threshold,
                        N_YEARS_SYNTHESIZED,
                        ALPHA,
                        BETA,
                        ASSIGN_DUP_VALS_MAX_RETURN,
                        ensemble,
                    )
                )
                lst_feature_count_rtrn_pds.append(ds_impacted_features)
                lst_min_rtrn_pd_of_impact_by_feature.append(
                    ds_min_rtrn_pd_of_feature_impact
                )
            lst_ds_flooded_areas_by_event_and_aoi.append(ds_flooded_area_by_event)
            # print(f"computed flood impact return periods for aoi {sdf_subarea["name"]} and depth range {str_depth_range}")
            # sys.exit('work')
    # combine event information into single dataset
    ds_flood_area_rtrn_pds = xr.merge(lst_ds_flooded_areas_by_event_and_aoi)
    ds_impacted_feature_count_rtrn_pds = xr.merge(lst_feature_count_rtrn_pds)
    ds_feature_impact_min_rtrn_pd = xr.merge(lst_min_rtrn_pd_of_impact_by_feature)
    ds_flood_impacts_by_aoi = xr.merge(
        [ds_flood_area_rtrn_pds, ds_impacted_feature_count_rtrn_pds]
    )
    return ds_flood_impacts_by_aoi, ds_feature_impact_min_rtrn_pd


# Function to get the number of decimal places in a float
def get_decimal_places(num):
    str_num = str(num)
    if "." in str_num:
        return len(str_num.split(".")[1])
    return 0  # Return 0 if there are no decimal places


def return_indices_of_series_geq_lb_and_leq_ub(s_to_subset, lb, ub):
    lb_decimal_places = get_decimal_places(lb)
    ub_decimal_places = get_decimal_places(ub)
    s_between_vals = (s_to_subset.round(lb_decimal_places) >= lb) & (
        s_to_subset.round(ub_decimal_places) <= ub
    )
    idx_between_vals = s_between_vals[s_between_vals].index
    return idx_between_vals
