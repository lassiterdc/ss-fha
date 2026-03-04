# REFACTORING STATUS: COMPLETE (2026-03-02)
# Refactored into:
#   src/ss_fha/analysis/event_comparison.py  — orchestration + DataTree output
#   src/ss_fha/runners/event_stats_runner.py — CLI runner
#   src/ss_fha/core/event_statistics.py      — core computation (Phase 02C)
# See: docs/planning/refactors/2026-02-25_full_codebase_refactor/work_chunks/implemented/03C_event_statistics_runner.md

# %%
from local.__inputs import (
    F_SIM_TSERIES,
    F_OBS_TSERIES,
    F_TRITON_OUTPUTS_DSGN,
    F_SIM_FLOOD_PROBS,
    F_SIM_FLOOD_PROBS_EVENT_NUMBER_MAPPING,
    N_YEARS_SYNTHESIZED,
    ALPHA,
    BETA,
    # ASSIGN_DUP_VALS_MAX_RETURN,
    F_RTRN_PDS_SEA_WATER_LEVEL,
    F_RTRN_PDS_RAINFALL,
    # RAIN_WINDOWS_MIN,
    DIR_SCRATCH_UNIVAR_EVENT_RTRN_BS,
    F_SIM_MULTIVAR_RETURN_PERIODS,
    DIR_SCRATCH_MULTVAR_EVENT_RTRN_BS,
    FLD_RTRN_PD_ALPHA,
    F_MULTIVAR_BS_UNCERTAINTY_CI,
    F_UNIVAR_BS_UNCERTAINTY_CI,
    F_BS_UNCERTAINTY_EVENTS_IN_CI,
)

from local.__utils import (
    compute_return_periods_for_series,
    prepare_for_bootstrapping,
    create_bar_label_one_line,
    empirical_multivariate_return_periods,
    delete_zarr,
    return_dic_zarr_encodingds,
    bs_samp_of_univar_event_return_period,
    compute_univariate_event_return_periods,
    bs_samp_of_multivar_event_return_period,
    compute_all_multivariate_return_period_combinations,
    analyze_bootstrapped_samples,
    return_vars_associated_with_event_stat,
    return_df_of_evens_within_ci_including_event_stats,
)

# from local.__plotting
import zarr
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
import sys
import shutil
from scipy.stats.mstats import plotting_positions
import time
from glob import glob
import os
from tqdm import tqdm
import pandas as pd
from pathlib import Path

n_bs_samples = 500

ds_sim_tseries = xr.open_dataset(F_SIM_TSERIES).chunk(
    dict(timestep=-1, year=-1, event_type=1, event_id=-1)
)
sim_idx_names = ds_sim_tseries.coords.to_index().names
event_idx_names = [name for name in sim_idx_names if name != "timestep"]

ds_obs_tseries = xr.open_dataset(F_OBS_TSERIES)

ds_triton_dsgn = xr.open_dataset(F_TRITON_OUTPUTS_DSGN, engine="zarr").chunk("auto")
# f_dsgn_tseries = f_design_storm_tseries_based_on_SSR
target_design_storms_years = ds_triton_dsgn.year.values

df_sim_flood_probs_event_num_mapping = pd.read_csv(
    F_SIM_FLOOD_PROBS_EVENT_NUMBER_MAPPING
)

ds_sim_flood_probs = xr.open_dataset(F_SIM_FLOOD_PROBS, engine="zarr").chunk("auto")

s_max_sea_wlevel = (
    ds_sim_tseries["waterlevel_m"]
    .max("timestep")
    .to_dataframe()["waterlevel_m"]
    .dropna()
)

n_years = N_YEARS_SYNTHESIZED

ar_sim_years = np.arange(N_YEARS_SYNTHESIZED)


# %% compute univariate stat return periods
val = input(
    f"type 'yes' to re-calculate univariate event return periods event if they already exist."
)
rewrite_intermediate_results_if_files_exist = True
if val.lower() != "yes":
    rewrite_intermediate_results_if_files_exist = False

if (rewrite_intermediate_results_if_files_exist == False) and (
    (Path(F_RTRN_PDS_SEA_WATER_LEVEL).exists()) and (Path(F_RTRN_PDS_RAINFALL).exists())
):
    df_wlevel_return_pds = pd.read_csv(
        F_RTRN_PDS_SEA_WATER_LEVEL, index_col=event_idx_names
    )
    df_rain_return_pds = pd.read_csv(F_RTRN_PDS_RAINFALL, index_col=event_idx_names)
    print(
        f"Univariate return periods already calculated. Loading from files since rewrite_intermediate_results_if_files_exist is set to {rewrite_intermediate_results_if_files_exist}"
    )
