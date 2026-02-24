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

currently_running = False
pickup_where_left_off = True

# load input weather

ds_sim_tseries = xr.open_dataset(f_sim_tseries)
sim_idx_names = ds_sim_tseries.coords.to_index().names
sim_smry_idx = [name for name in sim_idx_names if name != "timestep"]

df_sim_smries = pd.read_csv(f_sim_smries, index_col=sim_smry_idx)

f_dsgn_tseries = f_design_storm_tseries_based_on_SSR

ds_dsgn_tseries = xr.open_dataset(f_dsgn_tseries)
df_obs_smries = pd.read_csv(f_obs_smries, index_col=sim_smry_idx)
ds_obs_tseries = xr.open_dataset(f_obs_tseries)

# ds_triton = xr.open_dataset(f_triton_outputs, engine = "zarr", chunks = "auto")
# for dim in ds_triton.dims:
#     ds_triton = ds_triton.sortby(variables = dim)

ds_sim_flood_probs = xr.open_dataset(F_SIM_FLOOD_PROBS engine="zarr", chunks="auto")
ds_obs_flood_probs = xr.open_dataset(f_obs_flood_probs, engine="zarr", chunks="auto")

testing = False

# %% inspecting missing values (already done in script b1)
# obs_dims_no_na = ds_obs_flood_probs.dropna(dim='x', how='any').dropna(dim='y', how='any').dropna(dim='event_number', how='any').sizes
# sim_dims_no_na = ds_sim_flood_probs.dropna(dim='x', how='any').dropna(dim='y', how='any').dropna(dim='event_number', how='any').sizes


# for dim in obs_dims_no_na:
#     if obs_dims_no_na[dim] != ds_obs_flood_probs.sizes[dim]:
#         print(f"WARNING: In the OBSERVED dataset there are missing values along dimension {dim}")

# for dim in sim_dims_no_na:
#     if sim_dims_no_na[dim] != ds_sim_flood_probs.sizes[dim]:
#         print(f"WARNING: In the SIMULATED dataset there are missing values along dimension {dim}")

# %% first calculate fitted cdf values
# interpolated_cdf = interpolate_cdf_for_grid(ds_obs_flood_probs, ds_sim_flood_probs)

# def interpolate_cdf(new_x, ref_x, ref_y):
#     """
#     Vectorized interpolation of empirical CDF values based on reference dataset.
#     Returns the minimum value of ref_y if new_x is zero, otherwise interpolates the value.
#     """
#     # Perform interpolation
#     cdf_val = np.interp(new_x, ref_x, ref_y)
#     # where new_x is equal to zero
#     zero_indices_new_x = np.where(new_x == 0)[0]
#     #
#     zero_indices_ref_x = np.where(ref_x == 0)[0]
#     if len(zero_indices_new_x) > len(zero_indices_ref_x):
#         cdf_val[zero_indices_ref_x] = ref_y[zero_indices_ref_x]
#     else:
#         cdf_val[zero_indices_new_x] = ref_y[zero_indices_new_x]
#     return cdf_val


def interpolate_quantile_function(
    obs_plotting_positions, sim_cdf_sorted, sim_wlevel_sorted
):
    """
    interpolation of real-space values based on reference empirical CDF
    """
    return np.interp(obs_plotting_positions, sim_cdf_sorted, sim_wlevel_sorted)


