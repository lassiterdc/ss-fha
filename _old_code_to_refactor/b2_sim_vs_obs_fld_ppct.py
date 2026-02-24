#%%
from __inputs import *
from __utils import *
import zarr
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
import sys
import shutil
from scipy.stats.mstats import plotting_positions
import time
from tqdm import tqdm
import warnings

ds_sim_flood_probs = xr.open_dataset(F_SIM_FLOOD_PROBS engine = "zarr", chunks = "auto")
df_sim_flood_probs_event_num_mapping = pd.read_csv(f_sim_flood_probs_event_number_mapping)

ds_triton_sim = xr.open_dataset(f_triton_outputs, engine = "zarr").chunk("auto").sel(data_source = "sim", model = "tritonswmm", simtype = "compound")
ds_triton_obs = xr.open_dataset(f_triton_outputs_obs, engine = "zarr").chunk("auto").sel(data_source = "obs", model = "tritonswmm", simtype = "compound")
n_obs_years = len(np.arange(ds_triton_obs.year.to_series().min(), ds_triton_obs.year.to_series().max()+1))
#%% create bootstrap samples of the stochastically generated event flooding equal in nyears to the observed period
# ar_sim_years = pd.Series(ds_triton_sim.year.values).unique()
ar_sim_years = np.arange(n_years_synthesized)
from glob import glob
pickup_where_left_off = True

lst_files_processed = glob(f"{dif_ffa_ppct_bs_sim_cdfs}emp_cdf_*.zarr")
bs_ids_done = []
for f in lst_files_processed:
    bs_ids_done.append(int(f.split("emp_cdf_")[-1].split(".")[0]))

if pickup_where_left_off:
    bs_id_start = max(bs_ids_done) - 1
else:
    if len(lst_files_processed) > 0:
        print("Deleting previously processed outputs")
        for f in lst_files_processed:
            delete_zarr(f)
    bs_id_start = 0

for bs_id in tqdm(np.arange(bs_id_start, n_bs_samples)):
    f_out_zarr = f"{dif_ffa_ppct_bs_sim_cdfs}emp_cdf_{bs_id}.zarr"
    resampled_years = np.random.choice(ar_sim_years, size=n_obs_years, replace=True)
    da_wlevel_list = []
    next_first_event_idx = 0 
    for year in resampled_years:
        if year not in ds_triton_sim.year.to_series().unique():
            # print(f"Skipping year {year} because there were no events in the stochastically generated dataset")
            continue
        lst_event_nums = df_sim_flood_probs_event_num_mapping[df_sim_flood_probs_event_num_mapping["year"] == year].event_number.to_list()
        da_wlevel_for_year = ds_sim_flood_probs.sel(event_number = lst_event_nums)["max_wlevel_m"]
        da_wlevel_for_year["event_number"] = np.arange(next_first_event_idx, next_first_event_idx+len(da_wlevel_for_year["event_number"].to_series()))
        next_first_event_idx = da_wlevel_for_year["event_number"].to_series().max() + 1
        da_wlevel_list.append(da_wlevel_for_year)
    da_wlevel_resampled = xr.combine_by_coords(da_wlevel_list)["max_wlevel_m"]
    da_wlevel = da_wlevel_resampled.load()
    qaqc_plots = False
    export_intermediate_outputs = False
    testing = False
    print_benchmarking = False
    n_years = len(resampled_years)
    compute_emp_cdf_and_return_pds(da_wlevel=da_wlevel, alpha=alpha, beta=beta, qaqc_plots = qaqc_plots,
                                    export_intermediate_outputs = export_intermediate_outputs,
                                      dir_temp_zarrs = dir_temp_zarrs, f_out_zarr = f_out_zarr,
                                    testing = testing, print_benchmarking = print_benchmarking, n_years = n_years)