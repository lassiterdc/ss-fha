# %% import libraries
from local.__inputs import *
from local.__utils import *
import pandas as pd
import numpy as np
import sys
import shutil
import xarray as xr

from hpc.python.__filepaths_andes import constant_head_val

estimate_type_to_simulate = "point_estimate"  # for the final time series, I am only going to use the point estimates of return period values rather than a range
f_sim_tseries = "D:/Dropbox/_GradSchool/_norfolk/stormy/flood_attribution/weather/combined_simulation_time_series.nc"
ds_sim_tseries = xr.open_dataset(f_sim_tseries, chunks=dict(timestep="auto"))

surge_event_duration = 8

Path(dir_output_design_storm_tseries).mkdir(parents=True, exist_ok=True)

# load the NOAA design storms for reference

ds_design_event_tseries = xr.open_dataset(f_design_storm_tseries_NOAA)

# mean_high_high_tide = compute_mean_high_high_tide_from_NOAA_tide_gage(
#     f_noaa_tide_gage_csv, feet_per_meter
# )

print(
    "As of 11/19/2025, the manually computed mean high high tide was only used in event type = rain design storms.\n\
For all other simulations, including observed and stochastically generated even simulations, the 2025 projected\n\
MHHW from NOAA was used when a constant sea water level boundary condition was applied. This script has been\n\
updated to insert the NOAA mean high high tide but that means the outputs of this script do NOT reflect model\n\
results prior to 11/19/2025."
)

sys.exit(
    "the outputs of this script do not reflect outputs from prior to 11/19/2025 and should be run with caution.\n\
I'm pretty sure nothing could get over written, but be 100% sure beofre doing running this script."
)

# %% creating IDF table relating 6, 12, and 24 hour rainfall to 1, 2, 10, and 100-year return periods
df_univariate_return_periods_from_ssr = pd.read_csv(
    f_univar_bs_uncertainty_ci
).set_index(["quantile", "event_stat", "return_period_yrs"])
df_events_in_ci = pd.read_csv(f_bs_uncertainty_events_in_ci).set_index(
    ["formulation", "event_stats", "return_period_yrs", "event_number"]
)
df_wlevel_return_pds = pd.read_csv(f_rtrn_pds_sea_water_level)
df_rain_return_pds = pd.read_csv(f_rtrn_pds_rainfall)

lst_sources = ["point_estimate", "upper_bound", "lower_bound"]
lst_rtrn_pds = [1, 2, 10, 100]
lst_durations = [6, 12, 24]
# create empty rainfall idf
index = pd.MultiIndex.from_product(
    [lst_sources, lst_durations], names=["source", "duration_h"]
)
df_idf = pd.DataFrame(index=index, columns=lst_rtrn_pds)
# create empty suruge design storm
df_wlevel_dsgn_storms = pd.DataFrame(
    index=pd.Index(lst_sources, name="source"), columns=lst_rtrn_pds
)

for source in lst_sources:
    if source == "point_estimate":
        quant = 0.5
    elif source == "upper_bound":
        quant = 0.95
    else:
        quant = 0.05
    for return_pd in lst_rtrn_pds:
        # process water level
        df_univariate_return_periods_from_ssr_subset = (
            df_univariate_return_periods_from_ssr.loc[
                pd.IndexSlice[quant, "max_waterlevel_m", :]
            ]
        )
        rtrn_lookup = df_univariate_return_periods_from_ssr_subset.loc[
            return_pd, :
        ].iloc[0]
        wlevel = np.interp(
            rtrn_lookup,
            df_wlevel_return_pds["max_waterlevel_m_return_pd_yrs"].sort_values().values,
            df_wlevel_return_pds["max_waterlevel_m"].sort_values().values,
        )
        df_wlevel_dsgn_storms.loc[source, return_pd] = wlevel
        for duration in lst_durations:
            # rainfall
            df_univariate_return_periods_from_ssr_subset = (
                df_univariate_return_periods_from_ssr.loc[quant, :, return_pd]
            )
            idx_dur = df_univariate_return_periods_from_ssr_subset.index.str.contains(
                f"_{duration}hr"
            )
            event_stat_name = df_univariate_return_periods_from_ssr_subset.index[
                idx_dur
            ].values[0]
            og_rtrn_pd = df_univariate_return_periods_from_ssr_subset.loc[
                event_stat_name
            ]
            rain_depth = np.interp(
                og_rtrn_pd.values[0],
                df_rain_return_pds[f"{event_stat_name}_return_pd_yrs"]
                .sort_values()
                .values,
                df_rain_return_pds[event_stat_name].sort_values().values,
            )
            df_idf.loc[pd.IndexSlice[source, duration], return_pd] = rain_depth