def calc_emp_vs_fit_corr(obs_wlevel, obs_cdf, sim_wlevel, sim_cdf):
    """
    Interpolate emprical_cdf from ds_sim_flood_probs based on max_wlevel_m values from ds_obs_flood_probs.
    Interpolation is performed only along the event_number dimension.
    Returns n/a if either the obs_wlevel is all zeros and/or the empirical quantiles are all zeros
    """
    # sample data to make sure it is working properly
    # sys.exit("working")
    ## picking an x y with significant flooding
    # da_sim_max_wlevels = ds_all_sims["max_wlevel_m"].max(dim = "event_number").compute()
    # da_sim_max_wlevels = da_sim_max_wlevels.where((da_sim_max_wlevels>0.25) & (da_sim_max_wlevels<0.5), drop = True)
    # x, y = da_sim_max_wlevels.to_dataframe().dropna().sort_values(by="max_wlevel_m").iloc[-1, :].name
    ## picking an x y that resulted in n/a ppcc values
    # x, y = (np.float64(3696705.66198281), np.float64(1059882.5460307705))
    # obs_wlevel = ds_comp_sims['max_wlevel_m'].sel(x=x, y=y).values
    # obs_cdf = ds_comp_sims['emprical_cdf'].sel(x=x, y=y).values
    # sim_wlevel = ds_all_sims['max_wlevel_m'].sel(x=x, y=y).values
    # sim_cdf = ds_all_sims['emprical_cdf'].sel(x=x, y=y).values
    # end of sample data

    # sort obs values
    sorted_idx_obs = np.argsort(obs_cdf)
    obs_wlevel_sorted = obs_wlevel[sorted_idx_obs]
    obs_plotting_positions = obs_cdf[sorted_idx_obs]

    # sort simulated values
    sorted_idx_sim = np.argsort(sim_cdf)
    sim_wlevel_sorted = sim_wlevel[sorted_idx_sim]
    sim_cdf_sorted = sim_cdf[sorted_idx_sim]

    # compute x-values from the empirical quantile function at the plotting positions
    fitted_quantile_function = interpolate_quantile_function(
        obs_plotting_positions, sim_cdf_sorted, sim_wlevel_sorted
    )
    corr_matrix = np.corrcoef(obs_wlevel_sorted, fitted_quantile_function)
    corr = corr_matrix[0, 1]

    return corr


def create_data_array_of_ppct_stats(
    ds_comp_sims, ds_all_sims, fpath_save=None, chunks=None
):
    bm_time = time.time()
    ds_comp_sims = ds_comp_sims.reset_coords(drop=True)
    ds_all_sims = ds_all_sims.reset_coords(drop=True)
    if chunks is None:
        chunks = {"event_number": -1}
    ds_comp_sims = ds_comp_sims.chunk(chunks)
    ds_all_sims = ds_all_sims.chunk(chunks)
    # rename comp dimensions so they aren't unintentionally joined
    ds_comp_sims = ds_comp_sims.rename({"event_number": "event_number_comp"})
    da_ppct_corrs = xr.apply_ufunc(
        calc_emp_vs_fit_corr,
        ds_comp_sims["max_wlevel_m"],  # Observed max_wlevel_m
        ds_comp_sims["emprical_cdf"],  # Observed emprical_cdf
        ds_all_sims["max_wlevel_m"],  # Simulated max_wlevel_m
        ds_all_sims["emprical_cdf"],  # Simulated emprical_cdf
        input_core_dims=[
            ["event_number_comp"],
            ["event_number_comp"],
            ["event_number"],
            ["event_number"],
        ],  # Align only along event_number
        vectorize=True,  # Enable vectorized operations
        dask="parallelized",  # Parallelize using Dask
        join="outer",  # Allow broadcasting over dimensions that don't align
        output_dtypes=[float],  # Output data type
        dask_gufunc_kwargs={
            "allow_rechunk": True
        },  # Allow automatic rechunking if necessary
    )
    # da_ppct_corrs = da_ppct_corrs.compute()
    da_ppct_corrs.name = "ppc"
    if fpath_save is not None:
        Path(fpath_save).parent.mkdir(parents=True, exist_ok=True)
        # da_ppct_corrs.attrs["warnings"] = 'none'
        delete_zarr(fpath_save, attempt_time_limit_s=10)
        da_ppct_corrs.attrs["notes"] = (
            f"the correlation will be undefined if the fitted quantile function operates to all zeros or if the sample is all zeros."
        )
        da_ppct_corrs.chunk("auto").to_zarr(
            fpath_save,
            mode="w",
            encoding=return_dic_zarr_encodingds(da_ppct_corrs, clevel=5),
        )
        # da_ppct_corrs = xr.open_dataset(fpath_save, engine = "zarr", chunks = "auto").load()
        # df_ppc = da_ppct_corrs.to_dataframe()
        # if sum(df_ppc["ppc"].isna()) > 0:
        #     print("warning: na values introduced")
        # da_ppct_corrs.attrs["warnings"] = f'{sum(df_ppc["ppc"].isna())} na values introduced'
        print(
            f"Calculated ppct corrs and wrote zarr in ({(time.time() - bm_time)/60:.2f} min"
        )
    return da_ppct_corrs