else:
    print(
        "computing univariate return periods for water level and rainfall event statistics...."
    )
    df_wlevel_return_pds, df_rain_return_pds = compute_univariate_event_return_periods(
        ds_sim_tseries,
    )
    df_wlevel_return_pds.to_csv(F_RTRN_PDS_SEA_WATER_LEVEL)
    df_rain_return_pds.to_csv(F_RTRN_PDS_RAINFALL)


# %%  compute multivariate return periods
val = input(
    f"type 'yes' to re-calculate multivariate event return periods event if they already exist."
)
rewrite_intermediate_results_if_files_exist = True
if val.lower() != "yes":
    rewrite_intermediate_results_if_files_exist = False

if (rewrite_intermediate_results_if_files_exist == False) and (
    Path(F_SIM_MULTIVAR_RETURN_PERIODS).exists()
):
    # ds_multivar_return_periods_og = xr.open_dataset(f_sim_multivar_return_periods, engine = "zarr").chunk("auto")
    print(
        f"Multivariate return periods already calculated. Loading from file since rewrite_intermediate_results_if_files_exist is set to {rewrite_intermediate_results_if_files_exist}"
    )
else:
    # first figure out all the relevant combinations of event statistics
    ## reindex to include all events; fill missing values with zero since the return periods are negligable (threshold was not exceeded)
    df_multivar_return_periods_og = compute_all_multivariate_return_period_combinations(
        df_rain_return_pds,
        df_wlevel_return_pds,
    )
    ds_multivar_return_periods_og = df_multivar_return_periods_og.to_xarray()
    chunk_sizes = dict(event_stats=1, event_type=-1, year=-1, event_id=-1)
    delete_zarr(F_SIM_MULTIVAR_RETURN_PERIODS, attempt_time_limit_s=10)
    ds_multivar_return_periods_og.chunk(chunk_sizes).to_zarr(
        F_SIM_MULTIVAR_RETURN_PERIODS,
        mode="w",
        encoding=return_dic_zarr_encodingds(ds_multivar_return_periods_og, clevel=5),
        consolidated=True,
    )

ds_multivar_return_periods_og = xr.open_dataset(
    F_SIM_MULTIVAR_RETURN_PERIODS, engine="zarr"
).chunk("auto")
# %% bootstrapping univariate measurements
df_wlevel_return_pds_og, df_rain_return_pds_og = (
    df_wlevel_return_pds.copy(),
    df_rain_return_pds.copy(),
)

val = input(f"type 'yes' to re-draw bootstrapped samples of univariate return periods.")
perform_bootstrapping = True
if val.lower() != "yes":
    perform_bootstrapping = False

if perform_bootstrapping:
    lst_files_processed = glob(
        f"{DIR_SCRATCH_UNIVAR_EVENT_RTRN_BS}univar_rtrn_bs_*.csv"
    )
    if len(lst_files_processed) > 0:
        pickup_where_left_off = False
        val = input(
            f"write 'yes' to overwrite existing outputs. Otherwise the script picks up at the last bs_id."
        )
        if val.lower() != "yes":
            pickup_where_left_off = True
        bs_id_start, move_forward_with_bootstrapping = prepare_for_bootstrapping(
            lst_files_processed,
            pickup_where_left_off,
            currently_running=True,
            n_bs_samples=n_bs_samples,
            split_string=".csv",
        )
        if move_forward_with_bootstrapping == False:
            sys.exit(
                f"halting bootstrapping because move_forward_with_bootstrapping = {move_forward_with_bootstrapping}"
            )
    else:
        bs_id_start = 0
    for bs_id in tqdm(np.arange(bs_id_start, n_bs_samples)):
        df_bootstrapped_results = bs_samp_of_univar_event_return_period(
            bs_id,
            ds_sim_tseries,
            df_wlevel_return_pds_og,
            df_rain_return_pds_og,
        )
        f_out_temp = f"{DIR_SCRATCH_UNIVAR_EVENT_RTRN_BS}univar_rtrn_bs_{bs_id}.csv"
        df_bootstrapped_results.to_csv(f_out_temp)

# %% bootstrapping multivariate return period estimates (takes like 70 hours)
val = input(
    f"type 'yes' to re-draw bootstrapped samples of multivariate return periods."
)
rewrite_intermediate_results_if_files_exist = True
if val.lower() != "yes":
    rewrite_intermediate_results_if_files_exist = False

