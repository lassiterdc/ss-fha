# %%
from local.__inputs import (
    MC_QUANTS_FOR_FLOOD_MAPPING,
    DIR_SIM_FLOOD_PROBS_BOOTSTRAPPING,
    F_SIM_FLOOD_PROBS_BOOTSTRAPPED,
    DIR_SIM_FLOOD_PROBS_BOOTSTRAPPING_TRITONONLY,
    F_SIM_FLOOD_PROBS_BOOTSTRAPPED_TRITONONLY,
    F_SIM_FLOOD_PROBS_BOOTSTRAPPED_CIS,
    F_SIM_FLOOD_PROBS_BOOTSTRAPPED_CIS_TRITONONLY,
)
from local.__utils import (
    write_bootstrapped_samples_to_single_zarr,
    delete_zarr,
    write_zarr,
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
from pathlib import Path

# load input weather
currently_running = False
print_benchmarks = True
rewrite_if_file_already_exists = False
rewrite_if_any_na = False
# %% combine bootstrapped samples and export to a zarr
# triton-swmm
lst_f = glob(f"{DIR_SIM_FLOOD_PROBS_BOOTSTRAPPING}bs_*_rtrn_idxd.zarr")
f_out = F_SIM_FLOOD_PROBS_BOOTSTRAPPED
ds_tritonswmm_bs_combined = write_bootstrapped_samples_to_single_zarr(
    lst_f,
    f_out,
    rewrite_if_file_already_exists,
    currently_running,
    print_benchmarks=print_benchmarks,
)


# triton
lst_f = glob(f"{DIR_SIM_FLOOD_PROBS_BOOTSTRAPPING_TRITONONLY}bs_*_rtrn_idxd.zarr")
f_out = F_SIM_FLOOD_PROBS_BOOTSTRAPPED_TRITONONLY
if len(lst_f) > 0:
    ds_triton_bs_combined = write_bootstrapped_samples_to_single_zarr(
        lst_f,
        f_out,
        rewrite_if_file_already_exists,
        currently_running,
        rewrite_if_any_na=rewrite_if_any_na,
        print_benchmarks=print_benchmarks,
    )
else:
    print("no TRITON-only bootstrapped results")


# %% compute quantiles for each return period

from local.__utils import return_event_ids_for_each_ssfha_quantile


def compute_bootstrapped_flood_depth_cis(
    f_path_bs_sample, f_path_ci_output, rewrite_if_file_already_exists
):
    if Path(f_path_bs_sample).exists():
        ds_sim_flood_probs_bs = xr.open_dataset(
            f_path_bs_sample, engine="zarr", chunks="auto"
        )
        quantiles_computed_successfully = False
        if Path(f_path_ci_output).exists():
            try:
                da_sim_flood_probs_bs = xr.open_dataset(
                    f_path_ci_output, engine="zarr", chunks="auto"
                )
                if str(da_sim_flood_probs_bs.attrs["success"]).lower() == "true":
                    quantiles_computed_successfully = True
                    if not rewrite_if_file_already_exists:
                        return da_sim_flood_probs_bs
            except:
                delete_zarr(f_path_ci_output)
        # compute quantiles and write to file
        if not quantiles_computed_successfully:
            lst_zarrs_to_delete = []
            print("computing flood hazard quantiles using bootstrapped sample...")
            da_sim_flood_probs_bs = ds_sim_flood_probs_bs["max_wlevel_m"].quantile(
                q=MC_QUANTS_FOR_FLOOD_MAPPING,
                dim="bs_id",
                method="closest_observation",
            )
            temp_output = f_path_ci_output.replace(".zarr", "_temp1.zarr")
            lst_zarrs_to_delete.append(temp_output)
            write_zarr(da_sim_flood_probs_bs.chunk("auto"), temp_output)

            da_sim_flood_probs_bs = xr.open_dataset(
                temp_output, engine="zarr", chunks="auto"
            )["max_wlevel_m"]

            ds_CI_event_ids = return_event_ids_for_each_ssfha_quantile(
                da_sim_flood_probs_bs
            )

            temp_output = f_path_ci_output.replace(".zarr", "_temp2.zarr")
            lst_zarrs_to_delete.append(temp_output)
            write_zarr(ds_CI_event_ids.chunk("auto"), temp_output)
            ds_CI_event_ids = xr.open_dataset(temp_output, engine="zarr", chunks="auto")

            da_sim_flood_probs_bs_event_ids = xr.merge(
                [da_sim_flood_probs_bs, ds_CI_event_ids]
            )

            write_zarr(
                da_sim_flood_probs_bs_event_ids.chunk("auto"),
                f_path_ci_output,
                mode="w",
            )

            da_sim_flood_probs_bs_event_ids = xr.open_dataset(
                f_path_ci_output, engine="zarr", chunks="auto"
            )

            for zarr in lst_zarrs_to_delete:
                delete_zarr(zarr)

            print(f"Wrote {f_path_ci_output}")
            return xr.open_dataset(f_path_ci_output, engine="zarr", chunks="auto")
    else:
        print(
            f"did not compute flood depth CIs because {f_path_bs_sample} does not exist"
        )


f_path_bs_sample = F_SIM_FLOOD_PROBS_BOOTSTRAPPED
f_path_ci_output = F_SIM_FLOOD_PROBS_BOOTSTRAPPED_CIS
compute_bootstrapped_flood_depth_cis(
    F_SIM_FLOOD_PROBS_BOOTSTRAPPED,
    F_SIM_FLOOD_PROBS_BOOTSTRAPPED_CIS,
    rewrite_if_file_already_exists,
)

compute_bootstrapped_flood_depth_cis(
    F_SIM_FLOOD_PROBS_BOOTSTRAPPED_TRITONONLY,
    F_SIM_FLOOD_PROBS_BOOTSTRAPPED_CIS_TRITONONLY,
    rewrite_if_file_already_exists,
)


# %% check for na values


# %% attempt to subset at location with known issue

x, y = (np.float64(3697992.8434817656), np.float64(1060829.6483268768))

# for ds_combined in [ds_tritonswmm_bs_combined, ds_triton_bs_combined]:


def analyze_1_loc(ds_combined, x, y):
    df_1loc = ds_combined.sel(x=x, y=y).to_dataframe()["max_wlevel_m"]
    df_1loc = df_1loc.unstack(level="bs_id")

    fig, ax = plt.subplots(dpi=300)

    s_max = df_1loc.max(axis=1)
    s_min = df_1loc.min(axis=1)
    s_lb = df_1loc.quantile(FLD_RTRN_PD_ALPHA / 2, axis=1, interpolation="linear")
    s_ub = df_1loc.quantile(1 - FLD_RTRN_PD_ALPHA / 2, axis=1, interpolation="linear")

    idx = s_max.index

    xmin = idx.min()
    xmax = idx.max() * 0.75

    ax.fill_between(idx, s_lb, s_ub, color="grey", alpha=0.3, label="90% CI")

    # Plot s_max with a black dashed line
    linewidth = 0.5
    size = 3
    extremes_alpha = 0.5
    linestyle = (0, (5, 5))

    # ax.scatter(idx, s_max, s = size, facecolor = 'none', edgecolors = "black", linewidth = linewidth, label='upper bound')
    ax.plot(
        idx,
        s_max,
        color="black",
        linestyle=linestyle,
        linewidth=linewidth,
        marker="o",
        alpha=extremes_alpha,
        markerfacecolor="none",
        markeredgecolor="black",
        markersize=size,
        markeredgewidth=linewidth,
        label="extremes",
    )

    # Plot s_min with a black dashed line
    # ax.scatter(idx, s_min, s = size, facecolor = 'none', edgecolors = "black", linewidth = linewidth, label='lower bound')

    ax.plot(
        idx,
        s_min,
        color="black",
        linestyle=linestyle,
        linewidth=linewidth,
        marker="o",
        alpha=extremes_alpha,
        markerfacecolor="none",
        markeredgecolor="black",
        markersize=size,
        markeredgewidth=linewidth,
    )

    # Add labels, legend, and title
    ax.set_ylabel("Flood Depth (m)")
    ax.set_xlabel("Return Period (yr)")
    ax.set_title("")
    # ax.set_xlim(0, xmax)
    ax.set_xscale("log")

    ax.legend()
    plt.show()


ds_combined = ds_tritonswmm_bs_combined

analyze_1_loc(ds_combined, x, y)
