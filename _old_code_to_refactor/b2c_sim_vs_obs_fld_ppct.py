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
from glob import glob
from tqdm import tqdm
import warnings
ds_bs_sim_chunks = {'bs_id': -1}
f_zarr_corrs_bs = f"{dir_ffa_scripts_local_scratch}emp_vs_fitted_corrs_bs.zarr"
Path(dir_ffa_scripts_local_scratch).mkdir(parents=True, exist_ok=True)

testing = False
currently_running = False # this will include all but the last file in the list so you don't try to load a currently exporting bootstrapped sample
#%% extract the bootstrapped correlations of empirical vs. fitted and export to zarr
val = input(f"type 'yes' to extract bootstrapped PPCs of empirical vs fitted and export to zarr")
run_chunk = False
if val.lower() == "yes":
    run_chunk = True

if run_chunk:
    bm_time = time.time()

    fpattern_bs_corrs = f"{dif_ffa_ppct_bs_corrs}corrs_*.zarr"

    lst_files_processed_for_corrs = glob(fpattern_bs_corrs)
    bs_ids_processed_for_corrs = []
    for f in lst_files_processed_for_corrs:
        bs_ids_processed_for_corrs.append(int(f.split("corrs_")[-1].split(".")[0]))

    s_bs_files = pd.Series(data = lst_files_processed_for_corrs, index = bs_ids_processed_for_corrs).astype(str)
    s_bs_files.index.name = "bs_id"
    s_bs_files = s_bs_files.sort_index()
    s_bs_files = s_bs_files.loc[0:(max(bs_ids_processed_for_corrs) - int(currently_running))] # subset all but last one if currently running

    n_samples_used = len(s_bs_files)

    lst_idx_with_warnings_attribute = []
    lst_warnings = []

    lst_ds_bs_corrs = []
    for bs_id, f_ds in s_bs_files.items():
        ds_bs = xr.open_dataset(f_ds, engine = "zarr", chunks = "auto")
        ds_bs = ds_bs.expand_dims(dict(bs_id = [bs_id]))
        # if ds_bs["ppc"].attrs["warnings"] != "none":
            # sys.exit("error: na values encountered. Need to figure out what to do now.")
        lst_ds_bs_corrs.append(ds_bs)

    ds_bs_corrs = xr.combine_by_coords(lst_ds_bs_corrs, coords=["bs_id"])

    for dim in ds_bs_corrs.dims:
        ds_bs_corrs = ds_bs_corrs.sortby(dim)

    # total_mb, chunk_sizes = estimate_chunk_memory(ds_bs_corrs, input_chunk_sizes=dict(x=50, y=50))
    delete_zarr(f_zarr_corrs_bs)
    ds_bs_corrs.chunk(ds_bs_sim_chunks).to_zarr(f_zarr_corrs_bs, mode='w', encoding = return_dic_zarr_encodingds(ds_bs_corrs, clevel=5), consolidated=True)
    print(f"Exported bootstrapped emp vs fitted corrs ({(time.time() - bm_time)/60:.2f} min")

#%% analyzing missing values
ds_bs_corrs = xr.open_dataset(f_zarr_corrs_bs, engine = "zarr", chunks = ds_bs_sim_chunks)

# ds_bs_corrs = xr.where(np.isnan(ds_bs_corrs), 1, ds_bs_corrs) # replace na with 1
df_n_na_eid = np.isnan(ds_bs_corrs["ppc"]).sum("bs_id").to_dataframe()
df_n_na_xy = np.isnan(ds_bs_corrs["ppc"]).sum(["x", "y"]).to_dataframe()

df_frac_na_xy = df_n_na_xy / (len(ds_bs_corrs.x) * len(ds_bs_corrs.y))
if len(df_frac_na_xy.value_counts()) != 1:
    print("Warning: missing values present")

n_samples_used = len(ds_bs_corrs.bs_id)

# to see what happens when there are missing valuess
upper_limit_n_na = 10
some_na = df_n_na_eid["ppc"][(df_n_na_eid["ppc"]>0) & (df_n_na_eid["ppc"]<=(upper_limit_n_na))].sort_values()
num_na_some_na = some_na.max()
x_some_na, y_some_na = some_na.idxmax()