# load unit hyetograph time series
def reindex_at_first_tstep(df_tseries):
    df_tseries.index = df_tseries.index - df_tseries.index.min()
    return df_tseries


def change_colname_from_in_per_hr_to_mm_per_hr(df_tseries):
    df_tseries["mm_per_hr"] = df_tseries["in_per_hr"]  # * mm_per_inch
    df_tseries = df_tseries.drop(columns=["in_per_hr"])
    return df_tseries


df_unit_rain_tseries_6hr = change_colname_from_in_per_hr_to_mm_per_hr(
    reindex_at_first_tstep(
        pd.read_csv(
            f_unit_hyetograph_6hr, parse_dates=["date_time"], index_col="date_time"
        )
    )
)
df_unit_rain_tseries_12hr = change_colname_from_in_per_hr_to_mm_per_hr(
    reindex_at_first_tstep(
        pd.read_csv(
            f_unit_hyetograph_12hr, parse_dates=["date_time"], index_col="date_time"
        )
    )
)
df_unit_rain_tseries_24hr = change_colname_from_in_per_hr_to_mm_per_hr(
    reindex_at_first_tstep(
        pd.read_csv(
            f_unit_hyetograph_24hr, parse_dates=["date_time"], index_col="date_time"
        )
    )
)

og_tstep_pd_tdelt = pd.Series(df_unit_rain_tseries_6hr.index.diff().dropna()).mode()[0]
og_tstep_hr = og_tstep_pd_tdelt / np.timedelta64(1, "h")

lst_unit_dfs = []
for df in [
    df_unit_rain_tseries_6hr,
    df_unit_rain_tseries_12hr,
    df_unit_rain_tseries_24hr,
]:
    series = df["mm_per_hr"]
    if not np.isclose((series * og_tstep_hr).sum(), 1):
        print(
            f"Warning: the unit hyetographs don't seem to add up to 1: {(series * og_tstep_hr).sum()} for unit event of length {series.index.max()+og_tstep_pd_tdelt}"
        )
    # reindex to target timestep
    idx_1min = pd.timedelta_range(
        df.index.min(), df.index.max() + og_tstep_pd_tdelt, freq="1min"
    )
    target_idx = pd.timedelta_range(
        df.index.min(), df.index.max() + og_tstep_pd_tdelt, freq=target_tstep
    )[0:-1]
    df_1min = df.reindex(idx_1min[0:-1], method="ffill")
    df_trgt_idx = df_1min.resample(rule=target_tstep).mean()
    df_trgt_idx["design_storm_rain_duration_h"] = int(len(df) * og_tstep_hr)
    # df_trgt_idx["year"] = "unit"
    df_trgt_idx.index.name = "timestep"
    df_trgt_idx = df_trgt_idx.reset_index().set_index(
        ["design_storm_rain_duration_h", "timestep"]
    )
    lst_unit_dfs.append(df_trgt_idx)


df_unit_tseries = pd.concat(lst_unit_dfs)
tstep_pd_tdelt = pd.Series(
    df_unit_tseries.reset_index()["timestep"].diff().dropna()
).mode()[0]
tstep_hr = tstep_pd_tdelt / np.timedelta64(1, "h")

# create design rainfall events

df_idf_selected_events = df_idf.loc[
    pd.IndexSlice[:, LST_DESIGN_STORM_DURATIONS_TO_SIMULATE], return_periods
]

