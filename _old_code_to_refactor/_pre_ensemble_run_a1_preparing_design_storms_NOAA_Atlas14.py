# %% import libraries
from __inputs import *
import pandas as pd
import numpy as np
import sys
import shutil
import xarray as xr

f_sim_tseries = "D:/Dropbox/_GradSchool/_norfolk/stormy/flood_attribution/weather/combined_simulation_time_series.nc"
ds_sim_tseries = xr.open_dataset(f_sim_tseries, chunks=dict(timestep="auto"))

surge_event_duration = 8

Path(dir_output_design_storm_tseries).mkdir(parents=True, exist_ok=True)


d_fname_rian_pdfs = dict(
    point_estimate=f_rain_idf_pds,
    upper_bound=f_rain_idf_pds_upperbound,
    lower_bound=f_rain_idf_pds_lowerbound,
)

# load and process rain idf table
lst_df = []
for key in d_fname_rian_pdfs.keys():
    f = d_fname_rian_pdfs[key]
    df_idf = pd.read_csv(f, skiprows=13)
    df_idf = df_idf.rename(
        columns={"by duration for ARI (years):": "duration_h"}
    ).dropna()
    new_dur_col = []
    for val in df_idf["duration_h"]:
        dur = val.split(":")[0]
        if "min" in dur:
            dur_val_hr = int(dur.split("-min")[0]) / 60
        elif "-hr" in dur:
            dur_val_hr = int(dur.split("-hr")[0])
        elif "day" in dur:
            dur_val_hr = int(dur.split("-day")[0]) * 24
        else:
            sys.exit("duration not recognized")
        new_dur_col.append(dur_val_hr)
    df_idf["duration_h"] = new_dur_col
    df_idf["source"] = key
    df_idf = df_idf.set_index(["source", "duration_h"])
    df_idf.columns = df_idf.columns.astype(int)
    lst_df.append(df_idf)

df_idf = pd.concat(lst_df)


# convert from inches to mm
df_idf = df_idf * mm_per_inch


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

# load wlevel return periods
df_wlevel_return_pds = pd.read_csv(f_wlevel_return_pds, skiprows=6)


# create series with return period water levels in navd88 ft
row_wlevel_return_pds_og = df_wlevel_return_pds[
    (df_wlevel_return_pds["year"] == "2024") & (df_wlevel_return_pds["Type"] == "high")
].iloc[0]

# row_wlevel_return_pds = pd.Series(data = np.nan, index = return_periods + ["MHW"])
row_wlevel_return_pds = pd.Series(data=np.nan, index=RETURN_PERIODS)
row_wlevel_return_pds.name = "wlevel_return_periods_navd88_m"

# calculate water levels in navd88 feet for each return period
row_wlevel_return_pds.loc[1] = (
    row_wlevel_return_pds_og.loc["Level_MetersMSL_99%_Exc_prob"]
    - row_wlevel_return_pds_og.loc["NAVD88"]
)
row_wlevel_return_pds.loc[2] = (
    row_wlevel_return_pds_og.loc["Level_MetersMSL_50%_Ex_prob"]
    - row_wlevel_return_pds_og.loc["NAVD88"]
)
row_wlevel_return_pds.loc[10] = (
    row_wlevel_return_pds_og.loc["Level_MetersMSL_10%_Ex_prob"]
    - row_wlevel_return_pds_og.loc["NAVD88"]
)
row_wlevel_return_pds.loc[100] = (
    row_wlevel_return_pds_og.loc["Level_MetersMSL_1%_Ex_prob"]
    - row_wlevel_return_pds_og.loc["NAVD88"]
)
mean_high_high_water_level = (
    row_wlevel_return_pds_og.loc["MHW"] - row_wlevel_return_pds_og.loc["NAVD88"]
)

# create design rainfall events