upper_limit_n_na = 499
most_na = df_n_na_eid["ppc"][(df_n_na_eid["ppc"]>0) & (df_n_na_eid["ppc"]<=(upper_limit_n_na))].sort_values()
num_na_most_na = most_na.max()
x_most_na, y_most_na = most_na.idxmax()


#%% compute rejection threshold
bm_time = time.time()
ds_bs_corrs_rej_thresh = ds_bs_corrs.fillna(-9999).quantile(q=ppct_alpha, dim="bs_id", method = "linear", skipna = False)
ds_bs_corrs_rej_thresh.attrs["n_bootstrap_samples"] = n_samples_used

val_some_na = ds_bs_corrs_rej_thresh['ppc'].sel(x=x_some_na, y = y_some_na).values
val_most_na = ds_bs_corrs_rej_thresh['ppc'].sel(x=x_most_na, y = y_most_na).values
print("verifying that x and y locs with missing values still have valid rejection thresholds:")
print(f"rejection threshold at loc with at {num_na_some_na} missing value: {val_some_na:.3f}")
print(f"rejection threshold at loc with at {num_na_most_na} missing values: {val_most_na:.3f}")

ds_bs_corrs_rej_thresh.attrs["fill_value_notes"] = "Before computing the rejection threshold, I filled missing values with -9999 which corresponds to the BS sample not expereincing flooding in that grid cell."
# total_mb, chunk_sizes = estimate_chunk_memory(ds_bs_corrs_rej_thresh, input_chunk_sizes=dict(x=len(ds_bs_corrs_rej_thresh.x), y = len(ds_bs_corrs_rej_thresh.y)))
ds_bs_corrs_rej_thresh.chunk(x=-1,y=-1).to_zarr(dif_ffa_ppct_rej_threshold, mode='w', encoding = return_dic_zarr_encodingds(ds_bs_corrs_rej_thresh, clevel=5), consolidated=True)
print(f"Exported bootstrapped emp vs fitted corrs ({(time.time() - bm_time)/60:.2f} min")

#%% inspecting
ds_bs_corrs_rej_thresh = xr.open_dataset(dif_ffa_ppct_rej_threshold, engine = "zarr").load()
ds_obs_flood_probs = xr.open_dataset(f_obs_flood_probs, engine = "zarr", chunks = "auto")


ds_bs_corrs_rej_thresh.where((ds_obs_flood_probs["max_wlevel_m"].max(dim = "event_number") > nuisance_threshold) & \
                             (ds_bs_corrs_rej_thresh["ppc"]>=0)).to_dataframe().dropna()["ppc"].hist()

#%% compute empirical cdf of correlations for each bootstrapped sample and write to zarr file
# ds_bs_corrs = xr.open_dataset(f_zarr_corrs_bs, engine = "zarr", chunks = ds_bs_sim_chunks)
bm_time = time.time()

# figuring out what happens when there are missing values
data_og = ds_bs_corrs['ppc'].sel(x=x_most_na, y = y_most_na).to_series().values
# analyzing this helped me figure out that I need to fill missing values with na in order for the quantile calculations to make sense
# basically, if there was only 1 bs sample, no fill na results in an empirical cdf value of 0.5 for that single observations
# obviously having a non-na ppcc is super rare. Filling with -9999 and then reinserting na values at those other locations
# results in assigning that ppcc an empirical cdf value of 0.99800399

ppc_emp_cdf = xr.apply_ufunc(
                        calculate_positions,
                        ds_bs_corrs['ppc'],
                        input_core_dims=[["bs_id"]],
                        output_core_dims=[["bs_id"]],
                        vectorize=True,
                        dask="parallelized",  # Optional: Use Dask for large datasets
                        output_dtypes=[float],
                        keep_attrs=True,  # Preserve attributes if needed
                        kwargs={"alpha": alpha, "beta":beta, "fillna_val":-9999}
                    )
da_corr_emp_cdf = ppc_emp_cdf.load()

da_corr_emp_cdf.name = "emprical_cdf"

ds_bs_corrs_and_emp_cdf = xr.merge([ds_bs_corrs['ppc'].transpose('x', 'y', 'bs_id'), da_corr_emp_cdf.transpose('x', 'y', 'bs_id')])

