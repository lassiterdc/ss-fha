# %%
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.legend_handler import HandlerBase
import xarray as xr
import pandas as pd
import numpy as np
from tqdm import tqdm
from local.__utils import (
    return_ds_gridsize,
    compute_flooded_area_by_depth_threshold,
    compute_volume_at_max_flooding,
)

from local.__inputs import (
    TIMESERIES_BUFFER_BEFORE_FIRST_RAIN_H,
    LST_KEY_FLOOD_THRESHOLDS,
    DIF_FFA_FLOOD_MAPPING,
    FLD_RTRN_PD_ALPHA,
    MIN_THRESH_FLDING,
    COORD_EPSG,
    NUISANCE_THRESHOLD,
    ENSEMBLE_RETURN_PD_UB,
    TARGET_DESIGN_STORM_DURATION_HRS_FOR_COMPARISON,
    FLOOD_RTRN_PD_SUPPORT,
    LST_RTRNS,
    LST_KEY_FLOOD_THRESHOLDS_FOR_SENSITIVITY_ANALYSIS,
    FORMULATION_FOR_MC_DSGN_STRM_SEL_MULTIVAR_AND,
    EVENT_STAT_FOR_MC_DSGN_STRM_SEL_MULTIVAR_AND,
    FORMULATION_FOR_MC_DSGN_STRM_SEL_UNIVAR,
    EVENT_STAT_FOR_MC_DSGN_STRM_SEL_UNIVAR,
    FORMULATION_FOR_MC_DSGN_STRM_SEL_MULTIVAR_OR,
    EVENT_STAT_FOR_MC_DSGN_STRM_SEL_MULTIVAR_OR,
    PLOT_PARAMS,
    LST_RTRNS_ALL,
    LST_RTRN_PD_COLORS,
    F_WSHED_SHP,
)

import sys
from pathlib import Path
from local.__utils import create_mask_from_shapefile
import shutil
import matplotlib as mpl
from matplotlib.lines import Line2D
import matplotlib.colorbar as mcolorbar
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
import matplotlib.gridspec as gridspec

plt.rcParams["font.family"] = PLOT_PARAMS["font.family"]
plt.rcParams["font.serif"] = PLOT_PARAMS["font.serif"]
plt.rcParams["font.size"] = PLOT_PARAMS["font.size"]


def plot_flooded_areas_baseline_vs_alt(df_flooded_areas, target_return_pd, clf=True):
    colors = ["black", "#9467bd", "#17becf", "#ff7f0e"]
    col_order = ["ensemble_compound", "compound", "rain-only", "water level-only"]
    fig, axes = plt.subplots(ncols=3, nrows=2, dpi=300, figsize=(5 * 3, 3 * 2))
    axes = axes.flatten()
    # if there are multiple values for compound and rainfall, plot with error bars
    lst_df_error = None
    df_median_all = df_flooded_areas.copy()
    if len(df_flooded_areas.loc[:, "compound"].shape) > 1:
        if df_flooded_areas.loc[:, "compound"].shape[1] > 1:
            sys.exit(
                "If I am not including uncertainty bounds for design storms, this should not be triggered."
            )
            df_median_all = df_flooded_areas.loc[
                :, ["ensemble_compound", "water level-only"]
            ]
            df_max_all = df_median_all.copy()
            df_min_all = df_median_all.copy()
            for e_type in ["compound", "rain-only"]:
                s_median = df_flooded_areas.loc[:, e_type].median(axis=1)
                s_max = df_flooded_areas.loc[:, e_type].max(axis=1)
                s_min = df_flooded_areas.loc[:, e_type].min(axis=1)
                s_median.name = e_type
                s_max.name = e_type
                s_min.name = e_type
                df_median_all = df_median_all.join(s_median)
                df_max_all = df_max_all.join(s_max)
                df_min_all = df_min_all.join(s_min)
            lst_df_error = [
                df_median_all - df_min_all,
                df_max_all - df_median_all,
            ]
            for idx, df_error in enumerate(lst_df_error):
                lst_df_error[idx] = df_error.loc[:, col_order]
    else:
        lst_df_error = None
    df_median_all = df_median_all.loc[:, col_order]
    idx_ax = -1
    for row_idx, row in df_median_all.iterrows():
        idx_ax += 1
        ax = axes[idx_ax]
        row.plot.bar(ax=ax, color=colors)
        if lst_df_error is not None:
            lst_s_errors = []
            for df_error in lst_df_error:
                s_error = df_error.loc[row_idx,]
                s_error.loc["ensemble_compound"] = np.nan
                s_error.loc["water level-only"] = np.nan
                lst_s_errors.append(s_error)
            ax.errorbar(
                row.index,
                row,
                yerr=lst_s_errors,
                fmt="none",
                ecolor="black",
                capsize=5,
                capthick=2,
                linewidth=2,
            )
        # ax.legend(custom_labels, title='', loc='best')
        ax.set_title(row_idx)
        ax.set_ylabel("flooded area (km$^2$)")
        ax.set_xticklabels(row.index, rotation=0, ha="center")
    fig.tight_layout()
    fname_save_fig = f"{DIF_FFA_FLOOD_MAPPING}plots/ensemble_vs_dsgn_strms/flood_prob_map_diffs_{target_return_pd}yr_ensemble_vs_dsgn_strms_areas.png"
    Path(fname_save_fig).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(fname_save_fig, bbox_inches="tight")
    if clf:
        plt.clf()


def return_colorbar_extend(data_array, norm):
    extend_type = "neither"
    if data_array.max() > norm.vmax:
        extend_type = "max"
    if data_array.min() < norm.vmin:
        if extend_type == "max":
            extend_type = "both"
        else:
            extend_type = "min"
    return extend_type


def add_subplot_id(ax, ax_id, x=0.02, y=0.98):
    ax.text(
        x,
        y,  # position in axes coords
        f"({chr(97+ax_id)})",  # a), b), c), ...
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=9,
        # fontweight="bold",
    )


def plot_triton_results(
    datasets,
    titles,
    lab_cbar,
    cmap_name,
    fig_title,
    cbar_bins,
    cbar_tick_lables,
    cbar_bins_for_labeling=None,
    master_col_titles=None,
    master_row_titles=None,
    fname_save_fig=None,
    set_under=None,
    set_over=None,
    cbar_colors=None,
    shapefile_path=None,
    n_cols=3,
    plot_cbar=True,
    clf=True,
    figsize="default",
    add_subplot_ids = True,
):

    if shapefile_path is not None:
        from shapely.geometry import mapping
        import geopandas as gpd
        import rasterio.features
        import rioxarray
        from affine import Affine

        gdf = gpd.read_file(shapefile_path)
    cmap = plt.get_cmap(cmap_name)
    if cbar_colors is not None:
        cmap = mcolors.ListedColormap(cbar_colors)
    norm = mcolors.BoundaryNorm(cbar_bins, cmap.N)
    if set_under is not None:
        cmap.set_under(set_under)
    if set_over is not None:
        cmap.set_over(set_over)
    cmap.set_bad("lightgray")
    # Loop through datasets and axes to plot and set properties
    n_datasets = len(datasets)
    if n_datasets > n_cols:
        n_cols = n_cols
        n_rows = int(np.ceil(n_datasets / n_cols))
    else:
        n_cols = n_datasets
        n_rows = 1
    if figsize == "default":
        figsize = (4.5 * n_cols, 4 * n_rows)
    fig, axes = plt.subplots(
        n_rows,
        n_cols,
        dpi=300,
        figsize=figsize,
        constrained_layout=True,
    )
    try:
        axes = axes.ravel()
    except:
        axes = [axes]
    lst_extend_types = []
    ax_counter = -1  # 0 indexed
    for ax, data, title in zip(axes, datasets, titles):
        ax_counter += 1
        data = data.where(np.isfinite(data), np.nan).squeeze().load()
        if shapefile_path is not None:
            shapes = [
                mapping(geom) for geom in gdf.geometry
            ]  # Convert geometries to GeoJSON-like format
            # Use rasterio.features.geometry_mask to create the mask (True for outside, False for inside the shape)
            mask = rasterio.features.geometry_mask(
                shapes,
                transform=data.rio.transform(),
                invert=True,
                out_shape=data.shape,
            )
            transform = Affine(
                0.1, 0, 0, 0, 0.1, 0
            )  # <-- Define the affine transform (adjust as necessary)
            data = data.rio.write_transform(
                transform
            )  # <-- Added this line to apply the affine transform to the DataArray
            data = data.rio.write_crs(f"EPSG:{COORD_EPSG}")
            gdf = gdf.to_crs(data.rio.crs)
            data = data.where(mask)
        p = (
            data.squeeze()
            .reset_coords(drop=True)
            .plot.pcolormesh(
                cmap=cmap, x="x", y="y", ax=ax, add_colorbar=False, norm=norm
            )
        )
        if shapefile_path is not None:
            gdf.boundary.plot(ax=ax, color="black", linewidth=1)
        ax.set_xticklabels([])  # Remove x-axis tick labels
        ax.set_yticklabels([])  # Remove y-axis tick labels
        ax.set_ylabel("")
        ax.set_xlabel("")
        if master_col_titles is None:
            # print("assigning title")
            ax.set_title(title, fontsize=9)
        else:
            if ax_counter < n_cols:  # n_cols n_rows
                ax.set_title(master_col_titles[0], fontsize=9)
                master_col_titles.append("dummy")
                master_col_titles = master_col_titles[1:]  # drop the first one
            if (ax_counter == 0) or (ax_counter % n_cols == 0):
                ax.set_ylabel(master_row_titles[0], fontsize=9)
                master_row_titles.append("dummy")
                master_row_titles = master_row_titles[1:]  # drop the first one
        lst_extend_types.append(return_colorbar_extend(data, norm))

        if add_subplot_ids:
            # add identifier
            x = 0.02
            y = 0.98
            ax_id = ax_counter
            add_subplot_id(ax=ax, x=x, y=y, ax_id=ax_id)
    # determine extend type for colorbar
    if ("both" in lst_extend_types) or (
        ("max" in lst_extend_types) and ("min" in lst_extend_types)
    ):
        extend_type = "both"
    elif "max" in lst_extend_types:
        extend_type = "max"
    elif "min" in lst_extend_types:
        extend_type = "min"
    else:
        extend_type = "neither"
    # Remove any unused axes (if the number of datasets is less than total axes)
    for ax in axes[n_datasets:]:
        fig.delaxes(ax)
    # Adjust the colorbar width and center it horizontally
    colorbar_width = 0.6  # Width of the colorbar (fraction of figure width)
    cbar_left = (1 - colorbar_width) / 2  # Calculate left position to center it

    # Add a horizontal colorbar below the plots, centered horizontally
    if plot_cbar:
        if n_rows > 1:
            cbar_ax = fig.add_axes(
                [cbar_left, -0.05, colorbar_width, 0.03]
            )  # [left, bottom, width, height]
        if n_rows ==1 and n_cols == 1:
            colorbar_width = 1  # Width of the colorbar (fraction of figure width)
            cbar_left = (1 - colorbar_width) / 2  # Calculate left position to center it
            cbar_ax = fig.add_axes(
                [cbar_left, 0.1, colorbar_width, 0.03 * 0.8]
            )
        else:
            cbar_ax = fig.add_axes(
                [cbar_left, 0.25, colorbar_width, 0.03 * 0.8]
            )  # [left, bottom, width, height]
        cbar = fig.colorbar(
            p, cax=cbar_ax, extend=extend_type, orientation="horizontal"
        )
        if cbar_bins_for_labeling is not None:
            cbar.set_ticks(cbar_bins_for_labeling)
        else:
            cbar.set_ticks(cbar_bins)  # Remove the last bin as it represents 'over'
        cbar.ax.set_xticklabels(cbar_tick_lables)

        cbar_ax.set_xlabel(lab_cbar, fontsize=10)

    # fig.colorbar(p, cax=cbar_ax, orientation="horizontal")
    # cbar_ax.set_label(lab_cbar)

    # Add a title and adjust layout
    if fig_title is not None:
        fig.suptitle(fig_title)
    # fig.tight_layout()  # Adjust rect to leave space for the title
    # plt.tight_layout()
    if fname_save_fig is not None:
        Path(fname_save_fig).parent.mkdir(parents=True, exist_ok=True)
        frmt = fname_save_fig.split(".")[-1]
        if frmt != "png":
            plt.savefig(fname_save_fig, bbox_inches="tight", format=frmt)
        else:
            plt.savefig(fname_save_fig, bbox_inches="tight", dpi=450)
    if clf:
        plt.clf()

    return axes


def plot_fld_retrn_vs_event_return(
    da_sim_rtrn_pd_flood,
    ds_rtrn_pd_by_enum,
    event_stat,
    cmap_name_flood,
    cbar_bins_flood,
    fig_title,
    cmap_name_rtrn_pd,
    bin_labs_rtrn,
    bin_lab_rtrn_logspace_vals,
    cmap_name_event_stat,
    fname_save_fig=None,
    include_flood_depths=True,
    include_stat_values=True,
    shapefile_path=None,
    epsg_override=None,
    clf=True,
):  # , set_under = None):
    if shapefile_path is not None:
        from shapely.geometry import mapping
        import geopandas as gpd
        import rasterio.features
        import rioxarray
        from affine import Affine

        gdf = gpd.read_file(shapefile_path)
    # create colormaps
    ## flood depths
    cmap_flood = plt.get_cmap(cmap_name_flood)
    norm_flood = mcolors.BoundaryNorm(cbar_bins_flood, cmap_flood.N)
    cmap_flood.set_under("white")
    cmap_flood.set_bad("lightgray")
    ## return period
    cmap_rtrn_pd = plt.get_cmap(cmap_name_rtrn_pd)
    cmap_rtrn_pd.set_bad("lightgray")
    cmap_rtrn_pd.set_under("white")
    norm_rtrn_pd = mcolors.BoundaryNorm(bin_lab_rtrn_logspace_vals, cmap_rtrn_pd.N)
    ## event stat
    cmap_event_stat = plt.get_cmap(cmap_name_event_stat)
    cmap_event_stat.set_bad("lightgray")
    # create figure
    n_rows, n_cols = 1, 1
    if include_flood_depths:
        n_cols += 1
    if include_stat_values:
        n_cols += 1
    fig, axes = plt.subplots(
        n_rows,
        n_cols,
        dpi=300,
        figsize=(5.5 * n_cols, 4 * n_rows),
        constrained_layout=True,
    )
    if n_cols > 1:
        axes = axes.ravel()
    idx_ax = -1
    da_plot = da_sim_rtrn_pd_flood.squeeze().reset_coords(drop=True)
    if shapefile_path is not None:
        shp_mask = create_mask_from_shapefile(da_plot, shapefile_path)
    if include_flood_depths:  #  plot water level
        idx_ax += 1
        ax = axes[idx_ax]
        if shapefile_path is not None:
            gdf.boundary.plot(ax=ax, color="black", linewidth=1)
            da_plot = da_plot.where(shp_mask)
        p_fld = da_plot.plot.pcolormesh(
            cmap=cmap_flood, x="x", y="y", ax=ax, add_colorbar=False, norm=norm_flood
        )
        cbar = plt.colorbar(
            p_fld, ax=ax, extend=return_colorbar_extend(da_plot, norm_flood)
        )
        cbar.set_label("flood depth (m)")
        # ax.set_title("flood depth (m)")
    # plot event statistic
    event_stat_for_fig = event_stat
    # update axis title for rainfall statistics
    if "min_mm" in event_stat_for_fig:
        event_stat_for_fig_split = event_stat_for_fig.split("_")
        event_stat_for_fig = ""
        for substring in event_stat_for_fig_split:
            if substring in ["0hr", "0min"]:
                continue
            if "hr" in substring:
                dur_string = substring
                if "1hr" == substring:
                    dur_string = "1hr"
            if "min" in substring:
                dur_string = substring
        event_stat_for_fig = f"max {dur_string} precipitation depth"
        event_stat_units = "mm"
    else:
        # event_stat_for_fig = "max sea water level"
        event_stat_for_fig = "storm tide"
        event_stat_units = "m"
    if include_stat_values:
        idx_ax += 1
        ax = axes[idx_ax]
        da_event_stat = ds_rtrn_pd_by_enum[event_stat]
        da_plot = da_event_stat.squeeze().reset_coords(drop=True)
        if shapefile_path is not None:
            gdf.boundary.plot(ax=ax, color="black", linewidth=1)
            da_plot = da_plot.where(shp_mask)
        p_stat = da_plot.plot.pcolormesh(
            cmap=cmap_event_stat, x="x", y="y", ax=ax, add_colorbar=False
        )  # ,
        # norm = norm)
        cbar = plt.colorbar(p_stat, ax=ax)
        cbar.set_label(event_stat_units)
        ax.set_title(event_stat_for_fig)
    # plot log of event return period
    idx_ax += 1
    if n_cols > 1:
        ax = axes[idx_ax]
    else:
        ax = axes
    da_event_rtrn = np.log10(ds_rtrn_pd_by_enum[f"{event_stat}_return_pd_yrs"])
    da_plot = da_event_rtrn.squeeze().reset_coords(drop=True)
    if shapefile_path is not None:
        gdf.boundary.plot(ax=ax, color="black", linewidth=1)
        da_plot = da_plot.where(shp_mask)
    p_rtrn = da_plot.plot.pcolormesh(
        cmap=cmap_rtrn_pd, x="x", y="y", ax=ax, add_colorbar=False, norm=norm_rtrn_pd
    )  # ,
    cbar = plt.colorbar(
        p_rtrn, ax=ax, extend=return_colorbar_extend(da_plot, norm_rtrn_pd)
    )
    cbar.set_ticks(bin_lab_rtrn_logspace_vals)
    cbar.set_ticklabels(bin_labs_rtrn)
    cbar.set_label("return period (years)")  # , fontsize=12)
    ax.set_title(event_stat_for_fig)
    # norm = norm)
    # ax.set_title("return period (years)")
    if n_cols > 1:
        for ax in axes:
            ax.set_xticklabels([])  # Remove x-axis tick labels
            ax.set_yticklabels([])  # Remove y-axis tick labels
            ax.set_ylabel("")
            ax.set_xlabel("")
    else:
        axes.set_xticklabels([])  # Remove x-axis tick labels
        axes.set_yticklabels([])  # Remove y-axis tick labels
        axes.set_ylabel("")
        axes.set_xlabel("")
    if fig_title is not None:
        fig.suptitle(fig_title)
    if fname_save_fig is not None:
        Path(fname_save_fig).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(fname_save_fig, bbox_inches="tight")
    if clf:
        plt.clf()
    else:
        plt.show()


