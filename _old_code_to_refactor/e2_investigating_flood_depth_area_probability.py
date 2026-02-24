# %%
from local.__inputs import (
    F_SIM_FLOOD_PROBS_COMPARE,
    F_SIM_FLOOD_PROBS_BOOTSTRAPPED,
    F_SIM_FLOOD_PROBS_EVENT_NUMBER_MAPPING,
    SUBAREAS_FOR_COMPUTING_IMPACT_RETURN_PDS,
    ALPHA,
    BETA,
    N_YEARS_SYNTHESIZED,
    ASSIGN_DUP_VALS_MAX_RETURN,
    F_DESIGN_STORM_TSERIES_BASED_ON_SSR,
    F_TRITON_OUTPUTS_DSGN,
    F_MITIGATION_AOIS,
    F_WSHED_SHP,
    F_ROADS,
    F_BUILDINGS,
    F_PARCELS,
    F_SIDEWALKS,
    F_BUILDINGS_NO_BUFFER,
    F_FLOOD_IMPACT_RETURN_PERIODS_BY_AOI,
    TARGET_DESIGN_STORM_DURATION_HRS_FOR_COMPARISON,
    F_IMPACTED_FEATURE_MIN_RETURN_PDS,
    DIR_IMPACT_BASED_FFA,
    DIC_DPTH_DSC_LOOKUP,
    N_BS_SAMPLES,
    F_SCRATCH_FLOODAREA_RTRN_BS,
    FLD_RTRN_PD_ALPHA,
    F_FLOOD_IMPACT_BS_UNCERTAINTY_CI,
    F_BS_UNCERTAINTY_EVENTS_IN_CI,
    F_FLOOD_IMPACT_BS_UNCERTAINTY_EVENTS_IN_CI,
)
from local.__utils import (
    create_flood_metric_mask,
    compute_floodarea_retrn_pds,
    delete_zarr,
    return_dic_zarr_encodingds,
    delete_directory,
    return_mask_dataset_from_polygon,
    compute_return_periods_for_series,
    return_indices_of_series_geq_lb_and_leq_ub,
)
from local.__plotting import return_colorbar_extend
import matplotlib.colors as mcolors
import zarr
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
import sys
import shutil
from scipy.stats.mstats import plotting_positions
import time
from glob import glob
import os
import gc
from pathlib import Path
import pandas as pd

# import rioxarray
import geopandas as gpd
from tqdm import tqdm

# import geopandas as gpd
import rasterio

# import numpy as np
import rioxarray as rxr
from rasterio.features import shapes
from shapely.geometry import shape

f_dsgn_tseries = F_DESIGN_STORM_TSERIES_BASED_ON_SSR

ds_dsgn_tseries = xr.open_dataset(f_dsgn_tseries)

ds_triton_dsgn = xr.open_dataset(F_TRITON_OUTPUTS_DSGN, engine="zarr").chunk("auto")

max_dsgn_wlevel = ds_triton_dsgn.max_wlevel_m.sel(
    data_source="dsgn", simtype="compound", model="tritonswmm"
)

ds_sim_flood_probs = xr.open_dataset(F_SIM_FLOOD_PROBS_COMPARE, engine="zarr").chunk(
    dict(x=10, y=10, event_number=-1, sim_form=1)
)

if Path(F_SIM_FLOOD_PROBS_BOOTSTRAPPED).exists():
    ds_sim_flood_probs_bs = xr.open_dataset(
        F_SIM_FLOOD_PROBS_BOOTSTRAPPED, engine="zarr"
    ).chunk(dict(bs_id=-1, x=100, y=100, return_pd_yrs=1))
else:
    print(
        "Bootstrapped ensemble-based flood depths file does not exist so confidence intervals cannot be included in the plots."
    )
    ds_sim_flood_probs_bs = None

df_sim_flood_probs_event_num_mapping = pd.read_csv(
    F_SIM_FLOOD_PROBS_EVENT_NUMBER_MAPPING, index_col="event_number"
)


gdf_mitigation_aois = gpd.read_file(F_MITIGATION_AOIS)
gdf_mitigation_aois = gdf_mitigation_aois[
    gdf_mitigation_aois["name"].isin(SUBAREAS_FOR_COMPUTING_IMPACT_RETURN_PDS)
].reset_index(drop=True)


gdf_roads = gpd.read_file(F_ROADS)
gdf_roads.index.name = "road_segment_id"
gdf_bldngs = gpd.read_file(F_BUILDINGS)
gdf_bldngs.index.name = "building_id"
gdf_parcels = gpd.read_file(F_PARCELS)
gdf_parcels.index.name = "parcel_id"
gdf_sidewalks = gpd.read_file(F_SIDEWALKS)
gdf_sidewalks.index.name = "sidewalk_id"

# no buffer buildings for plotting
gdf_bldngs_no_buffer = gpd.read_file(F_BUILDINGS_NO_BUFFER)
gdf_bldngs_no_buffer.index.name = "building_id"

gdf_all_features = pd.concat(
    [
        gdf_roads.reset_index(),
        gdf_sidewalks.reset_index(),
        gdf_bldngs_no_buffer.reset_index(),
        gdf_parcels.reset_index(),
    ]
).reset_index()

da_road_raster = create_flood_metric_mask(gdf_roads, ds_sim_flood_probs)
da_road_raster = da_road_raster.where(da_road_raster > -1)
da_road_raster.name = gdf_roads.index.name

da_bldng_raster = create_flood_metric_mask(gdf_bldngs, ds_sim_flood_probs)
da_bldng_raster = da_bldng_raster.where(da_bldng_raster > -1)
da_bldng_raster.name = gdf_bldngs.index.name

da_parcel_raster = create_flood_metric_mask(gdf_parcels, ds_sim_flood_probs)
da_parcel_raster = da_parcel_raster.where(da_parcel_raster > -1)
da_parcel_raster.name = gdf_parcels.index.name

da_sidewalk_raster = create_flood_metric_mask(gdf_sidewalks, ds_sim_flood_probs)
da_sidewalk_raster = da_sidewalk_raster.where(da_sidewalk_raster > -1)
da_sidewalk_raster.name = gdf_sidewalks.index.name


ds_features = xr.merge(
    [da_road_raster, da_bldng_raster, da_parcel_raster, da_sidewalk_raster]
)

target_design_storms_years = ds_triton_dsgn.year.values

# peaks over threshold results
cols_event_idx = ["event_type", "year", "event_id"]

