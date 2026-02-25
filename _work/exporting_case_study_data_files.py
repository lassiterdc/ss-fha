# %%
# TODO - now that i've figured out that dropbox was part of the issue, try again using the toolkit's built in zarr file handling

from pathlib import Path
import xarray as xr
import TRITON_SWMM_toolkit.utils as tsut

from numcodecs import Blosc

reindexed_ensemble = Path(
    "/mnt/d/Dropbox/_GradSchool/_norfolk/_sharing/2025-06-30_research material for Aashutosh/simulation_results/reindexed_with_flood_probs/ensemble_results_reindexed.zarr"
)

reindexed_ensemble_obs = Path(
    "/mnt/d/Dropbox/_GradSchool/_norfolk/_sharing/2025-06-30_research material for Aashutosh/simulation_results/reindexed_with_flood_probs/flood_probs_obs.zarr"
)


hydroshare_datadir = Path("/mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data")

model_results = hydroshare_datadir / "model_results"
weather = hydroshare_datadir / "events"


def return_dic_zarr_encodings_v2(ds: xr.Dataset, clevel: int = 5) -> dict:
    compressor = Blosc(cname="zstd", clevel=clevel, shuffle=Blosc.SHUFFLE)
    encoding = {}

    for var in ds.data_vars:
        if ds[var].dtype.kind in {"i", "u", "f"}:
            encoding[var] = {"compressor": compressor}

    for coord in ds.coords:
        if ds[coord].dtype.kind == "U":
            max_len = int(ds[coord].str.len().max().item())
            encoding[coord] = {"dtype": f"<U{max_len}"}

    return encoding


# %% observed
da = xr.open_dataset(
    reindexed_ensemble_obs, engine="zarr", chunks="auto", consolidated=False
)["max_wlevel_m"]

# triton only
ds = (da.rename(dict(event_number="event_iloc"))).to_dataset()
fname_out = model_results / "obs_tritonswmm_combined.zarr"
# tsut.write_zarr(ds, fname_out, compression_level=5)
encoding = return_dic_zarr_encodings_v2(ds)
ds.to_zarr(fname_out, mode="w", encoding=encoding, consolidated=False, zarr_format=2)


# %% ss
da = xr.open_dataset(
    reindexed_ensemble, engine="zarr", chunks="auto", consolidated=False
)["max_wlevel_m"]

# triton only
ds = (
    da.sel(dict(ensemble_type=["2D_compound"]))
    .squeeze(drop=True)
    .rename(dict(event_number="event_iloc"))
).to_dataset()
fname_out = model_results / "ss_triton_only_combined.zarr"
# tsut.write_zarr(ds, fname_out, compression_level=5)

encoding = return_dic_zarr_encodings_v2(ds)
ds.to_zarr(fname_out, mode="w", encoding=encoding, consolidated=False, zarr_format=2)

# tritonswmm_rain_only
ds = (
    da.sel(dict(ensemble_type=["rain_only"]))
    .squeeze(drop=True)
    .rename(dict(event_number="event_iloc"))
).to_dataset()
fname_out = model_results / "ss_tritonswmm_rainonly.zarr"
# tsut.write_zarr(ds, fname_out, compression_level=5)
encoding = return_dic_zarr_encodings_v2(ds)
ds.to_zarr(fname_out, mode="w", encoding=encoding, consolidated=False, zarr_format=2)

# tritonswmm_surge_only
ds = (
    da.sel(dict(ensemble_type=["surge_only"]))
    .squeeze(drop=True)
    .rename(dict(event_number="event_iloc"))
).to_dataset()
fname_out = model_results / "ss_tritonswmm_surgeonly.zarr"
# tsut.write_zarr(ds, fname_out, compression_level=5)
encoding = return_dic_zarr_encodings_v2(ds)
ds.to_zarr(fname_out, mode="w", encoding=encoding, consolidated=False, zarr_format=2)

# tritonswmm_combined
ds = (
    da.sel(dict(ensemble_type=["compound"]))
    .squeeze(drop=True)
    .rename(dict(event_number="event_iloc"))
).to_dataset()
fname_out = model_results / "ss_tritonswmm_combined.zarr"
# tsut.write_zarr(ds, fname_out, compression_level=5)
encoding = return_dic_zarr_encodings_v2(ds)
ds.to_zarr(fname_out, mode="w", encoding=encoding, consolidated=False, zarr_format=2)

# %% designs storms
f_dsgn_tseries = (
    Path("/mnt/d/Dropbox/_GradSchool/_norfolk/stormy/flood_attribution/weather")
    / "design_storm_timeseries_SSR.nc"
)

design_storms = Path(
    "/mnt/d/Dropbox/_GradSchool/_norfolk/stormy/flood_attribution/model_scenarios/triton_tritonswmm_allsims_dsgn_triton.zarr"
)

ds_dsgn_tseries = xr.open_dataset(f_dsgn_tseries)

ds_triton_dsgn = xr.open_dataset(
    design_storms, engine="zarr", chunks="auto", consolidated=False
)


