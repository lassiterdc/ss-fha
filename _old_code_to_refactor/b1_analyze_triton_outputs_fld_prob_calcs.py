# =============================================================================
# REFACTORING STATUS (chunk 03A — 2026-03-01)
# =============================================================================
# STATUS: COMPLETE — replaced by src/ss_fha/analysis/flood_hazard.py
#
# Migrated to src/ss_fha/analysis/flood_hazard.py:
#   run_flood_hazard()             — orchestrates load, mask, compute, write
#   resolve_triton_zarr_path()     — resolves sim_type to zarr path via config
#   _validate_triton_schema()      — validates TRITON zarr structure
#
# Migrated to src/ss_fha/runners/flood_hazard_runner.py:
#   CLI entry point (argparse)     — replaces direct script execution
#
# Tests: tests/test_flood_hazard_workflow.py (9 integration tests)
# =============================================================================

# %%
import sys
import os
from pathlib import Path

path_cwd = Path(os.getcwd())
wd_is_fld_atr = False
while not wd_is_fld_atr:
    if path_cwd.name != "flood_attribution":
        path_cwd = path_cwd.parent
    else:
        break

sys.path.append(str(path_cwd))

from local.__inputs import 
from local.__utils import 
import zarr
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
import sys
import shutil
import time
import pandas as pd


prompt_for_overwrite = (
    True  # setting this to false will mean that files are silently overwritten
)

if not prompt_for_overwrite:
    print(
        "Warning: files will be overwritten because prompt_for_overwrite is set to False"
    )

# load input weather

ds_sim_tseries = xr.open_dataset(f_sim_tseries)
sim_idx_names = ds_sim_tseries.coords.to_index().names
sim_smry_idx = [name for name in sim_idx_names if name != "timestep"]

df_sim_smries = pd.read_csv(f_sim_smries, index_col=sim_smry_idx)
df_obs_smries = pd.read_csv(f_obs_smries, index_col=sim_smry_idx)

f_dsgn_tseries = f_design_storm_tseries_based_on_SSR

ds_dsgn_tseries = xr.open_dataset(f_dsgn_tseries)
ds_sim_tseries = xr.open_dataset(f_sim_tseries)
ds_obs_tseries = xr.open_dataset(f_obs_tseries)

ds_triton_sim = sort_dimensions(
    xr.open_dataset(f_triton_outputs, engine="zarr").chunk("auto"),
    lst_dims=["event_type", "event_id", "year"],
)
ds_triton_obs = sort_dimensions(
    xr.open_dataset(f_triton_outputs_obs, engine="zarr").chunk("auto"),
    lst_dims=["event_type", "event_id", "year"],
)
ds_triton_dsgn = xr.open_dataset(f_triton_outputs_dsgn, engine="zarr").chunk("auto")

# %% making sure all events are present in the TRITON outputs
val = "yes"
if prompt_for_overwrite:
    val = input(
        f"type 'yes' to assess whether all events are accounted for in the TRITON outputs (takes about 5 minutes)."
    )
run_chunk = False
if val.lower() == "yes":
    run_chunk = True


if run_chunk:
    # testing obs and design storms (15-20 seconds)
    ds_test = ds_triton_obs
    df_input_event_summaries = df_obs_smries
    df_missing_events_obs = identify_missing_events(ds_test, df_input_event_summaries)
    if len(df_missing_events_obs) > 0:
        print(
            f"There were {len(df_missing_events_obs)} missing events in the observed event results:\n{df_missing_events_obs}"
        )

    ds_test = ds_triton_dsgn
    df_input_event_summaries = (
        ds_dsgn_tseries["mm_per_hr"].isel(timestep=0).to_dataframe().dropna()
    )
    df_missing_events_dsgn = identify_missing_events(ds_test, df_input_event_summaries)
    if len(df_missing_events_dsgn) > 0:
        print(
            f"There were {len(df_missing_events_dsgn)} missing events in the design storm event results:\n{df_missing_events_dsgn}"
        )
    # testing on ensemble (takes a few minutes)
    ds_test = ds_triton_sim
    df_input_event_summaries = df_sim_smries
    df_missing_events_sim = identify_missing_events(ds_test, df_input_event_summaries)
    if len(df_missing_events_sim) > 0:
        print(
            f"There were {len(df_missing_events_sim)} missing events in the ensemble results:\n{df_missing_events_sim}"
        )

    # check to see that all individual events are accounted for (older version)
    dict_isel_1 = dict(x=0, y=0)
    ds_triton = ds_triton_sim
    s_events = df_sim_smries["precip_depth_mm"]

    print("Stochastically generated events:")
    all_missing_sim = make_sure_all_event_outputs_are_present(
        ds_triton_sim, df_sim_smries["precip_depth_mm"], sim_smry_idx
    )

    print("\nObserved events:")
    all_missing_obs = make_sure_all_event_outputs_are_present(
        ds_triton_obs, df_obs_smries["precip_depth_mm"], sim_smry_idx
    )

    print("\nDesign storm events:")
    s_design_storms = (
        ds_dsgn_tseries.isel(timestep=0)["mm_per_hr"]
        .to_dataframe()
        .dropna()["mm_per_hr"]
    )
    all_missing_dsgn = make_sure_all_event_outputs_are_present(
        ds_triton_dsgn, s_design_storms, sim_smry_idx
    )