if rewrite_intermediate_results_if_files_exist:
    lst_files_processed = glob(
        f"{DIR_SCRATCH_MULTVAR_EVENT_RTRN_BS}multivar_rtrn_bs_*.csv"
    )
    if len(lst_files_processed) > 0:
        pickup_where_left_off = False
        val = input(
            f"write 'yes' to overwrite existing outputs. Otherwise the script picks up at the last bs_id."
        )
        if val.lower() != "yes":
            pickup_where_left_off = True
        bs_id_start, move_forward_with_bootstrapping = prepare_for_bootstrapping(
            lst_files_processed,
            pickup_where_left_off,
            currently_running=True,
            n_bs_samples=n_bs_samples,
            split_string=".csv",
        )
    df_multivar_return_periods_og = ds_multivar_return_periods_og.to_dataframe()

    for bs_id in tqdm(np.arange(bs_id_start, n_bs_samples)):
        df_bootstrapped_results = bs_samp_of_multivar_event_return_period(
            bs_id,
            df_multivar_return_periods_og,
            ds_sim_tseries,
            df_rain_return_pds,
            df_wlevel_return_pds,
            target_design_storms_years,
        )
        f_out_temp = f"{DIR_SCRATCH_MULTVAR_EVENT_RTRN_BS}multivar_rtrn_bs_{bs_id}.csv"
        df_bootstrapped_results.to_csv(f_out_temp)


# %%  confidence intervals
# multivariate
df_event_all_stats = pd.concat([df_wlevel_return_pds, df_rain_return_pds], axis=1)

lst_idx = ["bs_id", "formulation", "event_stat", "return_period_yrs"]
colname_event_idx = "event_type.year.event_id"
lst_files_processed = glob(f"{DIR_SCRATCH_MULTVAR_EVENT_RTRN_BS}multivar_rtrn_bs_*.csv")
df_return_pd_cis_multivar, df_unique_events_multivar = analyze_bootstrapped_samples(
    lst_files_processed, colname_event_idx, lst_idx, df_event_all_stats
)

df_return_pd_cis_multivar.to_csv(F_MULTIVAR_BS_UNCERTAINTY_CI)

# univariate
df_event_all_stats = pd.concat([df_wlevel_return_pds, df_rain_return_pds], axis=1)

lst_idx = ["bs_id", "formulation", "event_stat", "return_period_yrs"]
colname_event_idx = "event_type.year.event_id"
lst_files_processed = glob(f"{DIR_SCRATCH_UNIVAR_EVENT_RTRN_BS}univar_rtrn_bs_*.csv")
df_return_pd_cis_univar, df_unique_events_univar = analyze_bootstrapped_samples(
    lst_files_processed, colname_event_idx, lst_idx, df_event_all_stats
)

df_return_pd_cis_univar.to_csv(F_UNIVAR_BS_UNCERTAINTY_CI)


# %% create csv files of all events within each confidence interval along with the statistics of those events
# univariate

# pull together dataset of univariate return periods
df_univar_return_periods_og = pd.concat(
    [df_wlevel_return_pds, df_rain_return_pds], axis=1
)
# extract column names associated with stat values and return periods
stat_values = df_univar_return_periods_og.columns[
    [
        ("emp_cdf" not in col) and ("return_pd" not in col)
        for col in df_univar_return_periods_og.columns
    ]
]
rtrn_pd_cols = df_univar_return_periods_og.columns[
    [("return_pd" in col) for col in df_univar_return_periods_og.columns]
]

# define to use in function
df_return_pd_cis = df_return_pd_cis_univar
# format to work with function (colnames are stat names, values are return periods)
all_event_return_pds = df_univar_return_periods_og.loc[:, rtrn_pd_cols]
all_event_return_pds.columns = stat_values
form = "empirical_univar_return_pd_yrs"
lst_trgt_return_pds = target_design_storms_years
lst_df_events = []

for stat in stat_values:
    df_events_in_ci = return_df_of_evens_within_ci_including_event_stats(
        all_event_return_pds,
        df_return_pd_cis,
        stat,
        form,
        lst_trgt_return_pds,
        df_event_all_stats,
    )
    df_events_in_ci["formulation"] = form
    df_events_in_ci = df_events_in_ci.rename(columns={form: "return_period_yrs_og"})
    df_events_in_ci = df_events_in_ci.set_index(
        [
            "formulation",
            "event_stats",
            "return_period_yrs",
            "event_type",
            "year",
            "event_id",
        ]
    ).sort_index()
    lst_df_events.append(df_events_in_ci)

df_univar_events_in_ci = pd.concat(lst_df_events).sort_index()

# multivariate
df_return_pd_cis = df_return_pd_cis_multivar
all_event_return_pds = ds_multivar_return_periods_og

lst_trgt_return_pds = target_design_storms_years
lst_df_events = []

