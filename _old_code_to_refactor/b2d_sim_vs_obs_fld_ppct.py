# %%
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
from glob import glob
from tqdm import tqdm
import warnings
import matplotlib.colors as mcolors
from matplotlib.patches import Patch

# %% load shapefile to mask data set

shapefile_path = f_wshed_shp

# %%


# functions
def plot_PPCT_result(da_result, title, fname_save_fig=None, shapefile_path=None):
    fig, ax = plt.subplots(dpi=300, figsize=(4, 3), constrained_layout=True)
    if shapefile_path is not None:
        import geopandas as gpd

        gdf = gpd.read_file(shapefile_path)

    cbar_tick_lables = ["reject", "fail_to_reject"]
    cmap = mcolors.ListedColormap(
        ["red", "green"]
    )  # gray for NaN, red for 0, green for 1
    cbar_bins = bounds = [0, 1, 2]  # Adjusted boundaries to handle 0, 1, and NaN
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    # Plotting using xarray's plot.pcolormesh method
    # plt.figure(figsize=(8, 6))

    if shapefile_path is not None:
        gdf.boundary.plot(ax=ax, color="black", linewidth=1)
    p = da_result.plot.pcolormesh(
        x="x", y="y", cmap=cmap, norm=norm, ax=ax, add_colorbar=False
    )
    #    cbar_kwargs={'ticks': [0, 1], 'label': 'ppc'})

    ax.set_title(title, fontsize=10)
    ax.set_xticklabels([])  # Remove x-axis tick labels
    ax.set_yticklabels([])  # Remove y-axis tick labels
    ax.set_ylabel("")
    ax.set_xlabel("")

    legend_elements = [
        Patch(facecolor="green", edgecolor="black", label="fail_to_reject"),
        Patch(facecolor="red", edgecolor="black", label="reject"),
        # Patch(facecolor='lightgray', edgecolor='black', label='missing')
    ]

    ax.legend(handles=legend_elements, loc="lower right", frameon=True, fontsize=9)

    if fname_save_fig is not None:
        Path(fname_save_fig).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(fname_save_fig, bbox_inches="tight")
    else:
        plt.show()


# %% load data
da_ppc_obs = xr.open_dataset(dif_ffa_ppct_obs, engine="zarr").load()
ds_bs_corrs_rej_thresh = xr.open_dataset(
    dif_ffa_ppct_rej_threshold, engine="zarr"
).load()
ds_ppct_pvalues = xr.open_dataset(
    dif_ffa_ppct_obs_pvalues, engine="zarr", chunks="auto"
).load()
ds_sim_flood_probs = xr.open_dataset(F_SIM_FLOOD_PROBS engine="zarr", chunks="auto")
ds_obs_flood_probs = xr.open_dataset(f_obs_flood_probs, engine="zarr", chunks="auto")
# %%
# create watershed mask
# wshed_mask = create_mask_from_shapefile(da_ppc_obs["ppc"], shapefile_path)

wshed_mask = return_mask_dataset_from_polygon(
    da_ppc_obs["ppc"], shapefile_path=shapefile_path, series_single_row_of_gdf=None
)
wshed_mask.name = "in_watershed"

# only valid where max flooding in observed dataset exceeds nuisance threshold
mask_flood_threshold = (
    ds_obs_flood_probs["max_wlevel_m"].max(dim="event_number") > MIN_THRESH_FLDING
).load()

# finally, only include grid cells that have non-null observed PPCC's
mask_valid_observed_ppccs = ~np.isnan(da_ppc_obs["ppc"])

# combine into 1 filter
mask_test_region = mask_flood_threshold & wshed_mask & mask_valid_observed_ppccs
mask_test_region.name = "in_wshed_and_experiences_min_fld"

ds_ppct_pvalues = ds_ppct_pvalues.where(mask_test_region)
# comparing results with using ds_bs_corrs_rej_thresh for the reject/fail to reject
test_using_rejection_threshold = da_ppc_obs["ppc"] >= ds_bs_corrs_rej_thresh[
    "ppc"
].squeeze().reset_coords(drop=True)
df_test_using_rejection_threshold = (
    test_using_rejection_threshold.where(mask_test_region)
    .to_dataframe()
    .dropna()["ppc"]
    .astype(int)
)

df_test_using_pvals = (
    ds_ppct_pvalues.to_dataframe().dropna()["obs_ppct_pvals"] > ppct_alpha
).astype(int)