# %% plotting some random observed events
df_sample_event = (
    ds_obs_tseries.sel(year=2, event_type="compound", event_id=1)
    .to_dataframe()
    .dropna()
)


fig, ax = plt.subplots(figsize=(6, 3), dpi=300)

df_sample_event["surge_m"].plot(ax=ax)
ax.set_ylabel("surge (m)")
ax.set_xlabel("")
ax.set_ylim(-0.5, 3)

xlim_extend = np.timedelta64(4, "h")

ax.set_xlim(
    df_sample_event.index.min() - xlim_extend, df_sample_event.index.max() + xlim_extend
)


# df_sample_event = ds_obs_tseries.sel(year = 2, event_type = "compound", event_id = 1).to_dataframe().dropna()
event_type = "rain"
year = 8
event_id = 4

s_event_details = df_obs_smries.loc[pd.IndexSlice[event_type, year, event_id]]

df_sample_event = (
    ds_obs_tseries.sel(year=year, event_type=event_type, event_id=event_id)
    .to_dataframe()
    .dropna()
)


real_idx = (
    pd.to_datetime(s_event_details["event_start"])
    - df_sample_event.index.min()
    + df_sample_event.index
)
df_sample_event.index = real_idx

fig, ax = plt.subplots(figsize=(6, 3), dpi=300)

df_sample_event["mm_per_hr"].plot(ax=ax, c="grey", alpha=0.8, lw=0.5, label="original")
ax.set_ylabel("rainfall (mm per hr)")
ax.set_xlabel("")
ax.legend()
# transform dataset
s_rain_rescaled = df_sample_event["mm_per_hr"] * 0.6
og_idx = s_rain_rescaled.index
og_length = og_idx.max() - og_idx.min()
frac_of_original_length = 0.7
new_length = frac_of_original_length * og_length

new_idx = pd.date_range(
    start=og_idx.min(), end=og_idx.min() + new_length, periods=len(og_idx)
)
s_rain_rescaled.index = new_idx


s_rain_rescaled = s_rain_rescaled.reindex(og_idx, method="nearest")


s_rain_rescaled.plot(ax=ax, c="k", alpha=0.8, lw=0.8, label="rescaled")
ax.set_ylabel("rainfall (mm per hr)")
ax.set_xlabel("")
ax.legend()


# %% testing code for computing cdfs and return periods
val = "yes"
if prompt_for_overwrite:
    val = input(
        f"type 'yes' to re-write the subsetted model output for testing function to compute return periods"
    )
rewrite_file = False
if val.lower() == "yes":
    rewrite_file = True

da_wlevel_for_testing = ds_triton_sim.max_wlevel_m.sel(
    data_source="sim", model="tritonswmm", simtype="surgeonly"
)

df_wlevel = (
    ds_triton_dsgn.sel(
        event_id=3,
        event_type="compound",
        year=2,
        simtype="surgeonly",
        model="tritonswmm",
    )["max_wlevel_m"]
    .squeeze()
    .to_dataframe()
    .reset_index()
)

idx_test = df_wlevel[
    df_wlevel["max_wlevel_m"]
    == df_wlevel["max_wlevel_m"].quantile(0.9995, interpolation="nearest")
].index
df_subset = df_wlevel.iloc[(idx_test[0] - 5) : (idx_test[0] + 5), :]

x_points = xr.DataArray(df_subset["x"].values, dims="x")
y_points = xr.DataArray(df_subset["y"].values, dims="y")


f_zar_out = Path(dir_temp_zarrs).joinpath("test_compute_emp_cdf_and_return_pds.zarr")
if (f_zar_out.exists() == False) or rewrite_file:
    da_wlevel = da_wlevel_for_testing.sel(
        x=x_points, y=y_points, method="nearest"
    ).load()
    write_zarr(da_wlevel, f_zar_out)
else:
    print(f"loading testing da_wlevel from {f_zar_out} created in 9/28/2025")
    print("####")
    da_wlevel = xr.open_dataset(f_zar_out, engine="zarr")["max_wlevel_m"]