# load event univariate return periods

# %% computing flooded areas by depth ranges
val = input(
    f"type 'yes' to re-calculate return periods flood area return periods event if the output file already exists."
)
rewrite_zarrs = False
if val.lower() == "yes":
    rewrite_zarrs = True

lst_impact_feature_rasters = [da_road_raster, da_bldng_raster]

chnk_dic_output = dict(subarea_name=1, depth_range_m=1, event_number=-1)
chnk_dic_feature_impact_min_rtrn = dict(subarea_name=1, depth_range_m=1)
lst_sim_forms = ds_sim_flood_probs.sim_form.to_series().to_list() + [
    "tritonswmm.design_storm_multidriver",
    "tritonswmm.design_storm_rain_only",
    "tritonswmm.design_storm_surge_only",
]
if (rewrite_zarrs == True) or (not Path(F_FLOOD_IMPACT_RETURN_PERIODS_BY_AOI).exists()):
    lst_ds_impact_by_aoi = []
    lst_ds_feature_impact_rtrn = []
    for sim_form in tqdm(lst_sim_forms):
        if "design_storm" in sim_form:  # process design storms
            # identify the event ID corresponding to the central estimate of rainfall depth for the targeted design storm duration
            df_rain_tseries = ds_dsgn_tseries.sel(event_type="compound")[
                "mm_per_hr"
            ].to_dataframe()
            tstep = pd.Series(
                df_rain_tseries.loc[pd.IndexSlice[1, 1, :]].index.diff()
            ).mode()[0]
            s_rain_event_durations = (
                df_rain_tseries[df_rain_tseries["mm_per_hr"] > 0]
                .groupby(["year", "event_id"])["mm_per_hr"]
                .size()
                * tstep
                / np.timedelta64(1, "h")
            )
            s_rain_event_durations.name = "design_storm_rain_duration_hrs"
            s_rain_event_depths = (
                df_rain_tseries[df_rain_tseries["mm_per_hr"] > 0]
                .groupby(["year", "event_id"])["mm_per_hr"]
                .mean()
                * s_rain_event_durations
            )
            s_rain_event_depths.name = "design_storm_depth_mm"
            df_design_storm_stats = pd.concat(
                [s_rain_event_durations, s_rain_event_depths], axis=1
            )
            df_design_storm_stats_trgt_dur = df_design_storm_stats[
                df_design_storm_stats["design_storm_rain_duration_hrs"]
                == TARGET_DESIGN_STORM_DURATION_HRS_FOR_COMPARISON
            ]
            df_median_depths = df_design_storm_stats_trgt_dur.groupby("year")[
                "design_storm_depth_mm"
            ].median()
            mask_target_depths = df_design_storm_stats_trgt_dur[
                "design_storm_depth_mm"
            ].isin(df_median_depths)
            event_id = (
                df_design_storm_stats_trgt_dur[mask_target_depths]
                .reset_index()["event_id"]
                .unique()
            )
            if len(event_id) > 1:
                sys.exit(
                    f"ERROR: there is more than 1 event ID corresponding to the central {TARGET_DESIGN_STORM_DURATION_HRS_FOR_COMPARISON} hour rain depth estimate for each return period"
                )

            if "multidriver" in sim_form:
                event_type = "compound"
            elif "rain_only" in sim_form:
                event_type = "rain"
            elif "surge_only" in sim_form:
                event_type = "surge"
                event_id = (
                    ds_dsgn_tseries.sel(event_type="surge")["surge_m"]
                    .to_dataframe()
                    .dropna()
                    .reset_index()
                    .event_id.unique()
                )
                # sys.exit('work')
            else:
                sys.exit("sim form not recognized")

            da_sim_wlevel = (
                ds_triton_dsgn.sel(
                    event_type=event_type,
                    simtype="compound",
                    model="tritonswmm",
                    data_source="dsgn",
                    event_id=event_id,
                )
                .reset_coords()
                .squeeze()["max_wlevel_m"]
            ).chunk(x=5, y=5, event_number=-1)
            if len(da_sim_wlevel.sel(year=100).to_dataframe().dropna()) == 0:
                sys.exit("no valid values in this simulation")

            da_sim_wlevel = da_sim_wlevel.rename(dict(year="event_number"))
            da_sim_wlevel.attrs["design_storms"] = True
            gc.collect()
            ds_flood_impacts_by_aoi, ds_feature_impact_min_rtrn_pd = (
                compute_floodarea_retrn_pds(
                    da_sim_wlevel,
                    ds_features,
                    gdf_mitigation_aois,
                    N_YEARS_SYNTHESIZED,
                    ALPHA,
                    BETA,
                    ASSIGN_DUP_VALS_MAX_RETURN,
                )
            )
        else:
            da_sim_wlevel = (
                ds_sim_flood_probs["max_wlevel_m"]
                .sel(sim_form=sim_form)
                .chunk(x=5, y=5, event_number=-1)
            )
            da_sim_wlevel.attrs["design_storms"] = False
            # da_sim_wlevel, lst_impact_feature_rasters, LST_KEY_FLOOD_THRESHOLDS_FOR_SENSITIVITY_ANALYSIS, gdf_mitigation_aois, alpha, beta
            gc.collect()
            ds_flood_impacts_by_aoi, ds_feature_impact_min_rtrn_pd = (
                compute_floodarea_retrn_pds(
                    da_sim_wlevel,
                    ds_features,
                    gdf_mitigation_aois,
                    N_YEARS_SYNTHESIZED,
                    ALPHA,
                    BETA,
                    ASSIGN_DUP_VALS_MAX_RETURN,
                )
            )
        ds_flood_impacts_by_aoi = ds_flood_impacts_by_aoi.assign_coords(
            sim_form=sim_form
        )
        ds_flood_impacts_by_aoi = ds_flood_impacts_by_aoi.expand_dims("sim_form")
        ds_feature_impact_min_rtrn_pd = ds_feature_impact_min_rtrn_pd.assign_coords(
            sim_form=sim_form
        )
        ds_feature_impact_min_rtrn_pd = ds_feature_impact_min_rtrn_pd.expand_dims(
            "sim_form"
        )
        # expand dimensions
        lst_ds_impact_by_aoi.append(ds_flood_impacts_by_aoi)
        lst_ds_feature_impact_rtrn.append(ds_feature_impact_min_rtrn_pd)
    ds_flood_impacts_by_aoi = xr.concat(lst_ds_impact_by_aoi, dim="sim_form")
    delete_zarr(F_FLOOD_IMPACT_RETURN_PERIODS_BY_AOI, attempt_time_limit_s=10)
    ds_flood_impacts_by_aoi.chunk(chnk_dic_output).to_zarr(
        F_FLOOD_IMPACT_RETURN_PERIODS_BY_AOI,
        mode="w",
        encoding=return_dic_zarr_encodingds(ds_flood_impacts_by_aoi, clevel=5),
        consolidated=True,
    )
    # ds_impacted_feature_count_rtrn_pds.chunk(chnk_dic_output).to_zarr(f_impacted_feature_count_return_pds, mode='w', encoding = return_dic_zarr_encodingds(ds_impacted_feature_count_rtrn_pds, clevel=5), consolidated=True)
    ds_feature_impact_min_rtrn_pd = xr.concat(
        lst_ds_feature_impact_rtrn, dim="sim_form"
    )
    delete_zarr(F_IMPACTED_FEATURE_MIN_RETURN_PDS, attempt_time_limit_s=10)
    ds_feature_impact_min_rtrn_pd.chunk(chnk_dic_feature_impact_min_rtrn).to_zarr(
        F_IMPACTED_FEATURE_MIN_RETURN_PDS,
        mode="w",
        encoding=return_dic_zarr_encodingds(ds_feature_impact_min_rtrn_pd, clevel=5),
        consolidated=True,
    )
    print(f"wrote flood impact return period files")
