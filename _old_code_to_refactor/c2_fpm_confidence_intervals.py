# %%
from local.__inputs import F_SIM_FLOOD_PROBS_BOOTSTRAPPED
from local.__utils import *
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
from glob import glob

# ds_triton = xr.open_dataset(f_triton_outputs, engine="zarr", chunks="auto")
# for dim in ds_triton.dims:
#     ds_triton = ds_triton.sortby(variables=dim)

ds_combined = xr.open_dataset(
    F_SIM_FLOOD_PROBS_BOOTSTRAPPED, engine="zarr", chunks="auto"
)


# %% see if there are any missing return periods
df_max = ds_combined["max_wlevel_m"].max(["return_pd_yrs", "bs_id"]).to_dataframe()
idx_higher_quant = df_max["max_wlevel_m"] == df_max["max_wlevel_m"].quantile(
    0.995, interpolation="nearest"
)
x, y = df_max["max_wlevel_m"][idx_higher_quant].index.values[0]

df_1loc = ds_combined.sel(x=x, y=y).to_dataframe()["max_wlevel_m"]
df_1loc = df_1loc.unstack(level="bs_id")
idx_return_pds_w_missing_vals = df_1loc.isna().any(axis=1)

n_rtrn_pds_w_na = idx_return_pds_w_missing_vals.sum()
if n_rtrn_pds_w_na > 0:
    print("The following return periods have missing values in the dataset:")
    print(df_1loc.index[idx_return_pds_w_missing_vals])

# %% testing computing confidence intervals
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