df_idf_selected_events = df_idf.loc[
    pd.IndexSlice[:, LST_DESIGN_STORM_DURATIONS_TO_SIMULATE], RETURN_PERIODS
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
for idx, val in row_wlevel_return_pds.items():
    s_wlevel_tseries = pd.Series(data=val, index=t_idx).astype(float)
    s_wlevel_tseries.name = "waterlevel_m"
    df_wlevel_tseries = s_wlevel_tseries.to_frame()
    try:
        desc = int(idx)
    except:
        desc = 0
    df_wlevel_tseries["year"] = desc
    df_wlevel_tseries.index.name = "timestep"
    lst_wlevel_tseries.append(
        df_wlevel_tseries.reset_index().set_index(["year", "timestep"])
    )

ds_design_wlevel = pd.concat(lst_wlevel_tseries).to_xarray()


#
mrms_gridkeys = []
for var in ds_sim_tseries.data_vars:
    if var in ["waterlevel_m", "surge_m", "tide_m"]:
        continue
    mrms_gridkeys.append(var)

idx_names = ds_sim_tseries.coords.to_index().names

lst_ds = []

# create time series
for e_type in ds_sim_tseries.event_type.values:
    for year in RETURN_PERIODS:
        event_id = 0
        for dsgn_strm_dur in ds_design_rainfall.design_storm_rain_duration_h.values:
            for source in ds_design_rainfall.source.to_series():
                event_id += 1
                if (e_type == "compound") or (e_type == "rain"):
                    df_rain_tseries = (
                        ds_design_rainfall.sel(
                            design_storm_rain_duration_h=dsgn_strm_dur, year=year
                        )
                        .to_dataframe()
                        .dropna()
                    )
                    df_rain_tseries = df_rain_tseries.drop(
                        columns=["design_storm_rain_duration_h", "year"]
                    )
                if (e_type == "compound") or (e_type == "surge"):
                    df_surge_tseries = (
                        ds_design_wlevel.sel(year=year).to_dataframe().dropna()
                    )
                    df_surge_tseries = df_surge_tseries.drop(columns=["year"])
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
                    df_rain_tseries["waterlevel_m"] = mean_high_high_water_level
                    df_tseries_combined = df_rain_tseries.loc[pd.IndexSlice[source, :]]
                elif e_type == "compound":
                    df_tseries_combined = pd.concat(
                        [
                            df_rain_tseries.loc[pd.IndexSlice[source, :]],
                            df_surge_tseries,
                        ],
                        axis=1,
                    ).dropna()
                # assign same rainfall to each mrms gridkey
                for gridkey in mrms_gridkeys:
                    rain_tseries = df_tseries_combined.loc[:, "mm_per_hr"].values
                    df_tseries_combined[gridkey] = rain_tseries
                df_tseries_combined["surge_m"] = 0
                df_tseries_combined["tide_m"] = 0
                df_tseries_combined["event_type"] = e_type
                df_tseries_combined.loc[:, "year"] = int(year)
                df_tseries_combined["event_id"] = event_id
                ds_tseries = (
                    df_tseries_combined.reset_index().set_index(idx_names).to_xarray()
                )
                lst_ds.append(ds_tseries)

# combining
ds_design_event_tseries = xr.merge(lst_ds)
ds_design_event_tseries.attrs["design_rainfall_statistic_notes"] = (
    "Each rain return period and duration has 3 time series, one associated with the point estimate for the depth statistic and 2 more representing the bounds of the 90 percent confidence interval of that statistic "
)
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
    "Rain depths were derived from NOAA atlas 14: https://hdsc.nws.noaa.gov/pfds/pfds_map_cont.html?bkmrk=va"
)
ds_design_event_tseries.attrs["waterlevel_return_periods"] = (
    "Water level return periods were extracted from the Sewells Point tide gage data through NOAA: https://tidesandcurrents.noaa.gov/est/stickdiagram.shtml?stnid=8638610"
)


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
ds_design_event_tseries.to_netcdf(f_design_storm_tseries_NOAA)