else:
    print(f"Loading from file")

# ds_flood_impacts_by_aoi = xr.open_dataset(f_flooded_areas_return_pds_by_aoi_and_dpth_rnge, engine = "zarr").chunk(chnk_dic_output)
# ds_impacted_feature_count_rtrn_pds = xr.open_dataset(f_impacted_feature_count_return_pds, engine = "zarr").chunk(chnk_dic_output)
ds_flood_impacts_by_aoi = xr.open_dataset(
    F_FLOOD_IMPACT_RETURN_PERIODS_BY_AOI, engine="zarr"
).chunk(chnk_dic_output)
ds_feature_impact_min_rtrn_pd = xr.open_dataset(
    F_IMPACTED_FEATURE_MIN_RETURN_PDS, engine="zarr"
).chunk(chnk_dic_feature_impact_min_rtrn)
# %% create maps of feature impact return period using geodataframes
import matplotlib as mp

DIR_IMPACT_BASED_FFA
dir_plot = f"{DIR_IMPACT_BASED_FFA}plots/feature_impact_return_periods/"
delete_directory(dir_plot)
Path(dir_plot).mkdir(parents=True, exist_ok=True)

shapefile_path = F_WSHED_SHP

# cmap_name_rtrn_pd = "plasma_r"


# cmap_name_rtrn_pd = "autumn"
# cmap_name_rtrn_pd = "cividis"
# cmap_name_rtrn_pd = "GnBu_r"

features_to_skip = ["parcel_id", "sidewalk_id"]
# features_to_skip = []

target_rtrn_pds = [0.5, 1, 2, 10, 50, 100, 200]
bin_labs_aap = np.sort((1 / np.asarray(target_rtrn_pds)))
cmap_name_rtrn_pd = "YlOrRd"

bin_labs = bin_labs_aap

# bin_lab_rtrn_logspace_vals = np.log10(bin_labs_rtrn)

cmap_rtrn_pd = plt.get_cmap(cmap_name_rtrn_pd)
cmap_rtrn_pd.set_bad("white")
# cmap_rtrn_pd.set_over('white')
# cmap_rtrn_pd.set_under('white')
# cmap_rtrn_pd.set_under('pink')
norm_rtrn_pd = mcolors.BoundaryNorm(bin_labs, cmap_rtrn_pd.N)
# norm_rtrn_pd = None

smallest_probability_limit = 0

# subarea_name = "watershed"
# depth_range_m = "[0.03,0.1)"
# depth_range_m = "[0.1,inf)"
# depth_range_m = "[0.3,inf)"

