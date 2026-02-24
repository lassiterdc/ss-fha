# %%
from local.__inputs import (
    F_TRITON_OUTPUTS,
    F_SIM_FLOOD_PROBS,
    F_SIM_FLOOD_PROBS_EVENT_NUMBER_MAPPING,
    F_SIM_FLOOD_PROBS_TRITON,
    N_YEARS_SYNTHESIZED,
    DIR_SIM_FLOOD_PROBS_BOOTSTRAPPING,
    DIR_SIM_FLOOD_PROBS_BOOTSTRAPPING_TRITONONLY,
    ALPHA,
    BETA,
)
from local.__utils import (
    sort_dimensions,
    prepare_for_bootstrapping,
    bootstrapping_return_period_estimates,
)
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
import os
import gc
from glob import glob
import pandas as pd

# user inputs
pickup_where_left_off = True
currently_running = False  # set this to True if you are resuming from an interrupted script (i.e., the last saved zarr is probably incomplete)
bootstrap_tritonswmm_results = True
bootstrap_triton_results = False
print_benchmarks = False

print(f"pickup_where_left_off = {pickup_where_left_off}")
if pickup_where_left_off == False:
    print(
        f"This means that existing bootstrap samples will be deleted and overwritten.\n"
    )
print(f"bootstrap_triton_results = {bootstrap_triton_results}")

print(f"bootstrap_tritonswmm_results = {bootstrap_tritonswmm_results}")

n_bs_samples = 500

# loading data
ds_triton_sim = sort_dimensions(
    xr.open_dataset(F_TRITON_OUTPUTS, engine="zarr").chunk("auto"),
    lst_dims=["event_type", "event_id", "year"],
)

ds_sim_flood_probs = xr.open_dataset(F_SIM_FLOOD_PROBS, engine="zarr", chunks="auto")


df_sim_flood_probs_event_num_mapping = pd.read_csv(
    F_SIM_FLOOD_PROBS_EVENT_NUMBER_MAPPING
)


ds_sim_flood_probs_tritononly = xr.open_dataset(
    F_SIM_FLOOD_PROBS_TRITON, engine="zarr", chunks="auto"
)

ar_sim_years = np.arange(
    N_YEARS_SYNTHESIZED
)  # need to include all years, including ones that have no events
n_ensemble_years = N_YEARS_SYNTHESIZED


# %% create bootstrapped samples of full ensemble
if bootstrap_tritonswmm_results:
    lst_files_processed = glob(f"{DIR_SIM_FLOOD_PROBS_BOOTSTRAPPING}bs_*.zarr")
    bs_id_start_tritonswmm, bootstrap_tritonswmm_results = prepare_for_bootstrapping(
        lst_files_processed, pickup_where_left_off, currently_running, n_bs_samples
    )

if bootstrap_triton_results:
    lst_files_processed = glob(
        f"{DIR_SIM_FLOOD_PROBS_BOOTSTRAPPING_TRITONONLY}bs_*.zarr"
    )
    bs_id_start_triton, bootstrap_triton_results = prepare_for_bootstrapping(
        lst_files_processed, pickup_where_left_off, currently_running, n_bs_samples
    )

# %%
years_with_at_least_1_event = ds_triton_sim.year.to_series().unique()
lst_bounds = []
alpha = ALPHA
beta = BETA

for bs_id in tqdm(np.arange(0, n_bs_samples)):
    # choose which years to resample
    resampled_years = np.random.choice(
        ar_sim_years, size=n_ensemble_years, replace=True
    )
    if bootstrap_tritonswmm_results and (bs_id >= bs_id_start_tritonswmm):
        dir_bootstrap_sample_destination = DIR_SIM_FLOOD_PROBS_BOOTSTRAPPING
        bootstrapping_return_period_estimates(
            resampled_years,
            years_with_at_least_1_event,
            df_sim_flood_probs_event_num_mapping,
            ds_sim_flood_probs,
            dir_bootstrap_sample_destination,
            ALPHA,
            BETA,
            n_ensemble_years,
            bs_id,
            print_benchmarks=print_benchmarks,
        )
    if bootstrap_triton_results and (bs_id >= bs_id_start_triton):
        dir_bootstrap_sample_destination = DIR_SIM_FLOOD_PROBS_BOOTSTRAPPING_TRITONONLY
        bootstrapping_return_period_estimates(
            resampled_years,
            years_with_at_least_1_event,
            df_sim_flood_probs_event_num_mapping,
            ds_sim_flood_probs_tritononly,
            dir_bootstrap_sample_destination,
            ALPHA,
            BETA,
            n_ensemble_years,
            bs_id,
            print_benchmarks=print_benchmarks,
        )