def plot_flood_map_with_loc(
    x,
    y,
    lst_ds_rtrn,
    titles,
    fname_save_fig_fldcrv,
    MIN_THRESH_FLDING,
    NUISANCE_THRESHOLD,
    target_return_pd,
    shapefile_path,
    title_axis=False,
):
    fig_title = None
    if title_axis:
        fig_title = f"{target_return_pd}-year Flood Depths"
    lab_cbar = "Water Level (m)"

    cbar_bins = [
        MIN_THRESH_FLDING,
        NUISANCE_THRESHOLD,
        0.1,
        0.15,
        0.3,
        0.6,
    ]  # nuisance flood depths up to 0.1; after are dangerous
    cbar_tick_lables = [str(lab) for lab in cbar_bins]
    cmap_name = "YlGnBu"
    datasets = [lst_ds_rtrn[0]]
    titles = [titles[0]]
    set_under = "white"
    fname_save_fig = None  # f"{DIF_FFA_FLOOD_MAPPING}plots/ensemble_vs_dsgn_strms/flood_prob_map_{target_return_pd}yr_ensemble_vs_dsgn_strms.png"

    axes = plot_triton_results(
        datasets,
        titles,
        lab_cbar,
        cmap_name,
        fig_title,
        cbar_bins,
        cbar_tick_lables,
        fname_save_fig,
        set_under,
        plot_cbar=False,
        shapefile_path=shapefile_path,
    )

    axes[0].annotate(
        "Target Cell",  # Annotation text
        xy=(x, y),  # The point to which the arrow points
        xytext=(0.7, 0.1),  # The position of the text label
        arrowprops=dict(facecolor="black", shrink=0.05),  # Arrow properties
        fontsize=12,  # Optional: set the font size of the text
        color="black",  # Optional: set the color of the text
        xycoords="data",
        textcoords="axes fraction",
    )
    if fname_save_fig_fldcrv is not None:
        plt.savefig(
            f"{fname_save_fig_fldcrv.split('.png')[0]}_map.png", bbox_inches="tight"
        )
        plt.clf()


def return_emp_cdf_of_single_loc_in_ensemble(
    ds_sim_flood_probs, x, y, ensemble_type, subset_with_rtrn_upper_lim=False
):
    df_cdf_1loc = (
        ds_sim_flood_probs.sel(x=x, y=y, ensemble_type=ensemble_type)
        .to_dataframe()
        .dropna()
        .sort_values("emprical_cdf")
        .reset_index(drop=True)
    )
    if subset_with_rtrn_upper_lim:
        df_cdf_1loc = df_cdf_1loc[df_cdf_1loc.return_pd_yrs < ENSEMBLE_RETURN_PD_UB]
    return df_cdf_1loc