for stat in ds_multivar_return_periods_og.event_stats.to_series():
    for form in ["empirical_multivar_rtrn_yrs_AND", "empirical_multivar_rtrn_yrs_OR"]:
        df_events_in_ci = return_df_of_evens_within_ci_including_event_stats(
            all_event_return_pds,
            df_return_pd_cis,
            stat,
            form,
            lst_trgt_return_pds,
            df_event_all_stats,
        )
        df_events_in_ci["formulation"] = form
        df_events_in_ci = df_events_in_ci.rename(columns={form: "return_period_yrs_og"})
        df_events_in_ci = df_events_in_ci.set_index(
            [
                "formulation",
                "event_stats",
                "return_period_yrs",
                "event_type",
                "year",
                "event_id",
            ]
        ).sort_index()
        lst_df_events.append(df_events_in_ci)


df_multivar_events_in_ci = pd.concat(lst_df_events).sort_index()

#  combine into single csv and export
df_events_in_ci = pd.concat(
    [df_univar_events_in_ci, df_multivar_events_in_ci]
).sort_index()

lst_long_idx = ["year", "event_type", "event_id"]

idx_keepers = pd.Series(df_events_in_ci.index.names)[
    [idx_name not in lst_long_idx for idx_name in df_events_in_ci.index.names]
].to_list()

# reindex by event number
event_mapping = df_sim_flood_probs_event_num_mapping.loc[
    :, ["event_number"] + lst_long_idx
]
event_mapping = event_mapping.set_index(lst_long_idx)

df_events_in_ci = (
    df_events_in_ci.join(event_mapping, how="left")
    .reset_index()
    .set_index(idx_keepers + ["event_number"])
)

df_events_in_ci.to_csv(F_BS_UNCERTAINTY_EVENTS_IN_CI)
# %% quick visualizations
# df_event_all_stats = pd.concat([df_wlevel_return_pds, df_rain_return_pds], axis = 1)

stat = "5min,24hr,w"
form = "empirical_multivar_rtrn_yrs_AND"
lst_trgt_return_pds = [2, 100]

# df_wlevel_return_pds
# df_rain_return_pds

# subset events within confidence interval

df_for_plotting = df_events_in_ci.loc[pd.IndexSlice[form, stat, lst_trgt_return_pds]]

# df = df_unique_events_multivar.loc[pd.IndexSlice[form, trgt_return_pds, stat]].reset_index()
import seaborn as sns

sns.set_theme(style="white")

from matplotlib.colors import Normalize
import matplotlib as mpl

norm = Normalize()
cmap = viridis = mpl.colormaps["viridis"].resampled(8)
# https://seaborn.pydata.org/generated/seaborn.scatterplot.html
sns.scatterplot(
    data=df_for_plotting,
    x="q1",
    y="q2",
    hue="return_period_yrs",
    alpha=0.5,
    palette=cmap,
    size="q3",
    hue_norm=norm,
)

#

fig, ax = plt.subplots()

stat = "5min,w"
form = "empirical_multivar_rtrn_yrs_AND"

df_for_plotting = df_events_in_ci.loc[pd.IndexSlice[form, stat, lst_trgt_return_pds]]

# df = df_unique_events_multivar.loc[pd.IndexSlice[form, [2, 100], stat]].reset_index()
import seaborn as sns

sns.set_theme(style="white")
from matplotlib.colors import Normalize
import matplotlib as mpl

norm = Normalize()
cmap = viridis = mpl.colormaps["viridis"].resampled(8)
# https://seaborn.pydata.org/generated/seaborn.scatterplot.html
sns.scatterplot(
    data=df_for_plotting,
    x="q1",
    y="q2",
    hue="return_period_yrs",
    alpha=0.5,
    palette=cmap,
    hue_norm=norm,
    **dict(edgecolors="g"),
)

fig, ax = plt.subplots()
stat = "5min,w"
form = "empirical_multivar_rtrn_yrs_OR"

df_for_plotting = df_events_in_ci.loc[pd.IndexSlice[form, stat, lst_trgt_return_pds]]
# df = df_unique_events_multivar.loc[pd.IndexSlice[form, [2, 100], stat]].reset_index()
import seaborn as sns

sns.set_theme(style="white")
from matplotlib.colors import Normalize
import matplotlib as mpl

norm = Normalize()
cmap = viridis = mpl.colormaps["viridis"].resampled(8)
# https://seaborn.pydata.org/generated/seaborn.scatterplot.html
sns.scatterplot(
    data=df_for_plotting,
    x="q1",
    y="q2",
    hue="return_period_yrs",
    alpha=0.5,
    palette=cmap,
    hue_norm=norm,
    **dict(edgecolors="g"),
)