delete_zarr(f_zarr_ds_bs_corrs_and_emp_cdf)
ds_bs_corrs_and_emp_cdf.chunk(ds_bs_sim_chunks).to_zarr(f_zarr_ds_bs_corrs_and_emp_cdf, mode='w', encoding = return_dic_zarr_encodingds(ds_bs_corrs_and_emp_cdf, clevel=5), consolidated=True)
print(f"Exported ds_bs_corrs_and_emp_cdf ({(time.time() - bm_time)/60:.2f} min")


#%% compute empirical cdf values (quantiles/pvalues) of observed corrs
def interpolate_cdf(obs_x_og, bs_sim_x_og, bs_sim_y_og, fillna_val = None):
    obs_x = obs_x_og.copy()
    bs_sim_x = bs_sim_x_og.copy()
    bs_sim_y = bs_sim_y_og.copy()

    if np.isnan(obs_x) or (np.isnan(bs_sim_x).sum() > 0) or (np.isnan(bs_sim_y).sum()):
        if fillna_val is not None:
            if np.isnan(obs_x):
                obs_x = -9999
            bs_sim_x_idx_null = np.isnan(bs_sim_x)
            bs_sim_x[bs_sim_x_idx_null] = fillna_val
            # bs_sim_y_idx_null = np.isnan(bs_sim_y)
            # bs_sim_y[bs_sim_y_idx_null] = fillna_val
        else:
            
                sys.exit("error: missing values present; this may throw off the interpolation")
    # sort obs values
    # sorted_idx_obs = np.argsort(obs_x)
    # obs_x = obs_x[sorted_idx_obs]
    # sort simulated values
    sorted_idx_sim = np.argsort(bs_sim_y)
    bs_sim_x = bs_sim_x[sorted_idx_sim]
    bs_sim_y = bs_sim_y[sorted_idx_sim]

    # Perform interpolation
    return np.interp(obs_x, bs_sim_x, bs_sim_y)


ds_bs_corrs_and_emp_cdf = xr.open_dataset(f_zarr_ds_bs_corrs_and_emp_cdf, engine = "zarr", chunks = ds_bs_sim_chunks)

val_some_na = ds_bs_corrs_and_emp_cdf['ppc'].sel(x=x_some_na, y = y_some_na).to_series().dropna()
val_most_na = ds_bs_corrs_and_emp_cdf['ppc'].sel(x=x_most_na, y = y_most_na).to_series().dropna()
# print("verifying that x and y locs with missing values still have valid rejection thresholds:")
# print(f"rejection threshold at loc with at {num_na_some_na} missing value: {val_some_na:.3f}")
# print(f"rejection threshold at loc with at {num_na_most_na} missing values: {val_most_na:.3f}")


ds_obs_chunks = {'x': -1, 'y': -1}
ds_ppc_obs = xr.open_dataset(dif_ffa_ppct_obs, engine = "zarr", chunks = ds_obs_chunks)


da_ppc_obs_aligned, ds_bs_corrs_and_emp_cdf_aligned = xr.align(
    ds_ppc_obs['ppc'],
    ds_bs_corrs_and_emp_cdf[['ppc', 'emprical_cdf']],
    join='inner'  # Ensure only overlapping coordinates are retained
)

da_obs=da_ppc_obs_aligned
ds_sim=ds_bs_corrs_and_emp_cdf_aligned

obs_x_og = da_obs.sel(x=x_most_na, y = y_most_na).values
bs_sim_x_og = ds_sim['ppc'].sel(x=x_most_na, y = y_most_na).values
bs_sim_y_og = ds_sim['emprical_cdf'].sel(x=x_most_na, y = y_most_na).values

da_ppc = xr.apply_ufunc(
    interpolate_cdf,
    da_obs,
    ds_sim['ppc'],         
    ds_sim['emprical_cdf'],
    input_core_dims=[[], ['bs_id'], ['bs_id']], 
    vectorize=True,                              # Enable vectorized operations
    dask="parallelized",                         # Parallelize using Dask
    output_dtypes=[float],                       # Output data type
    # join = 'outer',
    output_core_dims=[[]],                        # Output should not have 'bs_id' dimension
    dask_gufunc_kwargs={"allow_rechunk": True},   # Allow automatic rechunking if necessary
    kwargs={"fillna_val":-9999}
)

da_ppc = da_ppc.load()
da_ppc.name = "obs_ppct_pvals"
if len(da_ppc.to_dataframe()[da_ppc.name].dropna()) == 0:
    print("All results are nan")