def plot_compare_ensemble_to_design_flood_prob_curves_1loc(
    x,
    y,
    ds_sim_flood_probs,
    max_dsgn_wlevel,
    fname_save_fig,
    lst_ds_rtrn,
    titles,
    target_return_pd,
    shapefile_path,
    min_flood_depth_to_plot=None,
    ds_sim_flood_probs_bs=None,
    compound_dsgn_only=False,
    title_axis=False,
    min_ymax=None,
    clf=True,
):
    fig, ax = plt.subplots(dpi=300)

    df_baseline_cdf_1loc = return_emp_cdf_of_single_loc_in_ensemble(
        ds_sim_flood_probs, x, y, "compound", True
    )

    df_rain_cdf_1loc = return_emp_cdf_of_single_loc_in_ensemble(
        ds_sim_flood_probs, x, y, "rain_only", True
    )
    df_surge_cdf_1loc = return_emp_cdf_of_single_loc_in_ensemble(
        ds_sim_flood_probs, x, y, "surge_only", True
    )
    df_2D_cdf_1loc = return_emp_cdf_of_single_loc_in_ensemble(
        ds_sim_flood_probs, x, y, "2D_compound", True
    )

    df_all = (
        ds_sim_flood_probs.sel(x=x, y=y)
        .to_dataframe()
        .dropna()
        .sort_values("emprical_cdf")
        .reset_index(drop=True)
    )

    ymax = df_all["max_wlevel_m"].max()
    xmin = 0.5

    # compute ranges
    s_dsgn_cdf_1loc_compound_all = (
        max_dsgn_wlevel.sel(x=x, y=y, event_type="compound")
        .to_dataframe()
        .dropna()["max_wlevel_m"]
    )
    s_dsgn_cdf_1loc_compound_median = s_dsgn_cdf_1loc_compound_all.groupby(
        level="year"
    ).median()
    s_dsgn_cdf_1loc_compound_min = s_dsgn_cdf_1loc_compound_all.groupby(
        level="year"
    ).min()
    s_dsgn_cdf_1loc_compound_max = s_dsgn_cdf_1loc_compound_all.groupby(
        level="year"
    ).max()

    s_dsgn_cdf_1loc_rain_only_all = (
        max_dsgn_wlevel.sel(x=x, y=y, event_type="rain")
        .to_dataframe()
        .dropna()["max_wlevel_m"]
    )
    s_dsgn_cdf_1loc_rain_only_median = s_dsgn_cdf_1loc_rain_only_all.groupby(
        level="year"
    ).median()
    s_dsgn_cdf_1loc_rain_only_min = s_dsgn_cdf_1loc_rain_only_all.groupby(
        level="year"
    ).min()
    s_dsgn_cdf_1loc_rain_only_max = s_dsgn_cdf_1loc_rain_only_all.groupby(
        level="year"
    ).max()

    s_dsgn_cdf_1loc_surge_only_all = (
        max_dsgn_wlevel.sel(x=x, y=y, event_type="surge")
        .to_dataframe()
        .dropna()["max_wlevel_m"]
    )
    s_dsgn_cdf_1loc_surge_only_median = s_dsgn_cdf_1loc_surge_only_all.groupby(
        level="year"
    ).median()
    s_dsgn_cdf_1loc_surge_only_min = s_dsgn_cdf_1loc_surge_only_all.groupby(
        level="year"
    ).min()
    s_dsgn_cdf_1loc_surge_only_max = s_dsgn_cdf_1loc_surge_only_all.groupby(
        level="year"
    ).max()

    if title_axis:
        ax.set_title(
            "ensemble-based vs. design storm-based\nflood probability curve at a single gridcell"
        )

    # computing confidence intervals
    if ds_sim_flood_probs_bs is not None:
        df_ci_1loc = ds_sim_flood_probs_bs.sel(x=x, y=y).to_dataframe()["max_wlevel_m"]
        df_ci_1loc = df_ci_1loc.unstack(level="bs_id")
        df_ci_1loc = df_ci_1loc.loc[0:ENSEMBLE_RETURN_PD_UB]
        s_max = df_ci_1loc.max(axis=1)
        s_min = df_ci_1loc.min(axis=1)
        s_lb = df_ci_1loc.quantile(
            FLD_RTRN_PD_ALPHA / 2, axis=1, interpolation="linear"
        )
        s_ub = df_ci_1loc.quantile(
            1 - FLD_RTRN_PD_ALPHA / 2, axis=1, interpolation="linear"
        )
        # plotting confidence intervals
        idx = s_max.index
        ax.fill_between(
            idx, s_lb, s_ub, color="grey", alpha=0.3, label=r"ensemble 90\% CI"
        )
        # Plot s_max with a black dashed line
        linewidth = 0.5
        size = 3
        extremes_alpha = 0.5
        linestyle = (0, (5, 5))
        xmin = idx.min()
        xmax = idx.max() * 0.75
        ax.semilogx(
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
            label="ensemble extremes",
        )
        ax.semilogx(
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
        ax.set_xlim(xmin, xmax)
        ymax = s_max.max()
    else:
        ax.semilogx(
            df_baseline_cdf_1loc["return_pd_yrs"],
            df_baseline_cdf_1loc["max_wlevel_m"],
            label="ensemble-based",
            color="black",
            linestyle="--",
            linewidth=1,
            alpha=0.4,
        )

        ax.semilogx(
            df_rain_cdf_1loc["return_pd_yrs"],
            df_rain_cdf_1loc["max_wlevel_m"],
            label="ensemble rain-only",
            color="#17becf",
            linestyle=":",
            linewidth=1,
        )
        ax.semilogx(
            df_surge_cdf_1loc["return_pd_yrs"],
            df_surge_cdf_1loc["max_wlevel_m"],
            label="ensemble surge-only",
            color="#ff7f0e",
            linestyle=":",
            linewidth=1,
        )
        ax.semilogx(
            df_2D_cdf_1loc["return_pd_yrs"],
            df_2D_cdf_1loc["max_wlevel_m"],
            label="ensemble 2D",
            color="#9467bd",
            linestyle=":",
            linewidth=1,
        )
    # ax.set_ylabel("flood depth (m)")
    # ax.set_xlabel("return period (yr)")

    interaction_matters = False
    compound_and_rain_only_are_different = not np.isclose(
        (s_dsgn_cdf_1loc_compound_median - s_dsgn_cdf_1loc_rain_only_median).sum(), 0
    )
    comopund_and_surge_only_are_different = not np.isclose(
        (s_dsgn_cdf_1loc_compound_median - s_dsgn_cdf_1loc_surge_only_median).sum(), 0
    )
    if compound_and_rain_only_are_different and comopund_and_surge_only_are_different:
        interaction_matters = True
    rain_dominant = True
    markeredgewidth = 1.2
    cmpnd_marker_sz = 6
    surge_marker_sz = 6
    rain_marker_sz = 10
    lab_compound = "multi-driver design event"
    markerfacecolor = "none"
    marker = "o"
    err_linewidth = 0
    err_capthick = 0.8
    err_capsize = 3
    x_adj = 0
    if not compound_dsgn_only:
        cmpnd_marker_sz = 12
        marker = "s"
        markerfacecolor = "none"
        lab_compound = "compound"
        ax.semilogx(
            s_dsgn_cdf_1loc_rain_only_median.index,
            s_dsgn_cdf_1loc_rain_only_median,
            label="rain-only",
            marker="o",
            linestyle="None",
            markeredgecolor="#17becf",
            markerfacecolor="none",
            markeredgewidth=markeredgewidth,
            alpha=0.9,
            markersize=rain_marker_sz,
        )
        y_err = s_dsgn_cdf_1loc_rain_only_max - s_dsgn_cdf_1loc_rain_only_min
        if s_dsgn_cdf_1loc_rain_only_median.max() > ymax:
            ymax = (
                s_dsgn_cdf_1loc_rain_only_median.max()
                + y_err.loc[s_dsgn_cdf_1loc_rain_only_median.idxmax()]
            )
        ax.errorbar(
            s_dsgn_cdf_1loc_rain_only_median.index * (1 + x_adj),
            s_dsgn_cdf_1loc_rain_only_median,
            yerr=y_err,
            fmt="",
            ecolor="#17becf",
            capsize=err_capsize,
            capthick=err_capthick,
            linewidth=err_linewidth,
            zorder=1,
        )
        ax.semilogx(
            s_dsgn_cdf_1loc_surge_only_median.index,
            s_dsgn_cdf_1loc_surge_only_median,
            label="water level-only",
            marker="^",
            linestyle="None",
            markeredgecolor="#ff7f0e",
            markerfacecolor="none",
            markeredgewidth=markeredgewidth,
            alpha=0.9,
            markersize=surge_marker_sz,
        )
        y_err = s_dsgn_cdf_1loc_surge_only_max - s_dsgn_cdf_1loc_surge_only_min
        ax.errorbar(
            s_dsgn_cdf_1loc_surge_only_median.index * (1 - x_adj),
            s_dsgn_cdf_1loc_surge_only_median,
            yerr=y_err,
            fmt="",
            ecolor="#ff7f0e",
            capsize=err_capsize,
            capthick=err_capthick,
            linewidth=err_linewidth,
            zorder=1,
        )
        if s_dsgn_cdf_1loc_surge_only_median.max() > ymax:
            ymax = (
                s_dsgn_cdf_1loc_surge_only_median.max()
                + y_err.loc[s_dsgn_cdf_1loc_surge_only_median.idxmax()]
            )
        if (
            s_dsgn_cdf_1loc_surge_only_median.max()
            > s_dsgn_cdf_1loc_rain_only_median.max()
        ):
            rain_dominant = False

    ax.semilogx(
        s_dsgn_cdf_1loc_compound_median.index,
        s_dsgn_cdf_1loc_compound_median,
        label=lab_compound,
        marker=marker,
        linestyle="None",
        markeredgecolor="#9467bd",
        markerfacecolor=markerfacecolor,
        markeredgewidth=markeredgewidth,
        alpha=0.9,
        markersize=cmpnd_marker_sz,
    )
    y_err = s_dsgn_cdf_1loc_compound_max - s_dsgn_cdf_1loc_compound_min
    ax.errorbar(
        s_dsgn_cdf_1loc_compound_median.index,
        s_dsgn_cdf_1loc_compound_median,
        yerr=y_err,
        fmt="",
        ecolor="#9467bd",
        capsize=err_capsize,
        capthick=err_capthick,
        linewidth=err_linewidth,
        zorder=1,
    )
    if s_dsgn_cdf_1loc_compound_median.max() > ymax:
        ymax = (
            s_dsgn_cdf_1loc_compound_median.max()
            + y_err.loc[s_dsgn_cdf_1loc_compound_median.idxmax()]
        )

    ax.legend()

    ymax_mulitiplier = 1.05
    # enforce the minimum y limits (so it's easier to skim the graph thumbnails to filter out those with insignificant flooding)
    if (min_ymax is not None) and (min_ymax > ymax):
        if min_ymax >= ymax * ymax_mulitiplier:
            ymax = min_ymax
        else:
            ymax = (
                np.ceil(ymax * ymax_mulitiplier * 10) / 10
            )  # round up to the nearest tenth of a meter
    else:
        ymax = (
            np.ceil(ymax * ymax_mulitiplier * 10) / 10
        )  # round up to the nearest tenth of a meter
    ax.set_ylim(-0.05, ymax)

    ax.set_xlim(xmin, ENSEMBLE_RETURN_PD_UB * 1.2)

    # don't bother plotting if the maximum flood depth is less than the threshold
    if min_flood_depth_to_plot is not None:
        if ymax < min_flood_depth_to_plot:
            if clf:
                plt.clf()
            return

    if (
        fname_save_fig is not None
    ):  # account for the presence of an interaction in the file name
        prev_fname = fname_save_fig.split("/")[-1]
        if interaction_matters:
            fname = f"interaction_{prev_fname}"
        else:
            fname = f"no_interaction_{prev_fname}"
        if rain_dominant:
            fname = f"rain_dominant_{fname}"
        else:
            fname = f"surge_dominant_{fname}"
        fname_save_fig = fname_save_fig.split(prev_fname)[0] + fname
        Path(fname_save_fig).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(fname_save_fig, bbox_inches="tight")
        if clf:
            plt.clf()
        plot_flood_map_with_loc(
            x,
            y,
            lst_ds_rtrn,
            titles,
            fname_save_fig,
            MIN_THRESH_FLDING,
            NUISANCE_THRESHOLD,
            target_return_pd,
            shapefile_path,
            title_axis,
        )


def plot_histogram_of_differences_in_flood_depths_vs_baseline(
    datasets, titles, target_return_pd, clf=True
):
    grid_size = return_ds_gridsize(datasets[0])
    nrows = 2
    n_plots = len(datasets)
    ncols = int(np.ceil(n_plots / nrows))
    fig, axes = plt.subplots(
        nrows, ncols, dpi=300, figsize=(4 * ncols, 3 * ncols), sharex=True
    )
    axes = axes.flatten()
    # Compute the global range across all datasets
    global_min = 9999
    global_max = -9999
    for idx, ds_diff in enumerate(datasets):
        global_min = min(
            global_min,
            min(
                ds_diff.to_dataframe()["max_wlevel_m"].dropna().quantile(0.02)
                for ds_diff in datasets
            ),
        )
        global_max = max(
            global_max,
            max(
                ds_diff.to_dataframe()["max_wlevel_m"].dropna().quantile(0.98)
                for ds_diff in datasets
            ),
        )
    # Define the bins for the histograms
    bins = 30
    bin_edges = np.linspace(global_min, global_max, bins + 1)  # Ensure equal-width bins
    lst_s_diffs_rtrn = []
    for idx, ds_diff in enumerate(datasets):
        s_diffs = pd.Series().astype(float)
        title = titles[idx]
        df_diff = ds_diff.to_dataframe()["max_wlevel_m"].dropna()
        df_diff_dsgn_overestimates = df_diff[df_diff > 0]
        df_diff_dsgn_underestimates = df_diff[df_diff < 0]
        axes[idx].hist(df_diff, density=False, bins=bin_edges)
        axes[idx].set_yticks([])
        if "design" in title:
            if "median boundary water levels" in title:
                ax_title = "design storm rain-only"
            elif "no rainfall" in title:
                ax_title = "design storm water level-only"
            else:
                ax_title = "design storm compound"
        else:
            if "rain_only" in title:
                ax_title = "ensemble rain-only"
            elif "surge_only" in title:
                ax_title = "ensemble water level-only"
            elif "2D_compound" in title:
                ax_title = "ensemble 2D"
            elif "mcds" in title.lower():
                ax_title = "MCDS"
        s_diffs.name = ax_title
        axes[idx].set_title(ax_title)
        axes[idx].set_xlabel("alternative minus ensemble-based (m)")
        tot_overestimated = df_diff_dsgn_overestimates.sum() * grid_size**2
        tot_underestimated = df_diff_dsgn_underestimates.sum() * grid_size**2
        s_diffs.loc["overestimate"] = tot_overestimated
        s_diffs.loc["underestimate"] = tot_underestimated
        # flooded_area_perc_diff_from_ensemble = s_dsgn_frac_of_ensemble_flooded_area.loc[title]
        axes[idx].text(
            0.5,
            -0.29,
            f"overestimate: {tot_overestimated:.0f} m$^3$\n underestimate: {tot_underestimated:.0f} m$^3$",
            ha="center",
            transform=axes[idx].transAxes,
            fontsize=10,
        )
        lst_s_diffs_rtrn.append(s_diffs)
    fname_save_fig = f"{DIF_FFA_FLOOD_MAPPING}plots/ensemble_vs_dsgn_strms/flood_prob_map_diffs_{target_return_pd}yr_ensemble_vs_dsgn_strms_volumes.png"
    Path(fname_save_fig).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(fname_save_fig, bbox_inches="tight")
    if clf:
        plt.clf()
    return lst_s_diffs_rtrn


def plot_ensemble_vs_alternatives_probability_depth_curves_at_individual_gridcells(
    lst_s_diffs_rtrn,
    target_return_pd,
    lst_df_diffs,
    lst_ds_rtrn_diff,
    quants_to_compare,
    ds_sim_flood_probs,
    max_dsgn_wlevel,
    lst_ds_rtrn,
    titles,
    shapefile_path,
    ds_sim_flood_probs_bs,
    clf,
):
    df_diffs = pd.concat(lst_s_diffs_rtrn, axis=1).reset_index()
    df_diffs["return_period"] = target_return_pd
    lst_df_diffs.append(df_diffs)

    # plot flood depth probability curves at two locations
    ds_diffs = lst_ds_rtrn_diff[2]  # looking at diffs with 24 hour storm
    s_diff = (
        (ds_diffs)
        .squeeze()
        .reset_coords(drop=True)
        .to_dataframe()
        .dropna()
        .sort_values("max_wlevel_m")["max_wlevel_m"]
    )
    lst_coords_analyzed = []
    loc_idx = -1
    for quant in quants_to_compare:
        diff = s_diff.quantile(quant, interpolation="nearest")
        x, y = s_diff[s_diff == diff].index[0]
        ds = lst_ds_rtrn_diff[0]
        x_as_frac, y_as_frac = (x - ds.x.values.min()) / (
            ds.x.values.max() - ds.x.values.min()
        ), (y - ds.y.values.min()) / (ds.y.values.max() - ds.y.values.min())
        if (
            x,
            y,
        ) in lst_coords_analyzed:  # do not analyze same location more than once
            continue
        loc_idx += 1
        fname_save_fig = f"{DIF_FFA_FLOOD_MAPPING}plots/ensemble_vs_dsgn_strms/fld_crvs_1loc/ensemble-dsgn_xy_{x_as_frac:.2f}_{y_as_frac:.2f}.png"
        if loc_idx == 0:  # if this is the first plot, clear the folder
            try:
                shutil.rmtree(Path(fname_save_fig).parent)
            except:
                pass
        title_axis = False
        compound_dsgn_only = False
        min_flood_depth_to_plot = LST_KEY_FLOOD_THRESHOLDS[-3]
        plot_compare_ensemble_to_design_flood_prob_curves_1loc(
            x=x,
            y=y,
            ds_sim_flood_probs=ds_sim_flood_probs,
            max_dsgn_wlevel=max_dsgn_wlevel,
            fname_save_fig=fname_save_fig,
            lst_ds_rtrn=lst_ds_rtrn,
            titles=titles,
            target_return_pd=target_return_pd,
            shapefile_path=shapefile_path,
            min_flood_depth_to_plot=min_flood_depth_to_plot,
            ds_sim_flood_probs_bs=ds_sim_flood_probs_bs,
            clf=clf,
        )
        lst_coords_analyzed.append((x, y))
    return


def reindex_df_with_event_numbers(
    df_to_reindex, df_sim_flood_probs_event_num_mapping, og_idx_names
):
    s_eid_mapping = df_sim_flood_probs_event_num_mapping.reset_index().set_index(
        og_idx_names
    )["event_number"]
    df_reindexed = (
        pd.concat(
            [df_to_reindex.reset_index().set_index(og_idx_names), s_eid_mapping], axis=1
        )
        .reset_index(drop=True)
        .set_index("event_number")
        .sort_index()
    )
    return df_reindexed


class HandlerCircleX(HandlerBase):
    # Custom legend handler that draws a circle + X at the same center
    def create_artists(
        self, legend, orig_handle, xdescent, ydescent, width, height, fontsize, trans
    ):
        # center of the legend handle box
        cx = xdescent + width / 2
        cy = ydescent + height / 2

        # Circle
        circ = Line2D(
            [cx],
            [cy],
            marker="o",
            markersize=10,
            markerfacecolor="lightgrey",
            markeredgecolor="black",
            markeredgewidth=1,
            linestyle="",
            transform=trans,
        )

        # X on top
        ex = Line2D(
            [cx],
            [cy],
            marker="X",
            markersize=8.85,
            markerfacecolor="lightgrey",
            markeredgecolor="black",
            markeredgewidth=1,
            linestyle="",
            transform=trans,
        )

        return [circ, ex]


def retrieve_event_data_for_plotting(
    formulation,
    stats,
    df_rain_rtrn_pds,
    df_wlevel_return_pds,
    df_weather_events_in_ci_og,
    ds_multivar_return_periods,
    df_univariate_return_pds_og,
    df_sim_flood_probs_event_num_mapping,
    use_aep,
):
    multivar_formulation = None
    if "univar" not in formulation:
        multivar_formulation = formulation.split("_")[-1]
    lst_s_stats = []
    for stat in stats.split(","):
        if stat == "w":
            continue
        # else:
        col_idx = [
            ("emp_cdf" not in col) and ("return_pd" not in col)
            for col in df_rain_rtrn_pds.columns
        ]
        df_rain_rtrn_pds_stats_only = df_rain_rtrn_pds.loc[:, col_idx]
        if multivar_formulation is not None:
            df_trgt_stat = df_rain_rtrn_pds_stats_only.filter(like="_" + stat)
            if len(df_trgt_stat.columns) != 1:
                sys.exit("problem subsetting unique stat column")
            lst_s_stats.append(df_trgt_stat.iloc[:, 0])
        else:
            lst_s_stats.append(df_rain_rtrn_pds_stats_only.loc[:, stat])

    lst_s_stats.append(df_wlevel_return_pds["max_waterlevel_m"])

    df_stats = pd.concat(lst_s_stats, axis=1)
    # extracting events within CI
    df_weather_events_in_ci = df_weather_events_in_ci_og.copy()
    df_weather_events_in_ci = df_weather_events_in_ci.loc[
        pd.IndexSlice[:, :, LST_RTRNS, :]
    ]

    # df_return_pd_cis_univar = df_return_pd_cis_univar_og.copy()

    # df_event_stats_and_univar_return_periods = df_event_stats_and_univar_return_periods_og.copy()

    if multivar_formulation is not None:
        s_event_return_periods = (
            ds_multivar_return_periods.sel(event_stats=stats)[formulation]
            .to_dataframe()
            .dropna()[formulation]
        )

    else:
        s_event_return_periods = df_univariate_return_pds_og.filter(like=stat).iloc[
            :, 0
        ]

    og_idx_names = s_event_return_periods.index.names

    # df_sim_summaries_by_eid = reindex_df_with_event_numbers(df_sim_summaries, df_sim_flood_probs_event_num_mapping, og_idx_names)
    s_event_return_periods_by_eid = reindex_df_with_event_numbers(
        s_event_return_periods, df_sim_flood_probs_event_num_mapping, og_idx_names
    )
    df_stats_by_eid = reindex_df_with_event_numbers(
        df_stats, df_sim_flood_probs_event_num_mapping, og_idx_names
    )
    # df_event_stats_and_univar_return_periods_by_eid = reindex_df_with_event_numbers(df_event_stats_and_univar_return_periods, df_sim_flood_probs_event_num_mapping, og_idx_names)

    if use_aep:
        s_event_return_periods_by_eid = 1 / s_event_return_periods_by_eid
        og_idx = df_weather_events_in_ci.index.names
        df_weather_events_in_ci = df_weather_events_in_ci.reset_index()
        df_weather_events_in_ci["return_period_yrs"] = (
            1 / df_weather_events_in_ci["return_period_yrs"]
        )
        df_weather_events_in_ci = df_weather_events_in_ci.set_index(og_idx)

        # og_idx = df_return_pd_cis_univar.index.names
        # df_return_pd_cis_univar = df_return_pd_cis_univar.reset_index()
        # df_return_pd_cis_univar["return_period_yrs"] = 1/df_return_pd_cis_univar["return_period_yrs"]
        # df_return_pd_cis_univar = df_return_pd_cis_univar.set_index(og_idx)
    df_weather_events_in_ci_univar = df_weather_events_in_ci.loc[
        pd.IndexSlice["empirical_univar_return_pd_yrs", :, :, :]
    ]
    df_weather_events_in_ci = df_weather_events_in_ci.loc[
        pd.IndexSlice[formulation, stats, :, :]
    ]

    df_event_stats_and_prob = pd.concat(
        [df_stats_by_eid, s_event_return_periods_by_eid], axis=1
    )
    # if univar, add on the max sea water level as a column
    if use_aep:
        ar_probs_increasing_intensity = (
            df_weather_events_in_ci.reset_index()["return_period_yrs"]
            .sort_values(ascending=False)
            .unique()
        )
        legend_title = "annual\nfrequency\n"
    else:
        ar_probs_increasing_intensity = (
            df_weather_events_in_ci.reset_index()["return_period_yrs"]
            .sort_values(ascending=True)
            .unique()
        )
        legend_title = "return\n period (yrs)"
        sys.exit("figure out plotting for return period in years")
    return (
        df_stats,
        df_event_stats_and_prob,
        ar_probs_increasing_intensity,
        df_weather_events_in_ci,
        legend_title,
        multivar_formulation,
        df_weather_events_in_ci_univar,
    )


def return_axlims(x, y, ar_probs_increasing_intensity, df_weather_events_in_ci):

    lst_colors_increasing_severity = ["#ffffd4", "#fed98e", "#fe9929", "#cc4c02"]

    dic_cmap = dict()
    for idx, trgt_prob in enumerate(ar_probs_increasing_intensity):
        dic_cmap[trgt_prob] = lst_colors_increasing_severity[idx]

    lst_legend_handles = []

    x_ll = np.inf
    x_ul = -np.inf
    y_ll = np.inf
    y_ul = -np.inf
    for trgt_prob, df_grp in df_weather_events_in_ci.groupby("return_period_yrs"):
        idx_trgt_prob = df_weather_events_in_ci.loc[pd.IndexSlice[trgt_prob, :]].index

        x_subset = x.loc[idx_trgt_prob]
        y_subset = y.loc[idx_trgt_prob]

        # update ax lims
        if x_ll > x_subset.min():
            x_ll = x_subset.min()
        if x_ul < x_subset.max():
            x_ul = x_subset.max()

        if y_ll > y_subset.min():
            y_ll = y_subset.min()
        if y_ul < y_subset.max():
            y_ul = y_subset.max()

    lim_buff = 0.5
    xlims = (max(x_ll * (1 - lim_buff), 0), x_ul * (1 + lim_buff))
    ylims = (max(y_ll * (1 - lim_buff), 0), y_ul * (1 + lim_buff))

    return xlims, ylims


def mcds_scatter_and_return_lgnd(
    ar_probs_increasing_intensity, df_weather_events_in_ci, x, y, ax
):

    dic_cmap = dict()
    for idx, trgt_prob in enumerate(ar_probs_increasing_intensity):
        dic_cmap[trgt_prob] = LST_RTRN_PD_COLORS[idx]

    lst_legend_handles = []

    for trgt_prob, df_grp in df_weather_events_in_ci.groupby("return_period_yrs"):
        idx_trgt_prob = df_weather_events_in_ci.loc[pd.IndexSlice[trgt_prob, :]].index

        x_subset = x.loc[idx_trgt_prob]
        y_subset = y.loc[idx_trgt_prob]

        n_events = len(x_subset)

        sc_trgt_prob = ax.scatter(
            x=x_subset,
            y=y_subset,
            s=10,
            facecolor=dic_cmap[trgt_prob],
            zorder=10,
            edgecolor="k",
            linewidths=0.5,
            label=trgt_prob,
        )
        legend_handle = Line2D(
            [0],
            [0],
            linestyle="None",
            marker="o",
            markersize=8,
            markerfacecolor=dic_cmap[trgt_prob],
            zorder=10,
            markeredgecolor="k",
            label=f"{trgt_prob} ({n_events})",
        )
        lst_legend_handles.append(legend_handle)

    return lst_legend_handles


def populate_mcds_axis_object(
    formulation,
    stats,
    df_rain_rtrn_pds,
    df_wlevel_return_pds,
    df_weather_events_in_ci_og,
    ds_multivar_return_periods,
    df_univariate_return_pds_og,
    df_sim_flood_probs_event_num_mapping,
    use_aep,
    ax,
    show_legend=False,
    constant_sea_water_level_boundary=None,
):

    (
        df_stats,
        df_event_stats_and_prob,
        ar_probs_increasing_intensity,
        df_weather_events_in_ci,
        legend_title,
        multivar_formulation,
        df_weather_events_in_ci_univar,
    ) = retrieve_event_data_for_plotting(
        formulation,
        stats,
        df_rain_rtrn_pds,
        df_wlevel_return_pds,
        df_weather_events_in_ci_og,
        ds_multivar_return_periods,
        df_univariate_return_pds_og,
        df_sim_flood_probs_event_num_mapping,
        use_aep,
    )

    x = df_event_stats_and_prob.iloc[:, 0]
    y = df_event_stats_and_prob.iloc[:, 1]
    x_label = tidy_hydro_varnames_for_plots(x.name)
    y_label = tidy_hydro_varnames_for_plots(y.name)

    sc = ax.scatter(
        x=x,
        y=y,
        s=4,
        zorder=9,
        facecolors="none",
        edgecolors="k",
        alpha=0.2,
        linewidths=0.5,
    )

    lst_legend_handles = mcds_scatter_and_return_lgnd(
        ar_probs_increasing_intensity, df_weather_events_in_ci, x, y, ax
    )

    if show_legend:
        ax.legend(
            handles=lst_legend_handles,
            labels=[h.get_label() for h in lst_legend_handles],
            title=legend_title + f"({multivar_formulation})",
            fontsize=8,
            title_fontsize=9,
            loc="upper right",
        )

    ax.grid(True)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    xlims, ylims = return_axlims(
        x, y, ar_probs_increasing_intensity, df_weather_events_in_ci
    )
    ax.set_xlim(-1 * 0.05 * xlims[1], xlims[1] * 1.1)
    ax.set_ylim(ylims)
    lst_legend_handles.reverse()

    if constant_sea_water_level_boundary is not None:
        add_MHHW_line(ax, constant_sea_water_level_boundary, zorder=10, annotate=False)

    return lst_legend_handles


def plot_mcds_events(
    df_rain_rtrn_pds,
    df_wlevel_return_pds,
    df_weather_events_in_ci_og,
    ds_multivar_return_periods,
    df_sim_flood_probs_event_num_mapping,
    use_aep,
    dir_plots_event_return_periods,
    df_univariate_return_pds_og,
    dict_forms_and_stats,
    fname_savefig=None,
    lst_axes=None,
    clf=True,
    plot_legend=True,
    constant_sea_water_level_boundary=None,
):
    dpi = 300
    ncols = len(dict_forms_and_stats["stats"])
    figsize = (3 * ncols, 3)

    if lst_axes is None:
        fig, axes = plt.subplots(
            ncols=ncols, nrows=1, sharey=True, figsize=figsize, dpi=300
        )
        if ncols == 1:
            lst_axes = [axes]
        else:
            lst_axes = axes

    dict_legend_items = {}

    for idx in np.arange(len(dict_forms_and_stats["formulations"])):
        form = dict_forms_and_stats["formulations"][idx]
        stat = dict_forms_and_stats["stats"][idx]
        ax = lst_axes[idx]

        lst_legend_handles = populate_mcds_axis_object(
            form,
            stat,
            df_rain_rtrn_pds,
            df_wlevel_return_pds,
            df_weather_events_in_ci_og,
            ds_multivar_return_periods,
            df_univariate_return_pds_og,
            df_sim_flood_probs_event_num_mapping,
            use_aep,
            ax=ax,
            constant_sea_water_level_boundary=constant_sea_water_level_boundary,
        )
        dict_legend_items[f"{form}.{stat}"] = lst_legend_handles

        # lst_legend_handles_univar = populate_mcds_axis_object(
        #     FORMULATION_FOR_MC_DSGN_STRM_SEL_UNIVAR,
        #     EVENT_STAT_FOR_MC_DSGN_STRM_SEL_UNIVAR,
        #     df_rain_rtrn_pds,
        #     df_wlevel_return_pds,
        #     df_weather_events_in_ci_og,
        #     ds_multivar_return_periods,
        #     df_univariate_return_pds_og,
        #     df_sim_flood_probs_event_num_mapping,
        #     use_aep,
        #     ax=ax_univar,
        #     constant_sea_water_level_boundary=constant_sea_water_level_boundary,
        # )
        if idx > 0:
            ax.set_ylabel("")

        ax.grid(False)

        lgnd_y = 1
        lgnd_x = 1
        frameon = False
        if plot_legend:
            lgnd = ax.legend(
                handles=lst_legend_handles,
                labels=[h.get_label() for h in lst_legend_handles],
                title="annual freq.\n(n events)",
                fontsize=8,
                title_fontsize=9,
                loc="upper right",
                ncol=1,
                bbox_to_anchor=(lgnd_x, lgnd_y),
                facecolor="white",
                edgecolor="black",
                framealpha=1,
                frameon=frameon,
            )

            lgnd.set_zorder(1e10)
            lgnd.get_frame().set_zorder(1e10)

    if fname_savefig is not None:
        fig.tight_layout()
        Path(dir_plots_event_return_periods).mkdir(parents=True, exist_ok=True)
        plt.savefig(
            fname_savefig,
            format="pdf",
            bbox_inches="tight",
        )
        if clf:
            plt.clf()
    return dict_legend_items, lst_axes


def add_MHHW_line(
    ax, constant_sea_water_level_boundary, zorder=10, annotate=False, right_xlim=None
):
    if right_xlim is not None:
        xmin, xmax = ax.get_xlim()
        # print(f"only plotting MHHW from {[xmin, right_xlim]}")
        ax.plot(
            [xmin, right_xlim],  # x-range
            [constant_sea_water_level_boundary] * 2,  # same y for both points
            zorder=zorder,
            color="royalblue",
            linestyle="--",
            linewidth=2,
            label="MHHW",
        )

    else:
        ax.axhline(
            constant_sea_water_level_boundary,
            zorder=zorder,
            color="royalblue",
            ls="--",
            lw=2,
            label="MHHW",
        )

    if annotate:
        ax.annotate(
            "MHHW",
            xy=(0.75, 0.15),
            xycoords="axes fraction",
            fontsize=8,
            color="royalblue",
        )


def plot_conventional_design_storms_against_ensemble(
    df_rain_rtrn_pds,
    df_wlevel_return_pds,
    df_weather_events_in_ci_og,
    ds_multivar_return_periods,
    df_univariate_return_pds_og,
    df_sim_flood_probs_event_num_mapping,
    use_aep,
    ds_dsgn_tseries,
    constant_sea_water_level_boundary,
    dir_plots_event_return_periods,
    clf,
    ax=None,
    plot_legend=True,
    annotate_MHHW=True,
    clip_MHHW_to_max_rain=False,
):
    stats = f"{int(TARGET_DESIGN_STORM_DURATION_HRS_FOR_COMPARISON)}hr,w"
    formulation = "empirical_multivar_rtrn_yrs_AND"

    (
        df_stats,
        df_event_stats_and_prob,
        ar_probs_increasing_intensity,
        df_weather_events_in_ci,
        legend_title,
        multivar_formulation,
        df_weather_events_in_ci_univar,
    ) = retrieve_event_data_for_plotting(
        formulation,
        stats,
        df_rain_rtrn_pds,
        df_wlevel_return_pds,
        df_weather_events_in_ci_og,
        ds_multivar_return_periods,
        df_univariate_return_pds_og,
        df_sim_flood_probs_event_num_mapping,
        use_aep,
    )

    dpi = 300
    figsize = (3.5, 3)
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize, dpi=300)
    # sns.scatterplot(data=df_event_stats_and_prob, x=df_event_stats_and_prob.columns[0], y=df_event_stats_and_prob.columns[1], hue=df_event_stats_and_prob.columns[-1],
    #     alpha=.5, palette=cmap_rtrn_pd, hue_norm = norm_rtrn_pd, **dict(edgecolors = "g"))
    x = df_event_stats_and_prob.iloc[:, 0]
    y = df_event_stats_and_prob.iloc[:, 1]
    sc = ax.scatter(
        x=x,
        y=y,
        s=4,
        zorder=9,
        facecolors="none",
        edgecolors="k",
        alpha=0.2,
        linewidth=0.5,
    )

    dic_cmap = dict()
    lst_freq_patches = []
    for idx, trgt_prob in enumerate(ar_probs_increasing_intensity):
        dic_cmap[trgt_prob] = LST_RTRN_PD_COLORS[idx]
        patch = mpatches.Patch(
            facecolor=dic_cmap[trgt_prob],
            alpha=1,
            label=trgt_prob,
            edgecolor="grey",
        )
        lst_freq_patches.append(patch)

    xlims, ylims = return_axlims(
        x, y, ar_probs_increasing_intensity, df_weather_events_in_ci
    )

    x_label = tidy_hydro_varnames_for_plots(x.name)
    y_label = tidy_hydro_varnames_for_plots(y.name)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    xlims = (-1 * 0.05 * xlims[1], xlims[1] * 1.1)
    ax.set_xlim(xlims)
    if ax is not None:
        ax.set_ylim(ylims)

    df_design_storm_stats = retreive_design_storm_stats(ds_dsgn_tseries, use_aep)
    df_design_storm_stats = df_design_storm_stats.loc[ar_probs_increasing_intensity]

    rightmost_rain_depth = -9999

    for trgt_prob in df_design_storm_stats.sort_index().index:
        s_single_design_storm_stats = df_design_storm_stats.loc[trgt_prob]

        # combined
        # sc_trgt_prob = ax.scatter(
        #     x=[s_single_design_storm_stats["design_storm_depth_mm"]],
        #     y=[s_single_design_storm_stats["waterlevel_m"]],
        #     s=140,
        #     facecolor=dic_cmap[trgt_prob],
        #     zorder=20,
        #     edgecolor="k",
        #     marker="*",
        #     linewidths=0.8,
        #     label=trgt_prob,
        # )
        circ_size = 90
        x_size = 0.8 * circ_size
        scatter_zorder = 10

        ax.scatter(
            x=[s_single_design_storm_stats["design_storm_depth_mm"]],
            y=[s_single_design_storm_stats["waterlevel_m"]],
            s=circ_size,  # size of circles
            facecolor=dic_cmap[trgt_prob],
            edgecolor="black",
            linewidth=1,
            marker="o",
            zorder=scatter_zorder,
        )

        if s_single_design_storm_stats["design_storm_depth_mm"] > rightmost_rain_depth:
            rightmost_rain_depth = s_single_design_storm_stats["design_storm_depth_mm"]

        ax.scatter(
            x=[s_single_design_storm_stats["design_storm_depth_mm"]],
            y=[s_single_design_storm_stats["waterlevel_m"]],
            s=x_size,
            facecolor=dic_cmap[trgt_prob],
            edgecolor="black",
            linewidth=1,
            marker="X",
            zorder=scatter_zorder + 1,
        )

        # rain only
        ax.scatter(
            x=[s_single_design_storm_stats["design_storm_depth_mm"]],
            y=constant_sea_water_level_boundary,
            s=circ_size,  # size of circles
            facecolor=dic_cmap[trgt_prob],
            edgecolor="black",
            linewidth=1,
            marker="o",
            zorder=scatter_zorder,
        )

        # surge only
        ax.scatter(
            x=0,
            y=[s_single_design_storm_stats["waterlevel_m"]],
            s=x_size,
            facecolor=dic_cmap[trgt_prob],
            edgecolor="black",
            linewidth=1,
            marker="X",
            zorder=scatter_zorder + 1,
        )

        min_x = 0
        min_y = constant_sea_water_level_boundary
        xval = s_single_design_storm_stats["design_storm_depth_mm"]
        yval = s_single_design_storm_stats["waterlevel_m"]

        ax.plot(
            [xval, xval],
            [min_y, yval],
            color=dic_cmap[trgt_prob],
            linewidth=1.5,
            zorder=scatter_zorder - 0.1,
        )

        ax.plot(
            [min_x, xval],
            [yval, yval],
            color=dic_cmap[trgt_prob],
            linewidth=1.5,
            zorder=scatter_zorder - 0.1,
        )

    # print(f"rightmost rain depth: {right_xlim}")
    right_xlim = None
    if clip_MHHW_to_max_rain:
        right_xlim = rightmost_rain_depth
    add_MHHW_line(
        ax,
        constant_sea_water_level_boundary,
        zorder=scatter_zorder - 0.2,
        annotate=annotate_MHHW,
        right_xlim=right_xlim,
    )

    # figuring out legened
    # Legend proxies
    handle_composite = Line2D([], [], linestyle="")  # composite (needs custom handler)
    handle_circle = Line2D(
        [],
        [],
        marker="o",
        markersize=10,
        markerfacecolor="lightgrey",
        markeredgecolor="black",
        markeredgewidth=1,
        linestyle="",
    )
    handle_x = Line2D(
        [],
        [],
        marker="X",
        markersize=8,
        markerfacecolor="lightgrey",
        markeredgecolor="black",
        markeredgewidth=1,
        linestyle="",
    )

    handle_ensemble = Line2D(
        [],
        [],
        marker="o",
        markersize=3.5,
        markerfacecolor="none",
        markeredgecolor="black",
        markeredgewidth=1,
        alpha=0.2,
        linestyle="",
    )

    lgnd_x = 0.89  # 0.908
    frameon = True
    adj = 0.012

    dic_event_type = dict(
        symbols=[handle_composite, handle_circle, handle_x],
        labels=["Combined", "Rain-only", "Surge-only", "Ensemble"],
    )
    ax.grid(True)

    if plot_legend:
        legend_freqs = ax.legend(
            handles=lst_freq_patches,
            loc="upper left",
            # bbox_to_anchor=(1.129, 0.89),
            bbox_to_anchor=(0 - adj, 1 + adj),
            frameon=frameon,
            title="Annual Frequency",
            fontsize=8,
            title_fontsize=8,
            ncol=2,
            facecolor="white",
            edgecolor="black",
            framealpha=1,
        )
        legend_freqs.set_zorder(scatter_zorder + 2)
        legend_freqs.get_frame().set_zorder(scatter_zorder + 2)

        ax.add_artist(legend_freqs)

        legend_eventtype = ax.legend(
            dic_event_type["symbols"],  # , handle_ensemble],
            dic_event_type["labels"],
            handler_map={handle_composite: HandlerCircleX()},
            fontsize=8,
            title_fontsize=8,
            title="Event Type",
            loc="upper right",
            bbox_to_anchor=(1 + adj, 1 + adj),
            facecolor="white",
            edgecolor="black",
            frameon=frameon,
            ncol=1,
            framealpha=1,
        )

        legend_eventtype.set_zorder(scatter_zorder + 2)
        legend_eventtype.get_frame().set_zorder(scatter_zorder + 2)

    if ax is None:
        plt.savefig(
            f"{dir_plots_event_return_periods}CDS_with_MHHW.pdf",
            format="pdf",
            bbox_inches="tight",
        )
        if clf:
            plt.clf()
    return lst_freq_patches, dic_event_type