for depth_range_m in ds_feature_impact_min_rtrn_pd.depth_range_m.to_series():
    for sim_form in ds_flood_impacts_by_aoi.sim_form.to_series():
        for subarea_name in SUBAREAS_FOR_COMPUTING_IMPACT_RETURN_PDS:
            ds_impact_rtrn_for_aoi_and_dpth = ds_feature_impact_min_rtrn_pd.sel(
                subarea_name=subarea_name,
                depth_range_m=depth_range_m,
                sim_form=sim_form,
            )
            fig, ax = plt.subplots(dpi=300, figsize=(5, 4))
            ax.set_facecolor("lightgray")
            gdf = gpd.read_file(shapefile_path)
            gdf.boundary.plot(ax=ax, color="black", linewidth=1, zorder=50)
            lst_s_for_cbar = []
            for feature_impacted in ds_impact_rtrn_for_aoi_and_dpth.data_vars:
                df_feature_impact_rtrn = ds_impact_rtrn_for_aoi_and_dpth[
                    feature_impacted
                ].to_dataframe()[feature_impacted]
                # df_feature_impact_rtrn = df_feature_impact_rtrn.fillna(max(bin_labs_rtrn)*10)

                feature_idx_name = df_feature_impact_rtrn.index.name
                if feature_idx_name in features_to_skip:
                    continue

                idx_features = ~gdf_all_features[feature_idx_name].isnull()
                gdf_plotting_features = gdf_all_features[idx_features]
                # gdf_plotting_features.plot(ax = ax)

                int_idx = (
                    gdf_plotting_features.loc[:, feature_idx_name].astype(int).values
                )

                gdf_plotting_features = gdf_plotting_features.set_index(
                    feature_idx_name
                )

                gdf_plotting_features.index = int_idx

                # gdf_plotting_features = gdf_plotting_features.set_index(feature_idx_name)

                gdf_feature_impact_return_period = gdf_plotting_features.join(
                    df_feature_impact_rtrn, how="right"
                )
                gdf_feature_impact_return_period[feature_impacted] = (
                    1 / gdf_feature_impact_return_period[feature_impacted]
                )
                gdf_feature_impact_return_period[
                    "color"
                ] = gdf_feature_impact_return_period[feature_impacted].apply(
                    lambda x: "white" if pd.isna(x) else cmap_rtrn_pd(norm_rtrn_pd(x))
                )
                # gdf_feature_impact_return_period[feature_impacted] = gdf_feature_impact_return_period[feature_impacted].fillna(smallest_probability_limit)

                gdf_feature_impact_return_period = gpd.clip(
                    gdf_feature_impact_return_period, gdf
                )
                # lines = gdf_feature_impact_return_period.boundary
                # print(gdf_feature_impact_return_period.type.iloc[0].lower())

                if "polygon" in gdf_feature_impact_return_period.type.iloc[0].lower():
                    # print("plotting polygon")
                    # gdf_feature_impact_return_period.plot(column=feature_impacted, ax = ax, cmap = cmap_rtrn_pd, norm = norm_rtrn_pd, linewidth = 0.75, zorder = 7)
                    gdf_feature_impact_return_period.plot(
                        ax=ax,
                        color=gdf_feature_impact_return_period["color"],
                        linewidth=0.75,
                        zorder=7,
                    )
                    gdf_feature_impact_return_period.boundary.plot(
                        ax=ax, color="k", linewidth=0.15, zorder=8
                    )
                else:
                    gdf_feature_impact_return_period.plot(
                        ax=ax, color="k", linewidth=1.1, zorder=9
                    )
                    # gdf_feature_impact_return_period.plot(column=feature_impacted, ax = ax, cmap = cmap_rtrn_pd, norm = norm_rtrn_pd, linewidth = 0.75, zorder = 10)
                    gdf_feature_impact_return_period.plot(
                        ax=ax,
                        color=gdf_feature_impact_return_period["color"],
                        linewidth=0.75,
                        zorder=10,
                    )
                    # sys.exit('work')

                # save a shapefile that has the return period
                if "road" in feature_idx_name:
                    f_roads_return_periods = (
                        F_ROADS.split(".shp")[0]
                        + f"_{DIC_DPTH_DSC_LOOKUP[depth_range_m]}_aep_{sim_form}.shp"
                    )
                    gdf_feature_impact_return_period.loc[
                        :, [feature_impacted, "geometry"]
                    ].to_file(f_roads_return_periods)
                if "building" in feature_idx_name:
                    f_buildings_return_periods = (
                        F_BUILDINGS.split(".shp")[0]
                        + f"_{DIC_DPTH_DSC_LOOKUP[depth_range_m]}_aep_{sim_form}.shp"
                    )
                    gdf_feature_impact_return_period.loc[
                        :, [feature_impacted, "geometry"]
                    ].to_file(f_buildings_return_periods)
                lst_s_for_cbar.append(
                    gdf_feature_impact_return_period[feature_impacted]
                )
            cbar = plt.colorbar(
                mp.cm.ScalarMappable(norm=norm_rtrn_pd, cmap=cmap_rtrn_pd),
                ax=ax,
                extend=return_colorbar_extend(pd.concat(lst_s_for_cbar), norm_rtrn_pd),
            )
            cbar.set_ticks(bin_labs)
            cbar.set_ticklabels(bin_labs)
            cbar.set_label("annual flood frequency")  # , fontsize=12)

            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_xlabel("")
            ax.set_ylabel("")
            ax.set_aspect("equal")
            ax.set_title(
                f"return period of building\n and road segment exposure\nto {DIC_DPTH_DSC_LOOKUP[depth_range_m]} flooding {depth_range_m}\n{sim_form}"
            )
            fig.tight_layout()
            # sys.exit()
            plt.savefig(
                f"{dir_plot}{DIC_DPTH_DSC_LOOKUP[depth_range_m]}_feature_impact_return_pds_{subarea_name}_{sim_form}.png",
                bbox_inches="tight",
            )
            plt.clf()
print(f"saved figures to {dir_plot}")

# %% plot differences with TRITON-SWMM multidriver simulation formulation
dir_plot = f"{DIR_IMPACT_BASED_FFA}plots/feature_impact_prob_diffs/"
delete_directory(dir_plot)
Path(dir_plot).mkdir(parents=True, exist_ok=True)


target_rtrn_pd_diffs = [-100, -50, -10, -2, -1, 1, 2, 10, 50, 100]


bin_labs_aap_diffs = np.sort((1 / np.asarray(target_rtrn_pd_diffs)))
cmap_name_rtrn_pd = "RdBu"

bin_labs = bin_labs_aap_diffs

# bin_lab_rtrn_logspace_vals = np.log10(bin_labs_rtrn)

cmap_rtrn_pd = plt.get_cmap(cmap_name_rtrn_pd)
cmap_rtrn_pd.set_bad("white")
# cmap_rtrn_pd.set_over('white')
# cmap_rtrn_pd.set_under('white')
# cmap_rtrn_pd.set_under('pink')
norm_rtrn_pd = mcolors.BoundaryNorm(bin_labs, cmap_rtrn_pd.N)

sim_form_comp = "tritonswmm.multidriver"