# da = ds_triton_dsgn["max_wlevel_m"]
# da = (
#     da.rename(dict(year="return_pd_yrs"))
#     .sel(model="tritonswmm", simtype="compound")
#     .squeeze(drop=True)
# )

# da.isel(x=0, y=0).to_dataframe()
# %% figure out rainfall duration mapping
# process design storms
import pandas as pd
import numpy as np

s_rain = ds_dsgn_tseries["mm_per_hr"].to_dataframe().dropna()["mm_per_hr"]
s_rain = s_rain[s_rain > 0]

tstep_min = s_rain.reset_index()["timestep"].diff().mode().iloc[0] / np.timedelta64(
    1, "m"
)

event_dur_hrs = (
    s_rain.groupby(level=["event_type", "year", "event_id"]).count() * tstep_min / 60
)

# event_dur_hrs.loc[pd.IndexSlice[:, :, 3],]
event_dur_hrs


# %% assign this duration to the dataset
ds_dsgn_tseries = xr.open_dataset(f_dsgn_tseries)
mapping = {1: 6, 2: 12, 3: 24}
ds_dsgn_tseries = ds_dsgn_tseries.rename(dict(event_id="rain_duration_h"))

ds_dsgn_tseries = ds_dsgn_tseries.assign_coords(
    rain_duration_h=[mapping[v] for v in ds_dsgn_tseries.rain_duration_h.values]
)

ds_triton_dsgn = xr.open_dataset(
    design_storms, engine="zarr", chunks="auto", consolidated=False
)

ds_triton_dsgn = ds_triton_dsgn.rename(
    dict(event_id="rain_duration_h", year="return_pd_yrs")
)

ds_triton_dsgn = ds_triton_dsgn.assign_coords(
    rain_duration_h=[mapping[v] for v in ds_triton_dsgn.rain_duration_h.values]
)

# %% identify event id for surge events
ds_dsgn_tseries.sel(event_type="surge")["waterlevel_m"].to_dataframe().dropna()[
    "waterlevel_m"
].reset_index()["rain_duration_h"].unique()

# surge only events are 6 hours

# %% subset model results and weather
# combined
rain_duration_h = [24]
event_type = ["compound"]
simtype = ["compound"]
model = ["tritonswmm"]
scen_type = ["combined"]
ds = (
    ds_triton_dsgn.sel(
        rain_duration_h=rain_duration_h,
        event_type=event_type,
        simtype=simtype,
        model=model,
    )
    .squeeze(drop=True)["max_wlevel_m"]
    .to_dataset()
)
f_out = model_results / f"design_storm_tritonswmm_{scen_type[0]}.zarr"
encoding = return_dic_zarr_encodings_v2(ds)
ds.to_zarr(f_out, mode="w", encoding=encoding, consolidated=False, zarr_format=2)

ds = ds_dsgn_tseries.sel(rain_duration_h=rain_duration_h, event_type=event_type)
f_out = weather / f"design_storm_{scen_type[0]}.nc"
ds.to_netcdf(f_out)

#  rain only
rain_duration_h = [24]
event_type = ["rain"]
simtype = ["compound"]
model = ["tritonswmm"]
scen_type = ["rainonly"]
ds = (
    ds_triton_dsgn.sel(
        rain_duration_h=rain_duration_h,
        event_type=event_type,
        simtype=simtype,
        model=model,
    )
    .squeeze(drop=True)["max_wlevel_m"]
    .to_dataset()
)
f_out = model_results / f"design_storm_tritonswmm_{scen_type[0]}.zarr"
encoding = return_dic_zarr_encodings_v2(ds)
ds.to_zarr(f_out, mode="w", encoding=encoding, consolidated=False, zarr_format=2)

ds = ds_dsgn_tseries.sel(rain_duration_h=rain_duration_h, event_type=event_type)
f_out = weather / f"design_storm_{scen_type[0]}.nc"
ds.to_netcdf(f_out)


# ds_dsgn_tseries.sel(
#     rain_duration_h=rain_duration_h, event_type=event_type
# ).to_dataframe()[["mm_per_hr", "waterlevel_m"]].dropna()

# surge only
rain_duration_h = [6]
event_type = ["surge"]
simtype = ["compound"]
model = ["tritonswmm"]
scen_type = ["surgeonly"]
ds = (
    ds_triton_dsgn.sel(
        rain_duration_h=rain_duration_h,
        event_type=event_type,
        simtype=simtype,
        model=model,
    )
    .squeeze(drop=True)["max_wlevel_m"]
    .to_dataset()
)
f_out = model_results / f"design_storm_tritonswmm_{scen_type[0]}.zarr"
encoding = return_dic_zarr_encodings_v2(ds)
ds.to_zarr(f_out, mode="w", encoding=encoding, consolidated=False, zarr_format=2)

ds = ds_dsgn_tseries.sel(rain_duration_h=rain_duration_h, event_type=event_type)
f_out = weather / f"design_storm_{scen_type[0]}.nc"
ds.to_netcdf(f_out)


# ds_dsgn_tseries.sel(
#     rain_duration_h=rain_duration_h, event_type=event_type
# ).to_dataframe()[["mm_per_hr", "waterlevel_m"]].dropna()