def create_event_scatterplot_with_CDS_and_MCDS(
    df_rain_rtrn_pds,
    df_wlevel_return_pds,
    df_weather_events_in_ci_og,
    ds_multivar_return_periods,
    df_sim_flood_probs_event_num_mapping,
    use_aep,
    dir_plots_event_return_periods,
    df_univariate_return_pds_og,
    ds_dsgn_tseries,
    constant_sea_water_level_boundary,
):
    figsize = (7, 2)
    fig, axes = plt.subplots(
        ncols=3, nrows=1, sharey=True, figsize=figsize, dpi=300
    )  # , constrained_layout=True,)
    # fig.subplots_adjust(wspace=0, hspace=0)
    fig.subplots_adjust(wspace=0, hspace=0)
    ax_dsgn = axes[0]
    add_subplot_id(ax=ax_dsgn, ax_id=0)
    ax_multivar = axes[1]
    add_subplot_id(ax=ax_multivar, ax_id=1)
    ax_univar = axes[2]
    add_subplot_id(ax=ax_univar, ax_id=2)
    ax_multivar.tick_params(axis="y", left=False, labelleft=False)
    ax_univar.tick_params(axis="y", left=False, labelleft=False)

    dict_forms_and_stats = dict(
        formulations=[
            FORMULATION_FOR_MC_DSGN_STRM_SEL_MULTIVAR_AND,
            FORMULATION_FOR_MC_DSGN_STRM_SEL_UNIVAR,
        ],
        stats=[
            EVENT_STAT_FOR_MC_DSGN_STRM_SEL_MULTIVAR_AND,
            EVENT_STAT_FOR_MC_DSGN_STRM_SEL_UNIVAR,
        ],
    )

    lst_axes = [ax_multivar, ax_univar]

    dict_legend_items, lst_axes = plot_mcds_events(
        df_rain_rtrn_pds,
        df_wlevel_return_pds,
        df_weather_events_in_ci_og,
        ds_multivar_return_periods,
        df_sim_flood_probs_event_num_mapping,
        use_aep,
        dir_plots_event_return_periods,
        df_univariate_return_pds_og,
        dict_forms_and_stats=dict_forms_and_stats,
        clf=False,
        lst_axes=lst_axes,
        plot_legend=False,
        constant_sea_water_level_boundary=constant_sea_water_level_boundary,
    )

    lst_legend_handles_multivar = dict_legend_items[
        f"{FORMULATION_FOR_MC_DSGN_STRM_SEL_MULTIVAR_AND}.{EVENT_STAT_FOR_MC_DSGN_STRM_SEL_MULTIVAR_AND}"
    ]
    lst_legend_handles_univar = dict_legend_items[
        f"{FORMULATION_FOR_MC_DSGN_STRM_SEL_UNIVAR}.{EVENT_STAT_FOR_MC_DSGN_STRM_SEL_UNIVAR}"
    ]

    ax_multivar.set_ylabel("")

    lst_freq_patches, dic_event_type = plot_conventional_design_storms_against_ensemble(
        df_rain_rtrn_pds,
        df_wlevel_return_pds,
        df_weather_events_in_ci_og,
        ds_multivar_return_periods,
        df_univariate_return_pds_og,
        df_sim_flood_probs_event_num_mapping,
        use_aep,
        ds_dsgn_tseries,
        constant_sea_water_level_boundary=constant_sea_water_level_boundary,
        dir_plots_event_return_periods=dir_plots_event_return_periods,
        clf=False,
        ax=ax_dsgn,
        plot_legend=False,
        annotate_MHHW=False,
        clip_MHHW_to_max_rain=True,
    )

    ax_univar.set_ylabel("")

    # params for within
    lgnd_y = 1.04
    lgnd_x = 1.04
    ncols = 1
    loc_desc = "upper right"
    frameon = False
    framealpha = 0.5
    ax_multivar.grid(False)
    ax_univar.grid(False)

    multivar_lgnd = ax_multivar.legend(
        handles=lst_legend_handles_multivar,
        labels=[h.get_label() for h in lst_legend_handles_multivar],
        title="MCDS-AND\n(n events)",
        fontsize=8,
        title_fontsize=9,
        loc=loc_desc,
        ncol=ncols,
        bbox_to_anchor=(lgnd_x, lgnd_y),
        facecolor="white",
        edgecolor="black",
        framealpha=framealpha,
        frameon=frameon,
    )

    multivar_lgnd.set_zorder(1e10)
    multivar_lgnd.get_frame().set_zorder(1e10)

    univar_lgnd = ax_univar.legend(
        handles=lst_legend_handles_univar,
        labels=[h.get_label() for h in lst_legend_handles_univar],
        title="MCDS-U\n(n events)",
        fontsize=8,
        title_fontsize=9,
        loc=loc_desc,
        ncol=ncols,
        bbox_to_anchor=(lgnd_x, lgnd_y),
        facecolor="white",
        edgecolor="black",
        framealpha=framealpha,
        frameon=frameon,
    )

    univar_lgnd.set_zorder(1e10)
    univar_lgnd.get_frame().set_zorder(1e10)

    # design storm legends
    ax_dsgn.grid(False)
    lgnd_y = 1.04
    lgnd_x = 1.04
    ncols = 1
    loc_desc = "upper right"
    frameon = False
    framealpha = 0.5

    from local.__plotting import HandlerCircleX

    alt_labs = ["Joint", "Rain\nOnly", "Surge\nOnly"]

    legend_eventtype = ax_dsgn.legend(
        dic_event_type["symbols"],  # , handle_ensemble],
        alt_labs,  # dic_event_type["labels"],
        handler_map={dic_event_type["symbols"][0]: HandlerCircleX()},
        fontsize=8,
        title_fontsize=8,
        title="BDS Type",
        loc="upper right",
        bbox_to_anchor=(lgnd_x, lgnd_y),
        facecolor="white",
        edgecolor="black",
        frameon=frameon,
        ncol=ncols,
        framealpha=1,
    )

    legend_eventtype.set_zorder(1e6)
    legend_eventtype.get_frame().set_zorder(1e6)

    ax_dsgn.add_artist(legend_eventtype)

    legend_freqs = ax_dsgn.legend(
        handles=lst_freq_patches,
        loc=loc_desc,
        bbox_to_anchor=(lgnd_x, 0.455),
        frameon=frameon,
        title="Annual Freq",
        fontsize=8,
        title_fontsize=8,
        ncol=1,
        facecolor="white",
        edgecolor="black",
        framealpha=1,
    )

    legend_freqs.set_zorder(1e6)
    legend_freqs.get_frame().set_zorder(1e6)

    ax_dsgn.annotate(
        "MHHW",
        xy=(0.37, 0.02),
        xycoords="axes fraction",
        fontsize=8,
        color="royalblue",
        fontweight="bold",
    )

    plt.savefig(
        f"{dir_plots_event_return_periods}MCDS_and_CDS_event_scatterplots.pdf",
        format="pdf",
        bbox_inches="tight",
    )

    return


def plot_event_statistic_return_period_maps_for_target_return_period_and_minimum_flood_depth(
    ax,
    df_event_return_periods,
    ds_ssfha_rtrn_pds,
    return_period,
    event_stat,
    ensemble_type="compound",
    quantile=0.5,
    anchor_vals=np.asarray([0.5, 1, 2, 10, 50, 100, 250]),
    ticks=[0.5, 1, 2, 10, 50, 100, 200],
    min_fld_thrsh=MIN_THRESH_FLDING,
    quants=[0.05, 0.5, 0.95],
    cmap_name="Spectral",
    display_cbar=False,
):

    print(f"Maps are based on flood depths >= {min_fld_thrsh}")

    if "ensemble_type" in ds_ssfha_rtrn_pds.dims:
        ds_subset = ds_ssfha_rtrn_pds.sel(
            year=return_period, ensemble_type=ensemble_type
        )

    if "quantile" in ds_ssfha_rtrn_pds.dims:
        ds_subset = ds_ssfha_rtrn_pds.sel(
            return_pd_yrs=return_period, quantile=quantile
        )

    da_wlevel = ds_subset["max_wlevel_m"]
    mask_fld_thrsh = da_wlevel >= min_fld_thrsh
    da_event_ids = ds_subset["contributing_event_id"].where(mask_fld_thrsh)

    df_stat_rtrn_pds_only = df_event_return_periods.drop(
        columns=["data_source", "model", "simtype"]
    )

    og_idx = da_event_ids.to_dataframe().index

    df_contributing_event_ids = (
        da_event_ids.to_dataframe().dropna().astype(dict(contributing_event_id=int))
    )

    df_contributing_event_ids = df_contributing_event_ids.join(
        df_stat_rtrn_pds_only, on="contributing_event_id"
    )

    # compute positions in colormap space consistent with LogNorm
    from matplotlib.colors import LinearSegmentedColormap, LogNorm

    # anchor_vals = [2, 10, 100]
    # anchor_colors = ["#e41a1c", "#377eb8", "#4daf4a"]

    vmin = min(anchor_vals)
    vmax = max(anchor_vals)

    def log_pos(val, vmin=vmin, vmax=vmax):
        return (np.log(val) - np.log(vmin)) / (np.log(vmax) - np.log(vmin))

    # custom colorbar

    anchor_pos_log = [log_pos(a) for a in anchor_vals]
    # anchor_colors = [
    #     "#ffffbf",
    #     "#a6bddb",
    #     "#045a8d",
    #     "#78c679",
    #     "#fe9929",
    #     "#d73027",
    #     "#800026",
    # ]
    # cmap = LinearSegmentedColormap.from_list(
    #     "custom_cmap", list(zip(anchor_pos, anchor_colors)), N=256
    # )

    midpoints = (anchor_vals[:-1] + anchor_vals[1:]) / 2
    bounds = np.concatenate(
        (
            [anchor_vals[0] - (midpoints[0] - anchor_vals[0])],
            midpoints,
            [anchor_vals[-1] + (anchor_vals[-1] - midpoints[-1])],
        )
    )

    cmap = mpl.colormaps[cmap_name]
    cmap.set_bad("lightgray")
    norm = LogNorm(vmin=vmin, vmax=vmax)
    # norm = mpl.colors.BoundaryNorm(boundaries=bounds, ncolors=cmap.N)
    # norm = mpl.colors.BoundaryNorm(boundaries = anchor_vals, ncolors = len(anchor_vals))

    # desired colorbar ticks (you asked earlier about these)

    plt_map = (
        df_contributing_event_ids.reindex(og_idx)
        .to_xarray()[event_stat]
        .plot.pcolormesh(
            x="x",
            y="y",
            ax=ax,
            cmap=cmap,
            norm=norm,
            add_colorbar=display_cbar,
            # cbar_kwargs={"ticks": ticks},
        )
    )
    import geopandas as gpd

    gdf = gpd.read_file(F_WSHED_SHP)
    gdf.boundary.plot(ax=ax, color="black", linewidth=1)

    ax.set_xticklabels([])  # Remove x-axis tick labels
    ax.set_yticklabels([])  # Remove y-axis tick labels
    ax.set_ylabel("")
    ax.set_xlabel("")
    if display_cbar:
        plt_map.colorbar.set_ticks(ticks)
        plt_map.colorbar.set_ticklabels([str(t) for t in ticks])
        # optional: tweak font size/rotation
        plt_map.colorbar.ax.tick_params(labelsize=10, rotation=0)

    rtrn_quants = df_contributing_event_ids[event_stat].quantile(
        quants, interpolation="nearest"
    )

    q05, q50, q95 = rtrn_quants.values

    color_q05 = cmap(norm(q05))
    color_q50 = cmap(norm(q50))
    color_q95 = cmap(norm(q95))
    color_target_rtrn = cmap(norm(return_period))

    # ensure tick labels display exactly as you want (plain numbers)
    # this forces the labels to be the string form of the ticks you gave

    bbox_props = dict(
        boxstyle="round,pad=0.2", facecolor="lightgray", edgecolor="none", alpha=0.8
    )

    import matplotlib.patches as patches

    box_x = 0.68
    box_y = 0.01
    box_width = 0.31
    box_height = 0.28

    box = patches.FancyBboxPatch(
        (box_x, box_y),
        box_width,
        box_height,
        boxstyle="square,pad=0",
        transform=ax.transAxes,
        facecolor="lightgray",
        edgecolor="black",
        alpha=0.85,
        zorder=2,  # draw above map, below text
    )
    # annotation_text = "90% CI: " f"{q05:.2f}, {q95:.2f}\n" f"Median: {q50:.2f}"
    # ax.add_patch(box)

    # Write the annotation with individually colored numbers

    from matplotlib import patheffects

    fontsize = 9

    xs = [box_x - box_x * 0.1, box_x + (box_width - box_width * 0.7)]

    ys = [
        box_y + (box_height * 1.1 - box_height),
        box_y + (box_height * 1.35 - box_height),
        box_y + (box_height * 1.6 - box_height),
        box_y + (box_height * 1.8 - box_height),  # header
    ]

    # headers

    ax.text(
        xs[0] + 0.04,
        ys[3] - 0.02,
        "Quant.",
        transform=ax.transAxes,
        va="bottom",
        ha="left",
        fontsize=fontsize,
        color="black",  # label color
        # bbox=bbox_props,
        zorder=3,
    )

    # ax.text(
    #     xs[1] - 0.02,
    #     ys[3],
    #     "Ret.Pd.",
    #     transform=ax.transAxes,
    #     va="bottom",
    #     ha="left",
    #     fontsize=fontsize,
    #     color="black",  # label color
    #     # bbox=bbox_props,
    #     zorder=3,
    # )

    # column 1 = quantiles (top to bottom)
    ax.text(
        xs[0] * 1.25,
        ys[2],
        f"{quants[0]},",
        transform=ax.transAxes,
        va="center",
        ha="right",
        fontsize=fontsize,
        color="k",
        # bbox=bbox_props,
        zorder=3,
        # path_effects=[patheffects.withStroke(linewidth=2, foreground="k")],
        # weight="heavy",
    )
    ax.text(
        xs[0] * 1.25,
        ys[1],
        f"{quants[1]},",
        transform=ax.transAxes,
        va="center",
        ha="right",
        fontsize=fontsize,
        color="k",
        # bbox=bbox_props,
        zorder=3,
        # path_effects=[patheffects.withStroke(linewidth=2, foreground="k")],
        # weight="heavy",
    )
    ax.text(
        xs[0] * 1.25,
        ys[0],
        f"{quants[2]},",
        transform=ax.transAxes,
        va="center",
        ha="right",
        fontsize=fontsize,
        color="k",
        zorder=3,
        # path_effects=[patheffects.withStroke(linewidth=2, foreground="k")],
        # weight="heavy",
    )

    text_outline_width = 1.15
    # column 2 - values (top to bottom)

    def fmt_sig_maxdec(x, sig=3, max_dec=1):
        s = f"{x:.{sig}g}"
        if "e" in s or "." not in s:
            return s
        whole, frac = s.split(".")
        return whole + "." + frac[:max_dec]

    fontsize_for_quants = 8.5
    ax.text(
        xs[1],
        ys[2],
        fmt_sig_maxdec(q05),
        # f"{q05:.3g}",
        transform=ax.transAxes,
        va="center",
        ha="left",
        fontsize=fontsize_for_quants,
        color=color_q05,
        # bbox=bbox_props,
        zorder=3,
        path_effects=[
            patheffects.withStroke(linewidth=text_outline_width, foreground="k")
        ],
        weight="heavy",
    )
    ax.text(
        xs[1],
        ys[1],
        fmt_sig_maxdec(q50),
        # f"{q50:.3g}",
        transform=ax.transAxes,
        va="center",
        ha="left",
        fontsize=fontsize_for_quants,
        color=color_q50,
        zorder=3,
        path_effects=[
            patheffects.withStroke(linewidth=text_outline_width, foreground="k")
        ],
        weight="heavy",
    )
    ax.text(
        xs[1],
        ys[0],
        fmt_sig_maxdec(q95),
        # f"{q95:.3g}",
        transform=ax.transAxes,
        va="center",
        ha="left",
        fontsize=fontsize_for_quants,
        color=color_q95,
        zorder=3,
        path_effects=[
            patheffects.withStroke(linewidth=text_outline_width, foreground="k")
        ],
        weight="heavy",
    )

    return plt_map, ticks, color_target_rtrn