# %% compute observed correlations
ds_comp_sims = ds_obs_flood_probs
ds_all_sims = ds_sim_flood_probs
fpath_save = dif_ffa_ppct_obs

da_ppct_corrs = create_data_array_of_ppct_stats(ds_comp_sims, ds_all_sims, fpath_save)

da_ppct_corrs_obs = xr.open_dataset(dif_ffa_ppct_obs, engine="zarr", chunks="auto")
# %% doing for bootstrap samples
lst_files_processed = glob(f"{dif_ffa_ppct_bs_sim_cdfs}emp_cdf_*.zarr")

bs_ids_done = []
for f in lst_files_processed:
    bs_ids_done.append(int(f.split("emp_cdf_")[-1].split(".")[0]))

lst_files_processed_for_corrs = glob(f"{dif_ffa_ppct_bs_corrs}corrs_*.zarr")
bs_ids_processed_for_corrs = []
for f in lst_files_processed_for_corrs:
    bs_ids_processed_for_corrs.append(int(f.split("corrs_")[-1].split(".")[0]))

if pickup_where_left_off and len(lst_files_processed_for_corrs) > 0:
    bs_id_start = max(bs_ids_processed_for_corrs) - 1
    print(f"resuming processing at bootstrap id {bs_id_start}")
else:
    if len(lst_files_processed_for_corrs) > 0:
        print("Deleting previously processed outputs")
        for f in lst_files_processed_for_corrs:
            delete_zarr(f)
    print("starting bootstrapping from id 0")
    bs_id_start = 0

s_bs_files = pd.Series(data=lst_files_processed, index=bs_ids_done).astype(str)
s_bs_files.index.name = "bs_id"
s_bs_files = s_bs_files.sort_index()

# subset all but the last one
s_bs_files = s_bs_files.iloc[bs_id_start : (n_bs_samples - int(currently_running))]
# open dataset
lst_ds = []
for bs_id, f in tqdm(s_bs_files.items()):
    ds_comp_sims = xr.open_dataset(f, engine="zarr")
    fpath_save = f"{dif_ffa_ppct_bs_corrs}corrs_{bs_id}.zarr"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ds_all_sims = ds_sim_flood_probs
        create_data_array_of_ppct_stats(
            ds_comp_sims,
            ds_all_sims,
            fpath_save,
            chunks=dict(x=30, y=30, event_number=-1),
        )

# %% TESTING: verify with a few manual calculations (OBSOLETE AS OF 5/18/25 WHEN I CORRECTED MY PPCC TO BE THE CORRELATION BETWEEN REAL-SPACE SAMPLE AND QUANTILE-FUNCTION OUTPUTS RATHER THAN BETWEEN EMPIRICAL CDF AND FITTED CDF VALUES)
# look for the introduction of missing values
da_ppct_corrs = xr.open_dataset(dif_ffa_ppct_obs, engine="zarr", chunks="auto").load()
df_ppc = da_ppct_corrs.to_dataframe()


# if testing:
# find observed locations that had a range of max flood depths
ds_obs_sig_fld = ds_obs_flood_probs.where(
    ds_obs_flood_probs["max_wlevel_m"] > MIN_THRESH_FLDING
).compute()
ds_obs_sig_fld = ds_obs_sig_fld.where(
    ds_obs_flood_probs["max_wlevel_m"].max().compute() > nuisance_threshold
).compute()
ar_obs_sig_fld_quants = (
    ds_obs_sig_fld["max_wlevel_m"]
    .quantile([0.1, 0.5, 0.9, 0.999], skipna=True, method="nearest")
    .compute()
    .values
)


lst_xys_for_testing = []
lst_df_sim = []
lst_df_obs = []