s_compare = (
    pd.concat([df_test_using_pvals, df_test_using_rejection_threshold], axis=1)
    .diff(axis=1)["ppc"]
    .value_counts()
)
if len(s_compare) != 1:
    print("WARNING: Two tests are giving different rejection rates")

da_test_results_using_threhsold = (
    xr.where(test_using_rejection_threshold, 1, 0).where(mask_test_region).load()
)  # fail to reject is 1, reject is 0
da_test_results_using_threhsold.name = "result"
# using computed critical thresholds
# da_test_results = da_test_results_using_threhsold

# using the computed pvals (fail to reject is 1, reject is 0)
da_test_results_using_pvalues = xr.where(ds_ppct_pvalues >= ppct_alpha, 1, 0).where(
    mask_test_region
)["obs_ppct_pvals"]

da_diffs = (da_test_results_using_pvalues != da_test_results_using_threhsold).where(
    mask_test_region
)
da_diffs.name = "diff"
df_diffs = da_diffs.to_dataframe()

if len(df_diffs.dropna()["diff"].value_counts()) != 1:
    print("WARNING: Two tests are giving different rejection rates")

# %% checking out observed p-values
ds_ppct_pvalues["obs_ppct_pvals"].plot(x="x", y="y", vmin=0, vmax=1)

# %% plotting pcct results
# da_result = da_test_results_using_threhsold
da_result = da_test_results_using_pvalues
n_rejected = (da_result.to_dataframe().dropna() == 0).iloc[:, 0].sum()
n_gridcells = len(da_result.to_dataframe().dropna())
frac_rejected_obs = n_rejected / n_gridcells
title = f"PPCCT (n bootstrapped = {ds_bs_corrs_rej_thresh.attrs['n_bootstrap_samples']} | {frac_rejected_obs*100:.2f}% rejected)"
fname_save_fig = f"{dif_ffa_ppct_plots}ppct_obs_alpha.png"
shapefile_path = f_wshed_shp
plot_PPCT_result(da_result, title, fname_save_fig, shapefile_path)
# plt.clf()
# %% figuring out process for significance testing when running many tests
import numpy as np
from statsmodels.stats.multitest import multipletests

df_pvalues = ds_ppct_pvalues.to_dataframe().dropna().reset_index()

pvals = df_pvalues[
    "obs_ppct_pvals"
]  # np.random.rand(10)  # 10 random p-values between 0 and 1
pval_idx = df_pvalues.index
methods = [
    "bonferroni",
    "sidak",
    "holm",
    "holm-sidak",
    "simes-hochberg",
    "hommel",
    "fdr_bh",
    "fdr_by",
    "fdr_tsbh",
    "fdr_tsbky",
]

results = ["fail_to_reject", "pvals_corrected", "alpha_sidak", "alpha_bonf"]

multi_index = pd.MultiIndex.from_product(
    [methods, pval_idx], names=["method", "pval_idx"]
)
df_result = pd.DataFrame(index=multi_index, columns=results)

for idx_method, method in enumerate(methods):
    print(f"Performing multi test with method {method}")
    reject, pvals_corrected, alpha_sidak, alpha_bonf = multipletests(
        pvals, method=method, alpha=ppct_alpha, maxiter=-1
    )
    df_result.loc[pd.IndexSlice[method, :], "fail_to_reject"] = (~reject).astype(
        int
    )  # 1 = fail to reject, 0 = reject
    df_result.loc[pd.IndexSlice[method, :], "pvals_corrected"] = pvals_corrected
    df_result.loc[pd.IndexSlice[method, :], "alpha_sidak"] = alpha_sidak
    df_result.loc[pd.IndexSlice[method, :], "alpha_bonf"] = alpha_bonf

df_result = df_result.reset_index()
df_result_multi_test = df_result.merge(
    df_pvalues, left_on="pval_idx", right_index=True, how="left"
)

ds_result_multi_test = df_result_multi_test.set_index(["method", "x", "y"]).to_xarray()

ds_result_multi_test = convert_ob_datavars_to_dtype(
    ds_result_multi_test, lst_dtypes_to_try=[float], lst_vars_to_convert=None
)

ds_result_multi_test = ds_result_multi_test.reindex(
    x=da_ppc_obs["x"], y=da_ppc_obs["y"], fill_value=np.nan
)