def plot_event_statistic_return_period_scatterplots_for_target_return_period_and_minimum_flood_depth(
    ax,
    df_event_return_periods,
    ds_ensemble_return_pds,
    return_period,
    event_set,
    ensemble_type,
    x_axis,
    y_axis="max_waterlevel_m_return_pd_yrs",
):

    s_contributing_events = (
        (
            ds_ensemble_return_pds.sel(year=return_period, ensemble_type=ensemble_type)[
                event_set
            ]
            .to_dataframe()
            .dropna()
        )
        .reset_index()
        .rename(columns={event_set: "event_number"})
        .astype(dict(event_number=int))
    )["event_number"]

    df_event_return_periods.loc[s_contributing_events.values, :]

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.grid(True)

    x = df_event_return_periods[x_axis]
    y = df_event_return_periods[y_axis]
    ax.scatter(
        x=x,
        y=y,
        s=4,
        zorder=9,
        facecolors="none",
        edgecolors="k",
        alpha=0.2,
        linewidths=0.5,
    )
    return s_contributing_events


def plot_ensemle_vs_mc_design_storms_vs_conventional_design_storms(
    formulation,
    stats,
    df_rain_rtrn_pds,
    df_wlevel_return_pds,
    df_weather_events_in_ci_og,
    df_return_pd_cis_univar_og,
    ds_multivar_return_periods,
    df_sim_flood_probs_event_num_mapping,
    use_aep,
    dir_plots_event_return_periods,
    ds_dsgn_tseries,
    df_univariate_return_pds_og,
    constant_sea_water_level_boundary=None,
    clf=True,
    plot_univar_CIs=False,
):
    #  plot MCDS
    dpi = 300
    figsize = (3.5, 3)

    (
        df_stats,
        df_event_stats_and_prob,
        ar_probs_increasing_intensity,
        df_weather_events_in_ci,
        legend_title,
        multivar_formulation,
        df_weather_events_in_ci_univar,
    ) = retrieve_event_data_for_plotting(
        formulation,
        stats,
        df_rain_rtrn_pds,
        df_wlevel_return_pds,
        df_weather_events_in_ci_og,
        ds_multivar_return_periods,
        df_univariate_return_pds_og,
        df_sim_flood_probs_event_num_mapping,
        use_aep,
    )

    # if multivar_formulation is not None:
    if len(df_stats.columns) > 2:
        # return
        print("may cause error; uncomment return statement if so")
    # plotting the subset of events for this particular fomulation
    # sys.exit('work')
    # plot all events highlighting the ones that correspond to the MC return period
    fig, ax = plt.subplots(figsize=figsize, dpi=300)

    populate_mcds_axis_object(
        formulation,
        stats,
        df_rain_rtrn_pds,
        df_wlevel_return_pds,
        df_weather_events_in_ci_og,
        ds_multivar_return_periods,
        df_univariate_return_pds_og,
        df_sim_flood_probs_event_num_mapping,
        use_aep,
        ax,
    )

    Path(dir_plots_event_return_periods).mkdir(parents=True, exist_ok=True)
    plt.savefig(
        f"{dir_plots_event_return_periods}{formulation}_{stats}_mc_storms.pdf",
        format="pdf",
        bbox_inches="tight",
    )
    if clf:
        plt.clf()
    # # %%
    # if f"{int(TARGET_DESIGN_STORM_DURATION_HRS_FOR_COMPARISON)}hr" in x.name:
    #     # create plot of just design storms

    #     # %%

    #     rain_only_legend_item = Line2D(
    #         [0],
    #         [0],
    #         color="black",
    #         marker="o",
    #         markersize=6,
    #         linestyle="None",
    #         markerfacecolor="orange",
    #         label="Rain-only",
    #     )

    #     lst_legend_items = [
    #         rain_only_legend_item,
    #     ]

    #     legend = fig.legend(
    #         handles=lst_legend_items,
    #         loc="upper right",
    #         bbox_to_anchor=(1.2, 0.55),
    #         frameon=False,
    #         title="Storm\nFormulation",
    #         fontsize=8,
    #         title_fontsize=8,
    #         ncol=1,
    #         facecolor="none",
    #         edgecolor="black",
    #     )

    #     # %% plot MCDS with design storms
    #     # same plot but with shaded regions representing univariate return periods
    #     from matplotlib.patches import Patch

    #     fig, ax = plt.subplots(figsize=figsize, dpi=300)
    #     # sns.scatterplot(data=df_event_stats_and_prob, x=df_event_stats_and_prob.columns[0], y=df_event_stats_and_prob.columns[1], hue=df_event_stats_and_prob.columns[-1],
    #     #     alpha=.5, palette=cmap_rtrn_pd, hue_norm = norm_rtrn_pd, **dict(edgecolors = "g"))
    #     x = df_event_stats_and_prob.iloc[:, 0]
    #     y = df_event_stats_and_prob.iloc[:, 1]
    #     z = df_event_stats_and_prob.iloc[:, -1]
    #     # colors = cmap_rtrn_pd(norm_rtrn_pd(z))  # Compute edge colors manually
    #     # sc = ax.scatter(x = x, y = y, c = z,s = 10, cmap = cmap_rtrn_pd, norm = norm_rtrn_pd, zorder = 9,
    #     #                 facecolors='none', edgecolors=cmap_rtrn_pd(norm_rtrn_pd(z)))

    #     # sc = ax.scatter(x = x, y = y,s = 10, zorder = 9,
    #     #                 facecolors='none', edgecolors=colors)

    #     sc = ax.scatter(
    #         x=x, y=y, s=10, zorder=9, facecolors="none", edgecolors="k", alpha=0.2
    #     )

    #     lst_colors_increasing_severity = ["#ffffd4", "#fed98e", "#fe9929", "#cc4c02"]
    #     dic_cmap = dict()
    #     for idx, trgt_prob in enumerate(ar_probs_increasing_intensity):
    #         dic_cmap[trgt_prob] = lst_colors_increasing_severity[idx]

    #     lst_legend_handles = []
    #     lst_freq_patches = []
    #     x_ll = np.inf
    #     x_ul = -np.inf
    #     y_ll = np.inf
    #     y_ul = -np.inf
    #     for trgt_prob, df_grp in df_weather_events_in_ci.groupby("return_period_yrs"):
    #         idx_trgt_prob = df_weather_events_in_ci.loc[
    #             pd.IndexSlice[trgt_prob, :]
    #         ].index

    #         x_subset = x.loc[idx_trgt_prob]
    #         y_subset = y.loc[idx_trgt_prob]

    #         # update ax lims
    #         if x_ll > x_subset.min():
    #             x_ll = x_subset.min()
    #         if x_ul < x_subset.max():
    #             x_ul = x_subset.max()

    #         if y_ll > y_subset.min():
    #             y_ll = y_subset.min()
    #         if y_ul < y_subset.max():
    #             y_ul = y_subset.max()

    #         sc_trgt_prob = ax.scatter(
    #             x=x_subset,
    #             y=y_subset,
    #             s=10,
    #             facecolor=dic_cmap[trgt_prob],
    #             zorder=10,
    #             edgecolor="k",
    #             linewidths=0.5,
    #             label=trgt_prob,
    #         )
    #         legend_handle = Line2D(
    #             [0],
    #             [0],
    #             linestyle="None",
    #             marker="o",
    #             markersize=8,
    #             markerfacecolor=dic_cmap[trgt_prob],
    #             zorder=10,
    #             markeredgecolor="k",
    #             label=trgt_prob,
    #         )
    #         lst_legend_handles.append(legend_handle)

    #         # fill between representing univariate return periods
    #         fillbtw_alpha = 0.6

    #         s_weather_events_in_ci_univar_x = df_weather_events_in_ci_univar.loc[
    #             pd.IndexSlice[x.name, trgt_prob, :]
    #         ].copy()["q1"]
    #         s_weather_events_in_ci_univar_y = df_weather_events_in_ci_univar.loc[
    #             pd.IndexSlice[y.name, trgt_prob, :]
    #         ].copy()["q1"]

    #         if plot_univar_CIs:
    #             ax.fill_between(
    #                 [
    #                     s_weather_events_in_ci_univar_x.min(),
    #                     s_weather_events_in_ci_univar_x.max(),
    #                 ],
    #                 s_weather_events_in_ci_univar_y.min(),
    #                 facecolor=dic_cmap[trgt_prob],
    #                 alpha=fillbtw_alpha,
    #                 zorder=9,
    #                 edgecolor="none",
    #             )
    #             ax.fill_betweenx(
    #                 [
    #                     s_weather_events_in_ci_univar_y.min(),
    #                     s_weather_events_in_ci_univar_y.max(),
    #                 ],
    #                 s_weather_events_in_ci_univar_x.max(),
    #                 facecolor=dic_cmap[trgt_prob],
    #                 alpha=fillbtw_alpha,
    #                 zorder=9,
    #                 edgecolor="none",
    #             )
    #         patch = mpatches.Patch(
    #             facecolor=dic_cmap[trgt_prob],
    #             alpha=0.9,
    #             label=trgt_prob,
    #             edgecolor="grey",
    #         )
    #         lst_freq_patches.append(patch)
    #     # ax.set_facecolor("lightgrey")

    #     univar_legend_item = mpatches.Patch(
    #         facecolor="grey", alpha=0.9, edgecolor="grey", label="univariate"
    #     )
    #     ensemble_legend_item = Line2D(
    #         [0],
    #         [0],
    #         color="black",
    #         marker="o",
    #         markersize=6,
    #         linestyle="None",
    #         markerfacecolor="none",
    #         label="ensemble",
    #     )

    #     mcds_legend_item = Line2D(
    #         [0],
    #         [0],
    #         color="black",
    #         marker="o",
    #         markersize=6,
    #         linestyle="None",
    #         markerfacecolor="grey",
    #         alpha=0.9,
    #         label=f"Monte-Carlo\ndesign storm\n({multivar_formulation})",
    #     )

    #     header_storm_type_patch = [
    #         Line2D([], [], marker="", color="none", label="Storm\nFormulation")
    #     ]

    #     lim_buff = 0.5
    #     xlims = (max(x_ll * (1 - lim_buff), 0), x_ul * (1 + lim_buff))
    #     ylims = (max(y_ll * (1 - lim_buff), 0), y_ul * (1 + lim_buff))

    #     ax.grid(True)
    #     ax.set_xlabel(x_label)
    #     ax.set_ylabel(y_label)
    #     ax.set_xlim(xlims)
    #     ax.set_ylim(ylims)
    #     # plt.savefig(
    #     #     f"{dir_plots_event_return_periods}{formulation}_{stats}_w_univar_prob.pdf",
    #     #     format="pdf",
    #     # )
    #     lst_event_type_legend_items = [
    #         ensemble_legend_item,
    #         mcds_legend_item,
    #     ]

    #     # if f"{int(TARGET_DESIGN_STORM_DURATION_HRS_FOR_COMPARISON)}hr" in x.name:
    #     # add conventional design storm values to the plot and save again
    #     ## subset design storm time series for compound event of targeted return period
    #     df_design_storm_stats = retreive_design_storm_stats(ds_dsgn_tseries, use_aep)

    #     # lst_dsgn_strm_legend_handles = []
    #     for trgt_prob in df_design_storm_stats.sort_index().index:
    #         s_single_design_storm_stats = df_design_storm_stats.loc[trgt_prob]
    #         sc_trgt_prob = ax.scatter(
    #             x=[s_single_design_storm_stats["design_storm_depth_mm"]],
    #             y=[s_single_design_storm_stats["waterlevel_m"]],
    #             s=140,
    #             facecolor=dic_cmap[trgt_prob],
    #             zorder=20,
    #             edgecolor="k",
    #             marker="*",
    #             linewidths=0.8,
    #             label=trgt_prob,
    #         )

    #         # legend_handle = Line2D(
    #         #     [0],
    #         #     [0],
    #         #     linestyle="None",
    #         #     marker="*",
    #         #     markersize=12,
    #         #     markerfacecolor=dic_cmap[trgt_prob],
    #         #     zorder=20,
    #         #     markeredgecolor="k",
    #         #     label=trgt_prob,
    #         # )
    #         # lst_dsgn_strm_legend_handles.append(legend_handle)

    #     # header_dsgn_patch = Line2D(
    #     #     [], [], marker="", color="none", label="conventional design\nstorms"
    #     # )

    #     design_storm_legend_item = Line2D(
    #         [0],
    #         [0],
    #         color="black",
    #         marker="*",
    #         markersize=9,
    #         linestyle="None",
    #         markerfacecolor="grey",
    #         alpha=0.9,
    #         label="conventional\ndesign storm",
    #     )

    #     # all_legend_elements_w_dsgn = (
    #     #     all_legend_elements + [header_dsgn_patch] + lst_dsgn_strm_legend_handles
    #     # )
    #     # legend.remove()

    #     lst_event_type_legend_items.append(design_storm_legend_item)

    #     if constant_sea_water_level_boundary is not None:

    #         ax.axhline(
    #             constant_sea_water_level_boundary,
    #             zorder=1e20,
    #             color="royalblue",
    #             ls="--",
    #             lw=2,
    #             label="MHHW",
    #         )
    #         ax.annotate(
    #             "MHHW",
    #             xy=(0.7, 0.27),
    #             xycoords="figure fraction",
    #             fontsize=8,
    #             color="royalblue",
    #         )

    #     legend_freqs = fig.legend(
    #         handles=lst_freq_patches,
    #         loc="upper right",
    #         bbox_to_anchor=(1.129, 0.89),
    #         frameon=False,
    #         title="Annual\nFrequency",
    #         fontsize=8,
    #         title_fontsize=8,
    #         ncol=1,
    #         facecolor="none",
    #         edgecolor="black",
    #     )

    #     legend = fig.legend(
    #         handles=lst_event_type_legend_items,
    #         loc="upper right",
    #         bbox_to_anchor=(1.2, 0.55),
    #         frameon=False,
    #         title="Storm\nFormulation",
    #         fontsize=8,
    #         title_fontsize=8,
    #         ncol=1,
    #         facecolor="none",
    #         edgecolor="black",
    #     )

    #     plt.savefig(
    #         f"{dir_plots_event_return_periods}MCDS_with_MHHW_{formulation}.{stats}.pdf",
    #         format="pdf",
    #         bbox_inches="tight",
    #     )
    #     if clf:
    #         plt.clf()
    # commented out code below created univariate statistics vs. return period plot with MCDS highlighted
    # else:
    #  univar vs. annual frequence
    # fig, ax = plt.subplots(figsize=figsize, dpi=300)
    # x = df_event_stats_and_prob.iloc[:, 0]
    # y = df_event_stats_and_prob.iloc[:, -1]

    # x_label = tidy_hydro_varnames_for_plots(x.name)
    # y_label = tidy_hydro_varnames_for_plots(y.name)

    # sc = ax.scatter(
    #     x=x, y=y, s=10, zorder=9, facecolors="none", edgecolors="k", alpha=0.2
    # )

    # # testing plotting the 50 year events
    # lst_colors_increasing_severity = ["#ffffd4", "#fed98e", "#fe9929", "#cc4c02"]
    # dic_cmap = dict()
    # for idx, trgt_prob in enumerate(ar_probs_increasing_intensity):
    #     dic_cmap[trgt_prob] = lst_colors_increasing_severity[idx]

    # lst_legend_handles = []
    # x_ll = np.inf
    # x_ul = -np.inf
    # y_ll = np.inf
    # y_ul = -np.inf
    # for trgt_prob, df_grp in df_weather_events_in_ci.groupby("return_period_yrs"):
    #     idx_trgt_prob = df_weather_events_in_ci.loc[
    #         pd.IndexSlice[trgt_prob, :]
    #     ].index

    #     x_subset = x.loc[idx_trgt_prob]
    #     y_subset = y.loc[idx_trgt_prob]

    #     # update ax lims
    #     if x_ll > x_subset.min():
    #         x_ll = x_subset.min()
    #     if x_ul < x_subset.max():
    #         x_ul = x_subset.max()

    #     if y_ll > y_subset.min():
    #         y_ll = y_subset.min()
    #     if y_ul < y_subset.max():
    #         y_ul = y_subset.max()

    #     sc_trgt_prob = ax.scatter(
    #         x=x_subset,
    #         y=y_subset,
    #         s=10,
    #         facecolor=dic_cmap[trgt_prob],
    #         zorder=10,
    #         edgecolor="k",
    #         linewidths=0.5,
    #         label=trgt_prob,
    #     )
    #     legend_handle = Line2D(
    #         [0],
    #         [0],
    #         linestyle="None",
    #         marker="o",
    #         markersize=8,
    #         markerfacecolor=dic_cmap[trgt_prob],
    #         zorder=10,
    #         markeredgecolor="k",
    #         label=trgt_prob,
    #     )
    #     lst_legend_handles.append(legend_handle)

    # ax.legend(
    #     handles=lst_legend_handles,
    #     labels=[h.get_label() for h in lst_legend_handles],
    #     title=legend_title,
    #     fontsize=8,
    #     title_fontsize=9,
    #     loc="upper right",
    # )

    # lim_buff = 0.5
    # xlims = (max(x_ll * (1 - lim_buff), 0), x_ul * (1 + lim_buff))
    # ylims = (max(y_ll * (1 - lim_buff), 0), y_ul * (1 + lim_buff))

    # ax.grid(True)
    # ax.set_xlabel(x_label)
    # ax.set_ylabel(prob_lab)
    # ax.set_xlim(xlims)
    # ax.set_ylim(ylims)
    # ax.semilogy()
    # if use_aep:
    #     ax.invert_yaxis()
    # ax.set_yticks(ar_probs_increasing_intensity)
    # ax.set_yticklabels(ar_probs_increasing_intensity)
    # plt.savefig(
    #     f"{dir_plots_event_return_periods}{formulation}_{stats}.pdf",
    #     format="pdf",
    #     bbox_inches="tight",
    # )
    # if clf:
    #     plt.clf()
    return