# export to zarr file
bm_time = time.time()
delete_zarr(dif_ffa_ppct_obs_pvalues)
da_ppc.chunk("auto").to_zarr(dif_ffa_ppct_obs_pvalues, mode='w', encoding = return_dic_zarr_encodingds(da_ppc, clevel=5), consolidated=True)
print(f"Exported da_ppc ({(time.time() - bm_time)/60:.2f} min")

#%% inspecting
ds_ppct_pvalues = xr.open_dataset(dif_ffa_ppct_obs_pvalues, engine = "zarr", chunks = "auto").load()
ds_ppct_pvalues.where(ds_obs_flood_probs["max_wlevel_m"].max(dim = "event_number") > nuisance_threshold).to_dataframe().dropna()["obs_ppct_pvals"].hist()

#%% compare with xr.quantile at select coordinates
if testing:
    ds_bs_corrs_and_emp_cdf = xr.open_dataset(f_zarr_ds_bs_corrs_and_emp_cdf, engine = "zarr", chunks = ds_bs_sim_chunks)
    ds_ppc_obs = xr.open_dataset(dif_ffa_ppct_obs, engine = "zarr", chunks = "auto")
    ds_bs_corrs_rej_thresh = xr.open_dataset(dif_ffa_ppct_rej_threshold, engine = "zarr").load()
    ds_ppct_pvalues = xr.open_dataset(dif_ffa_ppct_obs_pvalues, engine = "zarr", chunks = "auto").load()

    df_sim_locs_for_testing = pd.read_csv(f"{dir_ffa_scripts_local_scratch}df_sim_locs_for_testing.csv")
    df_obs_locs_for_testing = pd.read_csv(f"{dir_ffa_scripts_local_scratch}df_obs_locs_for_testing.csv")


    xy_test = df_sim_locs_for_testing.loc[:, ["x", "y"]].drop_duplicates()

    quants = np.linspace(0,1,101)

    for idx, row in tqdm(xy_test.iterrows()):
        x = row["x"]
        y = row["y"]
        # extract empirical cdf of ppc's for single location
        ds_1loc = ds_bs_corrs_and_emp_cdf.sel(x=x, y=y, method = "nearest")
        df_1loc = ds_1loc.to_dataframe()
        df_1loc = df_1loc.sort_values("emprical_cdf").reset_index(drop=True)
        # perform statistical test like i do above
        obs_ppc_1loc = ds_ppc_obs.sel(x=x, y=y, method = "nearest")["ppc"].values
        pvalue = interpolate_cdf(obs_ppc_1loc, df_1loc["ppc"], df_1loc["emprical_cdf"])
        result_from_fxn = "reject"
        if pvalue >= ppct_alpha:
            result_from_fxn = "fail_to_reject"
        # compare with xarray result
        s_quants_from_xr = ds_1loc["ppc"].quantile(quants, method = "hazen").to_dataframe()["ppc"]
        ppc_threshold = s_quants_from_xr.loc[ppct_alpha]
        # also pull from the exported dataset to verify the threshold
        ppc_threshold_from_exported_dataset = ds_bs_corrs_rej_thresh.sel(x=x, y=y, method = "nearest")["ppc"].values
        if not np.isclose(ppc_threshold, ppc_threshold_from_exported_dataset, rtol=0.01):
            sys.exit("The exported threshold is different for some reason")
        # finally, pull the p-value derived above
        pvalue_from_exported_dataset = ds_ppct_pvalues.sel(x=x, y=y, method = "nearest")["obs_ppct_pvals"].values

        if not np.isclose(pvalue, pvalue_from_exported_dataset, rtol=0.001):
            sys.exit("The calculated p values are different different for some reason")

        result_from_xr = "reject"
        if obs_ppc_1loc > ppc_threshold:
            result_from_xr = "fail_to_reject"
        if result_from_xr != result_from_fxn:
            sys.exit("what's going on here?")

        # sys.exit("work")
        # Create subplots
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))
        # Plot each column on a different subplot
        df_1loc['ppc'].plot(ax=axes[0])
        axes[0].set_title("PPC_of_BS_samples_ordered")
        
        s_quants_from_xr.plot(ax = axes[1])
        axes[1].set_title("Xarray Computed PPC Quantiles")
        plt.show()