# %% loop through results and plot
# ds_result_finding = ds_result_multi_test.sel(result = "fail_to_reject").reset_coords(drop = True)
for method in ds_result_multi_test.method.values:
    ds_result = (
        ds_result_multi_test.where(
            ds_result_multi_test.method == "bonferroni", drop=True
        )
        .squeeze()
        .reset_coords(drop=True)
    )
    da_result = ds_result["fail_to_reject"]
    n_rejected = (da_result.to_dataframe().dropna()["fail_to_reject"] == 0).sum()
    n_gridcells = len(da_result.to_dataframe().dropna())
    frac_rejected = n_rejected / n_gridcells
    title = f"PPCCT (n bootstrapped = {ds_bs_corrs_rej_thresh.attrs['n_bootstrap_samples']} | {frac_rejected*100:.2f}% rejected)\nmethod = {method}"
    fname_save_fig = f"{dif_ffa_ppct_plots}ppct_obs_method_{method}.png"
    plot_PPCT_result(da_result, title, fname_save_fig, shapefile_path)
    plt.clf()
    # sys.exit("work")


# %% build a distribution of frac rejected
da_bs_ppc = (
    xr.open_dataset(f_zarr_ds_bs_corrs_and_emp_cdf, engine="zarr")
    .chunk(chunks="auto")["ppc"]
    .where(mask_test_region)
)

test = (
    da_bs_ppc >= ds_bs_corrs_rej_thresh["ppc"].squeeze().reset_coords(drop=True)
).where(mask_test_region)

da_test_results_using_threhsold_bs = xr.where(test, 1, 0).where(
    mask_test_region
)  # fail to reject is 1, reject is 0
da_test_results_using_threhsold_bs.name = "result"

df_n_fail_to_reject = da_test_results_using_threhsold_bs.sum(
    dim=["x", "y"]
).to_dataframe()
n_gridcells = mask_test_region.to_dataframe().iloc[:, 0].sum()
df_n_rejected = n_gridcells - df_n_fail_to_reject
s_frac_rejected = (
    (df_n_rejected.iloc[:, 0] / n_gridcells).sort_values().reset_index(drop=True)
)

ar_frac_rejected_emp_cdf = calculate_positions(s_frac_rejected, alpha, beta)
pval = 1 - np.interp(frac_rejected_obs, s_frac_rejected, ar_frac_rejected_emp_cdf)
# interpolate frac rejected based on ppct_alpha (1 sided test)
reject_threshold = np.interp(1 - ppct_alpha, ar_frac_rejected_emp_cdf, s_frac_rejected)
# %% plot result
vline_value = frac_rejected_obs
vline_txt = pval

fname_save_fig = f"{dif_ffa_ppct_plots}ppct_frac_rej_dist.png"


fig, ax = plt.subplots(dpi=300, figsize=(6, 4), constrained_layout=True)
result = "reject"
if frac_rejected_obs < reject_threshold:
    result = "fail_to_reject"

ax.hist(s_frac_rejected, bins=30, alpha=0.7)
fig.suptitle(
    f"n={ds_bs_corrs_rej_thresh.attrs['n_bootstrap_samples']} bootstrap-derived distribution of PPCT rejection rates\nConclusion: {result} that observed PPCT rejection rate comes from the same distribution",
    fontsize=10,
)
ax.set_ylabel("Count")
ax.set_xlabel("Fraction of gridcells rejected by PPCT")

ax.axvline(x=vline_value, color="blue", linestyle="--")
lab_offset = 0.01
ax.text(
    vline_value - lab_offset + 0.04,
    ax.get_ylim()[1] * 0.95,
    f"Observed\nrejection rate\n(p-value: {vline_txt:.2f})",
    color="blue",
    ha="left",
    va="top",
)

# Shade
ax.axvspan(ax.get_xlim()[0], reject_threshold, color="green", alpha=0.3)
ax.axvspan(reject_threshold, ax.get_xlim()[1], color="red", alpha=0.3)
# add shading to legend
green_patch = plt.Rectangle(
    (0, 0), 1, 1, color="green", alpha=0.3, label="fail_to_reject"
)
red_patch = plt.Rectangle((0, 0), 1, 1, color="red", alpha=0.3, label="reject")
# ax.legend(handles=[green_patch, red_patch])
ax.legend(
    handles=[green_patch, red_patch],
    loc="upper right",
    bbox_to_anchor=(0.95, 1),
    ncol=1,
)

if fname_save_fig is not None:
    Path(fname_save_fig).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(fname_save_fig, bbox_inches="tight")
    # plt.clf()
else:
    plt.show()