for depth_range_m in ds_feature_impact_min_rtrn_pd.depth_range_m.to_series():
    for sim_form in ds_flood_impacts_by_aoi.sim_form.to_series():
        if sim_form == sim_form_comp:
            continue
        ds_impact_rtrn_for_aoi_and_dpth_tritonswmm_multidriver = (
            ds_feature_impact_min_rtrn_pd.sel(
                subarea_name=subarea_name,
                depth_range_m=depth_range_m,
                sim_form=sim_form_comp,
            )
        )

        ds_impact_rtrn_for_aoi_and_dpth = ds_feature_impact_min_rtrn_pd.sel(
            subarea_name=subarea_name, depth_range_m=depth_range_m, sim_form=sim_form
        )
        fig, ax = plt.subplots(dpi=300, figsize=(5, 4))
        ax.set_facecolor("lightgray")
        gdf = gpd.read_file(shapefile_path)
        gdf.boundary.plot(ax=ax, color="black", linewidth=1, zorder=50)
        lst_s_for_cbar = []
        for feature_impacted in ds_impact_rtrn_for_aoi_and_dpth.data_vars:
            # sys.exit('work')

            df_feature_impact_rtrn = ds_impact_rtrn_for_aoi_and_dpth[
                feature_impacted
            ].to_dataframe()[feature_impacted]
            df_feature_impact_rtrn_ts_multidriver = (
                ds_impact_rtrn_for_aoi_and_dpth_tritonswmm_multidriver[
                    feature_impacted
                ].to_dataframe()[feature_impacted]
            )
            if (
                "design_storm" in sim_form
            ):  # assign a minimum return period of 1 to ts_multidriver results; conventional design storms cannot be used to estimate subannaul return periods
                # so without this adjustment, the comparison could give a false impression of the magnitude and extent that conventional design storms underestimate probability
                idx_ts_multdriver_lt1 = df_feature_impact_rtrn_ts_multidriver[
                    df_feature_impact_rtrn_ts_multidriver < 1
                ].index
                df_feature_impact_rtrn_ts_multidriver.loc[idx_ts_multdriver_lt1] = 1

            feature_idx_name = df_feature_impact_rtrn.index.name
            if feature_idx_name in features_to_skip:
                continue

            idx_features = ~gdf_all_features[feature_idx_name].isnull()
            gdf_plotting_features = gdf_all_features[idx_features]
            # gdf_plotting_features.plot(ax = ax)

            int_idx = gdf_plotting_features.loc[:, feature_idx_name].astype(int).values

            gdf_plotting_features = gdf_plotting_features.set_index(feature_idx_name)

            gdf_plotting_features.index = int_idx

            # gdf_plotting_features = gdf_plotting_features.set_index(feature_idx_name)

            # compute difference with sim form TRITONSWMM multi drivers
            gdf_feature_impact_return_period_ts_multidriver = (
                gdf_plotting_features.join(
                    df_feature_impact_rtrn_ts_multidriver, how="right"
                )
            )
            gdf_feature_impact_return_period_ts_multidriver[feature_impacted] = (
                1 / gdf_feature_impact_return_period_ts_multidriver[feature_impacted]
            )

            gdf_feature_impact_return_period_comp = gdf_plotting_features.join(
                df_feature_impact_rtrn, how="right"
            )
            gdf_feature_impact_return_period_comp[feature_impacted] = (
                1 / gdf_feature_impact_return_period_comp[feature_impacted]
            )

            loc_both_na = (
                gdf_feature_impact_return_period_comp[feature_impacted].isna()
                & gdf_feature_impact_return_period_ts_multidriver[
                    feature_impacted
                ].isna()
            )
            idx_both_na = gdf_feature_impact_return_period_comp[loc_both_na].index

            gdf_feature_impact_return_period_ts_multidriver[feature_impacted] = (
                gdf_feature_impact_return_period_ts_multidriver[
                    feature_impacted
                ].fillna(smallest_probability_limit)
            )
            gdf_feature_impact_return_period_comp[feature_impacted] = (
                gdf_feature_impact_return_period_comp[feature_impacted].fillna(
                    smallest_probability_limit
                )
            )

            gdf_feature_impact_return_period_diff = (
                gdf_feature_impact_return_period_comp[feature_impacted]
                - gdf_feature_impact_return_period_ts_multidriver[feature_impacted]
            )
            gdf_feature_impact_return_period_diff.loc[idx_both_na] = np.nan
            # alternative minus triton swmm multidriver probability
            # a negative difference indicates that TS multidriver shows a HIGHER probability which would indicate that the alternative approach underestimates probability

            gdf_feature_impact_return_period = gdf_plotting_features.copy()
            gdf_feature_impact_return_period[feature_impacted] = (
                gdf_feature_impact_return_period_diff
            )

            gdf_feature_impact_return_period["color"] = (
                gdf_feature_impact_return_period[feature_impacted].apply(
                    lambda x: "white" if pd.isna(x) else cmap_rtrn_pd(norm_rtrn_pd(x))
                )
            )

            gdf_feature_impact_return_period = gpd.clip(
                gdf_feature_impact_return_period, gdf
            )
            # lines = gdf_feature_impact_return_period.boundary
            # print(gdf_feature_impact_return_period.type.iloc[0].lower())

            if "polygon" in gdf_feature_impact_return_period.type.iloc[0].lower():
                # print("plotting polygon")
                gdf_feature_impact_return_period.plot(
                    ax=ax,
                    color=gdf_feature_impact_return_period["color"],
                    linewidth=0.75,
                    zorder=7,
                )
                gdf_feature_impact_return_period.boundary.plot(
                    ax=ax, color="k", linewidth=0.15, zorder=8
                )
            else:
                gdf_feature_impact_return_period.plot(
                    ax=ax, color="k", linewidth=1.1, zorder=9
                )
                gdf_feature_impact_return_period.plot(
                    ax=ax,
                    color=gdf_feature_impact_return_period["color"],
                    linewidth=0.75,
                    zorder=10,
                )

            lst_s_for_cbar.append(
                gdf_feature_impact_return_period[feature_impacted].dropna()
            )
        cbar = plt.colorbar(
            mp.cm.ScalarMappable(norm=norm_rtrn_pd, cmap=cmap_rtrn_pd),
            ax=ax,
            extend=return_colorbar_extend(pd.concat(lst_s_for_cbar), norm_rtrn_pd),
        )
        cbar.set_ticks(bin_labs)
        cbar.set_ticklabels(bin_labs)
        cbar.set_label("annual flood frequency difference")  # , fontsize=12)

        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.set_aspect("equal")
        ax.set_title(
            f"return period of building\n and road segment exposure\nto {DIC_DPTH_DSC_LOOKUP[depth_range_m]} flooding {depth_range_m}\n{sim_form} minus\n{sim_form_comp}"
        )
        fig.tight_layout()
        # sys.exit('work')
        plt.savefig(
            f"{dir_plot}feature_impact_aap_diffs_{subarea_name}_{sim_form}_minus_{sim_form_comp}_{DIC_DPTH_DSC_LOOKUP[depth_range_m]}.png",
            bbox_inches="tight",
        )
        plt.clf()
print(f"saved figures to {dir_plot}")

# %% create maps of feature impact return period using feature rasters for qaqc
# shapefile_path = f_wshed_shp
# features_to_skip = ["parcel_id", "sidewalk_id"]
# cmap_name_rtrn_pd = "plasma_r"
# cmap_name_rtrn_pd = "YlOrRd_r"
# cmap_name_rtrn_pd = "autumn"
# cmap_name_rtrn_pd = "cividis"
# cmap_name_rtrn_pd = "inferno"
# cmap_name_rtrn_pd = "GnBu_r"

# bin_labs_rtrn = [0.5,1,2,10,50,100, 200]

# bin_lab_rtrn_logspace_vals = np.log10(bin_labs_rtrn)

# cmap_rtrn_pd = plt.get_cmap(cmap_name_rtrn_pd)
# cmap_rtrn_pd.set_bad('none')
# cmap_rtrn_pd.set_over('white')
# norm_rtrn_pd = mcolors.BoundaryNorm(bin_lab_rtrn_logspace_vals, cmap_rtrn_pd.N)
# norm_rtrn_pd = None