def retreive_design_storm_stats(ds_dsgn_tseries, use_aep):
    df_rain_tseries = ds_dsgn_tseries.sel(event_type="compound")[
        "mm_per_hr"
    ].to_dataframe()
    tstep = pd.Series(df_rain_tseries.loc[pd.IndexSlice[1, 1, :]].index.diff()).mode()[
        0
    ]
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
    mask_target_depths = df_design_storm_stats_trgt_dur["design_storm_depth_mm"].isin(
        df_median_depths
    )
    event_id = (
        df_design_storm_stats_trgt_dur[mask_target_depths]
        .reset_index()["event_id"]
        .unique()
    )

    df_wlevels = (
        ds_dsgn_tseries.sel(event_id=event_id, event_type="compound")["waterlevel_m"]
        .to_dataframe()
        .groupby(["event_type", "year", "event_id"])
        .max()
    )
    df_wlevels = df_wlevels.reset_index()[["year", "waterlevel_m"]].set_index("year")
    df_design_storm_stats = pd.concat([df_median_depths, df_wlevels], axis=1)
    df_design_storm_stats.index.name = "return_period"
    if use_aep:
        df_design_storm_stats.index = 1 / df_design_storm_stats.index
        df_design_storm_stats.index.name = "aep"
    return df_design_storm_stats


def tidy_hydro_varnames_for_plots(name, multivar_formulation=None):
    # name = "max_1hr_0min_mm"
    label = name
    label = label.replace("_return_pd_yrs", "")
    if "mm" in label:
        dur = (
            label.replace("_0hr", "")
            .replace("_0min", "")
            .replace("_mm", "")
            .replace("max_", "")
        )
        # dur = dur.replace("hr", " hours").replace("min", " minutes")
        # label = f"max rain intensity (mm per {dur})"
        label = f"max mm per {dur}"
        label = label.replace("hr", " hr")
        label = label.replace("min", " min")
    if "max_waterlevel_m" in label:
        # label = "max sea water level (m)"
        label = "max storm tide (m)"
    if "," in label:
        lab_parts = label.split(",")
        wlevel = lab_parts[-1]
        rain_parts = lab_parts[0:-1]
        label = ""
        for rain_part in rain_parts:
            dur = rain_part.split("hr")[0].split("min")[0]
            sublab = f"max mm per {dur} hr"
            label += f"{sublab}, "
        if len(rain_parts) == 1:
            label = label.replace(",", "")
        # label += f"{multivar_formulation} max sea water level"
        label += f"{multivar_formulation} max storm tide"
    if " 1 hr" in label:
        label = label.replace("1 hr", "hr")
    return label


def create_hexbin_weather_vs_impact_rtrn(
    df_sim_flood_probs_event_num_mapping,
    df_univariate_return_pds_og,
    ds_multivar_return_periods,
    ds_flood_impacts_by_aoi,
    df_return_pd_cis_flood_impacts_og,
    df_return_pd_cis_univar_og,
    df_return_pd_cis_multivar_og,
    impact_var,
    depth_range_m,
    subarea_name,
    stats,
    use_aep,
    event_idx_names,
    str_fig_title=None,
    fname_savefig=None,
    multivar_formulation=None,
    dpi=300,
):

    df_univariate_return_pds = df_univariate_return_pds_og.copy()
    df_return_pd_cis_univar = df_return_pd_cis_univar_og.copy()
    df_return_pd_cis_multivar = df_return_pd_cis_multivar_og.copy()
    df_return_pd_cis_flood_impacts = df_return_pd_cis_flood_impacts_og.copy()
    if multivar_formulation not in ["AND", "OR", None]:
        sys.exit(
            "need to specify a valid input for multivar_formulation of either AND or OR"
        )

    # determine whether the stat is multivariate or univariate
    lst_stat_components = stats.split(",")
    idx_valid_stat = [len(stat) > 0 for stat in lst_stat_components]
    s_stats = pd.Series(lst_stat_components)[idx_valid_stat]
    multivariate = False
    if len(s_stats) > 1:
        multivariate = True
    # subset either the multivariate or univariate event statistic return period dataframes
    if multivariate:
        df_cis = df_return_pd_cis_multivar
        df_multivar_return_periods_all = (
            ds_multivar_return_periods.sel(event_stats=stats)
            .to_dataframe()
            .reset_index()
            .set_index(event_idx_names)
            .drop(columns=["event_stats"])
        )
        # multivar_formulation = event_stat_type.split("_")[-1]
        idx_cols = [
            ("rtrn_yrs" in col) and (multivar_formulation in col)
            for col in df_multivar_return_periods_all.columns
        ]
        cols = df_multivar_return_periods_all.columns[idx_cols]
        df_event_return_periods_all = df_multivar_return_periods_all.loc[:, cols]
    else:
        df_cis = df_return_pd_cis_univar
        idx_cols = [(stats in col) for col in df_univariate_return_pds.columns]
        cols = df_univariate_return_pds.columns[idx_cols]
        df_event_return_periods_all = df_univariate_return_pds.loc[:, cols]

    min_x, min_y = (
        0.5,
        0.5,
    )  # minimum value for x and y axes (really small values can do crazy things in loglog)
    # subset flood area return period for the subarea and depth range being analyzed
    df_flood_impact_return_pds_subset_all = (
        ds_flood_impacts_by_aoi.sel(
            subarea_name=subarea_name, depth_range_m=depth_range_m
        )
        .to_dataframe()
        .dropna()
    )
    if "flooded_area" in impact_var:
        # continue
        df_flood_impact_return_pds_subset_all = (
            df_flood_impact_return_pds_subset_all.filter(like="flooded_area")
        )
    else:
        df_flood_impact_return_pds_subset_all = (
            df_flood_impact_return_pds_subset_all.filter(like=impact_var)
        )

    colname_return = (
        df_flood_impact_return_pds_subset_all.filter(like="return_pd").iloc[:, 0].name
    )

    if use_aep:
        df_flood_impact_return_pds_subset_all = (
            df_flood_impact_return_pds_subset_all.copy()
        )
        df_flood_impact_return_pds_subset_all[colname_return] = (
            1 / df_flood_impact_return_pds_subset_all[colname_return]
        )
        # weather probabilities
        ## events
        col_rtrn = df_event_return_periods_all.columns[0]
        df_event_return_periods_all[col_rtrn] = (
            1 / df_event_return_periods_all[col_rtrn]
        )
        ## CIs
        idx_names = df_cis.index.names
        df_cis = 1 / df_cis
        df_cis = df_cis.reset_index()
        df_cis["return_period_yrs"] = 1 / df_cis["return_period_yrs"]
        df_cis = df_cis.set_index(idx_names)
        # impact confidence intervals
        idx_names = df_return_pd_cis_flood_impacts.index.names
        df_return_pd_cis_flood_impacts = df_return_pd_cis_flood_impacts.reset_index()
        df_return_pd_cis_flood_impacts["return_period_yrs_og"] = (
            1 / df_return_pd_cis_flood_impacts["return_period_yrs_og"]
        )
        df_return_pd_cis_flood_impacts["return_period_yrs"] = (
            1 / df_return_pd_cis_flood_impacts["return_period_yrs"]
        )
        df_return_pd_cis_flood_impacts = df_return_pd_cis_flood_impacts.set_index(
            idx_names
        )

    s_impact_return_periods = df_flood_impact_return_pds_subset_all[colname_return]

    # sys.exit('work')

    colname_return = s_impact_return_periods.name
    # create figure and subfigures
    fig_width = 8
    fig_height = 5
    main_fig = plt.figure(
        figsize=(fig_width, fig_height), dpi=dpi
    )  # layout = "constrained"
    ## create a subfigure
    subfigs = main_fig.subfigures(nrows=1, ncols=1)

    # re-index flood area return periods using the original indexing strategy given by event_idx_names
    df_flood_impacts = df_flood_impact_return_pds_subset_all.join(
        df_sim_flood_probs_event_num_mapping.set_index("event_number"), how="left"
    ).set_index(event_idx_names)

    df_flood_impacts_flooding = df_flood_impacts[df_flood_impacts[impact_var] > 0]
    df_flood_impacts_zero_flooding = df_flood_impacts[df_flood_impacts[impact_var] == 0]

    # subset return period
    s_flood_impact_rtrn_pd_nonzero = df_flood_impacts_flooding[colname_return]
    s_flood_impact_nonzero = df_flood_impacts_flooding[impact_var]
    idx_events_considered_nonzero = s_flood_impact_rtrn_pd_nonzero.index

    s_flood_impact_zero = df_flood_impacts_zero_flooding[impact_var]
    idx_events_zero_flooding = s_flood_impact_zero.index

    df_event_return_periods_flooding = df_event_return_periods_all.loc[
        idx_events_considered_nonzero, :
    ]
    df_event_return_periods_zeroflooding = df_event_return_periods_all.loc[
        idx_events_zero_flooding, :
    ]
    # define the x and y variables for plotting
    x = df_event_return_periods_flooding.iloc[:, 0]
    y = s_flood_impact_rtrn_pd_nonzero.copy()
    ## zero flooding
    x_zero_flooding = df_event_return_periods_zeroflooding.iloc[:, 0]
    y_zero_flooding = s_flood_impact_zero.copy()
    # plotting hexbins
    gs_rows = 30  # need a lot to display bottom plot of event return period vs. no flood events
    nrows_mainplot = 28
    ngrid_gap = 0
    nrows_zeros_plot = nrows_mainplot + ngrid_gap
    gs_grid_with = 5
    height_ratios = None
    gs = gridspec.GridSpec(
        gs_rows, gs_grid_with, figure=subfigs, height_ratios=height_ratios
    )
    # add a line plot on the right to map return periods to flood areas
    df_plot = df_flood_impacts_flooding.sort_values(colname_return).loc[
        :, [impact_var, colname_return]
    ]
    # only plot the maximum return period associated with duplicate flood areas
    df_plot = df_plot.loc[df_plot.groupby(impact_var).idxmax().iloc[:, 0], :]
    df_plot = df_plot.sort_values(colname_return)
    ax_fld_rtrn_mapping = subfigs.add_subplot(gs[0:nrows_mainplot, 3:])
    s_plt_x = df_plot[impact_var]
    if "flooded_area" in impact_var:
        ord_mag = 1000
        s_plt_x = df_plot[impact_var] / ord_mag
        # label the x axis
        xlab = "impact ("
        for substring in s_flood_impact_nonzero.name.split("_"):
            if "sqm" in substring:
                xlab += f"$10^{np.log10(ord_mag):.0f}$ m$^2$)"
            else:
                xlab += f"{substring} "
    else:
        xlab = f"impact ({impact_var})"
    ax_fld_rtrn_mapping.set_xlabel(xlab)
    ax_fld_rtrn_mapping.plot(s_plt_x, df_plot[colname_return])

    ax_fld_rtrn_mapping.set_yscale("log")

    # ax_fld_rtrn_mapping.grid(True, axis='y')
    # Add major and minor y-axis gridlines
    flood_rtrn_pd_support = FLOOD_RTRN_PD_SUPPORT
    extent = (
        np.log10(min_y),
        np.log10(flood_rtrn_pd_support),
        np.log10(min_y),
        np.log10(flood_rtrn_pd_support),
    )
    if use_aep:
        flood_rtrn_pd_support = 1 / FLOOD_RTRN_PD_SUPPORT
        min_y = 1 / min_y
        min_x = 1 / min_x
        extent = (
            np.log10(flood_rtrn_pd_support),
            np.log10(min_y),
            np.log10(flood_rtrn_pd_support),
            np.log10(min_y),
        )

    prob_ax_lims = np.asarray((min_y, flood_rtrn_pd_support))

    x_upper_limit = np.interp([flood_rtrn_pd_support], df_plot[colname_return], s_plt_x)
    ax_fld_rtrn_mapping.set_xlim(0, x_upper_limit)
    ax_fld_rtrn_mapping.set_ylim(prob_ax_lims)

    ax_fld_rtrn_mapping.grid(
        True, which="major", linestyle="-", linewidth=0.8, axis="y"
    )  # axis='y'
    ax_fld_rtrn_mapping.grid(
        True, which="minor", linestyle="--", linewidth=0.5, axis="y"
    )  # axis='y'
    ax_fld_rtrn_mapping.grid(
        True, which="major", linestyle="-", linewidth=0.8, axis="x"
    )  # axis='y'
    rtrn_mapping_xlims = ax_fld_rtrn_mapping.get_xlim()
    # interpolate the return period associated with the upper limit of the plot

    # create main hexbin plot
    ax_main = subfigs.add_subplot(gs[0:nrows_mainplot, 0:3])
    ax_main.axline((min_x, min_y), slope=1, c="r", ls="--", zorder=100)  # 1:1 line

    hb_main = ax_main.hexbin(
        x,
        y,
        gridsize=50,
        xscale="log",
        yscale="log",
        bins="log",
        mincnt=1,
        alpha=0.92,
        edgecolors="none",
        extent=extent,
    )  #
    cmap, norm = hb_main.get_cmap(), hb_main.norm  # extract colorbar information
    # define stat label
    # ax_main.set_ylabel(y.name)
    ylab = "$\\hat{R}_{F}({y})$"
    xlab = "$\\hat{R}_{E}(e)$"
    if use_aep:
        ylab = "impact AEF"
        xlab = "driver AEF"

    ax_main.set_ylabel(ylab)

    ax_main.grid(True, which="major", linestyle="-", linewidth=0.8)  # axis='y'
    ax_main.grid(True, which="minor", linestyle="--", linewidth=0.5)  # axis='y'
    yticks = np.asarray(LST_RTRNS)
    xticks = np.asarray(LST_RTRNS)
    if use_aep:
        xticks = 1 / xticks
        yticks = 1 / yticks
    ax_main.set_yticks(yticks)
    ax_main.set_xticks(xticks)

    newlabs = []
    for idx, lab in enumerate(ax_main.get_yticklabels()):
        lab.set_text(str(lab.get_position()[1]))
        newlabs.append(lab)

    ax_main.set_yticklabels(newlabs)

    ax_main.set_yticks(xticks)
    # create suplot of zero flood events
    xlab_adj = None
    out_of_bounds_impact_events = x_zero_flooding.max() < min_y
    if use_aep:
        out_of_bounds_impact_events = x_zero_flooding.min() < 1 / min_y
    ax_zero_flood = None
    if out_of_bounds_impact_events:
        # if len(x_zero_flooding)>0:
        ax_main.set_xlabel("")
        xlab_adj = 30
        ax_zero_flood = subfigs.add_subplot(gs[nrows_zeros_plot:gs_rows, 0:3])
        nx = 60  # smaller makes wider
        ny = 2
        xrange = 1
        # extract colorbar information from the main plot
        extent = (np.log10(min_y), np.log10(FLOOD_RTRN_PD_SUPPORT), -xrange, xrange)
        # if use_aep:
        #     extent = 1 / np.asarray(extent)
        ax_zero_flood.hexbin(
            x_zero_flooding,
            y_zero_flooding,
            gridsize=(nx, ny),
            xscale="log",
            yscale="linear",
            mincnt=1,
            alpha=0.92,
            edgecolors="none",
            extent=extent,
            cmap=cmap,
            norm=norm,
        )  #
        ax_zero_flood.set_xlim(prob_ax_lims)
        ax_zero_flood.set_yticks([])
        ax_zero_flood.set_yticklabels([])
        ax_zero_flood.set_ylabel(
            "$y=0$",
            rotation=360,
            verticalalignment="center",
            horizontalalignment="left",
            labelpad=30,
        )

        ax_zero_flood.annotate(
            text="All plotted events ($\\hat{R}\\geq$"
            + f"{min_x}) generated nonzero impacts",
            xycoords="axes fraction",
            xy=(0.010, 0.5),
            verticalalignment="center",
            horizontalalignment="left",
            fontsize="x-small",
        )
        # else:
        #     ax_zero_flood.grid(True, which='major', linestyle='-', linewidth=0.8)  # axis='y'
        #     ax_zero_flood.grid(True, which='minor', linestyle='--', linewidth=0.5)  # axis='y'
        ax_zero_flood.set_xticks(xticks)
        ax_zero_flood.set_xticklabels(newlabs)
        ylim_zero_fld = ax_zero_flood.get_ylim()
    else:
        ax_main.set_xticklabels(newlabs)

    ax_main.set_xlabel(xlab, labelpad=xlab_adj)

    lst_yticks = []

    ax_fld_rtrn_mapping.set_yticks(xticks)  # Ensure ticks match the labels
    for lab in ax_fld_rtrn_mapping.get_yticklabels():
        lab.set_text("")
        lst_yticks.append(lab)
    ax_fld_rtrn_mapping.set_yticklabels(lst_yticks)

    if str_fig_title is not None:
        subfigs.suptitle(str_fig_title)
    # add shaded area for targeted return periods
    for idx_rtrn, trgt_rtrn in enumerate(LST_RTRNS):
        if use_aep:
            trgt_rtrn = 1 / trgt_rtrn
        s_lims = df_cis.loc[pd.IndexSlice[:, stats, trgt_rtrn]]
        if multivariate:
            s_lims = s_lims.filter(like=f"_{multivar_formulation}_").iloc[:, 0]
        # fill between for event return period confidence intervals
        event_rtrn_ci = (s_lims.values.min(), s_lims.values.max())
        s_flood_impact_lims = df_return_pd_cis_flood_impacts.loc[
            pd.IndexSlice[:, subarea_name, depth_range_m, trgt_rtrn]
        ]
        flood_rtrn_ci = (
            s_flood_impact_lims.values.min(),
            s_flood_impact_lims.values.max(),
        )
        ax_main.fill_between(
            [event_rtrn_ci[0], event_rtrn_ci[1]], 1000, color="blue", alpha=0.3
        )
        ## add CI to bottom subplot if there are any plotted events in it
        if out_of_bounds_impact_events:
            ax_zero_flood.fill_between(
                [event_rtrn_ci[0], event_rtrn_ci[1]],
                ylim_zero_fld[1],
                y2=ylim_zero_fld[0],
                color="blue",
                alpha=0.3,
            )
        # fill between value for event confidence intervals
        ax_main.fill_betweenx(
            [flood_rtrn_ci[0], flood_rtrn_ci[1]], 1000, color="orange", alpha=0.3
        )
        ax_fld_rtrn_mapping.fill_betweenx(
            y=[flood_rtrn_ci[0], flood_rtrn_ci[1]],
            x1=rtrn_mapping_xlims[1],
            color="orange",
            alpha=0.3,
        )
    rng_low_bound = float(depth_range_m.split(",")[0].split("(")[-1].split("[")[-1])
    dpth_range_sort_order = (
        np.array(LST_KEY_FLOOD_THRESHOLDS_FOR_SENSITIVITY_ANALYSIS) == rng_low_bound
    ).argmax() + 1
    ax_main.set_ylim(prob_ax_lims)
    ax_main.set_xlim(prob_ax_lims)
    # add colorbar
    # cbar_location = "bottom"
    cbar_location = "left"
    if cbar_location == "bottom":
        orientation, cbar_ax = "horizontal", main_fig.add_axes([0.24, -0, 0.33, 0.03])
        cb = mcolorbar.ColorbarBase(
            cbar_ax, cmap=cmap, norm=norm, orientation=orientation
        )
        loc, bbox_to_anchor = "lower left", (0.07, -0.09)  # bottom left
    elif cbar_location == "left":
        orientation, cbar_ax = "vertical", main_fig.add_axes([0, 0.15, 0.02, 0.55])
        cb = mcolorbar.ColorbarBase(
            cbar_ax, cmap=cmap, norm=norm, orientation=orientation
        )
        cb.ax.yaxis.set_ticks_position("left")
        cb.ax.yaxis.set_label_position("left")
        loc, bbox_to_anchor = "upper left", (-0.068, 0.88)

    cb.set_label("event count")
    # get the tick locations
    ticks = cb.get_ticks()
    max_val = norm.vmax
    new_ticks = []
    for tick in ticks:
        if (tick < max_val) and (tick >= 1):
            new_ticks.append(tick)
        else:
            continue
    val_to_round_by = 10 ** (np.floor(np.log10(max_val)))
    max_tick = int(np.ceil(max_val / val_to_round_by)) * 10
    new_ticks.append(max_tick)
    cb.set_ticks(new_ticks)
    if cbar_location == "bottom":
        cb.ax.xaxis.set_major_formatter(
            mticker.FuncFormatter(lambda x, _: f"{int(x):,}")
        )
    elif cbar_location == "left":
        cb.ax.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda x, _: f"{int(x):,}")
        )

    # create a legend for the confidence intervals
    legend_elements = [
        mpatches.Patch(label="driver", facecolor="blue", alpha=0.3, edgecolor="k"),
        mpatches.Patch(label="impact", facecolor="orange", alpha=0.3, edgecolor="k"),
    ]

    main_fig.legend(
        handles=legend_elements,
        loc=loc,
        fontsize=8,
        title_fontsize=8,
        bbox_to_anchor=bbox_to_anchor,
        ncols=1,
        title="90% CI for target\nfrequencies:",
        frameon=True,
    )

    # save and clear figure
    if fname_savefig is not None:
        plt.savefig(fname_savefig, bbox_inches="tight")

    return