df_unit_tseries
tstep_hr
t_buffer_h = np.timedelta64(TIMESERIES_BUFFER_BEFORE_FIRST_RAIN_H, "h")
lst_dfs_design_storm_tseries = []
for idx, row_dpths_mm in df_idf_selected_events.iterrows():
    src, dur_h = idx
    df_unit_for_dur = df_unit_tseries.loc[pd.IndexSlice[dur_h, :]]
    for return_pd, depth_mm in row_dpths_mm.items():
        df_unit_for_dur_rtrn_pd = df_unit_for_dur.copy()
        # sys.exit("work")
        if not np.isclose((df_unit_for_dur_rtrn_pd * tstep_hr).sum(), 1):
            sys.exit("Problem: issue with unit event")
        df_unit_for_dur_rtrn_pd = df_unit_for_dur_rtrn_pd * depth_mm
        if not np.isclose((df_unit_for_dur_rtrn_pd * tstep_hr).sum(), depth_mm):
            sys.exit("Problem: target depth and actual depth do not line up")
        target_idx = pd.timedelta_range(
            df_unit_for_dur_rtrn_pd.index.min() - t_buffer_h,
            df_unit_for_dur_rtrn_pd.index.max() + t_buffer_h,
            freq=target_tstep,
        )
        df_unit_for_dur_rtrn_pd = df_unit_for_dur_rtrn_pd.reindex(
            target_idx, fill_value=0
        )
        # reidnex so it starts with 0
        df_unit_for_dur_rtrn_pd.index = (
            df_unit_for_dur_rtrn_pd.index
            - df_unit_for_dur_rtrn_pd.index.min()
            + ARBIRARY_START_DATE
        )
        df_unit_for_dur_rtrn_pd.index.name = "timestep"
        df_unit_for_dur_rtrn_pd["design_storm_rain_duration_h"] = int(dur_h)
        df_unit_for_dur_rtrn_pd["year"] = int(return_pd)
        df_unit_for_dur_rtrn_pd["source"] = src
        df_unit_for_dur_rtrn_pd = df_unit_for_dur_rtrn_pd.reset_index().set_index(
            ["year", "design_storm_rain_duration_h", "source", "timestep"]
        )
        lst_dfs_design_storm_tseries.append(df_unit_for_dur_rtrn_pd)

ds_design_rainfall = pd.concat(lst_dfs_design_storm_tseries).to_xarray()

# create design surge time series
t_idx = pd.DatetimeIndex(ds_design_rainfall.timestep)

lst_wlevel_tseries = []
for source, row_wlevel_return_pds in df_wlevel_dsgn_storms.iterrows():
    for idx, val in row_wlevel_return_pds.items():
        s_wlevel_tseries = pd.Series(data=val, index=t_idx).astype(float)
        s_wlevel_tseries.name = "waterlevel_m"
        df_wlevel_tseries = s_wlevel_tseries.to_frame()
        try:
            desc = int(idx)
        except:
            desc = 0
        df_wlevel_tseries["source"] = source
        df_wlevel_tseries["year"] = desc
        df_wlevel_tseries.index.name = "timestep"
        lst_wlevel_tseries.append(
            df_wlevel_tseries.reset_index().set_index(["year", "source", "timestep"])
        )

ds_design_wlevel = pd.concat(lst_wlevel_tseries).to_xarray()

# %% creating simulation ready time series
mrms_gridkeys = []
for var in ds_sim_tseries.data_vars:
    if var in ["waterlevel_m", "surge_m", "tide_m"]:
        continue
    mrms_gridkeys.append(var)

idx_names = ds_sim_tseries.coords.to_index().names

lst_ds = []