target_rtrn_pds = [0.5, 1, 2, 10, 50, 100, 200]
# bin_labs_aap = np.sort((1/np.asarray(target_rtrn_pds)))
cmap_name_rtrn_pd = "YlOrRd"

bin_labs = target_rtrn_pds

# bin_lab_rtrn_logspace_vals = np.log10(bin_labs_rtrn)

cmap_rtrn_pd = plt.get_cmap(cmap_name_rtrn_pd)
cmap_rtrn_pd.set_bad("lightgray")
# cmap_rtrn_pd.set_over('white')
cmap_rtrn_pd.set_under("white")
# cmap_rtrn_pd.set_under('pink')
norm_rtrn_pd = mcolors.BoundaryNorm(bin_labs, cmap_rtrn_pd.N)

subarea_name = "watershed"
# depth_range_m = "[0.03,0.1)"
depth_range_m = "[0.1,inf)"
# depth_range_m = "[0.3,inf)"

ds_impact_rtrn_for_aoi_and_dpth = ds_feature_impact_min_rtrn_pd.sel(
    subarea_name=subarea_name, depth_range_m=depth_range_m, sim_form=sim_form_comp
)

zorder = 10
fig, ax = plt.subplots(dpi=200, figsize=(5, 4))
ax.set_facecolor("lightgray")
gdf = gpd.read_file(shapefile_path)
gdf.boundary.plot(ax=ax, color="black", linewidth=1, zorder=zorder)

for feature_impacted in ds_impact_rtrn_for_aoi_and_dpth.data_vars:
    zorder -= 1

    df_feature_impact_rtrn = ds_impact_rtrn_for_aoi_and_dpth[
        feature_impacted
    ].to_dataframe()[feature_impacted]

    feature_idx_name = df_feature_impact_rtrn.index.name
    if feature_idx_name in features_to_skip:
        continue
    da_features = ds_features[feature_idx_name]

    # fill missing with a super high value to be colored by the set_over property of the colormap
    df_feature_impact_rtrn = df_feature_impact_rtrn.fillna(max(target_rtrn_pds) * 10)

    da_feature_impact_return_period = (
        da_features.to_dataframe()
        .join(df_feature_impact_rtrn, on=feature_idx_name)
        .to_xarray()[feature_impacted]
    )

    # fig, ax = plt.subplots(dpi = 200, figsize = (5, 4))
    da_plot = da_feature_impact_return_period
    # shp_mask = create_mask_from_shapefile(da_plot, shapefile_path)
    da_mask = return_mask_dataset_from_polygon(da_plot, shapefile_path=shapefile_path)
    # da_mask.plot(x="x", y ="y")

    da_plot = da_plot.where(da_mask)

    # gdf = gpd.read_file(shapefile_path)
    # gdf.boundary.plot(ax=ax, color='black', linewidth=1)

    p_rtrn = da_plot.plot.pcolormesh(
        cmap=cmap_rtrn_pd,
        x="x",
        y="y",
        ax=ax,
        add_colorbar=False,
        norm=norm_rtrn_pd,
        zorder=zorder,
    )  # ,

cbar = plt.colorbar(p_rtrn, ax=ax, extend=return_colorbar_extend(da_plot, norm_rtrn_pd))
cbar.set_ticks(target_rtrn_pds)
cbar.set_ticklabels(target_rtrn_pds)
cbar.set_label("return period (years)")  # , fontsize=12)

# da_feature_impact_return_period.plot.pcolormesh(x="x", y = "y", ax = ax, )
ax.set_xticks([])
ax.set_yticks([])
ax.set_xlabel("")
ax.set_ylabel("")
# sys.exit('work')


# %% bootstrapping flood impact return periods by aoi
# print("only doing this for TRITONSWMM multidriver")

val = input(f"type 'yes' to draw bootstrapped samples of flooded areas.")
perform_bootstrapping = True
if val.lower() != "yes":
    perform_bootstrapping = False