# extract a location that returned a missing value for ppc
if sum(df_ppc["ppc"].isna()) > 0:
    print(
        "There are still na values being introduced into the ppc calculations. Inspecting..."
    )
    x_na, y_na = df_ppc[df_ppc["ppc"].isna()].index[0]
    lst_xys_for_testing.append((x_na, y_na))

# extract a location that never floods
s_obs_zeros = (
    (ds_obs_flood_probs["max_wlevel_m"] == 0)
    .sum(dim="event_number")
    .to_dataframe()["max_wlevel_m"]
)
s_sim_zeros = (
    (ds_sim_flood_probs["max_wlevel_m"] == 0)
    .sum(dim="event_number")
    .to_dataframe()["max_wlevel_m"]
)
# find an obs xy that never floods
x_obs_all_zero, y_obs_all_zero = s_obs_zeros[
    s_obs_zeros == len(ds_obs_flood_probs.event_number)
].index[0]
lst_xys_for_testing.append((x_obs_all_zero, y_obs_all_zero))
# find an obs xy that floods in all but 1 event
x_obs_all_but1_zero, y_obs_all_but1_zero = s_obs_zeros[
    s_obs_zeros == len(ds_obs_flood_probs.event_number) - 1
].index[0]
lst_xys_for_testing.append((x_obs_all_but1_zero, y_obs_all_but1_zero))
# find an obs xy that floods in all but 2 events
x_obs_all_but2_zero, y_obs_all_but2_zero = s_obs_zeros[
    s_obs_zeros == len(ds_obs_flood_probs.event_number) - 2
].index[0]
lst_xys_for_testing.append((x_obs_all_but2_zero, y_obs_all_but2_zero))
# find an obs xy that floods in all but 3 events
x_obs_all_but3_zero, y_obs_all_but3_zero = s_obs_zeros[
    s_obs_zeros == len(ds_obs_flood_probs.event_number) - 3
].index[0]
lst_xys_for_testing.append((x_obs_all_but3_zero, y_obs_all_but3_zero))
# find an sim xy that never floods
x_sim_all_zero, y_sim_all_zero = s_sim_zeros[
    s_sim_zeros == len(ds_sim_flood_probs.event_number)
].index[0]
lst_xys_for_testing.append((x_sim_all_zero, y_sim_all_zero))
# find an sim xy that floods in all but 1 event
x_sim_all_but1_zero, y_sim_all_but1_zero = s_sim_zeros[
    s_sim_zeros == len(ds_sim_flood_probs.event_number) - 1
].index[0]
lst_xys_for_testing.append((x_sim_all_but1_zero, y_sim_all_but1_zero))
# find an sim xy that floods in all but 2 events
x_sim_all_but2_zero, y_sim_all_but2_zero = s_sim_zeros[
    s_sim_zeros == len(ds_sim_flood_probs.event_number) - 2
].index[0]
lst_xys_for_testing.append((x_sim_all_but2_zero, y_sim_all_but2_zero))
# find an sim xy that floods in all but 3 events
x_sim_all_but3_zero, y_sim_all_but3_zero = s_sim_zeros[
    s_sim_zeros == len(ds_sim_flood_probs.event_number) - 3
].index[0]
lst_xys_for_testing.append((x_sim_all_but3_zero, y_sim_all_but3_zero))

ar_obs_sig_fld_quants = np.insert(
    ar_obs_sig_fld_quants, 0, 0
)  # adding zero to see how this can f things up

for max_value in ar_obs_sig_fld_quants:
    # max_value = ds_sim_flood_probs["max_wlevel_m"].max().compute()
    max_indices = ds_obs_flood_probs["max_wlevel_m"].where(
        ds_obs_flood_probs["max_wlevel_m"].compute() == max_value, drop=True
    )
    x = max_indices["x"].values[0]
    y = max_indices["y"].values[0]
    if (x, y) in lst_xys_for_testing:
        continue
    lst_xys_for_testing.append((x, y))


# %%
def compute_ppf(df_cdf, new_probabilities, xname="max_wlevel_m", yname="emprical_cdf"):
    # Interpolate new_probabilities based on empirical CDF and return the corresponding max_wlevel_m
    ppf_values = np.interp(new_probabilities, df_cdf[yname], df_cdf[xname])
    return ppf_values