n_years = n_years_synthesized
qaqc_plots = True
export_intermediate_outputs = True
f_out_zarr = None
f_event_number_mapping = PATTERN_EVENT_NUMBER_MAPPING.format("ensemble", "test")
testing = False
ds_sim_flood_probs_test = compute_emp_cdf_and_return_pds(
    da_wlevel,
    alpha,
    beta,
    qaqc_plots=qaqc_plots,
    export_intermediate_outputs=export_intermediate_outputs,
    dir_temp_zarrs=dir_temp_zarrs,
    f_out_zarr=f_out_zarr,
    n_years=n_years,
    f_event_number_mapping=f_event_number_mapping,
)
print("####")
df = ds_sim_flood_probs_test.to_dataframe()

rtrn_pds = df.sort_values(["emprical_cdf"])["return_pd_yrs"].unique()

assert len(rtrn_pds) == 3798
assert np.isclose(rtrn_pds.max(), 1000.263296)
print("tests passed!")
print("###")
# %% params

export_intermediate_outputs = True
qaqc_plots = True
n_years = n_years_synthesized
testing = False
print_benchmarking = True
# %% semicontinuous ensemble tritonswmm compound
val = "yes"
if prompt_for_overwrite:
    val = input(
        f"type 'yes' to compute flood probabilities for\
            ensemble combined events simulated in triton-swmm"
    )
run_chunk = False
if val.lower() == "yes":
    run_chunk = True

if run_chunk:
    da_wlevel = ds_triton_sim.max_wlevel_m.sel(
        data_source="sim", model="tritonswmm", simtype="compound"
    )
    f_out_zarr = F_SIM_FLOOD_PROBS
    f_event_number_mapping = PATTERN_EVENT_NUMBER_MAPPING.format("ensemble", "compound")
    ds_sim_flood_probs = compute_emp_cdf_and_return_pds(
        da_wlevel,
        alpha,
        beta,
        qaqc_plots=qaqc_plots,
        export_intermediate_outputs=export_intermediate_outputs,
        dir_temp_zarrs=dir_temp_zarrs,
        f_out_zarr=f_out_zarr,
        n_years=n_years,
        f_event_number_mapping=f_event_number_mapping,
    )

# %% semicontinuous emsenble tritonswmm surge-only
val = "yes"
if prompt_for_overwrite:
    val = input(
        f"type 'yes' to compute flood probabilities\
        for ensemble surge-only events simulated in triton-swmm"
    )
run_chunk = False
if val.lower() == "yes":
    run_chunk = True

if run_chunk:
    da_wlevel = ds_triton_sim.max_wlevel_m.sel(
        data_source="sim", model="tritonswmm", simtype="surgeonly"
    )
    f_event_number_mapping = PATTERN_EVENT_NUMBER_MAPPING.format(
        "ensemble", "surgeonly"
    )
    f_out_zarr = F_SIM_FLOOD_PROBS_SURGEONLY
    ds_sim_flood_probs = compute_emp_cdf_and_return_pds(
        da_wlevel,
        alpha,
        beta,
        qaqc_plots=qaqc_plots,
        export_intermediate_outputs=export_intermediate_outputs,
        dir_temp_zarrs=dir_temp_zarrs,
        f_out_zarr=f_out_zarr,
        n_years=n_years,
        f_event_number_mapping=f_event_number_mapping,
    )
# %%% semicontinuous emsenble tritonswmm rain-only
val = "yes"
if prompt_for_overwrite:
    val = input(
        f"type 'yes' to compute flood probabilities\
        for ensemble rain-only events simulated in triton-swmm"
    )
run_chunk = False
if val.lower() == "yes":
    run_chunk = True

if run_chunk:
    da_wlevel = ds_triton_sim.max_wlevel_m.sel(
        data_source="sim", model="tritonswmm", simtype="rainonly"
    )
    f_event_number_mapping = PATTERN_EVENT_NUMBER_MAPPING.format("ensemble", "rainonly")
    f_out_zarr = F_SIM_FLOOD_PROBS_RAINONLY
    ds_sim_flood_probs = compute_emp_cdf_and_return_pds(
        da_wlevel,
        alpha,
        beta,
        qaqc_plots=qaqc_plots,
        export_intermediate_outputs=export_intermediate_outputs,
        dir_temp_zarrs=dir_temp_zarrs,
        f_out_zarr=f_out_zarr,
        n_years=n_years,
        f_event_number_mapping=f_event_number_mapping,
    )
# %% semicontinuous ensemble triton compound
val = "yes"
if prompt_for_overwrite:
    val = input(
        f"type 'yes' to compute flood probabilities\
        for ensemble rain-only events simulated in triton"
    )
run_chunk = False
if val.lower() == "yes":
    run_chunk = True