def process_stat_for_hexbin_plot(
    stats,
    df_return_pd_cis_multivar,
    ds_multivar_return_periods,
    event_idx_names,
    multivar_formulation,
    df_return_pd_cis_univar,
    df_univariate_return_pds,
    use_aep,
    impact_var,
    df_sim_flood_probs_event_num_mapping,
    ds_flood_impacts_by_aoi,
    subarea_name,
    depth_range_m,
    df_return_pd_cis_flood_impacts,
):
    # determine whether the stat is multivariate or univariate
    lst_stat_components = stats.split(",")
    idx_valid_stat = [len(stat) > 0 for stat in lst_stat_components]
    s_stats = pd.Series(lst_stat_components)[idx_valid_stat]
    multivariate = False
    if len(s_stats) > 1:
        multivariate = True
    # subset either the multivariate or univariate event statistic return period dataframes
    if multivariate:
        df_cis = df_return_pd_cis_multivar
        df_multivar_return_periods_all = (
            ds_multivar_return_periods.sel(event_stats=stats)
            .to_dataframe()
            .reset_index()
            .set_index(event_idx_names)
            .drop(columns=["event_stats"])
        )
        # multivar_formulation = event_stat_type.split("_")[-1]
        idx_cols = [
            ("rtrn_yrs" in col) and (multivar_formulation in col)
            for col in df_multivar_return_periods_all.columns
        ]
        cols = df_multivar_return_periods_all.columns[idx_cols]
        df_event_return_periods_all = df_multivar_return_periods_all.loc[:, cols]
    else:
        df_cis = df_return_pd_cis_univar
        idx_cols = [(stats in col) for col in df_univariate_return_pds.columns]
        cols = df_univariate_return_pds.columns[idx_cols]
        df_event_return_periods_all = df_univariate_return_pds.loc[:, cols]

    df_flood_impact_return_pds_subset_all = (
        ds_flood_impacts_by_aoi.sel(
            subarea_name=subarea_name, depth_range_m=depth_range_m
        )
        .to_dataframe()
        .dropna()
    )
    if "flooded_area" in impact_var:
        # continue
        df_flood_impact_return_pds_subset_all = (
            df_flood_impact_return_pds_subset_all.filter(like="flooded_area")
        )
    else:
        df_flood_impact_return_pds_subset_all = (
            df_flood_impact_return_pds_subset_all.filter(like=impact_var)
        )

    colname_return = (
        df_flood_impact_return_pds_subset_all.filter(like="return_pd").iloc[:, 0].name
    )

    s_impact_return_periods = df_flood_impact_return_pds_subset_all[colname_return]

    colname_return = s_impact_return_periods.name

    if use_aep:
        df_flood_impact_return_pds_subset_all = (
            df_flood_impact_return_pds_subset_all.copy()
        )
        df_flood_impact_return_pds_subset_all[colname_return] = (
            1 / df_flood_impact_return_pds_subset_all[colname_return]
        )
        # weather probabilities
        ## events
        col_rtrn = df_event_return_periods_all.columns[0]
        df_event_return_periods_all[col_rtrn] = (
            1 / df_event_return_periods_all[col_rtrn]
        )
        ## CIs
        idx_names = df_cis.index.names
        df_cis = 1 / df_cis
        df_cis = df_cis.reset_index()
        df_cis["return_period_yrs"] = 1 / df_cis["return_period_yrs"]
        df_cis = df_cis.set_index(idx_names)
        # impact confidence intervals
        idx_names = df_return_pd_cis_flood_impacts.index.names
        df_return_pd_cis_flood_impacts = df_return_pd_cis_flood_impacts.reset_index()
        df_return_pd_cis_flood_impacts["return_period_yrs_og"] = (
            1 / df_return_pd_cis_flood_impacts["return_period_yrs_og"]
        )
        df_return_pd_cis_flood_impacts["return_period_yrs"] = (
            1 / df_return_pd_cis_flood_impacts["return_period_yrs"]
        )
        df_return_pd_cis_flood_impacts = df_return_pd_cis_flood_impacts.set_index(
            idx_names
        )

    df_flood_impacts = df_flood_impact_return_pds_subset_all.join(
        df_sim_flood_probs_event_num_mapping.set_index("event_number"), how="left"
    ).set_index(event_idx_names)

    df_flood_impacts_zero_flooding = df_flood_impacts[df_flood_impacts[impact_var] == 0]

    df_flood_impacts_flooding = df_flood_impacts[df_flood_impacts[impact_var] > 0]
    # subset return period
    s_flood_impact_rtrn_pd_nonzero = df_flood_impacts_flooding[colname_return]
    s_flood_impact_nonzero = df_flood_impacts_flooding[impact_var]
    idx_events_considered_nonzero = s_flood_impact_rtrn_pd_nonzero.index

    s_flood_impact_zero = df_flood_impacts_zero_flooding[impact_var]
    idx_events_zero_flooding = s_flood_impact_zero.index
    df_event_return_periods_flooding = df_event_return_periods_all.loc[
        idx_events_considered_nonzero, :
    ]
    df_event_return_periods_zeroflooding = df_event_return_periods_all.loc[
        idx_events_zero_flooding, :
    ]

    # define the x and y variables for plotting
    x = df_event_return_periods_flooding.iloc[:, 0]
    y = s_flood_impact_rtrn_pd_nonzero.copy()
    ## zero flooding
    x_zero_flooding = df_event_return_periods_zeroflooding.iloc[:, 0]
    y_zero_flooding = s_flood_impact_zero.copy()

    # add a line plot on the right to map return periods to flood areas
    df_plot_hexbin = df_flood_impacts_flooding.sort_values(colname_return).loc[
        :, [impact_var, colname_return]
    ]
    # only plot the maximum return period associated with duplicate flood areas
    df_plot_hexbin = df_plot_hexbin.loc[
        df_plot_hexbin.groupby(impact_var).idxmax().iloc[:, 0], :
    ]
    df_plot_hexbin = df_plot_hexbin.sort_values(colname_return)

    return (
        df_plot_hexbin,
        s_flood_impact_nonzero,
        colname_return,
        x,
        y,
        x_zero_flooding,
        y_zero_flooding,
        df_cis,
        multivariate,
        multivar_formulation,
        df_return_pd_cis_flood_impacts,
    )


def shade_impact_rtrn_pd_CIs(
    ax,
    x1,
    use_aep,
    df_cis,
    stats,
    multivariate,
    multivar_formulation,
    df_return_pd_cis_flood_impacts,
    subarea_name,
    depth_range_m,
    color="orange",
):
    # for ax_main, x1 = 1000
    # for ax_fld_rtrn_mapping, x1 = rtrn_mapping_xlims[1]
    dic_impact_cis = dict()
    for idx_rtrn, trgt_rtrn in enumerate(LST_RTRNS):
        dic_impact_cis[trgt_rtrn] = dict(y=[])
        if use_aep:
            trgt_rtrn = 1 / trgt_rtrn
        s_lims = df_cis.loc[pd.IndexSlice[:, stats, trgt_rtrn]]
        if multivariate:
            s_lims = s_lims.filter(like=f"_{multivar_formulation}_").iloc[:, 0]
        # fill between for event return period confidence intervals
        event_rtrn_ci = (s_lims.values.min(), s_lims.values.max())
        s_flood_impact_lims = df_return_pd_cis_flood_impacts.loc[
            pd.IndexSlice[:, subarea_name, depth_range_m, trgt_rtrn]
        ]
        flood_rtrn_ci = (
            s_flood_impact_lims.values.min(),
            s_flood_impact_lims.values.max(),
        )

        ax.fill_betweenx(
            y=[flood_rtrn_ci[0], flood_rtrn_ci[1]],
            x1=x1,
            color=color,
            alpha=0.3,
        )
    return


def shade_event_return_pd_cis(
    ax,
    use_aep,
    df_cis,
    stats,
    multivariate,
    multivar_formulation,
    df_return_pd_cis_flood_impacts,
    subarea_name,
    depth_range_m,
    out_of_bounds_impact_events,
    ax_zero_flood,
    ylim_zero_fld,
    color="blue",
):
    dic_impact_cis = dict()
    for idx_rtrn, trgt_rtrn in enumerate(LST_RTRNS):
        dic_impact_cis[trgt_rtrn] = dict(y=[])

        if use_aep:
            trgt_rtrn = 1 / trgt_rtrn
        s_lims = df_cis.loc[pd.IndexSlice[:, stats, trgt_rtrn]]
        if multivariate:
            s_lims = s_lims.filter(like=f"_{multivar_formulation}_").iloc[:, 0]
        # fill between for event return period confidence intervals
        event_rtrn_ci = (s_lims.values.min(), s_lims.values.max())
        s_flood_impact_lims = df_return_pd_cis_flood_impacts.loc[
            pd.IndexSlice[:, subarea_name, depth_range_m, trgt_rtrn]
        ]
        flood_rtrn_ci = (
            s_flood_impact_lims.values.min(),
            s_flood_impact_lims.values.max(),
        )
        ax.fill_between(
            [event_rtrn_ci[0], event_rtrn_ci[1]], 1000, color=color, alpha=0.3
        )
        ## add CI to bottom subplot if there are any plotted events in it
        if out_of_bounds_impact_events:
            ax_zero_flood.fill_between(
                [event_rtrn_ci[0], event_rtrn_ci[1]],
                ylim_zero_fld[1],
                y2=ylim_zero_fld[0],
                color=color,
                alpha=0.3,
            )

    return


def set_integerish_ticks(ax, axis="x", x_upper_limit=None):
    # get limits
    if axis == "x":
        lo, hi = ax.get_xlim()
    else:
        lo, hi = ax.get_ylim()

    # Candidate tick spacings (multiples of 1 or 5)
    # smallest first so the first valid one is used
    spacings = [1, 2, 5, 10, 20, 25, 50, 100, 200, 500]
    spacings.reverse()

    # choose the smallest spacing that gives >= 5 ticks
    for step in spacings:
        ticks = np.arange(
            np.floor(lo / step) * step, np.ceil(hi / step) * step + step, step
        )
        if len(ticks) >= 5:
            break
    if x_upper_limit is not None:
        old_ticks = ticks
        ticks = []
        for tick in old_ticks:
            if tick <= x_upper_limit:
                ticks.append(tick)

    # apply ticks to the correct axis
    if axis == "x":
        ax.set_xticks(ticks)
    else:
        ax.set_yticks(ticks)

    # Format labels as integers
    tick_labels = [f"{int(t)}" for t in ticks]
    if axis == "x":
        ax.set_xticklabels(tick_labels)
    else:
        ax.set_yticklabels(tick_labels)
    return


def plot_impact_return_period(
    df_plot_hexbin,
    prob_ax_lims,
    ax_fld_rtrn_mapping,
    impact_var,
    colname_return,
    s_flood_impact_nonzero,
    xticks,
    flood_rtrn_pd_support,
    use_aep,
    df_cis,
    stats,
    multivariate,
    multivar_formulation,
    df_return_pd_cis_flood_impacts,
    subarea_name,
    depth_range_m,
):
    # fig, ax_fld_rtrn_mapping = plt.subplots()
    if "flooded_area" in impact_var:
        ord_mag = 1000
        s_plt_x = df_plot_hexbin[impact_var] / ord_mag
        # label the x axis
        xlab = "area flooded "
        for substring in s_flood_impact_nonzero.name.split("_"):
            if "sqm" in substring:
                xlab += f"$10^{np.log10(ord_mag):.0f}$ m$^2$"
            # else:
            #     xlab += f"{substring} "
        if "inf" in depth_range_m:
            lb = depth_range_m.split(",")[0].split("[")[-1]
            xlab += f"\n depths $\geq{lb}$ m "
        else:
            xlab += f"\n depths $\subset$ {depth_range_m}"
    else:
        xlab = f"impact\n{impact_var}"
    ax_fld_rtrn_mapping.set_xlabel(xlab)
    ax_fld_rtrn_mapping.plot(s_plt_x, df_plot_hexbin[colname_return])

    x_upper_limit = np.interp(
        [flood_rtrn_pd_support], df_plot_hexbin[colname_return], s_plt_x
    )

    ax_fld_rtrn_mapping.set_yscale("log")

    ax_fld_rtrn_mapping.set_ylim(prob_ax_lims)

    ax_fld_rtrn_mapping.grid(
        True, which="major", linestyle="-", linewidth=0.8, axis="y"
    )  # axis='y'
    ax_fld_rtrn_mapping.grid(
        True, which="minor", linestyle="--", linewidth=0.5, axis="y"
    )  # axis='y'
    ax_fld_rtrn_mapping.grid(
        True, which="major", linestyle="-", linewidth=0.8, axis="x"
    )  # axis='y'
    rtrn_mapping_xlims = ax_fld_rtrn_mapping.get_xlim()
    ax_fld_rtrn_mapping.set_yticks(xticks)  # Ensure ticks match the labels
    lst_yticks = []
    for lab in ax_fld_rtrn_mapping.get_yticklabels():
        lab.set_text("")
        lst_yticks.append(lab)
    ax_fld_rtrn_mapping.set_yticklabels(lst_yticks)

    shade_impact_rtrn_pd_CIs(
        ax_fld_rtrn_mapping,
        x1=rtrn_mapping_xlims[1],
        use_aep=use_aep,
        df_cis=df_cis,
        stats=stats,
        multivariate=multivariate,
        multivar_formulation=multivar_formulation,
        df_return_pd_cis_flood_impacts=df_return_pd_cis_flood_impacts,
        subarea_name=subarea_name,
        depth_range_m=depth_range_m,
    )

    # set x ticks
    ax_fld_rtrn_mapping.set_xlim(0, x_upper_limit)
    set_integerish_ticks(ax_fld_rtrn_mapping, axis="x", x_upper_limit=x_upper_limit)
    # ax_fld_rtrn_mapping.grid(True, axis='y')
    return