if perform_bootstrapping:
    # identify all impacts being considered
    target_design_storms_years = ds_triton_dsgn.year.values
    bs_id_start = 0
    ar_sim_years = np.arange(N_YEARS_SYNTHESIZED)
    lst_bs_samps = []
    # define impact variables
    lst_impact_vars = []
    for var in ds_flood_impacts_by_aoi.data_vars:
        # print(var)
        if ("fraction" in var) or ("emp_cdf" in var) or ("return_pd_yrs" in var):
            continue
        lst_impact_vars.append(var)
    for bs_id in tqdm(np.arange(bs_id_start, N_BS_SAMPLES)):
        lst_df_rtrn_pds = []
        # draw bootstrapped years
        resampled_years = pd.Series(
            np.random.choice(ar_sim_years, size=N_YEARS_SYNTHESIZED, replace=True)
        )
        resampled_years = resampled_years[
            resampled_years.isin(df_sim_flood_probs_event_num_mapping["year"])
        ]
        resampled_event_numbers = (
            df_sim_flood_probs_event_num_mapping.reset_index()
            .set_index("year")
            .loc[resampled_years]["event_number"]
            .sort_values()
            .values
        )
        # loop through each impact variable and compute impact return periods for the bootstrapped sample
        for impact_var in lst_impact_vars:
            # load dataframe for bootstrapped sample
            df_bs_impact = ds_flood_impacts_by_aoi.sel(
                event_number=resampled_event_numbers
            )[impact_var].to_dataframe()
            # loop through each subarae name/depth range combo and compute impact return periods
            for grp_id, df_group in df_bs_impact.groupby(
                level=["subarea_name", "depth_range_m", "sim_form"]
            ):
                subarea_name, depth_range_m, sim_form = grp_id
                if "design_storm" in sim_form:
                    continue
                # extract original return period estimate for the impact from the full ensemble
                df_og = ds_flood_impacts_by_aoi.sel(
                    subarea_name=subarea_name,
                    depth_range_m=depth_range_m,
                    sim_form=sim_form,
                ).to_dataframe()
                if "flooded_area" in impact_var:
                    df_og = df_og.filter(like="flooded_area")
                else:
                    df_og = df_og.filter(like=impact_var)

                og_rtrn_name = df_og.filter(like="return_pd_yrs").iloc[:, 0].name
                df_og = df_og.sort_values(og_rtrn_name)

                s_og_imapcts = df_og.loc[
                    :,
                    [
                        (("emp_cdf" not in col) and ("return_pd" not in col))
                        for col in df_og.columns
                    ],
                ].iloc[:, 0]
                s_og_rtrn_yrs = df_og[og_rtrn_name]
                s_og_rtrn_yrs.name = "return_period_yrs_og"

                df_bs_impact_rtrn_pds = compute_return_periods_for_series(
                    df_group[impact_var],
                    N_YEARS_SYNTHESIZED,
                    ALPHA,
                    BETA,
                    ASSIGN_DUP_VALS_MAX_RETURN,
                    varname=impact_var,
                )
                df_bs_impact_rtrn_pds = df_bs_impact_rtrn_pds.loc[
                    :, ~df_bs_impact_rtrn_pds.columns.str.contains("emp_cdf")
                ]
                colname_return = df_bs_impact_rtrn_pds.filter(
                    like="return_pd_yrs"
                ).columns[0]
                df_bs_impact_rtrn_pds = df_bs_impact_rtrn_pds.rename(
                    columns={
                        colname_return: "return_period_yrs_bs",
                        impact_var: "impact_value",
                    }
                )

                # extract the targeted return periods
                ar_rtrn_pds_rounded = (
                    (df_bs_impact_rtrn_pds["return_period_yrs_bs"] * 2).round() / 2
                ).unique()
                for trgt_rtrn in target_design_storms_years:
                    if (pd.Series(ar_rtrn_pds_rounded) == trgt_rtrn).sum() == 0:
                        ar_rtrn_pds_rounded = np.append(ar_rtrn_pds_rounded, trgt_rtrn)
                ar_rtrn_pds = np.sort(ar_rtrn_pds_rounded)
                # interpolate impacts for return periods
                df_bs_impact_rtrn_pds = df_bs_impact_rtrn_pds.sort_values(
                    "impact_value"
                )
                impact_for_rtrn_pd_bs = np.interp(
                    ar_rtrn_pds,
                    df_bs_impact_rtrn_pds["return_period_yrs_bs"],
                    df_bs_impact_rtrn_pds["impact_value"],
                )
                # interpolate og return periods for these impacts
                og_rtrn_pds_for_impacts = np.interp(
                    impact_for_rtrn_pd_bs, s_og_imapcts, s_og_rtrn_yrs
                )

                df_output = pd.DataFrame(
                    dict(
                        return_period_yrs_og=og_rtrn_pds_for_impacts,
                        return_period_yrs=ar_rtrn_pds,
                        impact_value=impact_for_rtrn_pd_bs,
                    )
                )
                df_output["sim_form"] = sim_form
                df_output["impact_var"] = impact_var
                df_output["subarea_name"] = subarea_name
                df_output["depth_range_m"] = depth_range_m

                df_output = df_output.reset_index(drop=True).set_index(
                    [
                        "sim_form",
                        "impact_var",
                        "subarea_name",
                        "depth_range_m",
                        "return_period_yrs",
                    ]
                )

                lst_df_rtrn_pds.append(df_output)

                # df_bs_impact_rtrn_pds["return_period_yrs_bs_rounded_absdiff"] = (df_bs_impact_rtrn_pds["return_period_yrs_bs"] - df_bs_impact_rtrn_pds["return_period_yrs_bs_rounded"]).abs()
                # idx_names = df_bs_impact_rtrn_pds.index.names
                # df_bs_impact_rtrn_pds = df_bs_impact_rtrn_pds.reset_index()

                # idx_rtrn_pds = df_bs_impact_rtrn_pds.groupby(["return_period_yrs_bs_rounded"])['return_period_yrs_bs_rounded_absdiff'].idxmin()
                # df_bs_impact_rtrn_pds = df_bs_impact_rtrn_pds.loc[idx_rtrn_pds,:]
                # df_bs_impact_rtrn_pds =  df_bs_impact_rtrn_pds.set_index(idx_names)

                # # interpolate the target return period
                # for trgt_rtrn in target_design_storms_years:
                #     if (df_bs_impact_rtrn_pds["return_period_yrs_bs_rounded"]==trgt_rtrn).sum() > 0:
                #         continue

                #     impact_for_rtrn_pd = np.interp(trgt_rtrn, df_bs_impact_rtrn_pds["return_period_yrs_bs_rounded"], df_bs_impact_rtrn_pds["impact_value"])

                #     s_rtrn_pds = df_bs_impact_rtrn_pds.loc[:,"return_period_yrs_bs"]
                #     s_diffs_from_target = (s_rtrn_pds - trgt_rtrn).abs()
                #     min_diff_from_trgt = s_diffs_from_target.min()
                #     idx_rtrn_pd = s_diffs_from_target[s_diffs_from_target == min_diff_from_trgt].index
                #     df_output = df_bs_impact_rtrn_pds.loc[idx_rtrn_pd, :].reset_index().drop_duplicates()
                #     df_output["n_events_with_same_impact"] = len(df_og[df_og[impact_var]==df_output["impact_value"].unique()[0]])
                #     df_output["impact_var"] = impact_var
                #     df_output["return_period_yrs"] = trgt_rtrn
                #     df_output = df_output.reset_index(drop=True).set_index(["impact_var", "subarea_name", "depth_range_m", "return_period_yrs"])
                #     # add the original return period estimate
                #     df_output[s_og_rtrn_yrs.name] = s_og_rtrn_yrs.loc[df_output["event_number"]].values
                #     # subset to include just 1 event event
                #     df_output = df_output.iloc[[0],:]
                #     colnames = list(df_output.columns)
                #     colnames.sort()
                #     lst_df_rtrn_pds.append(df_output.loc[:, colnames])
        df_bootstrapped_results = pd.concat(lst_df_rtrn_pds).sort_index()
        df_bootstrapped_results.loc[:, "bs_id"] = bs_id
        idx_cols = df_bootstrapped_results.index.names + ["bs_id"]
        lst_cols = list(df_bootstrapped_results.columns)
        lst_cols.sort()
        df_bootstrapped_results = (
            df_bootstrapped_results.loc[:, lst_cols].reset_index().set_index(idx_cols)
        )
        lst_bs_samps.append(df_bootstrapped_results)
    df_bs_combined = pd.concat(lst_bs_samps).sort_index()
    # ds_bs_combined = df_bs_combined.to_xarray()
    df_bs_combined.to_csv(F_SCRATCH_FLOODAREA_RTRN_BS)