def compute_cdf(new_x, df_cdf, xname="max_wlevel_m", yname="emprical_cdf"):
    # Interpolate new max_wlevel_m values based on the empirical CDF
    cdf_values = np.interp(new_x, df_cdf[xname], df_cdf[yname])
    # where new_x is equal to zero
    zero_indices_new_x = np.where(new_x == 0)[0]
    #
    zero_indices_ref_x = np.where(df_cdf[xname] == 0)[0]
    if len(zero_indices_new_x) > len(zero_indices_ref_x):
        cdf_values[zero_indices_ref_x] = df_cdf[yname][zero_indices_ref_x]
    else:
        cdf_values[zero_indices_new_x] = df_cdf[yname][zero_indices_new_x]
    return cdf_values


def compute_emp_vs_ftd_corr(df_new, df_cdf, xname="max_wlevel_m", yname="emprical_cdf"):
    df_new = df_new.sort_values(yname).reset_index()
    new_x, emp_cdf = df_new[xname], df_new[yname]
    df_cdf = df_cdf.sort_values(yname).reset_index()
    fitted_emp_cdf = compute_cdf(new_x, df_cdf, xname=xname, yname=yname)
    corr_matrix = np.corrcoef(fitted_emp_cdf, emp_cdf)
    corr = corr_matrix[0, 1]  # Extract the correlation value
    return corr


for xy in lst_xys_for_testing:
    # break
    x, y = xy
    # testing on x, y with highest max flooding
    # max_value = ds_sim_flood_probs["max_wlevel_m"].max().compute()
    # max_indices = ds_sim_flood_probs["max_wlevel_m"].where(ds_sim_flood_probs["max_wlevel_m"].compute() == max_value, drop=True)
    # x = max_indices["x"].values
    # y = max_indices["y"].values
    # event_number_max = max_indices["event_number"].values

    df_all_sims = ds_sim_flood_probs.sel(x=x, y=y).to_dataframe()
    # df_all_sim_empcdf = df_all_sims.loc[:, ["emprical_cdf", "max_wlevel_m"]].sort_values("emprical_cdf").reset_index(drop = True)
    # ar_sim_years = df_all_sims.sort_values("year")['year'].unique()

    df_all_obs = ds_obs_flood_probs.sel(x=x, y=y).to_dataframe()
    # df_all_obs_emp_cdf = df_all_obs.loc[:, ["emprical_cdf", "max_wlevel_m"]].sort_values("emprical_cdf").reset_index(drop = True)

    df_new, df_cdf = df_all_obs, df_all_sims
    test_corr_slow = compute_emp_vs_ftd_corr(
        df_new, df_cdf, xname="max_wlevel_m", yname="emprical_cdf"
    )
    # test_corr_fast = da_ppct_corrs['ppc'].sel(x = x, y = y).values
    test_corr_fast = calc_emp_vs_fit_corr(
        df_new["max_wlevel_m"].values,
        df_new["emprical_cdf"].values,
        df_cdf["max_wlevel_m"].values,
        df_cdf["emprical_cdf"].values,
    )

    df_all_obs["ppc_manual_test"] = test_corr_slow
    df_all_sims["ppc_using_same_as_datasets"] = test_corr_fast

    if np.isnan(test_corr_fast):
        print("test_corr_fast is nan")
    elif not np.isclose(test_corr_fast, test_corr_slow):
        print(
            f"test_corr_slow = {test_corr_slow:.2f}; test_corr_slow = {test_corr_fast:.2f}"
        )
    else:
        print(
            "The vectorized function for computing probability plot correlations values worked!"
        )

    lst_df_sim.append(df_all_sims)
    lst_df_obs.append(df_all_obs)

df_sim_locs_for_testing = pd.concat(lst_df_sim)
df_obs_locs_for_testing = pd.concat(lst_df_obs)

df_sim_locs_for_testing.to_csv(
    f"{dir_ffa_scripts_local_scratch}df_sim_locs_for_testing.csv"
)
df_obs_locs_for_testing.to_csv(
    f"{dir_ffa_scripts_local_scratch}df_obs_locs_for_testing.csv"
)