def plot_impact_vs_event_return_period_hexbin(
    nrows_mainplot,
    min_x,
    min_y,
    use_aep,
    x_zero_flooding,
    y_zero_flooding,
    prob_ax_lims,
    str_fig_title,
    df_cis,
    stats,
    multivariate,
    multivar_formulation,
    df_return_pd_cis_flood_impacts,
    subarea_name,
    depth_range_m,
    x,
    y,
    nrows_zeros_plot,
    gs_rows,
    gs,
    subfigs,
    subfig_x1,
    subfig_x2,
    extent,
    no_y_ax_lab=False,
    cmap=None,
    norm=None,
    ax_id_for_label=None,
):
    # subfix_x = 0
    # subfig_y = 3
    ax_main = subfigs.add_subplot(gs[0:nrows_mainplot, subfig_x1:subfig_x2])
    if ax_id_for_label is not None:
        add_subplot_id(ax=ax_main, ax_id=ax_id_for_label)

    ax_main.axline((min_x, min_y), slope=1, c="r", ls="--", zorder=100)  # 1:1 line

    if norm is None:
        hb_main = ax_main.hexbin(
            x,
            y,
            gridsize=50,
            xscale="log",
            yscale="log",
            bins="log",
            mincnt=1,
            alpha=0.92,
            edgecolors="none",
            extent=extent,
        )  #
    else:
        hb_main = ax_main.hexbin(
            x,
            y,
            gridsize=50,
            xscale="log",
            yscale="log",
            # bins="log",
            mincnt=1,
            alpha=0.92,
            edgecolors="none",
            extent=extent,
            norm=norm,
            cmap=cmap,
        )
    cmap, norm = hb_main.get_cmap(), hb_main.norm  # extract colorbar information
    # define stat label
    # ax_main.set_ylabel(y.name)
    ylab = "$\\hat{R}_{F}({y})$"
    xlab = "$\\hat{R}_{E}(e)$"

    if use_aep:
        if "flooded_area" in y.name:
            ylab = "flood area AEF"
        else:
            ylab = f"{y.name} AEF"
        label = tidy_hydro_varnames_for_plots(stats, multivar_formulation)
        xlab = f"{tidy_hydro_varnames_for_plots(stats, multivar_formulation)} AEF"
        if "AND" in xlab:
            xlab = xlab.replace("AND", "AND\n")

    if no_y_ax_lab:
        ax_main.set_ylabel("")
    else:
        ax_main.set_ylabel(ylab)

    ax_main.grid(True, which="major", linestyle="-", linewidth=0.8)  # axis='y'
    ax_main.grid(True, which="minor", linestyle="--", linewidth=0.5)  # axis='y'
    yticks = np.asarray(LST_RTRNS)
    xticks = np.asarray(LST_RTRNS)
    if use_aep:
        xticks = 1 / xticks
        yticks = 1 / yticks

    ax_main.set_yticks(yticks)

    ax_main.set_xticks(xticks)

    new_x_labs = []
    new_y_labs = []
    for idx, lab in enumerate(ax_main.get_yticklabels()):
        lab.set_text(str(lab.get_position()[1]))
        new_x_labs.append(lab)
        if no_y_ax_lab:
            new_y_labs.append("")
        else:
            new_y_labs.append(lab)

    ax_main.set_yticks(xticks)
    # create suplot of zero flood events
    xlab_adj = None
    out_of_bounds_impact_events = x_zero_flooding.max() < min_y
    if use_aep:
        out_of_bounds_impact_events = x_zero_flooding.min() < 1 / min_y
    ax_zero_flood = None
    ylim_zero_fld = None
    if out_of_bounds_impact_events:
        # if len(x_zero_flooding)>0:
        ax_main.set_xlabel("")
        xlab_adj = 30
        ax_zero_flood = subfigs.add_subplot(
            gs[nrows_zeros_plot:gs_rows, subfig_x1:subfig_x2]
        )
        nx = 60  # smaller makes wider
        ny = 2
        xrange = 1
        # extract colorbar information from the main plot
        extent = (np.log10(min_y), np.log10(FLOOD_RTRN_PD_SUPPORT), -xrange, xrange)
        # if use_aep:
        #     extent = 1 / np.asarray(extent)
        ax_zero_flood.hexbin(
            x_zero_flooding,
            y_zero_flooding,
            gridsize=(nx, ny),
            xscale="log",
            yscale="linear",
            mincnt=1,
            alpha=0.92,
            edgecolors="none",
            extent=extent,
            cmap=cmap,
            norm=norm,
        )  #
        ax_zero_flood.set_xlim(prob_ax_lims)
        ax_zero_flood.set_yticks([])
        ax_zero_flood.set_yticklabels([])
        ax_zero_flood.set_ylabel(
            "$y=0$",
            rotation=360,
            verticalalignment="center",
            horizontalalignment="left",
            labelpad=30,
        )

        ax_zero_flood.annotate(
            text="All plotted events ($\\hat{R}\\geq$"
            + f"{min_x}) generated nonzero impacts",
            xycoords="axes fraction",
            xy=(0.010, 0.5),
            verticalalignment="center",
            horizontalalignment="left",
            fontsize="x-small",
        )
        # else:
        #     ax_zero_flood.grid(True, which='major', linestyle='-', linewidth=0.8)  # axis='y'
        #     ax_zero_flood.grid(True, which='minor', linestyle='--', linewidth=0.5)  # axis='y'
        ax_zero_flood.set_xticks(xticks)
        ax_zero_flood.set_xticklabels(new_x_labs)
        ylim_zero_fld = ax_zero_flood.get_ylim()
    else:
        ax_main.set_xticklabels(new_x_labs)
    ax_main.set_yticklabels(new_y_labs)
    ax_main.set_xlabel(xlab, labelpad=xlab_adj)

    if str_fig_title is not None:
        subfigs.suptitle(str_fig_title)

    shade_impact_rtrn_pd_CIs(
        ax_main,
        x1=1000,
        use_aep=use_aep,
        df_cis=df_cis,
        stats=stats,
        multivariate=multivariate,
        multivar_formulation=multivar_formulation,
        df_return_pd_cis_flood_impacts=df_return_pd_cis_flood_impacts,
        subarea_name=subarea_name,
        depth_range_m=depth_range_m,
        color="orange",
    )

    shade_event_return_pd_cis(
        ax_main,
        use_aep,
        df_cis,
        stats,
        multivariate,
        multivar_formulation,
        df_return_pd_cis_flood_impacts,
        subarea_name,
        depth_range_m,
        out_of_bounds_impact_events,
        ax_zero_flood,
        ylim_zero_fld,
        color="blue",
    )

    rng_low_bound = float(depth_range_m.split(",")[0].split("(")[-1].split("[")[-1])
    dpth_range_sort_order = (
        np.array(LST_KEY_FLOOD_THRESHOLDS_FOR_SENSITIVITY_ANALYSIS) == rng_low_bound
    ).argmax() + 1
    ax_main.set_ylim(prob_ax_lims)
    ax_main.set_xlim(prob_ax_lims)
    return cmap, norm


def mcds_hexbin_weather_vs_impact_rtrn(
    df_sim_flood_probs_event_num_mapping,
    df_univariate_return_pds_og,
    ds_multivar_return_periods,
    ds_flood_impacts_by_aoi,
    df_return_pd_cis_flood_impacts_og,
    df_return_pd_cis_univar_og,
    df_return_pd_cis_multivar_og,
    impact_var,
    depth_range_m,
    subarea_name,
    use_aep,
    event_idx_names,
    multivar_formulation,
    str_fig_title=None,
    fname_savefig=None,
    dpi=300,
):
    df_univariate_return_pds = df_univariate_return_pds_og.copy()
    df_return_pd_cis_univar = df_return_pd_cis_univar_og.copy()
    df_return_pd_cis_multivar = df_return_pd_cis_multivar_og.copy()
    df_return_pd_cis_flood_impacts = df_return_pd_cis_flood_impacts_og.copy()

    min_x, min_y = (
        0.5,
        0.5,
    )  # minimum value for x and y axes (really small values can do crazy things in loglog)
    # subset flood area return period for the subarea and depth range being analyzed

    # Add major and minor y-axis gridlines
    flood_rtrn_pd_support = FLOOD_RTRN_PD_SUPPORT
    extent = (
        np.log10(min_y),
        np.log10(flood_rtrn_pd_support),
        np.log10(min_y),
        np.log10(flood_rtrn_pd_support),
    )
    if use_aep:
        flood_rtrn_pd_support = 1 / FLOOD_RTRN_PD_SUPPORT
        min_y = 1 / min_y
        min_x = 1 / min_x
        extent = (
            np.log10(flood_rtrn_pd_support),
            np.log10(min_y),
            np.log10(flood_rtrn_pd_support),
            np.log10(min_y),
        )

    prob_ax_lims = np.asarray((min_y, flood_rtrn_pd_support))

    # plotting
    fig_width = 6
    fig_height = 2.5
    main_fig = plt.figure(
        figsize=(fig_width, fig_height), dpi=dpi
    )  # layout = "constrained"
    ## create a subfigure
    subfigs = main_fig.subfigures(nrows=1, ncols=1)
    gs_rows = 30  # need a lot to display bottom plot of event return period vs. no flood events
    nrows_mainplot = 28
    ngrid_gap = 0
    nrows_zeros_plot = nrows_mainplot + ngrid_gap
    gs_grid_with = 8
    height_ratios = None
    gs = gridspec.GridSpec(
        gs_rows, gs_grid_with, figure=subfigs, height_ratios=height_ratios
    )

    ax_fld_rtrn_mapping = subfigs.add_subplot(gs[0:nrows_mainplot, 6:])
    add_subplot_id(ax=ax_fld_rtrn_mapping, ax_id=2)

    yticks = np.asarray(LST_RTRNS)
    xticks = np.asarray(LST_RTRNS)
    if use_aep:
        xticks = 1 / xticks
        yticks = 1 / yticks

    # create main hexbin plot

    # multivar hexbin
    subfig_x1 = 0
    subfig_x2 = 3
    stats = EVENT_STAT_FOR_MC_DSGN_STRM_SEL_MULTIVAR_AND
    (
        df_plot_hexbin,
        s_flood_impact_nonzero,
        colname_return,
        x,
        y,
        x_zero_flooding,
        y_zero_flooding,
        df_cis,
        multivariate,
        multivar_formulation,
        df_return_pd_cis_flood_impacts,
    ) = process_stat_for_hexbin_plot(
        stats,
        df_return_pd_cis_multivar_og,
        ds_multivar_return_periods,
        event_idx_names,
        multivar_formulation,
        df_return_pd_cis_univar_og,
        df_univariate_return_pds_og,
        use_aep,
        impact_var,
        df_sim_flood_probs_event_num_mapping,
        ds_flood_impacts_by_aoi,
        subarea_name,
        depth_range_m,
        df_return_pd_cis_flood_impacts_og,
    )
    cmap, norm = plot_impact_vs_event_return_period_hexbin(
        nrows_mainplot,
        min_x,
        min_y,
        use_aep,
        x_zero_flooding,
        y_zero_flooding,
        prob_ax_lims,
        str_fig_title,
        df_cis,
        stats,
        multivariate,
        multivar_formulation,
        df_return_pd_cis_flood_impacts,
        subarea_name,
        depth_range_m,
        x,
        y,
        nrows_zeros_plot,
        gs_rows,
        gs,
        subfigs,
        subfig_x1,
        subfig_x2,
        extent,
        ax_id_for_label=0,
    )

    # random_variable = 5
    # univar hexbin
    subfig_x1 = 3
    subfig_x2 = 6
    stats = EVENT_STAT_FOR_MC_DSGN_STRM_SEL_UNIVAR
    (
        df_plot_hexbin,
        s_flood_impact_nonzero,
        colname_return,
        x,
        y,
        x_zero_flooding,
        y_zero_flooding,
        df_cis,
        multivariate,
        multivar_formulation,
        df_return_pd_cis_flood_impacts,
    ) = process_stat_for_hexbin_plot(
        EVENT_STAT_FOR_MC_DSGN_STRM_SEL_UNIVAR,
        df_return_pd_cis_multivar_og,
        ds_multivar_return_periods,
        event_idx_names,
        multivar_formulation,
        df_return_pd_cis_univar_og,
        df_univariate_return_pds_og,
        use_aep,
        impact_var,
        df_sim_flood_probs_event_num_mapping,
        ds_flood_impacts_by_aoi,
        subarea_name,
        depth_range_m,
        df_return_pd_cis_flood_impacts_og,
    )
    cmap, norm = plot_impact_vs_event_return_period_hexbin(
        nrows_mainplot,
        min_x,
        min_y,
        use_aep,
        x_zero_flooding,
        y_zero_flooding,
        prob_ax_lims,
        str_fig_title,
        df_cis,
        stats,
        multivariate,
        multivar_formulation,
        df_return_pd_cis_flood_impacts,
        subarea_name,
        depth_range_m,
        x,
        y,
        nrows_zeros_plot,
        gs_rows,
        gs,
        subfigs,
        subfig_x1=3,
        subfig_x2=6,
        extent=extent,
        no_y_ax_lab=True,
        cmap=cmap,
        norm=norm,
        ax_id_for_label=1,
    )

    plot_impact_return_period(
        df_plot_hexbin,
        prob_ax_lims,
        ax_fld_rtrn_mapping,
        impact_var,
        colname_return,
        s_flood_impact_nonzero,
        xticks,
        flood_rtrn_pd_support,
        use_aep,
        df_cis,
        stats,
        multivariate,
        multivar_formulation,
        df_return_pd_cis_flood_impacts,
        subarea_name,
        depth_range_m,
    )

    cbar_location = "right"
    if cbar_location == "bottom":
        orientation, cbar_ax = "horizontal", main_fig.add_axes([0.24, -0, 0.33, 0.03])
        cb = mcolorbar.ColorbarBase(
            cbar_ax, cmap=cmap, norm=norm, orientation=orientation
        )
        loc, bbox_to_anchor = "lower left", (0.07, -0.09)  # bottom left
    elif cbar_location in ["left", "right"]:
        if cbar_location == "left":
            cbar_coords = [0, 0.15, 0.02, 0.55]
        else:
            cbar_coords = [0.93, 0.16, 0.02, 0.45]
        orientation, cbar_ax = "vertical", main_fig.add_axes(cbar_coords)
        cb = mcolorbar.ColorbarBase(
            cbar_ax, cmap=cmap, norm=norm, orientation=orientation
        )
        cb.ax.yaxis.set_ticks_position(cbar_location)
        cb.ax.yaxis.set_label_position(cbar_location)
        loc, bbox_to_anchor = f"upper {cbar_location}", (1.06, 0.91)

    cb.set_label("event count", labelpad=-35)
    # get the tick locations
    ticks = cb.get_ticks()
    max_val = norm.vmax
    new_ticks = []
    for tick in ticks:
        if (tick < max_val) and (tick >= 1):
            new_ticks.append(tick)
        else:
            continue
    val_to_round_by = 10 ** (np.floor(np.log10(max_val)))
    max_tick = int(np.ceil(max_val / val_to_round_by)) * 10
    new_ticks.append(max_tick)
    cb.set_ticks(new_ticks)
    if cbar_location == "bottom":
        cb.ax.xaxis.set_major_formatter(
            mticker.FuncFormatter(lambda x, _: f"{int(x):,}")
        )
    elif cbar_location in ["left", "right"]:
        cb.ax.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda x, _: f"{int(x):,}")
        )

    # create a legend for the confidence intervals
    legend_elements = [
        mpatches.Patch(label="driver CI", facecolor="blue", alpha=0.3, edgecolor="k"),
        mpatches.Patch(label="impact CI", facecolor="orange", alpha=0.3, edgecolor="k"),
        Line2D([0], [0], c="r", ls="--", label="AEF\nequality"),
    ]

    main_fig.legend(
        handles=legend_elements,
        loc="upper right",
        fontsize=8,
        title_fontsize=8,
        bbox_to_anchor=bbox_to_anchor,
        ncols=1,
        # title="90% CI",
        frameon=False,
    )
    # save and clear figure
    if fname_savefig is not None:
        frmt = fname_savefig.split(".")[-1]
        if frmt != "png":
            plt.savefig(fname_savefig, bbox_inches="tight", format=frmt)
        else:
            plt.savefig(fname_savefig, bbox_inches="tight")
    print(f"saved plot: {fname_savefig}")
    return


def analyze_flood_impact_rtrn_pd(
    ds_flood_impacts_by_aoi,
    lst_subareas_to_include,
    lst_df_ER_FR_relationships,
    dir_plots_event_vs_flood_impact_rtrn,
    minimize,
    dpi,
    lst_group_idx,
    bin_labs_rtrn,
    ord_mag,
    lst_rtrns,
    f_best_format,
    dic_event_form_label_lookup,
    df_return_pd_cis_multivar,
    df_return_pd_cis_univar,
    df_return_pd_cis_flood_impacts,
    zoomed_in_subplots,
    chosen_perf_metric=None,
):
    """
    ord_mag is the value to divide the flood meteric by so the y labels don't have a bunch of zeros
    rtrn_range_for_zoomed_in_plots determins the xlims of the zoomed in plot (.1 would yield 90-110 for the targeted 100 year return period)
    """
    lst_subareas_not_included = []
    for subarea in ds_flood_impacts_by_aoi.subarea_name.to_series().to_list():
        if subarea not in lst_subareas_to_include:
            lst_subareas_not_included.append(subarea)
    if len(lst_subareas_not_included) > 0:
        print(f"Skipping subareas: {lst_subareas_not_included}")
    # this is the gridding for each subfigure which allows the colorbar to shifted inward a little bit
    for df_ER_FR_relationship in lst_df_ER_FR_relationships:
        for grp_id, df_group in tqdm(
            df_ER_FR_relationship.groupby(level=lst_group_idx)
        ):
            # define dic of identifiers (these are the constant values describing the data being analyzed)
            dic_identifiers = dict()
            idx_lev_var = None
            for idx_lev in df_group.index.names:
                s_id = df_group.index.to_frame()[idx_lev]
                if len(s_id.unique()) == 1:
                    dic_identifiers[idx_lev] = s_id.unique()[0]
                else:
                    if idx_lev_var is None:
                        idx_lev_var = idx_lev  # if there is more than 1 performance parameter, this is the name of the variable, e.g., err_method
                    else:
                        sys.exit(
                            "this code was only expecing 1 index level to have multiple unique values"
                        )
            # use the dictionary to populate some variables (mostly used for plot labeling)
            impact_var = dic_identifiers["impact_var"]
            depth_range_m = dic_identifiers["depth_range_m"]
            subarea_name = dic_identifiers["subarea_name"]
            event_stat_type = dic_identifiers["event_stat_type"]
            perf_idxs = df_group.reset_index()[
                idx_lev_var
            ].values  # the performance parameter values, e.g., mse and mae
            df_perf_shaped = df_group.reset_index(drop=True).set_index(perf_idxs).T
            # subset target variable if desired
            if chosen_perf_metric is not None:
                df_perf_shaped = df_perf_shaped.loc[:, chosen_perf_metric].to_frame()
            dic_top_cols = dict()
            for comp_idx, s_comp in df_perf_shaped.items():
                dic_top_cols[comp_idx] = s_comp.sort_values(ascending=minimize).head(1)
            # define dataframe with the event return period (ER) that performs the best
            df_best_ERs = pd.DataFrame(dic_top_cols)
            # subfig_idx += 1
            s_row_perf = (
                s_row_perf.dropna()
            )  # this leaves all performance metrics for which this event formulation was the best
            comp_metric = ""
            for metric, val in s_row_perf.items():
                if len(comp_metric) == 0:
                    comp_metric += f"{metric} = {val:.2f}"
                else:
                    comp_metric += f" | {metric} = {val:.2f}"
            str_of_stats = ""
            for stat_idx, stat in s_stats.items():
                if (stat_idx > 0) and stat_idx != 0:  # adds comma before the next entry
                    str_of_stats += ","
                    # str_of_stats += " "
                    # if stat_idx == s_stats.index.max():
                    #     str_of_stats += f"{multivar_formulation}"
                if "waterlevel" in stat:
                    str_of_stats += "$w$"
                else:
                    str_of_stats += f"${create_bar_label_one_line(stat)}$"
            lab_formulation = f"${f_best_format}" + "{f}_m$"
            str_fig_title = f"$a$ = {subarea_name}\n$d$ = {DIC_DPTH_DSC_LOOKUP[depth_range_m]} {depth_range_m}"
            str_fig_title += (
                f"\n{lab_formulation} = ${dic_event_form_label_lookup[event_stat_type].replace("$", "")}_"
                + "{"
                + f"{str_of_stats.replace("$", "")}"
                + "}$"
            )
            # str_fig_title += f"\n{lab_formulation}, $m$: {dic_event_form_label_lookup[event_stat_type]}, {str_of_stats}"
            str_fig_title += f"\n{comp_metric}"
            create_hexbin_weather_vs_impact_rtrn(
                ds_flood_impacts_by_aoi,
                df_return_pd_cis_univar,
                df_return_pd_cis_multivar,
                impact_var,
                depth_range_m,
                subarea_name,
                stats,
                str_fig_title=None,
                fname_savefig=None,
                multivar_formulation=None,
                dpi=300,
            )
    return


# %%