if run_chunk:
    da_wlevel = ds_triton_sim.max_wlevel_m.sel(
        data_source="sim", model="triton", simtype="compound"
    )
    f_event_number_mapping = PATTERN_EVENT_NUMBER_MAPPING.format("ensemble", "2D")
    f_out_zarr = F_SIM_FLOOD_PROBS_TRITON
    ds_sim_flood_probs = compute_emp_cdf_and_return_pds(
        da_wlevel,
        alpha,
        beta,
        qaqc_plots=qaqc_plots,
        export_intermediate_outputs=export_intermediate_outputs,
        dir_temp_zarrs=dir_temp_zarrs,
        f_out_zarr=f_out_zarr,
        n_years=n_years,
        f_event_number_mapping=f_event_number_mapping,
    )
# %% triton - observed
val = "yes"
if prompt_for_overwrite:
    val = input(
        f"type 'yes' to compute flood probabilities for observed combined events simulated in triton-swmm"
    )
run_chunk = False
if val.lower() == "yes":
    run_chunk = True

if run_chunk:
    da_wlevel = ds_triton_obs.max_wlevel_m.sel(
        data_source="obs", model="tritonswmm", simtype="compound"
    )
    f_out_zarr = f_obs_flood_probs
    f_event_number_mapping = F_OBS_FLOOD_PROBS_EVENT_NUMBER_MAPPING
    n_years = len(
        np.arange(
            da_wlevel.year.to_series().min(), da_wlevel.year.to_series().max() + 1
        )
    )
    ds_obs_flood_probs = compute_emp_cdf_and_return_pds(
        da_wlevel,
        alpha,
        beta,
        qaqc_plots=qaqc_plots,
        export_intermediate_outputs=export_intermediate_outputs,
        dir_temp_zarrs=dir_temp_zarrs,
        f_out_zarr=f_out_zarr,
        n_years=n_years,
        f_event_number_mapping=f_event_number_mapping,
    )

# %% combine into single dataframe
val = "yes"
if prompt_for_overwrite:
    val = input(f"type 'yes' to combine outputs into netcdf")

run_chunk = False
if val.lower() == "yes":
    run_chunk = True

if run_chunk:
    ds_sim_flood_probs = xr.open_dataset(F_SIM_FLOOD_PROBS, engine="zarr").chunk("auto")
    ds_sim_flood_probs = ds_sim_flood_probs.assign_coords(
        sim_form="tritonswmm.multidriver"
    )
    ds_sim_flood_probs = ds_sim_flood_probs.expand_dims("sim_form")

    ds_sim_flood_probs_surgeonly = xr.open_dataset(
        F_SIM_FLOOD_PROBS_SURGEONLY, engine="zarr"
    ).chunk("auto")
    ds_sim_flood_probs_surgeonly = ds_sim_flood_probs_surgeonly.assign_coords(
        sim_form="tritonswmm.seawater_lvl_only"
    )
    ds_sim_flood_probs_surgeonly = ds_sim_flood_probs_surgeonly.expand_dims("sim_form")

    ds_sim_flood_probs_rainonly = xr.open_dataset(
        F_SIM_FLOOD_PROBS_RAINONLY, engine="zarr"
    ).chunk("auto")
    ds_sim_flood_probs_rainonly = ds_sim_flood_probs_rainonly.assign_coords(
        sim_form="tritonswmm.rain_only"
    )
    ds_sim_flood_probs_rainonly = ds_sim_flood_probs_rainonly.expand_dims("sim_form")

    ds_sim_flood_probs_triton = xr.open_dataset(
        F_SIM_FLOOD_PROBS_TRITON, engine="zarr"
    ).chunk("auto")
    ds_sim_flood_probs_triton = ds_sim_flood_probs_triton.assign_coords(
        sim_form="triton.multidriver"
    )
    ds_sim_flood_probs_triton = ds_sim_flood_probs_triton.expand_dims("sim_form")

    # combine into single dataframe indexed by model setup
    lst_ds = [
        ds_sim_flood_probs,
        ds_sim_flood_probs_surgeonly,
        ds_sim_flood_probs_rainonly,
        ds_sim_flood_probs_triton,
    ]
    ds_sim_flood_probs_combined = xr.concat(lst_ds, dim="sim_form")

    chunk_sizes = dict(x=10, y=10, event_number=-1, sim_form=1)
    delete_zarr(F_SIM_FLOOD_PROBS_COMPARE, attempt_time_limit_s=10)
    ds_sim_flood_probs_combined.chunk(chunk_sizes).to_zarr(
        F_SIM_FLOOD_PROBS_COMPARE,
        mode="w",
        encoding=return_dic_zarr_encodingds(ds_sim_flood_probs_combined, clevel=5),
        consolidated=True,
    )