# create time series
for e_type in ds_sim_tseries.event_type.values:
    for year in return_periods:
        event_id = 0
        for dsgn_strm_dur in ds_design_rainfall.design_storm_rain_duration_h.values:
            for source in ds_design_rainfall.source.to_series():
                if source != estimate_type_to_simulate:
                    continue
                event_id += 1
                if (e_type == "compound") or (e_type == "rain"):
                    df_rain_tseries = (
                        ds_design_rainfall.sel(
                            design_storm_rain_duration_h=dsgn_strm_dur,
                            year=year,
                            source=source,
                        )
                        .to_dataframe()
                        .dropna()["mm_per_hr"]
                        .to_frame()
                    )
                    # df_rain_tseries = df_rain_tseries.drop(columns = ["design_storm_rain_duration_h", "year"])
                if (e_type == "compound") or (e_type == "surge"):
                    df_surge_tseries = (
                        ds_design_wlevel.sel(year=year, source=source)
                        .to_dataframe()
                        .dropna()["waterlevel_m"]
                        .to_frame()
                    )
                    # df_surge_tseries = df_surge_tseries.drop(columns = ["year"])
                if e_type == "surge":  # set rainfall to zero and truncate to 8 hours
                    df_surge_tseries = df_surge_tseries.loc[
                        df_surge_tseries.index.min() : df_surge_tseries.index.min()
                        + np.timedelta64(surge_event_duration, "h")
                    ].copy()
                    df_surge_tseries["mm_per_hr"] = 0
                    df_tseries_combined = df_surge_tseries
                    if (
                        event_id > 1
                    ):  # only writing 1 surge event per return period since they all have the same duration
                        continue
                elif e_type == "rain":  # set surge to the mean high water level
                    df_rain_tseries["waterlevel_m"] = constant_head_val
                    # df_rain_tseries["waterlevel_m"] = mean_high_high_tide
                    df_tseries_combined = df_rain_tseries
                elif e_type == "compound":
                    df_tseries_combined = pd.concat(
                        [df_rain_tseries, df_surge_tseries], axis=1
                    ).dropna()
                # assign same rainfall to each mrms gridkey
                for gridkey in mrms_gridkeys:
                    rain_tseries = df_tseries_combined.loc[:, "mm_per_hr"].values
                    df_tseries_combined[gridkey] = rain_tseries
                df_tseries_combined["surge_m"] = 0
                df_tseries_combined["tide_m"] = 0
                df_tseries_combined["event_type"] = e_type
                df_tseries_combined["year"] = int(year)
                df_tseries_combined["event_id"] = event_id
                ds_tseries = (
                    df_tseries_combined.reset_index().set_index(idx_names).to_xarray()
                )
                lst_ds.append(ds_tseries)

# combining
ds_design_event_tseries = xr.merge(lst_ds)
# ds_design_event_tseries.attrs["design_rainfall_statistic_notes"] = "Each rain return period and duration has 3 time series, one associated with the point estimate for the depth statistic and 2 more representing the bounds of the 90 percent confidence interval of that statistic "
ds_design_event_tseries.attrs["return_period_notes"] = (
    "The year assigned to each design storm corresponds to the return period of the contributing hydrology"
)
ds_design_event_tseries.attrs["event_type_notes"] = (
    "Compound events assume the same return period for the input hydrology; surge events have zero rainfall; rain events have surge equal to the mean high high water"
)
ds_design_event_tseries.attrs["design_rainfall_unit_time_series"] = (
    "The rainfall unit time series follow the SCS Type II unit hyetographs. They were exported from the built-in design storm library in PCSWMM."
)
ds_design_event_tseries.attrs["design_rainfall_return_periods"] = (
    "return periods were derived using empirically from 1,000 years of stochastically generated combined rainfall and sea water level time series"
)

# %%

# inspecting events of each type
e_type = "compound"
yr = 10
e_id = 1
ds_design_event_tseries.sel(
    event_type=e_type, year=yr, event_id=e_id
).to_dataframe().dropna().loc[:, ["mm_per_hr", "waterlevel_m", "156"]].plot(
    subplots=True,
    title=f"{e_type} design storm | {yr}yr return period | event id {e_id}",
)


e_type = "compound"
yr = 10
e_id = 2
ds_design_event_tseries.sel(
    event_type=e_type, year=yr, event_id=e_id
).to_dataframe().dropna().loc[:, ["mm_per_hr", "waterlevel_m"]].plot(
    subplots=True,
    title=f"{e_type} design storm | {yr}yr return period | event id {e_id}",
)

e_type = "rain"
yr = 10
e_id = 2
ds_design_event_tseries.sel(
    event_type=e_type, year=yr, event_id=e_id
).to_dataframe().dropna().loc[:, ["mm_per_hr", "waterlevel_m"]].plot(
    subplots=True,
    title=f"{e_type} design storm | {yr}yr return period | event id {e_id}",
)


e_type = "surge"
yr = 10
e_id = 1
ds_design_event_tseries.sel(
    event_type=e_type, year=yr, event_id=e_id
).to_dataframe().dropna().loc[:, ["mm_per_hr", "waterlevel_m"]].plot(
    subplots=True,
    title=f"{e_type} design storm | {yr}yr return period | event id {e_id}",
)


#
d_encoding = {}
for da_name in ds_design_event_tseries.data_vars:
    d_encoding[da_name] = {"zlib": True}
ds_design_event_tseries.to_netcdf(f_design_storm_tseries_based_on_SSR)

print(f"wrote {f_design_storm_tseries_based_on_SSR}")