df_bs_combined = pd.read_csv(
    F_SCRATCH_FLOODAREA_RTRN_BS,
    index_col=[
        "sim_form",
        "impact_var",
        "subarea_name",
        "depth_range_m",
        "return_period_yrs",
        "bs_id",
    ],
)
# %% computing uncertainty outputs based on bootstrapping
# references
# df_univar_all_events = pd.read_csv(f_univar_bs_uncertainty_all_unique_events)
# df_univar_cis = pd.read_csv(f_univar_bs_uncertainty_ci)

lst_df_cis = []
for (
    sim_form,
    impact_var,
    subarea_name,
    depth_range_m,
    return_period_yrs,
), df_grp in tqdm(
    df_bs_combined.groupby(
        level=[
            "sim_form",
            "impact_var",
            "subarea_name",
            "depth_range_m",
            "return_period_yrs",
        ]
    )
):
    if "design_storm" in sim_form:
        continue
    # sys.exit('work')
    # compute quantiles
    idx_quant = [FLD_RTRN_PD_ALPHA / 2, 1 - FLD_RTRN_PD_ALPHA / 2]
    df_ci = pd.DataFrame(columns=["return_period_yrs_og"], index=idx_quant)
    df_ci.index.name = "quantile"
    for ci_bound in idx_quant:
        df_ci.loc[ci_bound, "return_period_yrs_og"] = df_grp[
            "return_period_yrs_og"
        ].quantile(ci_bound, interpolation="linear")
    df_ci["sim_form"] = sim_form
    df_ci["impact_var"] = impact_var
    df_ci["subarea_name"] = subarea_name
    df_ci["depth_range_m"] = depth_range_m
    df_ci["return_period_yrs"] = return_period_yrs
    df_ci = df_ci.reset_index().set_index(
        [
            "sim_form",
            "impact_var",
            "subarea_name",
            "depth_range_m",
            "return_period_yrs",
            "quantile",
        ]
    )
    # sys.exit('work')
    lst_df_cis.append(df_ci)


df_cis = pd.concat(lst_df_cis).sort_index()

# df_unique = df_bs_combined.loc[:, ["flooded_area_emp_cdf_og", "flooded_area_return_pd_yrs_og", "flooded_area_sqm"]].reset_index().drop(columns = ["bs_id"]).drop_duplicates()
# df_unique = df_unique.set_index(["subarea_name", "depth_range_m", "return_period_yrs", "event_number"]).sort_index()
# df_unique.to_csv(f_floodarea_bs_uncertainty_all_unique_events)
df_cis.to_csv(F_FLOOD_IMPACT_BS_UNCERTAINTY_CI)


# %% writing csv with all events that fall within the 90% confidence interval
# reference dataset of event return periods within confidence interval
df_event_rtrns_with_CI = pd.read_csv(
    F_BS_UNCERTAINTY_EVENTS_IN_CI, index_col=[0, 1, 2, 3, 4, 5]
)

lst_impact_vars = []
for var in ds_flood_impacts_by_aoi.data_vars:
    # print(var)
    if ("fraction" in var) or ("emp_cdf" in var) or ("return_pd_yrs" in var):
        continue
    lst_impact_vars.append(var)


lst_dfs = []
for depth_range_m in ds_flood_impacts_by_aoi.depth_range_m.to_series():
    for subarea_name in ds_flood_impacts_by_aoi.subarea_name.to_series():
        df_subset = (
            ds_flood_impacts_by_aoi.sel(
                depth_range_m=depth_range_m, subarea_name=subarea_name
            )
            .to_dataframe()
            .dropna()
        )
        for rtrn in target_design_storms_years:
            for impact_var in lst_impact_vars:
                for sim_form in df_cis.reset_index()["sim_form"].unique():
                    if "design_storm" in sim_form:
                        continue
                    #
                    s_ci_subset = df_cis.loc[
                        pd.IndexSlice[
                            sim_form, impact_var, subarea_name, depth_range_m, rtrn, :
                        ],
                        "return_period_yrs_og",
                    ]
                    # if s_ci_subset.min() == s_ci_subset.max():
                    #     sys.exit("figure out what to do here")
                    if "flooded_area" in impact_var:
                        df_subset_impact = df_subset.filter(like="flooded_area")
                    else:
                        df_subset_impact = df_subset.filter(like=impact_var)
                    # subset the return period column
                    s_impact_rtrn_pds = df_subset_impact.filter(like="return_pd").iloc[
                        :, 0
                    ]
                    idx_events_in_ci = return_indices_of_series_geq_lb_and_leq_ub(
                        s_impact_rtrn_pds, lb=s_ci_subset.min(), ub=s_ci_subset.max()
                    )
                    df_subset_in_ci = df_subset.loc[idx_events_in_ci, :]
                    # extract values column
                    df_subset_in_ci = df_subset_in_ci.loc[
                        :,
                        [
                            impact_var,
                            s_impact_rtrn_pds.name,
                            "subarea_name",
                            "depth_range_m",
                        ],
                    ]
                    # add original event indexing
                    df_event_idx_og = df_sim_flood_probs_event_num_mapping.join(
                        df_subset_in_ci, how="right"
                    ).loc[:, ["year", "event_type", "event_id"]]
                    df_subset_in_ci = df_subset_in_ci.join(df_event_idx_og)
                    # rename columns for easier indexing
                    # if (df_subset_in_ci[impact_var].max() == 0) or (df_subset_in_ci[impact_var].min() == 0):
                    #     sys.exit("check this out")
                    df_subset_in_ci = df_subset_in_ci.rename(
                        columns={
                            impact_var: "impact",
                            s_impact_rtrn_pds.name: "return_period_yrs_og",
                        }
                    )
                    # df_subset_in_ci["sim_form"] = sim_form
                    df_subset_in_ci["impact_var"] = impact_var
                    df_subset_in_ci["return_period_yrs"] = rtrn
                    df_subset_in_ci = df_subset_in_ci.reset_index().set_index(
                        [
                            "sim_form",
                            "impact_var",
                            "subarea_name",
                            "depth_range_m",
                            "return_period_yrs",
                        ]
                    )
                    lst_dfs.append(df_subset_in_ci)
                    # sys.exit('work')

df_flood_events_within_ci = pd.concat(lst_dfs).sort_index()
df_flood_events_within_ci.to_csv(F_FLOOD_IMPACT_BS_UNCERTAINTY_EVENTS_IN_CI)
