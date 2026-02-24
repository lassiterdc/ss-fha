# %%
import xarray as xr
from local.__inputs import (
    F_SIM_TSERIES,
    F_FLOOD_IMPACT_RETURN_PERIODS_BY_AOI,
    F_SIM_MULTIVAR_RETURN_PERIODS,
    F_SIM_FLOOD_PROBS_EVENT_NUMBER_MAPPING,
    F_RTRN_PDS_SEA_WATER_LEVEL,
    F_RTRN_PDS_RAINFALL,
    F_BS_UNCERTAINTY_EVENTS_IN_CI,
    F_FLOOD_IMPACT_BS_UNCERTAINTY_EVENTS_IN_CI,
    F_FLOOD_IMPACT_BS_UNCERTAINTY_CI,
    F_WEATHER_EVENT_VS_IMPACT_EVENT_CLASSIFICATION,
    DIC_DPTH_COLOR_LOOKUP,
    DIC_DPTH_DSC_LOOKUP,
    DIR_FLOOD_PROB_VS_EVENT_PROB,
    LST_RTRNS,
    FLD_RTRN_PD_ALPHA,
    SUBAREAS_FOR_COMPUTING_IMPACT_RETURN_PDS,
)
import pandas as pd
import time
from pathlib import Path
from local.__utils import delete_directory
from tqdm import tqdm
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import numpy as np
import sys

ds_sim_tseries = xr.open_dataset(F_SIM_TSERIES).chunk(
    dict(timestep=-1, year=-1, event_type=1, event_id=-1)
)
sim_idx_names = ds_sim_tseries.coords.to_index().names
event_idx_names = [name for name in sim_idx_names if name != "timestep"]

# flood area return periods
df_sim_flood_probs_event_num_mapping = pd.read_csv(
    F_SIM_FLOOD_PROBS_EVENT_NUMBER_MAPPING, index_col=event_idx_names
)
ds_flood_impacts_by_aoi = (
    xr.open_dataset(F_FLOOD_IMPACT_RETURN_PERIODS_BY_AOI, engine="zarr")
    .chunk("auto")
    .sel(sim_form="tritonswmm.multidriver")
)
lst_impact_vars = []
for var in ds_flood_impacts_by_aoi.data_vars:
    # print(var)
    if ("fraction" in var) or ("emp_cdf" in var) or ("return_pd_yrs" in var):
        continue
    lst_impact_vars.append(var)
# event return periods
ds_multivar_return_periods = xr.open_dataset(
    F_SIM_MULTIVAR_RETURN_PERIODS, engine="zarr"
).chunk("auto")
df_wlevel_return_pds = pd.read_csv(
    F_RTRN_PDS_SEA_WATER_LEVEL, index_col=event_idx_names
)
df_rain_rtrn_pds = pd.read_csv(F_RTRN_PDS_RAINFALL, index_col=event_idx_names)
df_univar_return_periods = pd.concat([df_wlevel_return_pds, df_rain_rtrn_pds], axis=1)

df_weather_events_in_ci_og = pd.read_csv(
    F_BS_UNCERTAINTY_EVENTS_IN_CI, index_col=[0, 1, 2, 3]
)

df_flood_events_in_ci_og = pd.read_csv(
    F_FLOOD_IMPACT_BS_UNCERTAINTY_EVENTS_IN_CI, index_col=[0, 1, 2, 3, 4]
)
# subset tritonswmm.multidriver
df_flood_events_in_ci_og = df_flood_events_in_ci_og.loc[
    pd.IndexSlice["tritonswmm.multidriver", :, :, :, :]
]

lst_idx = [
    "sim_form",
    "impact_var",
    "subarea_name",
    "depth_range_m",
    "return_period_yrs",
    "quantile",
]
df_return_pd_cis_flood_impacts_og = pd.read_csv(
    F_FLOOD_IMPACT_BS_UNCERTAINTY_CI, index_col=lst_idx
)
df_return_pd_cis_flood_impacts_og = df_return_pd_cis_flood_impacts_og.loc[
    pd.IndexSlice["tritonswmm.multidriver"]
]
# %% functions


def label_yticks_target_return_pd(ax, LST_RTRNS, blank=False):
    ax.set_yticks(LST_RTRNS)
    newlabs_y = []
    for idx, lab in enumerate(ax.get_yticklabels()):
        if blank:
            lab.set_text("")
        else:
            lab.set_text(str(LST_RTRNS[idx]))
        newlabs_y.append(lab)
    ax.set_yticklabels(newlabs_y)


def classify_events_for_targeted_return_period(
    df_flood_events_in_ci_og,
    df_weather_events_in_ci_og,
    ds_flood_impacts_by_aoi,
    depth_range_m,
    subarea_name,
    lst_impact_vars_classify,
    return_period_yrs,
    formulation,
    event_stat,
):
    lst_idx_classes = ["correct", "misspecified", "omitted"]

    df_flood_events_in_ci = df_flood_events_in_ci_og.reset_index().copy()
    df_weather_events_in_ci = df_weather_events_in_ci_og.reset_index().copy()
    df_flood_events_in_ci_subset = df_flood_events_in_ci[
        (df_flood_events_in_ci["return_period_yrs"] == return_period_yrs)
        & (df_flood_events_in_ci["impact_var"].isin(lst_impact_vars_classify))
        & (df_flood_events_in_ci["subarea_name"] == subarea_name)
        & (df_flood_events_in_ci["depth_range_m"] == depth_range_m)
    ]
    df_weather_events_in_ci_subset = df_weather_events_in_ci[
        (df_weather_events_in_ci["return_period_yrs"] == return_period_yrs)
        & (df_weather_events_in_ci["formulation"] == formulation)
        & (df_weather_events_in_ci["event_stats"] == event_stat)
    ]

    ds_flood_impacts_subset = ds_flood_impacts_by_aoi.sel(
        subarea_name=subarea_name, depth_range_m=depth_range_m
    )

    df_all_event_impacts = ds_flood_impacts_subset.to_dataframe().loc[
        :, lst_impact_vars_classify
    ]

    df_weather_event_impacts = (
        ds_flood_impacts_by_aoi.sel(
            subarea_name=subarea_name,
            depth_range_m=depth_range_m,
            event_number=df_weather_events_in_ci_subset.event_number.unique(),
        )
        .to_dataframe()
        .loc[:, lst_impact_vars_classify]
    )

    df_weather_events_in_ci_subset = df_weather_events_in_ci_subset.join(
        df_weather_event_impacts, on="event_number"
    )

    ## pull out event indices of target events
    # df_weather_events = df_plt_in_ci_grp[(df_plt_in_ci_grp[x_var] == subarea_name)]
    # define classification categories of each event
    # df_class = pd.DataFrame(columns = lst_idx_classes)
    # define center of bin group
    # impact_var = lst_impact_vars_classify[0]

    # create dataframe of the classification of each event
    idx_all_possible_events = df_all_event_impacts.index

    # df_classification_by_event_and_impact_var = pd.DataFrame(index = idx_all_possible_events)

    lst_df_class_by_event = []
    lst_cols = lst_idx_classes + [
        "flood_event",
        "weather_event",
        "nonzero_flooding_in_event",
    ]
    for impact_var in lst_impact_vars_classify:

        df_classify_by_event = pd.DataFrame(
            data=False, index=idx_all_possible_events, columns=lst_cols
        )
        df_classify_by_event.index.name = "event_number"
        df_classify_by_event = df_classify_by_event.reset_index()
        df_classify_by_event["impact_var"] = impact_var
        df_classify_by_event = df_classify_by_event.set_index(
            ["impact_var", "event_number"]
        )
        lst_df_class_by_event.append(df_classify_by_event)

    df_classification_by_event_and_impact_var = pd.concat(lst_df_class_by_event)
    ds_classification_by_event_and_impact_var = (
        df_classification_by_event_and_impact_var.to_xarray()
    )

    lst_ds = []

    for impact_var in lst_impact_vars_classify:
        df_flood_events_in_ci_subset_impact_var = df_flood_events_in_ci_subset[
            df_flood_events_in_ci_subset["impact_var"] == impact_var
        ]
        # subset only flood events with nonzero flooding since these are the ones that would be used as "design floods"
        df_flood_events_in_ci_subset_impact_var = (
            df_flood_events_in_ci_subset_impact_var[
                df_flood_events_in_ci_subset_impact_var["impact"] > 0
            ]
        )
        all_unique_events = pd.concat(
            [
                df_weather_events_in_ci_subset["event_number"],
                df_flood_events_in_ci_subset_impact_var["event_number"],
            ]
        ).unique()
        # classifying events
        ds_classification_for_impact_var = (
            ds_classification_by_event_and_impact_var.sel(impact_var=impact_var)
        )

        ds_classification_for_impact_var["flood_event"].loc[
            dict(
                event_number=df_flood_events_in_ci_subset_impact_var.event_number.values
            )
        ] = True
        ds_classification_for_impact_var["flood_event"] = (
            ds_classification_for_impact_var["flood_event"].expand_dims("impact_var")
        )
        ds_classification_for_impact_var["weather_event"].loc[
            dict(event_number=df_weather_events_in_ci_subset.event_number.values)
        ] = True
        ds_classification_for_impact_var["weather_event"] = (
            ds_classification_for_impact_var["weather_event"].expand_dims("impact_var")
        )

        # if the event is within the confidence interval for both a flood event and a weather event, then it is correctly classified
        ds_classification_for_impact_var["correct"] = xr.where(
            (
                ds_classification_for_impact_var["flood_event"]
                & ds_classification_for_impact_var["weather_event"]
            ),
            True,
            False,
        )  # .expand_dims("impact_var")
        # if it is a flood event and NOT a weather event, then it is omitted
        ds_classification_for_impact_var["omitted"] = xr.where(
            (
                ds_classification_for_impact_var["flood_event"]
                & ~ds_classification_for_impact_var["weather_event"]
            ),
            True,
            False,
        )  # .expand_dims("impact_var")
        # if it is a weather event but not a flood event, then it is misspecified
        ds_classification_for_impact_var["misspecified"] = xr.where(
            (
                ~ds_classification_for_impact_var["flood_event"]
                & ds_classification_for_impact_var["weather_event"]
            ),
            True,
            False,
        )  # .expand_dims("impact_var")
        # populate the field "nonzero_flooding_in_event"
        ds_classification_for_impact_var["nonzero_flooding_in_event"].loc[
            dict(
                event_number=df_all_event_impacts[
                    df_all_event_impacts.loc[:, impact_var] > 0
                ].index.values
            )
        ] = True
        ds_classification_for_impact_var["nonzero_flooding_in_event"] = (
            ds_classification_for_impact_var["nonzero_flooding_in_event"].expand_dims(
                "impact_var"
            )
        )

        lst_ds.append(ds_classification_for_impact_var)
    # combined into a single dataset
    ds_classification_by_event_and_impact_var = xr.merge(lst_ds)
    # classification
    dic_counts = dict()
    # ds_classification_by_event_and_impact_var = df_classification_by_event_and_impact_var.to_xarray()
    n_weather_or_flood_events = (
        ds_classification_by_event_and_impact_var[["weather_event", "flood_event"]]
        .any("impact_var")
        .to_dataframe()
        .any(axis=1)
        .sum()
    )
    dic_counts["correct"] = (
        ds_classification_by_event_and_impact_var["correct"]
        .all("impact_var")
        .to_series()
        .sum()
    )
    dic_counts["omitted"] = (
        ds_classification_by_event_and_impact_var["omitted"]
        .all("impact_var")
        .to_series()
        .sum()
    )
    atleast_1_correct = (
        ds_classification_by_event_and_impact_var["correct"]
        .any("impact_var")
        .to_series()
        .sum()
    )
    dic_counts["misspecified"] = (
        ds_classification_by_event_and_impact_var["misspecified"]
        .all("impact_var")
        .to_series()
        .sum()
    )
    dic_counts["mixed1_correct"] = atleast_1_correct - dic_counts["correct"]
    n_events_classified = 0
    for key in dic_counts.keys():
        n_events_classified += dic_counts[key]
    dic_counts["mixed_omitted_or_misspecified"] = (
        n_weather_or_flood_events - n_events_classified
    )

    # dic_counts["overbuild"] = ds_classification_by_event_and_impact_var["overbuild"].all("impact_var").to_series().sum()
    # dic_counts["underbuild"] = ds_classification_by_event_and_impact_var["underbuild"].all("impact_var").to_series().sum()
    # dic_counts["omitted"] = ds_classification_by_event_and_impact_var["omitted"].all("impact_var").to_series().sum()

    # identify all events that were classified

    # dic_counts["multi_impact_neither_correct_different_reasons"] = n_weather_or_flood_events - n_events_classified
    df_class = pd.DataFrame(columns=dic_counts.keys())
    for key in dic_counts.keys():
        df_class.loc[0, key] = dic_counts[key] / n_weather_or_flood_events

    impact_var_for_col = return_impact_varname_from_list(lst_impact_vars_classify)
    df_class.loc[0, "impact_var"] = impact_var_for_col
    df_class["n_events"] = n_weather_or_flood_events

    da_mask_nonzero_flooding = ds_classification_by_event_and_impact_var[
        "nonzero_flooding_in_event"
    ].any("impact_var")

    e_id = 18
    df_all_event_impacts.loc[e_id, :]

    da_mask_impact_events = ds_classification_by_event_and_impact_var[
        "flood_event"
    ].any("impact_var")
    df_class["n_impact_events"] = int(da_mask_impact_events.to_series().sum())
    df_class["n_impact_events_nonzero_flooding"] = int(
        da_mask_nonzero_flooding.where(da_mask_impact_events).to_series().sum()
    )

    da_mask_weather_events = ds_classification_by_event_and_impact_var[
        "weather_event"
    ].any("impact_var")
    df_class["n_weather_events"] = int(da_mask_weather_events.to_series().sum())
    df_class["n_weather_events_nonzero_flooding"] = int(
        da_mask_nonzero_flooding.where(da_mask_weather_events).to_series().sum()
    )

    df_class.loc[0, "formulation"] = formulation
    df_class.loc[0, "event_stats"] = event_stat
    df_class.loc[0, "subarea_name"] = subarea_name
    df_class.loc[0, "depth_range_m"] = depth_range_m
    df_class.loc[0, "return_period_yrs"] = int(return_period_yrs)
    return df_class


def return_impact_varname_from_list(lst_impact_vars):
    impact_var_combined = ""
    for impact_var in lst_impact_vars:
        if impact_var_combined == "":
            impact_var_combined += impact_var
        else:
            impact_var_combined += f".{impact_var}"
    return impact_var_combined


def return_flood_impact_ci_bounds(
    df_return_pd_cis_flood_impacts_og,
    df_flood_impacts_by_aoi_subset,
    depth_range_m,
    subarea_name,
    impact_var,
    return_period_yrs,
    use_aep,
):
    # df_return_pd_cis_flood_impacts_og, df_flood_impacts_by_aoi_subset, depth_range_m, subarea_name, impact_var, return_period_yrs, use_aep = df_return_pd_cis_flood_impacts_og, df_flood_impacts_by_aoi_subset, depth_range_m, subarea_name, impact_var, x_idx, use_aep
    df_return_pd_cis_flood_impacts = (
        df_return_pd_cis_flood_impacts_og.reset_index().copy()
    )
    if use_aep:
        df_return_pd_cis_flood_impacts["return_period_yrs_og"] = (
            1 / df_return_pd_cis_flood_impacts["return_period_yrs_og"]
        )
        df_return_pd_cis_flood_impacts["return_period_yrs"] = (
            1 / df_return_pd_cis_flood_impacts["return_period_yrs"]
        )

    df_return_pd_cis_flood_impacts = df_return_pd_cis_flood_impacts[
        (df_return_pd_cis_flood_impacts["return_period_yrs"] == return_period_yrs)
        & (df_return_pd_cis_flood_impacts["impact_var"] == impact_var)
        & (df_return_pd_cis_flood_impacts["subarea_name"] == subarea_name)
        & (df_return_pd_cis_flood_impacts["depth_range_m"] == depth_range_m)
    ]

    rtrn_col = df_flood_impacts_by_aoi_subset.filter(like="return_pd").iloc[:, 0].name
    df_flood_impacts = df_flood_impacts_by_aoi_subset.sort_values(
        rtrn_col
    ).reset_index()
    df_flood_impacts = df_flood_impacts[
        df_flood_impacts["depth_range_m"] == depth_range_m
    ]

    rtrn_periods = df_return_pd_cis_flood_impacts["return_period_yrs_og"].values
    interpolated_impacts = np.interp(
        rtrn_periods, df_flood_impacts[rtrn_col], df_flood_impacts[impact_var]
    )

    lb_flood_rtrn_rlspc, ub_flood_rtrn_rlspc = (
        interpolated_impacts.min(),
        interpolated_impacts.max(),
    )
    lb_flood_rtrn, ub_flood_rtrn = rtrn_periods.min(), rtrn_periods.max()

    return lb_flood_rtrn, lb_flood_rtrn_rlspc, ub_flood_rtrn, ub_flood_rtrn_rlspc


# %% classifying events

# create some additonal classes
lst_lst_impact_vars = [
    ["n_building_id_impacted", "n_road_segment_id_impacted"],
    ["flooded_area_sqm"],
    ["n_building_id_impacted"],
    ["n_road_segment_id_impacted"],
]

ar_return_periods = (
    df_weather_events_in_ci_og.reset_index()["return_period_yrs"].sort_values().unique()
)

# # df_flood_impacts_by_aoi = ds_flood_impacts_by_aoi.to_dataframe()
# n_iterations_required = 0
# # loop through event formulations
# for event_group, df_event_formulation in tqdm(df_weather_events_in_ci_og.groupby(level = ["formulation", "event_stats"])):
#     formulation, event_stats = event_group
#     # loop through return periods, AOIs, and hazard levels
#     for grp_idx, df_grp in df_flood_events_in_ci_og.groupby(level = ["return_period_yrs", "subarea_name", "depth_range_m"]):
#         return_period_yrs, subarea_name, depth_range_m = grp_idx
#         # loop through impact variables
#         for lst_impact_vars_classify in lst_lst_impact_vars:
#             n_iterations_required += 1

#
val = input(f"type 'yes' to classify events")
classify_events = False
if val.lower() == "yes":
    classify_events = True

if classify_events:
    lst_df_class = []
    # n_iterations = 0
    for event_group, df_event_formulation in tqdm(
        df_weather_events_in_ci_og.groupby(level=["formulation", "event_stats"])
    ):
        # n_iterations += 1
        formulation, event_stat = event_group
        # loop through return periods, AOIs, and hazard levels
        for grp_idx, df_grp in df_flood_events_in_ci_og.groupby(
            level=["return_period_yrs", "subarea_name", "depth_range_m"]
        ):
            return_period_yrs, subarea_name, depth_range_m = grp_idx
            if subarea_name not in SUBAREAS_FOR_COMPUTING_IMPACT_RETURN_PDS:
                continue

            # loop through impact variables
            for lst_impact_vars_classify in lst_lst_impact_vars:
                # impact_var = return_impact_varname_from_list(lst_impact_vars_classify)
                # if (return_period_yrs == 10) and (impact_var == "n_road_segment_id_impacted") and (depth_range_m == "[0.03,0.1)") and ("univar" in formulation) and (event_stat == "max_0hr_15min_mm"):
                #     sys.exit('work')
                # else:
                #     continue
                bm_time = time.time()
                df_class = classify_events_for_targeted_return_period(
                    df_flood_events_in_ci_og,
                    df_weather_events_in_ci_og,
                    ds_flood_impacts_by_aoi,
                    depth_range_m,
                    subarea_name,
                    lst_impact_vars_classify,
                    return_period_yrs,
                    formulation,
                    event_stat,
                )
                lst_df_class.append(df_class)
    df_weather_vs_impact_retrn_pd_classification = pd.concat(lst_df_class).set_index(
        [
            "impact_var",
            "formulation",
            "event_stats",
            "subarea_name",
            "depth_range_m",
            "return_period_yrs",
        ]
    )
    df_weather_vs_impact_retrn_pd_classification.to_csv(
        F_WEATHER_EVENT_VS_IMPACT_EVENT_CLASSIFICATION
    )

df_weather_vs_impact_retrn_pd_classification = pd.read_csv(
    F_WEATHER_EVENT_VS_IMPACT_EVENT_CLASSIFICATION, index_col=[0, 1, 2, 3, 4, 5]
)

# %% create separate plots with KDE and stacked bars
subarea_name = "watershed"
use_aep = True
# impact_var = "n_building_id_impacted"
plot_interval_for_weatherbased_impact_quantiles = False
bar_width = 0.6
whisker_alpha = 0.05
dpi = 200
x_var = "return_period_yrs"
grp_var = "depth_range_m"
xlab = ""
dic_pallet = DIC_DPTH_COLOR_LOOKUP
dic_legend_name_mapping = DIC_DPTH_DSC_LOOKUP
use_aep_for_yvar = False
if use_aep_for_yvar:
    y_range = (0.2, 500)
    if use_aep:
        y_range = 1 / np.asarray(y_range)

dir_kde_plots = f"{DIR_FLOOD_PROB_VS_EVENT_PROB}plots/mcds_vs_ss_kde/"
dir_stacked_bar_plots = f"{DIR_FLOOD_PROB_VS_EVENT_PROB}plots/mcds_vs_ss_stackedbars/"
Path(dir_kde_plots).mkdir(parents=True, exist_ok=True)
Path(dir_stacked_bar_plots).mkdir(parents=True, exist_ok=True)
val = input(f"type 'delete' to remove all existing plots first")
delete_plots = False
if val.lower() == "delete":
    delete_plots = True
if delete_plots:
    delete_directory(dir_kde_plots, attempt_time_limit_s=10)
    delete_directory(dir_stacked_bar_plots, attempt_time_limit_s=10)
    Path(dir_kde_plots).mkdir(parents=True, exist_ok=True)
    Path(dir_stacked_bar_plots).mkdir(parents=True, exist_ok=True)

# determine formulatoins to check out
df_weather_vs_impact_retrn_pd_classification_AND = (
    df_weather_vs_impact_retrn_pd_classification.loc[
        pd.IndexSlice[:, "empirical_multivar_rtrn_yrs_AND", :, :, :, :]
    ]
)
idx_best_multivar = (
    df_weather_vs_impact_retrn_pd_classification_AND.groupby(
        ["impact_var", "subarea_name", "depth_range_m", "return_period_yrs"]
    )["correct"]
    .idxmax()
    .values
)
df_classification_multivar_best_aoi = (
    df_weather_vs_impact_retrn_pd_classification_AND.loc[idx_best_multivar].loc[
        pd.IndexSlice["n_building_id_impacted", :, subarea_name, :, :]
    ]
)
df_classification_multivar_best_aoi = df_classification_multivar_best_aoi[
    df_classification_multivar_best_aoi["n_impact_events_nonzero_flooding"] > 0
]

lst_formulations = [
    "best",
    "empirical_univar_return_pd_yrs",
    "empirical_univar_return_pd_yrs",
    "empirical_univar_return_pd_yrs",
    "empirical_multivar_rtrn_yrs_AND",
    "empirical_multivar_rtrn_yrs_AND",
    "empirical_multivar_rtrn_yrs_AND",
    "empirical_multivar_rtrn_yrs_OR",
    "empirical_multivar_rtrn_yrs_OR",
    "empirical_multivar_rtrn_yrs_OR",
]
lst_stat_to_choose = [
    "best",
    "max_0hr_15min_mm",
    "max_4hr_0min_mm",
    "max_24hr_0min_mm",
    "15min,24hr,w",
    "30min,w",
    "15min,w",
    "15min,24hr,w",
    "30min,w",
    "15min,w",
]

# print("ONLY PRINTING ONE OF THE EVENT FORMULATOINS")
# lst_formulations = ["empirical_univar_return_pd_yrs"]
# lst_stat_to_choose = ["max_0hr_15min_mm"]


df_formulations_to_plot = pd.DataFrame(
    dict(formulation=lst_formulations, event_stat=lst_stat_to_choose)
)

# input datasets
df_weather_vs_impact_retrn_pd_classification
ds_flood_impacts_by_aoi
df_weather_events_in_ci_og
df_flood_events_in_ci_og

working = False
if working:
    print("only plotting first loop while working on script")
lst_lst_impact_vars = [
    ["n_building_id_impacted"],
    ["flooded_area_sqm"],
    ["n_road_segment_id_impacted"],
]
for lst_impact_vars in lst_lst_impact_vars:

    impact_var = return_impact_varname_from_list(lst_impact_vars)
    # n_building_id_impacted.n_road_segment_id_impacted  'n_road_segment_id_impacted.n_road_segment_id_impacted'
    for idx, row_stat in df_formulations_to_plot.iterrows():
        formulation = row_stat["formulation"]
        event_stat = row_stat["event_stat"]
        if formulation == "best":
            fname_savefig_kde = f"{dir_kde_plots}{subarea_name}_{impact_var}.event_formulation_best_kde.png"
            fname_savefig_stckdbar = f"{dir_stacked_bar_plots}{subarea_name}_{impact_var}.event_formulation_best_stacked_bar.png"
            plt_title = f"{subarea_name} {impact_var} for the weather\nevent formulation yielding the most true positives"
            idx_best = (
                df_weather_vs_impact_retrn_pd_classification.groupby(
                    ["impact_var", "subarea_name", "depth_range_m", "return_period_yrs"]
                )["correct"]
                .idxmax()
                .values
            )
            df_classification_best_aoi = (
                df_weather_vs_impact_retrn_pd_classification.loc[idx_best].loc[
                    pd.IndexSlice[impact_var, :, :, subarea_name, :, :, :]
                ]
            )
            filter_weather_events_with_best_stats = (
                df_weather_events_in_ci_og.reset_index()["event_stats"].isin(
                    df_classification_best_aoi.reset_index()["event_stats"].unique()
                )
            )
            df_weather_events_in_ci_subset = df_weather_events_in_ci_og[
                filter_weather_events_with_best_stats.values
            ]
        else:
            fname_savefig_kde = f"{dir_kde_plots}{subarea_name}_{impact_var}.event_formulation_{formulation}_of_{event_stat}_kde.png"
            fname_savefig_stckdbar = f"{dir_stacked_bar_plots}{subarea_name}_{impact_var}.event_formulation_{formulation}_of_{event_stat}_stacked_bar.png"
            plt_title = (
                f"{subarea_name} {impact_var} based on\n{formulation} of {event_stat}"
            )
            df_classification_best_aoi = (
                df_weather_vs_impact_retrn_pd_classification.loc[
                    pd.IndexSlice[
                        impact_var, formulation, event_stat, subarea_name, :, :
                    ]
                ]
            )
            df_weather_events_in_ci_subset = df_weather_events_in_ci_og.loc[
                pd.IndexSlice[formulation, event_stat]
            ]
        # only extract rows where the number of impact events is greater than zero
        # df_classification_best_aoi = df_classification_best_aoi[df_classification_best_aoi["n_impact_events"]>0]

        # compound_impact = False
        # if len(impact_var)

        # prepare data for plotting
        df_flood_impacts_by_aoi = ds_flood_impacts_by_aoi.sel(
            subarea_name="watershed"
        ).to_dataframe()
        # subset flood impacts
        if "flooded_area" in impact_var:
            # continue
            df_flood_impacts_by_aoi_subset = df_flood_impacts_by_aoi.filter(
                like="flooded_area"
            )
            subvar = "flooded_area_sqm"
        else:
            cols = []
            for subvar in impact_var.split("."):
                cols += list(df_flood_impacts_by_aoi.filter(like=subvar).columns)
            df_flood_impacts_by_aoi_subset = df_flood_impacts_by_aoi.loc[:, cols]

        colname_impact_return_period = (
            df_flood_impacts_by_aoi_subset.filter(like="return_pd").iloc[:, 0].name
        )

        if use_aep:
            # impacts
            df_flood_impacts_by_aoi_subset = df_flood_impacts_by_aoi_subset.copy()
            df_flood_impacts_by_aoi_subset[colname_impact_return_period] = (
                1 / df_flood_impacts_by_aoi_subset[colname_impact_return_period]
            )
            # weather
            idx_names = df_weather_events_in_ci_subset.index.names
            df_weather_events_in_ci_subset = (
                df_weather_events_in_ci_subset.reset_index()
            )
            df_weather_events_in_ci_subset["return_period_yrs"] = (
                1 / df_weather_events_in_ci_subset["return_period_yrs"]
            )
            df_weather_events_in_ci_subset = df_weather_events_in_ci_subset.set_index(
                idx_names
            )

        s_impact_return_periods = df_flood_impacts_by_aoi_subset[
            colname_impact_return_period
        ]
        colname_impact_return_period = s_impact_return_periods.name

        if use_aep_for_yvar:
            y_var = colname_impact_return_period
        else:
            y_var = subvar

        # return the impact return period of all weather events of each return period
        ##

        # df_event_return_pds = df_weather_events_in_ci_subset.loc[pd.IndexSlice[formulation,event_stat]].reset_index().set_index('event_number')
        df_weather_events_w_impact_stats = (
            df_weather_events_in_ci_subset.reset_index()
            .set_index("event_number")
            .join(
                df_flood_impacts_by_aoi_subset.reset_index().set_index("event_number"),
                on="event_number",
                how="left",
            )
            .reset_index()
        )  # these are the results of all x-year weather events

        # these two dataframes contain all the plotting information
        fig_kde, ax_kde = plt.subplots(figsize=(6, 4), dpi=300)

        width_dist_plot = 1
        # kde_bw = 0.8
        kde_method = "scott"
        kde_gap = 0.15
        col_mcfra_ci = "red"
        df_weather_events_w_impact_stats[x_var]
        log_scale = False
        if use_aep_for_yvar:
            log_scale = True
        parts = sns.violinplot(
            data=df_weather_events_w_impact_stats,
            x=x_var,
            y=y_var,
            hue=grp_var,
            split=True,
            inner=None,
            log_scale=log_scale,
            ax=ax_kde,
            palette=dic_pallet,
            legend=False,
            alpha=0.8,
            width=width_dist_plot,
            dodge=True,
            common_norm=True,
            orient="x",
            cut=0,
            bw_method=kde_method,
            gap=kde_gap,
            linecolor="k",
            linewidth=0.8,
            order=df_weather_events_w_impact_stats[x_var].unique(),
        )

        n_groups = len(df_weather_events_w_impact_stats[grp_var].unique())

        # Lower zorder of boxplot elements (artists and lines)
        for artist in ax_kde.artists + ax_kde.lines:
            artist.set_zorder(2)

        # Force gridlines to be redrawn on top
        if use_aep_for_yvar:
            ax_kde.set_yscale("log")
        ax_kde.set_axisbelow(False)  # This puts grid *on top* of plot elements
        ax_kde.grid(
            True, which="major", linestyle="--", linewidth=0.5, axis="y", zorder=10
        )
        ax_kde.grid(
            True, which="major", linestyle="--", linewidth=0.5, axis="x", zorder=10
        )
        if use_aep_for_yvar:
            yticks = LST_RTRNS
            if use_aep:
                yticks = 1 / np.asarray(LST_RTRNS)
            label_yticks_target_return_pd(ax_kde, yticks, blank=False)

        # plot confidence interval of flood return period
        # parameters for figuring out the location of each bar
        xtick_labs = ax_kde.get_xticklabels()

        length_of_bar_group = bar_width
        width_of_shaded_region = bar_width / n_groups / 8
        # loop through each x variable and plot flood impact return periods
        lst_xs = []
        for lab in xtick_labs:
            x_idx = lab.get_text()
            try:
                x_idx = float(x_idx)
            except:
                pass
            x_position = lab.get_position()[0]
            lst_xs.append(x_position)
            # define spacing for the bars
            if n_groups != 2:
                sys.exit("the code currently only accomodates 2 hazard levels")
            if n_groups % 2 == 0:  # even number of groups
                even_grp = True
                futhest_left = (x_position + bar_width / 2) - (
                    bar_width * (n_groups / 2)
                )
                futhest_right = futhest_left + bar_width * (n_groups - 1)
            else:
                even_grp = False
                futhest_left = x_position - length_of_bar_group / n_groups
                futhest_right = x_position + length_of_bar_group / n_groups
            # bring them closer to eachother
            squeeze_factor = (
                0.75  # value from 0 to 1; the larger the number, the closer they are
            )
            distance_to_center = (futhest_right - futhest_left) / 2
            futhest_right = (
                futhest_right - distance_to_center * squeeze_factor + kde_gap / 3
            )
            futhest_left = (
                futhest_left + distance_to_center * squeeze_factor - kde_gap / 3
            )
            # define the center of each confidence interval
            x_locs = np.linspace(start=futhest_left, stop=futhest_right, num=n_groups)
            idx = -1

            # loop through each depth range and create a fillbetween plot representing the flood impact return period
            for depth_range_m in np.sort(
                df_weather_events_w_impact_stats["depth_range_m"].unique()
            ):
                # for grp_idx, df_plt_in_ci_grp in df_weather_events_w_impact_stats.groupby(grp_var):
                df_plt_in_ci_grp = df_weather_events_w_impact_stats[
                    df_weather_events_w_impact_stats["depth_range_m"] == depth_range_m
                ]
                idx += 1
                # depth_range_m = grp_idx
                (
                    lb_flood_rtrn,
                    lb_flood_rtrn_rlspc,
                    ub_flood_rtrn,
                    ub_flood_rtrn_rlspc,
                ) = return_flood_impact_ci_bounds(
                    df_return_pd_cis_flood_impacts_og,
                    df_flood_impacts_by_aoi_subset,
                    depth_range_m,
                    subarea_name,
                    impact_var,
                    return_period_yrs=x_idx,
                    use_aep=use_aep,
                )
                # if there is nonzero flooding for one of the bounds, create a fillbetween plot
                if (lb_flood_rtrn_rlspc == 0) and (ub_flood_rtrn_rlspc == 0):
                    continue
                # if x_idx == 100:
                #     sys.exit('work')
                center_x = x_locs[idx]
                # ax_kde.fill_between(x=(center_x-width_of_shaded_region, center_x+width_of_shaded_region), y1 = ub_flood_rtrn,
                #                     y2 = lb_flood_rtrn, edgecolor = "orange", facecolor = "none", alpha = 0.7, zorder = 100,
                #                 linewidth = 2)
                lb, ub = lb_flood_rtrn_rlspc, ub_flood_rtrn_rlspc
                if use_aep_for_yvar:
                    lb, ub = lb_flood_rtrn, ub_flood_rtrn
                for bound in [lb, ub]:
                    ax_kde.plot(
                        [
                            center_x - width_of_shaded_region,
                            center_x + width_of_shaded_region,
                        ],
                        [bound, bound],
                        color="orange",
                        linewidth=1.5,
                    )
                ax_kde.plot(
                    [center_x, center_x], [lb, ub], color="orange", linewidth=1.5
                )

                # also add lines representing the 90% confidence interval of the MC-FRA approach
                s_weatherbased_impact_return_pds = df_plt_in_ci_grp[
                    df_plt_in_ci_grp[x_var] == x_idx
                ].loc[:, y_var]
                s_weatherbased_impact_quants = (
                    s_weatherbased_impact_return_pds.quantile(
                        [FLD_RTRN_PD_ALPHA / 2, (1 - FLD_RTRN_PD_ALPHA / 2)],
                        interpolation="nearest",
                    )
                )
                # if (x_idx == 1) and (depth_range_m == "[0.03,0.1)"):
                #     sys.exit('work')
                # ax_kde.fill_between(x=(center_x-width_of_shaded_region, center_x+width_of_shaded_region), y1 = s_weatherbased_impact_quants.max(),
                #                     y2 = s_weatherbased_impact_quants.min(), edgecolor = "black", facecolor = "none", alpha = 0.7, zorder = 100,
                #                 linewidth = 2)
                # from matplotlib.lines import Line2D
                # Line2D()
                if plot_interval_for_weatherbased_impact_quantiles:
                    from scipy import stats

                    kde_estimator = stats.gaussian_kde(
                        np.log(s_weatherbased_impact_return_pds), bw_method=kde_method
                    )
                    # kde_estimator = stats.gaussian_kde(s_weatherbased_impact_return_pds, bw_method = kde_bw)
                    for weather_bound in s_weatherbased_impact_quants.values:
                        kds_estimate = kde_estimator(np.log(weather_bound))[0] / 2
                        # kds_estimate = kde_estimator(weather_bound)[0]

                        x_origin = x_position
                        # find the kde density estimate which will correspond to the length along the x axis (seaborn uses a Gaussian kernel)
                        overrun_adjustment = 0.02
                        if depth_range_m == "[0.1,inf)":
                            x_left = x_origin + kde_gap / 3
                            x_right = x_origin + kds_estimate - overrun_adjustment
                        elif depth_range_m == "[0.03,0.1)":
                            x_right = x_origin - kde_gap / 3
                            x_left = x_origin - kds_estimate + overrun_adjustment
                        else:
                            sys.exit("unrecognized depth range")
                        y_position = weather_bound
                        ax_kde.plot(
                            [x_left, x_right],
                            [y_position, y_position],
                            color=col_mcfra_ci,
                            linewidth=1.5,
                        )
                        # ax_kde.plot([center_x, center_x], [lb_flood_rtrn, ub_flood_rtrn], color = "red", linewidth = 1.5)
                        # figure out how to plot kde estimates

        ax_kde.set_xlabel(xlab)
        ylab = "$\\hat{R}_{F}({y})$"
        if use_aep:
            ylab = subvar
            if use_aep_for_yvar:
                ylab = "annual flood\nimpact frequency"
        ax_kde.set_ylabel(ylab)
        if use_aep_for_yvar:
            ax_kde.set_ylim(y_range)
        xlab = "$\\hat{R}_{E}({y})$"
        if use_aep:
            xlab = "annual frequency"
        ax_kde.set_xlabel(xlab)
        ax_kde.set_xticks(ax_kde.get_xticks())
        xticks = ax_kde.get_xticklabels()
        newticks = []
        for lab in xticks:
            current_text = lab.get_text()
            newticks.append(current_text.replace("_", "\n"))
        ax_kde.set_xticklabels(newticks)

        legend_vert_adjst_factor = -0.05
        # create custom legend
        legend_elements = []
        # add the shaded region
        # patch = mpatches.Patch(label = "$\\hat{R}_{F}({y})$ 90% CI",  edgecolor = "orange", facecolor = "grey", alpha = 0.7)
        # legend_elements.append(patch)
        import matplotlib.lines as mlines

        # append_lab = ""
        # if use_aep_for_yvar:
        #     append_lab = "\nfrequency"
        line_impact_ci = mlines.Line2D(
            [], [], label=f"90% CI from\nfull ensemble", color="orange", linewidth=1.5
        )
        if plot_interval_for_weatherbased_impact_quantiles:
            line_weather_ci = mlines.Line2D(
                [], [], label="MC-FRA 90% CI", color=col_mcfra_ci, linewidth=1.5
            )
            legend_elements.append(line_weather_ci)
        legend_elements.append(line_impact_ci)
        # add a shaded region for 90% CI of event return period
        patch = mpatches.Patch(
            label="90% CI of driver\nfrequency\nsubsetting MDS",
            facecolor="white",
            edgecolor="black",
            alpha=0.5,
        )
        legend_elements.append(patch)

        fig_kde.legend(
            handles=legend_elements,
            loc="upper center",
            fontsize=8,
            title="",
            title_fontsize=8,
            bbox_to_anchor=(1.04, 0.55 + legend_vert_adjst_factor),
            ncols=1,
            frameon=False,
        )
        legend_elements = []
        for key in dic_pallet.keys():
            if dic_legend_name_mapping is None:
                label = key
            else:
                label = dic_legend_name_mapping[key]
            if "_" in label:
                label = label.replace("_", "\n")
            patch = mpatches.Patch(
                label=f"{label} depths", facecolor=dic_pallet[key], edgecolor="k"
            )
            legend_elements.append(patch)

        fig_kde.legend(
            handles=legend_elements,
            loc="upper center",
            fontsize=8,
            title_fontsize=9,
            bbox_to_anchor=(1.035, 0.36 + legend_vert_adjst_factor),
            ncols=1,
            title="KDE of MDS impact\n frequencies for:",
            frameon=False,
        )

        # add a miniature KDE plot as a legend
        plot_mini_kde = False
        if not plot_mini_kde:
            # print("Plotting mini KDE in legend is set to false")
            pass
        elif plot_mini_kde:
            # Simulated example DataFrame
            np.random.seed(42)
            df_weather_events_dummy = pd.DataFrame(
                {
                    x_var: np.repeat(["A", "B"], 200),
                    y_var: np.concatenate(
                        [
                            np.random.lognormal(mean=1, sigma=0.5, size=200),
                            np.random.lognormal(mean=1.2, sigma=0.4, size=200),
                        ]
                    ),
                    grp_var: np.tile(["[0.03,0.1)", "[0.1,inf)"], 200),
                }
            )

            inset_ax = fig_kde.add_axes(
                [0.92, 0.11 + legend_vert_adjst_factor, 0.18, 0.18]
            )
            # Violin plot parameters
            # x_var = 'x_var'
            # y_var = 'y_var'
            # grp_var = 'grp_var'
            # dic_pallet = {'G1': 'skyblue', 'G2': 'orange'}
            width_dist_plot = 0.9
            kde_method = "scott"
            kde_gap = 0  # You might be using this to adjust spacing
            alpha = 0.8
            # Violin plot in inset
            sns.violinplot(
                data=df_weather_events_dummy,
                x=x_var,
                y=y_var,
                hue=grp_var,
                split=True,
                inner=None,
                log_scale=True,
                ax=inset_ax,
                palette=dic_pallet,
                legend=False,
                alpha=alpha,
                width=width_dist_plot,
                dodge=True,
                common_norm=True,
                orient="x",
                cut=0,
                bw_method=kde_method,
                linewidth=0.8,
            )
            # Clean up the inset to look more like a legend
            inset_ax.set_title("MDS-FRA\nimpact frequency KDE", fontsize=8)
            inset_ax.set_xticks([])
            inset_ax.set_yticks([])
            inset_ax.set_xlabel("")
            inset_ax.set_ylabel("")
            inset_ax.set_facecolor("white")
        ################################ creating scatterplot visual legend ###################################################
        np.random.seed(0)
        x = np.random.normal(0, 1, 200)
        y = 1.2 * x + np.random.normal(0, 1, 200)

        # Compute mean and standard error
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        x_se = np.std(x) / np.sqrt(len(x)) * 9  # Make it wider (scaled by factor of 2)

        # Create figure and axis
        inset_ax_fb = fig_kde.add_axes(
            [0.94, 0.6 + legend_vert_adjst_factor, 0.2, 0.24]
        )

        # Scatter plot
        df_plotting_data = pd.DataFrame(dict(x=x, y=y))
        # subset data within MDS CI
        idx_MDS = df_plotting_data[
            (df_plotting_data["x"] >= -x_se) & (df_plotting_data["x"] <= x_se)
        ].index

        inset_ax_fb.scatter(
            x,
            y,
            alpha=0.7,
            edgecolor="k",
            s=10,
            label="Data",
            facecolor="none",
            linewidth=0.5,
        )
        inset_ax_fb.scatter(
            df_plotting_data.loc[idx_MDS, "x"],
            df_plotting_data.loc[idx_MDS, "y"],
            alpha=0.8,
            edgecolor="k",
            s=10,
            label="Data",
            facecolor="#3182bd",
            linewidth=0.5,
            zorder=10,
        )

        # Fill vertical band for standard error of y (centered on zero)
        # inset_ax_fb.fill_between(
        #     x=np.linspace(min(x), max(x), 100),
        #     y1=-x_se,  # Start the band at -y_se (centered on 0)
        #     y2=x_se,   # End the band at +y_se (centered on 0)
        #     facecolor='none',  # No fill color
        #     edgecolor='black',  # Black outline
        #     label='SE in Y'
        # )

        inset_ax_fb.fill_betweenx(
            y=np.linspace(min(x), max(x), 100),
            x1=-x_se,  # Start the band at -y_se (centered on 0)
            x2=x_se,  # End the band at +y_se (centered on 0)
            facecolor="white",  # No fill color
            edgecolor="black",  # Black outline
            alpha=0.5,
        )
        inset_ax_fb.set_title(
            "visual legend for\n one target frequency\nand hazard level", fontsize=9
        )
        inset_ax_fb.set_xlabel("driver frequency", fontsize=8)
        inset_ax_fb.set_ylabel("impact frequency", fontsize=8)
        # inset_ax_fb.legend()
        inset_ax_fb.set_xticks([])
        inset_ax_fb.set_yticks([])
        inset_ax_fb.set_xlim((x.min(), x.max()))
        inset_ax_fb.set_ylim((x.min(), x.max()))

        inset_ax_fb.axhline(y=-x_se, color="orange", linewidth=1.5, zorder=11)
        inset_ax_fb.axhline(y=x_se, color="orange", linewidth=1.5, zorder=11)

        if plt_title is not None:
            # fig_stckd_bar.suptitle(f"{plt_title}", x = .5, y = .94)
            ax_kde.set_title(plt_title)
        # extract ticks and labels for the stacked bars

        kde_ticks = ax_kde.get_xticks()
        kde_tick_labs = ax_kde.get_xticklabels()

        plt.savefig(fname_savefig_kde, bbox_inches="tight")
        # sys.exit('work')
        if not working:
            plt.clf()

        # sys.exit('work')

        fig_stckd_bar, ax_stckd_bar = plt.subplots(figsize=(5, 4), dpi=300)

        ## top plot
        df_classification_best_aoi
        width = width_of_each_box = bar_width / n_groups
        multiplier = 0

        # define the center of each bar group
        # ax_stckd_bar.set_xlim(ax_kde.get_xlim())
        x = np.asarray(lst_xs)
        # for xval in x:
        #     ax_stckd_bar.axvline(xval, color = "red")
        # determine location of furthest left plot of each group
        if even_grp:  # shift so that each x occurs in between the two middle bars
            futhest_left = (
                x - width / 2
            )  # width_dist_plot/2) - (width_dist_plot * (n_groups/2))
        else:
            futhest_left = x - length_of_bar_group / n_groups
        x = x + futhest_left[0]

        n_hatch_mltp = 8
        if (df_classification_best_aoi["mixed1_correct"].sum() > 0) or (
            df_classification_best_aoi["mixed_omitted_or_misspecified"].sum() > 0
        ):  # meaning the impact variable is a combination of multiple impacts and in some cases, there are events that yield the targeted return period impact for one and not the other
            # dic_cmapping = {"correct":"k", "mixed":"#fce674", "misspecified":"#fce674"}
            # dic_cmapping = {"correct":"k","omitted":"k", "mixed":"k", "misspecified":"k"}
            # dic_hatch_mapping = {"correct":"."*n_hatch_mltp, "mixed":"|"*6, "misspecified":"x"*n_hatch_mltp, "omitted":"/"*n_hatch_mltp}
            sys.exit(
                "need to figure out visualizations for the multi-impact variable case"
            )
        else:
            # dic_cmapping = {"correct":"k","misspecified":"#fce674"}
            dic_cmapping = {"correct": "k", "omitted": "k", "misspecified": "k"}
            dic_hatch_mapping = {
                "correct": "." * n_hatch_mltp,
                "omitted": "/" * n_hatch_mltp,
                "misspecified": "x" * n_hatch_mltp,
            }

        cols = dic_hatch_mapping.keys()

        for grp_idx, df_group in df_classification_best_aoi.loc[:, cols].groupby(
            level=grp_var
        ):
            offset = width * multiplier
            bottom = np.zeros(x.shape)
            n_events_grp = df_classification_best_aoi[
                (
                    df_classification_best_aoi.reset_index()["depth_range_m"] == grp_idx
                ).values
            ].loc[:, "n_events"]
            for col_idx, col in df_group.items():
                vals = col.astype(float).values
                last_col = False
                if col_idx == df_group.columns[-1]:
                    last_col = True
                    # sys.exit("work")
                edgecolor = "k"
                facecolor = dic_pallet[grp_idx]
                hatch = dic_hatch_mapping[col_idx]

                hatchcol = dic_cmapping[col_idx]
                rects = ax_stckd_bar.bar(
                    x + offset,
                    vals,
                    width,
                    label=col_idx,
                    bottom=bottom,
                    facecolor=facecolor,
                    linewidth=1,
                    edgecolor=edgecolor,
                    alpha=0.8,
                )
                ax_stckd_bar.bar(
                    x + offset,
                    vals,
                    width,
                    label=col_idx,
                    bottom=bottom,
                    facecolor="none",
                    linewidth=0,
                    edgecolor=hatchcol,
                    hatch=hatch,
                    hatch_linewidth=0.5,
                )
                if last_col:
                    ax_stckd_bar.bar_label(
                        rects, labels=n_events_grp.to_list(), fontsize="xx-small"
                    )

                bottom += vals
            multiplier += 1
        ax_stckd_bar.set_ylim(0, 1.1)

        ax_stckd_bar.set_xlabel(xlab)
        # ylab = "$\\hat{R}_{F}({y})$"
        # if use_aep:
        #     ylab = "annual flood\nimpact frequency"
        # ax_stckd_bar.set_ylabel(ylab)
        # ax_stckd_bar.set_ylim(y_range)
        xlab = "$\\hat{R}_{E}({y})$"
        if use_aep:
            xlab = "annual frequency"
        ax_stckd_bar.set_xlabel(xlab)

        ax_stckd_bar.set_xticks(kde_ticks)

        newticks = []
        for lab in kde_tick_labs:
            current_text = lab.get_text()
            newticks.append(current_text.replace("_", "\n"))
        ax_stckd_bar.set_xticklabels(newticks)

        xticks = ax_stckd_bar.get_xticklabels()
        newticks = []
        for lab in xticks:
            current_text = lab.get_text()
            newticks.append(current_text.replace("_", "\n"))
        ax_stckd_bar.set_xticklabels(newticks)

        lab_str1 = "fraction of driver and impact events\nfor targeted "
        lab_str2 = "return period"
        if use_aep:
            lab_str2 = "annual frequency"
        ax_stckd_bar.set_ylabel(lab_str1 + lab_str2, fontsize="small")

        # Lower zorder of boxplot elements (artists and lines)
        for artist in ax_stckd_bar.artists + ax_stckd_bar.lines:
            artist.set_zorder(2)

        # Force gridlines to be redrawn on top
        ax_stckd_bar.set_axisbelow(True)  # This puts grid *on top* of plot elements
        ax_stckd_bar.grid(
            True, which="major", linestyle="--", linewidth=0.5, axis="y", zorder=1
        )

        # annotate the plot (title, legends, etc.)
        if plt_title is not None:
            # fig_stckd_bar.suptitle(f"{plt_title}", x = .5, y = .94)
            ax_stckd_bar.set_title(plt_title)

        legend_yadj = 0
        # add a miniature scatterplot as a legend for the stacked bar

        # Create correlated data
        np.random.seed(0)
        x = np.random.normal(0, 1, 200)
        y = 1.2 * x + np.random.normal(0, 1, 200)

        # Compute mean and standard error
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        x_se = np.std(x) / np.sqrt(len(x)) * 9  # Make it wider (scaled by factor of 2)

        # Create figure and axis
        inset_ax_fb = fig_stckd_bar.add_axes([0.96, 0.53 + legend_yadj, 0.2, 0.25])

        # Scatter plot
        inset_ax_fb.scatter(
            x,
            y,
            alpha=0.7,
            edgecolor="k",
            s=10,
            label="Data",
            facecolor="none",
            linewidth=0.5,
        )

        # Fill vertical band for standard error of y (centered on zero)
        inset_ax_fb.fill_between(
            x=np.linspace(min(x), max(x), 100),
            y1=-x_se,  # Start the band at -y_se (centered on 0)
            y2=x_se,  # End the band at +y_se (centered on 0)
            facecolor="none",  # No fill color
            edgecolor="black",  # Black outline
            label="SE in Y",
        )

        inset_ax_fb.fill_betweenx(
            y=np.linspace(min(x), max(x), 100),
            x1=-x_se,  # Start the band at -y_se (centered on 0)
            x2=x_se,  # End the band at +y_se (centered on 0)
            facecolor="none",  # No fill color
            edgecolor="black",  # Black outline
            label="SE in Y",
        )
        inset_ax_fb.set_title(
            "visual legend for\none targeted frequency\nand hazard level", fontsize=9
        )
        inset_ax_fb.set_xlabel("driver frequency", fontsize=8)
        inset_ax_fb.set_ylabel("impact frequency", fontsize=8)
        # inset_ax_fb.legend()
        inset_ax_fb.set_xticks([])
        inset_ax_fb.set_yticks([])
        inset_ax_fb.set_xlim((x.min(), x.max()))
        inset_ax_fb.set_ylim((x.min(), x.max()))
        # use fillbetween to add appropriate hatching
        for key in dic_hatch_mapping.keys():
            # if plt_var == "return_period_yrs": # color
            edgecolor = dic_cmapping[key]
            # else:
            #     edgecolor = 'k'
            label = key
            d_regions = dict()
            if key == "correct":
                d_regions["correct"] = dict(
                    x=np.linspace(-x_se, x_se, 100), y1=-x_se, y2=x_se
                )

            elif key == "omitted":
                d_regions["omitted1"] = dict(
                    x=np.linspace(-9999, -x_se, 100), y1=-x_se, y2=x_se
                )
                d_regions["omitted2"] = dict(
                    x=np.linspace(x_se, 9999, 100), y1=-x_se, y2=x_se
                )
            elif key == "misspecified":
                d_regions["misspecified1"] = dict(
                    x=np.linspace(-x_se, x_se, 100), y1=-9999, y2=-x_se
                )
                d_regions["misspecified2"] = dict(
                    x=np.linspace(-x_se, x_se, 100), y1=x_se, y2=9999
                )
                # continue
            else:
                sys.exit("key not recognized")
            for region_key in d_regions.keys():
                x = d_regions[region_key]["x"]
                y1 = d_regions[region_key]["y1"]
                y2 = d_regions[region_key]["y2"]
                inset_ax_fb.fill_between(
                    x=x,
                    y1=y1,  # Start the band at -y_se (centered on 0)
                    y2=y2,  # End the band at +y_se (centered on 0)
                    facecolor="white",  # No fill color
                    edgecolor=edgecolor,  # Black outline
                    alpha=0.8,
                    zorder=5,
                )

                # hatching
                inset_ax_fb.fill_between(
                    x=x,
                    y1=y1,  # Start the band at -y_se (centered on 0)
                    y2=y2,  # End the band at +y_se (centered on 0)
                    hatch=dic_hatch_mapping[key],
                    hatch_linewidth=0.5,
                    facecolor="none",  # No fill color
                    edgecolor=edgecolor,  # Black outline
                    label=label,
                    zorder=6,
                )

            # patch = mpatches.Patch(label = label, edgecolor = edgecolor, , , hatch_linewidth = 0.5)

        legend_elements = []
        for key in dic_hatch_mapping.keys():
            # if plt_var == "return_period_yrs": # color
            edgecolor = dic_cmapping[key]
            # else:
            #     edgecolor = 'k'
            label = key
            if key == "correct":
                label = "$\\hat{R}_{E} \\approx \\hat{R}_{F}$"
                lgnd_x_adjst = 0
                if use_aep:
                    label = "aligned"
                    lgnd_x_adjst = 0.0
            patch = mpatches.Patch(
                label=label,
                edgecolor=edgecolor,
                facecolor="white",
                hatch=dic_hatch_mapping[key][0:6],
                hatch_linewidth=0.01,
            )
            legend_elements.append(patch)
        legend_elements.reverse()
        fig_stckd_bar.legend(
            handles=legend_elements,
            loc="upper center",
            fontsize=8,
            title="MDS-based\nclassification",
            title_fontsize=9,
            bbox_to_anchor=(1.06 + lgnd_x_adjst, 0.48 + legend_yadj),
            ncols=1,
            frameon=False,
        )

        legend_elements = []
        for key in dic_pallet.keys():
            if dic_legend_name_mapping is None:
                label = key
            else:
                label = dic_legend_name_mapping[key]
            if "_" in label:
                label = label.replace("_", "\n")
            patch = mpatches.Patch(
                label=f"{label} depths", facecolor=dic_pallet[key], edgecolor="k"
            )
            legend_elements.append(patch)

        fig_stckd_bar.legend(
            handles=legend_elements,
            loc="upper center",
            fontsize=8,
            title_fontsize=9,
            bbox_to_anchor=(1.05, 0.255 + legend_yadj),
            ncols=1,
            title="hazard level",
            frameon=False,
        )

        if working:
            sys.exit("work")
        # sys.exit('work')
        # fig.tight_layout()
        plt.savefig(fname_savefig_stckdbar, bbox_inches="tight")
        plt.clf()

print(f"Saved plots in {dir_kde_plots}")
print(f"Saved plots in {dir_stacked_bar_plots}")
# %% create dual plots with KDE and the stacked bar in 1
subarea_name = "watershed"
use_aep = True
# impact_var = "n_building_id_impacted"
plot_interval_for_weatherbased_impact_quantiles = False
y_range = (0.2, 500)
if use_aep:
    y_range = 1 / np.asarray(y_range)
bar_width = 0.6
whisker_alpha = 0.05
dpi = 200
x_var = "return_period_yrs"
grp_var = "depth_range_m"
xlab = ""
dic_pallet = DIC_DPTH_COLOR_LOOKUP
dic_legend_name_mapping = DIC_DPTH_DSC_LOOKUP
dir_plots = (
    f"{DIR_FLOOD_PROB_VS_EVENT_PROB}plots/mcds_vs_ss_combined_kde_and_stacked_bars/"
)
Path(dir_plots).mkdir(parents=True, exist_ok=True)
val = input(f"type 'delete' to remove all existing plots first")
delete_plots = False
if val.lower() == "delete":
    delete_plots = True
if delete_plots:
    delete_directory(dir_plots, attempt_time_limit_s=10)
    Path(dir_plots).mkdir(parents=True, exist_ok=True)

# determine formulatoins to check out
df_weather_vs_impact_retrn_pd_classification_AND = (
    df_weather_vs_impact_retrn_pd_classification.loc[
        pd.IndexSlice[:, "empirical_multivar_rtrn_yrs_AND", :, :, :, :]
    ]
)
idx_best_multivar = (
    df_weather_vs_impact_retrn_pd_classification_AND.groupby(
        ["impact_var", "subarea_name", "depth_range_m", "return_period_yrs"]
    )["correct"]
    .idxmax()
    .values
)
df_classification_multivar_best_aoi = (
    df_weather_vs_impact_retrn_pd_classification_AND.loc[idx_best_multivar].loc[
        pd.IndexSlice["n_building_id_impacted", :, subarea_name, :, :]
    ]
)
df_classification_multivar_best_aoi = df_classification_multivar_best_aoi[
    df_classification_multivar_best_aoi["n_impact_events_nonzero_flooding"] > 0
]

lst_formulations = [
    "best",
    "empirical_univar_return_pd_yrs",
    "empirical_univar_return_pd_yrs",
    "empirical_univar_return_pd_yrs",
    "empirical_multivar_rtrn_yrs_AND",
    "empirical_multivar_rtrn_yrs_AND",
    "empirical_multivar_rtrn_yrs_AND",
    "empirical_multivar_rtrn_yrs_OR",
    "empirical_multivar_rtrn_yrs_OR",
    "empirical_multivar_rtrn_yrs_OR",
]
lst_stat_to_choose = [
    "best",
    "max_0hr_15min_mm",
    "max_4hr_0min_mm",
    "max_24hr_0min_mm",
    "15min,24hr,w",
    "30min,w",
    "15min,w",
    "15min,24hr,w",
    "30min,w",
    "15min,w",
]

# print("ONLY PRINTING ONE OF THE EVENT FORMULATOINS")
# lst_formulations = ["empirical_univar_return_pd_yrs"]
# lst_stat_to_choose = ["max_0hr_15min_mm"]


df_formulations_to_plot = pd.DataFrame(
    dict(formulation=lst_formulations, event_stat=lst_stat_to_choose)
)

# input datasets
df_weather_vs_impact_retrn_pd_classification
ds_flood_impacts_by_aoi
df_weather_events_in_ci_og
df_flood_events_in_ci_og

lst_lst_impact_vars = [
    ["n_building_id_impacted"],
    ["flooded_area_sqm"],
    ["n_road_segment_id_impacted"],
]
for lst_impact_vars in lst_lst_impact_vars:

    impact_var = return_impact_varname_from_list(lst_impact_vars)
    # n_building_id_impacted.n_road_segment_id_impacted  'n_road_segment_id_impacted.n_road_segment_id_impacted'
    for idx, row_stat in df_formulations_to_plot.iterrows():
        formulation = row_stat["formulation"]
        event_stat = row_stat["event_stat"]
        if formulation == "best":
            fname_savefig = (
                f"{dir_plots}{subarea_name}_{impact_var}.event_formulation_best.png"
            )
            plt_title = f"{subarea_name} {impact_var} for the weather\nevent formulation yielding the most true positives"
            idx_best = (
                df_weather_vs_impact_retrn_pd_classification.groupby(
                    ["impact_var", "subarea_name", "depth_range_m", "return_period_yrs"]
                )["correct"]
                .idxmax()
                .values
            )
            df_classification_best_aoi = (
                df_weather_vs_impact_retrn_pd_classification.loc[idx_best].loc[
                    pd.IndexSlice[impact_var, :, :, subarea_name, :, :, :]
                ]
            )
            filter_weather_events_with_best_stats = (
                df_weather_events_in_ci_og.reset_index()["event_stats"].isin(
                    df_classification_best_aoi.reset_index()["event_stats"].unique()
                )
            )
            df_weather_events_in_ci_subset = df_weather_events_in_ci_og[
                filter_weather_events_with_best_stats.values
            ]
        else:
            fname_savefig = f"{dir_plots}{subarea_name}_{impact_var}.event_formulation_{formulation}_of_{event_stat}.png"
            plt_title = (
                f"{subarea_name} {impact_var} based on\n{formulation} of {event_stat}"
            )
            df_classification_best_aoi = (
                df_weather_vs_impact_retrn_pd_classification.loc[
                    pd.IndexSlice[
                        impact_var, formulation, event_stat, subarea_name, :, :
                    ]
                ]
            )
            df_weather_events_in_ci_subset = df_weather_events_in_ci_og.loc[
                pd.IndexSlice[formulation, event_stat]
            ]
        # only extract rows where the number of impact events is greater than zero
        # df_classification_best_aoi = df_classification_best_aoi[df_classification_best_aoi["n_impact_events"]>0]

        # compound_impact = False
        # if len(impact_var)

        # prepare data for plotting
        df_flood_impacts_by_aoi = ds_flood_impacts_by_aoi.sel(
            subarea_name="watershed"
        ).to_dataframe()
        # subset flood impacts
        if "flooded_area" in impact_var:
            # continue
            df_flood_impacts_by_aoi_subset = df_flood_impacts_by_aoi.filter(
                like="flooded_area"
            )
        else:
            cols = []
            for subvar in impact_var.split("."):
                cols += list(df_flood_impacts_by_aoi.filter(like=subvar).columns)
            df_flood_impacts_by_aoi_subset = df_flood_impacts_by_aoi.loc[:, cols]

        colname_impact_return_period = (
            df_flood_impacts_by_aoi_subset.filter(like="return_pd").iloc[:, 0].name
        )

        if use_aep:
            # impacts
            df_flood_impacts_by_aoi_subset = df_flood_impacts_by_aoi_subset.copy()
            df_flood_impacts_by_aoi_subset[colname_impact_return_period] = (
                1 / df_flood_impacts_by_aoi_subset[colname_impact_return_period]
            )
            # weather
            idx_names = df_weather_events_in_ci_subset.index.names
            df_weather_events_in_ci_subset = (
                df_weather_events_in_ci_subset.reset_index()
            )
            df_weather_events_in_ci_subset["return_period_yrs"] = (
                1 / df_weather_events_in_ci_subset["return_period_yrs"]
            )
            df_weather_events_in_ci_subset = df_weather_events_in_ci_subset.set_index(
                idx_names
            )

        s_impact_return_periods = df_flood_impacts_by_aoi_subset[
            colname_impact_return_period
        ]
        colname_impact_return_period = s_impact_return_periods.name

        y_var = colname_impact_return_period

        # return the impact return period of all weather events of each return period
        ##

        # df_event_return_pds = df_weather_events_in_ci_subset.loc[pd.IndexSlice[formulation,event_stat]].reset_index().set_index('event_number')
        df_weather_events_w_impact_stats = (
            df_weather_events_in_ci_subset.reset_index()
            .set_index("event_number")
            .join(
                df_flood_impacts_by_aoi_subset.reset_index().set_index("event_number"),
                on="event_number",
                how="left",
            )
            .reset_index()
        )  # these are the results of all x-year weather events

        # these two dataframes contain all the plotting information
        figsize = (6, 6)
        main_fig = plt.figure(figsize=figsize, dpi=dpi)
        gs_rows = 100
        gs_grid_with = 1
        gs = gridspec.GridSpec(
            gs_rows, gs_grid_with, figure=main_fig, height_ratios=None
        )

        frac_for_stckd_bar = 0.4
        grd_bndry = int(np.ceil(gs_rows * frac_for_stckd_bar))
        ax_bw = main_fig.add_subplot(gs[grd_bndry:, :])
        ax_stckd_bar = main_fig.add_subplot(gs[0 : grd_bndry - 1, :])

        # add boxplot
        # sns.boxplot(x=x_var, y=y_var, hue=grp_var, data=df_weather_events_w_impact_stats, log_scale = True,
        #             width=bar_width, ax=ax_bw, whis = (whisker_alpha/2, 1-whisker_alpha/2), palette=dic_pallet,
        #             legend = False)
        # try violin plot instead
        width_dist_plot = 1
        # kde_bw = 0.8
        kde_method = "scott"
        kde_gap = 0
        col_mcfra_ci = "red"
        df_weather_events_w_impact_stats[x_var]
        parts = sns.violinplot(
            data=df_weather_events_w_impact_stats,
            x=x_var,
            y=y_var,
            hue=grp_var,
            split=True,
            inner=None,
            log_scale=True,
            ax=ax_bw,
            palette=dic_pallet,
            legend=False,
            alpha=0.8,
            width=width_dist_plot,
            dodge=True,
            common_norm=True,
            orient="x",
            cut=0,
            bw_method=kde_method,
            gap=kde_gap,
            linecolor="k",
            linewidth=0.8,
            order=df_weather_events_w_impact_stats[x_var].unique(),
        )

        n_groups = len(df_weather_events_w_impact_stats[grp_var].unique())

        # Extract the max width of the violin from the PathCollection

        # plt.violinplot(dataset = df_weather_events_w_impact_stats, positions = )
        #    hue_order=['[0.03,0.1)', '[0.1,inf)'])
        # ['[0.1,inf)', '[0.03,0.1)']
        # ['[0.03,0.1)', '[0.1,inf)']
        # sns.boxplot(data=df_weather_events_w_impact_stats, x=x_var, y=y_var, hue=grp_var,
        #              showfliers=False, showbox=False, whis=[(fld_rtrn_pd_alpha)/2,(1-fld_rtrn_pd_alpha)/2],
        #              ax=ax_bw, width=bar_width, legend = False)

        # Lower zorder of boxplot elements (artists and lines)
        for artist in ax_bw.artists + ax_bw.lines:
            artist.set_zorder(2)

        # Force gridlines to be redrawn on top
        ax_bw.set_yscale("log")
        ax_bw.set_axisbelow(False)  # This puts grid *on top* of plot elements
        ax_bw.grid(
            True, which="major", linestyle="--", linewidth=0.5, axis="y", zorder=10
        )
        ax_bw.grid(
            True, which="major", linestyle="--", linewidth=0.5, axis="x", zorder=10
        )
        yticks = LST_RTRNS
        if use_aep:
            yticks = 1 / np.asarray(LST_RTRNS)
        label_yticks_target_return_pd(ax_bw, yticks, blank=False)

        # plot confidence interval of flood return period
        # parameters for figuring out the location of each bar
        xtick_labs = ax_bw.get_xticklabels()

        length_of_bar_group = bar_width
        width_of_shaded_region = bar_width / n_groups / 8
        # loop through each x variable and plot flood impact return periods
        lst_xs = []
        for lab in xtick_labs:
            x_idx = lab.get_text()
            try:
                x_idx = float(x_idx)
            except:
                pass
            x_position = lab.get_position()[0]
            lst_xs.append(x_position)
            # define spacing for the bars
            if n_groups != 2:
                sys.exit("the code currently only accomodates 2 hazard levels")
            if n_groups % 2 == 0:  # even number of groups
                even_grp = True
                futhest_left = (x_position + bar_width / 2) - (
                    bar_width * (n_groups / 2)
                )
                futhest_right = futhest_left + bar_width * (n_groups - 1)
            else:
                even_grp = False
                futhest_left = x_position - length_of_bar_group / n_groups
                futhest_right = x_position + length_of_bar_group / n_groups
            # bring them closer to eachother
            squeeze_factor = (
                0.75  # value from 0 to 1; the larger the number, the closer they are
            )
            distance_to_center = (futhest_right - futhest_left) / 2
            futhest_right = (
                futhest_right - distance_to_center * squeeze_factor + kde_gap / 3
            )
            futhest_left = (
                futhest_left + distance_to_center * squeeze_factor - kde_gap / 3
            )
            # define the center of each confidence interval
            x_locs = np.linspace(start=futhest_left, stop=futhest_right, num=n_groups)
            idx = -1

            # loop through each depth range and create a fillbetween plot representing the flood impact return period
            for depth_range_m in np.sort(
                df_weather_events_w_impact_stats["depth_range_m"].unique()
            ):
                # for grp_idx, df_plt_in_ci_grp in df_weather_events_w_impact_stats.groupby(grp_var):
                df_plt_in_ci_grp = df_weather_events_w_impact_stats[
                    df_weather_events_w_impact_stats["depth_range_m"] == depth_range_m
                ]
                idx += 1
                # depth_range_m = grp_idx
                (
                    lb_flood_rtrn,
                    lb_flood_rtrn_rlspc,
                    ub_flood_rtrn,
                    ub_flood_rtrn_rlspc,
                ) = return_flood_impact_ci_bounds(
                    df_return_pd_cis_flood_impacts_og,
                    df_flood_impacts_by_aoi_subset,
                    depth_range_m,
                    subarea_name,
                    impact_var,
                    return_period_yrs=x_idx,
                    use_aep=use_aep,
                )
                # if there is nonzero flooding for one of the bounds, create a fillbetween plot
                if (lb_flood_rtrn_rlspc == 0) and (ub_flood_rtrn_rlspc == 0):
                    continue
                # if x_idx == 100:
                #     sys.exit('work')
                center_x = x_locs[idx]
                # ax_bw.fill_between(x=(center_x-width_of_shaded_region, center_x+width_of_shaded_region), y1 = ub_flood_rtrn,
                #                     y2 = lb_flood_rtrn, edgecolor = "orange", facecolor = "none", alpha = 0.7, zorder = 100,
                #                 linewidth = 2)

                for bound in [lb_flood_rtrn, ub_flood_rtrn]:
                    ax_bw.plot(
                        [
                            center_x - width_of_shaded_region,
                            center_x + width_of_shaded_region,
                        ],
                        [bound, bound],
                        color="orange",
                        linewidth=1.5,
                    )
                ax_bw.plot(
                    [center_x, center_x],
                    [lb_flood_rtrn, ub_flood_rtrn],
                    color="orange",
                    linewidth=1.5,
                )

                # also add lines representing the 90% confidence interval of the MC-FRA approach
                s_weatherbased_impact_return_pds = df_plt_in_ci_grp[
                    df_plt_in_ci_grp[x_var] == x_idx
                ].loc[:, y_var]
                s_weatherbased_impact_quants = (
                    s_weatherbased_impact_return_pds.quantile(
                        [FLD_RTRN_PD_ALPHA / 2, (1 - FLD_RTRN_PD_ALPHA / 2)],
                        interpolation="nearest",
                    )
                )
                # if (x_idx == 1) and (depth_range_m == "[0.03,0.1)"):
                #     sys.exit('work')
                # ax_bw.fill_between(x=(center_x-width_of_shaded_region, center_x+width_of_shaded_region), y1 = s_weatherbased_impact_quants.max(),
                #                     y2 = s_weatherbased_impact_quants.min(), edgecolor = "black", facecolor = "none", alpha = 0.7, zorder = 100,
                #                 linewidth = 2)
                # from matplotlib.lines import Line2D
                # Line2D()
                if plot_interval_for_weatherbased_impact_quantiles:
                    from scipy import stats

                    kde_estimator = stats.gaussian_kde(
                        np.log(s_weatherbased_impact_return_pds), bw_method=kde_method
                    )
                    # kde_estimator = stats.gaussian_kde(s_weatherbased_impact_return_pds, bw_method = kde_bw)
                    for weather_bound in s_weatherbased_impact_quants.values:
                        kds_estimate = kde_estimator(np.log(weather_bound))[0] / 2
                        # kds_estimate = kde_estimator(weather_bound)[0]

                        x_origin = x_position
                        # find the kde density estimate which will correspond to the length along the x axis (seaborn uses a Gaussian kernel)
                        overrun_adjustment = 0.02
                        if depth_range_m == "[0.1,inf)":
                            x_left = x_origin + kde_gap / 3
                            x_right = x_origin + kds_estimate - overrun_adjustment
                        elif depth_range_m == "[0.03,0.1)":
                            x_right = x_origin - kde_gap / 3
                            x_left = x_origin - kds_estimate + overrun_adjustment
                        else:
                            sys.exit("unrecognized depth range")
                        y_position = weather_bound
                        ax_bw.plot(
                            [x_left, x_right],
                            [y_position, y_position],
                            color=col_mcfra_ci,
                            linewidth=1.5,
                        )
                        # ax_bw.plot([center_x, center_x], [lb_flood_rtrn, ub_flood_rtrn], color = "red", linewidth = 1.5)
                        # figure out how to plot kde estimates

        ## top plot
        df_classification_best_aoi
        width = width_of_each_box = bar_width / n_groups
        multiplier = 0

        # define the center of each bar group
        ax_stckd_bar.set_xlim(ax_bw.get_xlim())
        x = np.asarray(lst_xs)
        # for xval in x:
        #     ax_stckd_bar.axvline(xval, color = "red")
        # determine location of furthest left plot of each group
        if even_grp:  # shift so that each x occurs in between the two middle bars
            futhest_left = (
                x - width / 2
            )  # width_dist_plot/2) - (width_dist_plot * (n_groups/2))
        else:
            futhest_left = x - length_of_bar_group / n_groups
        x = x + futhest_left[0]

        n_hatch_mltp = 8
        if (df_classification_best_aoi["mixed1_correct"].sum() > 0) or (
            df_classification_best_aoi["mixed_omitted_or_misspecified"].sum() > 0
        ):  # meaning the impact variable is a combination of multiple impacts and in some cases, there are events that yield the targeted return period impact for one and not the other
            # dic_cmapping = {"correct":"k", "mixed":"#fce674", "misspecified":"#fce674"}
            # dic_cmapping = {"correct":"k","omitted":"k", "mixed":"k", "misspecified":"k"}
            # dic_hatch_mapping = {"correct":"."*n_hatch_mltp, "mixed":"|"*6, "misspecified":"x"*n_hatch_mltp, "omitted":"/"*n_hatch_mltp}
            sys.exit(
                "need to figure out visualizations for the multi-impact variable case"
            )
        else:
            # dic_cmapping = {"correct":"k","misspecified":"#fce674"}
            dic_cmapping = {"correct": "k", "omitted": "k", "misspecified": "k"}
            dic_hatch_mapping = {
                "correct": "." * n_hatch_mltp,
                "omitted": "/" * n_hatch_mltp,
                "misspecified": "x" * n_hatch_mltp,
            }

        cols = dic_hatch_mapping.keys()

        for grp_idx, df_group in df_classification_best_aoi.loc[:, cols].groupby(
            level=grp_var
        ):
            offset = width * multiplier
            bottom = np.zeros(x.shape)
            n_events_grp = df_classification_best_aoi[
                (
                    df_classification_best_aoi.reset_index()["depth_range_m"] == grp_idx
                ).values
            ].loc[:, "n_events"]
            for col_idx, col in df_group.items():
                vals = col.astype(float).values
                last_col = False
                if col_idx == df_group.columns[-1]:
                    last_col = True
                    # sys.exit("work")
                edgecolor = "k"
                facecolor = dic_pallet[grp_idx]
                hatch = dic_hatch_mapping[col_idx]

                hatchcol = dic_cmapping[col_idx]
                rects = ax_stckd_bar.bar(
                    x + offset,
                    vals,
                    width,
                    label=col_idx,
                    bottom=bottom,
                    facecolor=facecolor,
                    linewidth=1,
                    edgecolor=edgecolor,
                    alpha=0.8,
                )
                ax_stckd_bar.bar(
                    x + offset,
                    vals,
                    width,
                    label=col_idx,
                    bottom=bottom,
                    facecolor="none",
                    linewidth=0,
                    edgecolor=hatchcol,
                    hatch=hatch,
                    hatch_linewidth=0.5,
                )
                if last_col:
                    ax_stckd_bar.bar_label(
                        rects, labels=n_events_grp.to_list(), fontsize="xx-small"
                    )

                bottom += vals
            multiplier += 1
        ax_stckd_bar.set_ylim(0, 1.1)
        ax_stckd_bar.set_xticks([])
        ax_stckd_bar.set_xticklabels([])
        ax_stckd_bar.set_xlabel("")
        lab_str1 = "fraction of flood driver and flood events\nfor targeted "
        lab_str2 = "return period"
        if use_aep:
            lab_str2 = "annual frequency"
        ax_stckd_bar.set_ylabel(lab_str1 + lab_str2, fontsize="small")

        # Lower zorder of boxplot elements (artists and lines)
        for artist in ax_stckd_bar.artists + ax_stckd_bar.lines:
            artist.set_zorder(2)

        # Force gridlines to be redrawn on top
        ax_stckd_bar.set_axisbelow(True)  # This puts grid *on top* of plot elements
        ax_stckd_bar.grid(
            True, which="major", linestyle="--", linewidth=0.5, axis="y", zorder=1
        )

        # annotate the plot (title, legends, etc.)
        if plt_title is not None:
            main_fig.suptitle(f"{plt_title}", x=0.5, y=0.94)
        ax_bw.set_xlabel(xlab)
        ylab = "$\\hat{R}_{F}({y})$"
        if use_aep:
            ylab = "annual flood\nimpact frequency"
        ax_bw.set_ylabel(ylab)
        ax_bw.set_ylim(y_range)
        xlab = "$\\hat{R}_{E}({y})$"
        if use_aep:
            xlab = "annual flood driver frequency"
        ax_bw.set_xlabel(xlab)
        # create custom legend
        legend_elements = []
        # add the shaded region
        # patch = mpatches.Patch(label = "$\\hat{R}_{F}({y})$ 90% CI",  edgecolor = "orange", facecolor = "grey", alpha = 0.7)
        # legend_elements.append(patch)
        import matplotlib.lines as mlines

        line_impact_ci = mlines.Line2D(
            [], [], label="SS-FRA 90% CI", color="orange", linewidth=1.5
        )
        if plot_interval_for_weatherbased_impact_quantiles:
            line_weather_ci = mlines.Line2D(
                [], [], label="MC-FRA 90% CI", color=col_mcfra_ci, linewidth=1.5
            )
            legend_elements.append(line_weather_ci)
        legend_elements.append(line_impact_ci)

        for key in dic_pallet.keys():
            if dic_legend_name_mapping is None:
                label = key
            else:
                label = dic_legend_name_mapping[key]
            if "_" in label:
                label = label.replace("_", "\n")
            patch = mpatches.Patch(label=label, color=dic_pallet[key])
            legend_elements.append(patch)
        main_fig.legend(
            handles=legend_elements,
            loc="upper center",
            fontsize=8,
            title="",
            title_fontsize=8,
            bbox_to_anchor=(1.01, 0.46),
            ncols=1,
        )

        # add a miniature KDE plot as a legend
        # Simulated example DataFrame
        np.random.seed(42)
        df_weather_events_dummy = pd.DataFrame(
            {
                x_var: np.repeat(["A", "B"], 200),
                y_var: np.concatenate(
                    [
                        np.random.lognormal(mean=1, sigma=0.5, size=200),
                        np.random.lognormal(mean=1.2, sigma=0.4, size=200),
                    ]
                ),
                grp_var: np.tile(["[0.03,0.1)", "[0.1,inf)"], 200),
            }
        )

        inset_ax = main_fig.add_axes([0.92, 0.11, 0.18, 0.18])
        # Violin plot parameters
        # x_var = 'x_var'
        # y_var = 'y_var'
        # grp_var = 'grp_var'
        # dic_pallet = {'G1': 'skyblue', 'G2': 'orange'}
        width_dist_plot = 0.9
        kde_method = "scott"
        kde_gap = 0  # You might be using this to adjust spacing
        alpha = 0.8
        # Violin plot in inset
        sns.violinplot(
            data=df_weather_events_dummy,
            x=x_var,
            y=y_var,
            hue=grp_var,
            split=True,
            inner=None,
            log_scale=True,
            ax=inset_ax,
            palette=dic_pallet,
            legend=False,
            alpha=alpha,
            width=width_dist_plot,
            dodge=True,
            common_norm=True,
            orient="x",
            cut=0,
            bw_method=kde_method,
            linewidth=0.8,
        )
        # Clean up the inset to look more like a legend
        inset_ax.set_title("MDS-FRA\nimpact frequency KDE", fontsize=8)
        inset_ax.set_xticks([])
        inset_ax.set_yticks([])
        inset_ax.set_xlabel("")
        inset_ax.set_ylabel("")
        inset_ax.set_facecolor("white")

        # add a miniature scatterplot as a legend for the stacked bar

        # Create correlated data
        np.random.seed(0)
        x = np.random.normal(0, 1, 200)
        y = 1.2 * x + np.random.normal(0, 1, 200)

        # Compute mean and standard error
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        x_se = np.std(x) / np.sqrt(len(x)) * 9  # Make it wider (scaled by factor of 2)

        # Create figure and axis
        inset_ax_fb = main_fig.add_axes([0.94, 0.73, 0.18, 0.18])

        # Scatter plot
        inset_ax_fb.scatter(x, y, alpha=0.7, edgecolor="k", s=10, label="Data")

        # Fill vertical band for standard error of y (centered on zero)
        inset_ax_fb.fill_between(
            x=np.linspace(min(x), max(x), 100),
            y1=-x_se,  # Start the band at -y_se (centered on 0)
            y2=x_se,  # End the band at +y_se (centered on 0)
            facecolor="none",  # No fill color
            edgecolor="black",  # Black outline
            label="SE in Y",
        )

        inset_ax_fb.fill_betweenx(
            y=np.linspace(min(x), max(x), 100),
            x1=-x_se,  # Start the band at -y_se (centered on 0)
            x2=x_se,  # End the band at +y_se (centered on 0)
            facecolor="none",  # No fill color
            edgecolor="black",  # Black outline
            label="SE in Y",
        )
        inset_ax_fb.set_title("classification legend", fontsize=8)
        inset_ax_fb.set_xlabel("driver frequency", fontsize=8)
        inset_ax_fb.set_ylabel("impact frequency", fontsize=8)
        # inset_ax_fb.legend()
        inset_ax_fb.set_xticks([])
        inset_ax_fb.set_yticks([])
        inset_ax_fb.set_xlim((x.min(), x.max()))
        inset_ax_fb.set_ylim((x.min(), x.max()))
        # use fillbetween to add appropriate hatching
        for key in dic_hatch_mapping.keys():
            # if plt_var == "return_period_yrs": # color
            edgecolor = dic_cmapping[key]
            # else:
            #     edgecolor = 'k'
            label = key
            d_regions = dict()
            if key == "correct":
                d_regions["correct"] = dict(
                    x=np.linspace(-x_se, x_se, 100), y1=-x_se, y2=x_se
                )

            elif key == "omitted":
                d_regions["omitted1"] = dict(
                    x=np.linspace(-9999, -x_se, 100), y1=-x_se, y2=x_se
                )
                d_regions["omitted2"] = dict(
                    x=np.linspace(x_se, 9999, 100), y1=-x_se, y2=x_se
                )
            elif key == "misspecified":
                d_regions["misspecified1"] = dict(
                    x=np.linspace(-x_se, x_se, 100), y1=-9999, y2=-x_se
                )
                d_regions["misspecified2"] = dict(
                    x=np.linspace(-x_se, x_se, 100), y1=x_se, y2=9999
                )
                # continue
            else:
                sys.exit("key not recognized")
            for region_key in d_regions.keys():
                x = d_regions[region_key]["x"]
                y1 = d_regions[region_key]["y1"]
                y2 = d_regions[region_key]["y2"]
                inset_ax_fb.fill_between(
                    x=x,
                    y1=y1,  # Start the band at -y_se (centered on 0)
                    y2=y2,  # End the band at +y_se (centered on 0)
                    facecolor="white",  # No fill color
                    edgecolor=edgecolor,  # Black outline
                    alpha=0.8,
                    zorder=5,
                )

                # hatching
                inset_ax_fb.fill_between(
                    x=x,
                    y1=y1,  # Start the band at -y_se (centered on 0)
                    y2=y2,  # End the band at +y_se (centered on 0)
                    hatch=dic_hatch_mapping[key],
                    hatch_linewidth=0.5,
                    facecolor="none",  # No fill color
                    edgecolor=edgecolor,  # Black outline
                    label=label,
                    zorder=6,
                )

            # patch = mpatches.Patch(label = label, edgecolor = edgecolor, , , hatch_linewidth = 0.5)

        # working_on_legend = False
        # print('WARNING; NOT INCLUDING LEGEND WHILE WORKING ON THE NEW ONE')
        # END making legend
        # if not working_on_legend:
        legend_elements = []
        for key in dic_hatch_mapping.keys():
            # if plt_var == "return_period_yrs": # color
            edgecolor = dic_cmapping[key]
            # else:
            #     edgecolor = 'k'
            label = key
            if key == "correct":
                label = "$\\hat{R}_{E} \\approx \\hat{R}_{F}$"
                lgnd_x_adjst = 0
                if use_aep:
                    label = "driver\nequals\nimpact AEP"
                    lgnd_x_adjst = 0.0
            patch = mpatches.Patch(
                label=label,
                edgecolor=edgecolor,
                facecolor="white",
                hatch=dic_hatch_mapping[key],
                hatch_linewidth=0.5,
            )
            legend_elements.append(patch)
        legend_elements.reverse()
        main_fig.legend(
            handles=legend_elements,
            loc="upper center",
            fontsize=8,
            title="",
            title_fontsize=8,
            bbox_to_anchor=(1.025 + lgnd_x_adjst, 0.7),
            ncols=1,
        )

        ax_bw.set_xticks(ax_bw.get_xticks())
        xticks = ax_bw.get_xticklabels()
        newticks = []
        for lab in xticks:
            current_text = lab.get_text()
            newticks.append(current_text.replace("_", "\n"))
        ax_bw.set_xticklabels(newticks)
        # fig.tight_layout()
        plt.savefig(fname_savefig, bbox_inches="tight")
        plt.clf()

print(f"Saved plots in {dir_plots}")

# %%
sys.exit(
    "stuff from here down was for EDA and anything useful has been consolidated in code above this."
)


def create_box_and_whiskers(
    ds_flood_impacts_by_aoi,
    df_weather_events_in_ci_og,
    df_data_for_plotting,
    formulation,
    event_stat,
    impact_var,
    plt_var,
    plt_var_val,
    x_var,
    y_var,
    grp_var,
    bar_width,
    df_flood_events_in_ci_og,
    xlab,
    y_range,
    dic_pallet,
    dic_legend_name_mapping=None,
    plt_title=None,
    whisker_alpha=0.05,
    dpi=200,
    add_subplot_with_classifications=True,
):
    # df_flood_impacts_by_aoi = ds_flood_impacts_by_aoi.to_dataframe()
    # preprocessing
    # if plt_var in df_data_for_plotting.index.names:
    #     df_plt = df_data_for_plotting.loc[pd.IndexSlice[plt_var_val,:]].copy()
    # else:
    df_plt = (
        df_data_for_plotting[df_data_for_plotting[plt_var] == plt_var_val]
        .copy()
        .reset_index()
        .copy()
    )
    # fill na where all flood events in a box and whiskers plot are zero
    for idx, df_group in df_plt.groupby([grp_var, x_var]):
        grp_idx, x_idx = idx
        n_flooded = (df_group[impact_var] > 0).sum()
        if n_flooded == 0:
            # sys.exit("make sure this is doing what I think it's doing")
            idx_to_fill_with_na = df_plt[
                (df_plt[x_var] == x_idx) & (df_plt[grp_var] == grp_idx)
            ].index
            df_plt.loc[idx_to_fill_with_na, y_var] = np.nan
    # create figure
    figsize = (10, 6)
    main_fig = plt.figure(figsize=figsize, dpi=dpi)
    gs_rows = 100
    gs_grid_with = 1
    gs = gridspec.GridSpec(gs_rows, gs_grid_with, figure=main_fig, height_ratios=None)
    if add_subplot_with_classifications:
        frac_for_stckd_bar = 0.4
        grd_bndry = int(np.ceil(gs_rows * frac_for_stckd_bar))
        ax_bw = main_fig.add_subplot(gs[grd_bndry:, :])
        ax_stckd_bar = main_fig.add_subplot(gs[0 : grd_bndry - 1, :])
    else:
        ax_bw = main_fig.add_subplot(gs[:, :])

    # add boxplot
    sns.boxplot(
        x=x_var,
        y=y_var,
        hue=grp_var,
        data=df_plt,
        log_scale=True,
        width=bar_width,
        ax=ax_bw,
        whis=(whisker_alpha / 2, 1 - whisker_alpha / 2),
        palette=dic_pallet,
        legend=False,
    )
    ax_bw.set_yscale("log")

    ax_bw.grid(True, which="major", linestyle="--", linewidth=0.5, axis="y")  # axis='y'
    # ax_bw.grid(True, which='minor', linestyle='--', linewidth=0.5, axis='y')  # axis='y'

    # add red dashed line through targeted return period
    if plt_var == "return_period_yrs":
        ax_bw.axhline(plt_var_val, c="r", ls="--", linewidth=0.6)  # 1:1 line
    # label axes
    label_yticks_target_return_pd(ax_bw, LST_RTRNS, blank=False)
    # plot confidence interval of flood return period
    # parameters for figuring out the location of each bar
    xtick_labs = ax_bw.get_xticklabels()
    n_groups = len(df_plt[grp_var].unique())
    length_of_bar_group = bar_width
    width_of_shaded_region = bar_width / n_groups / 8
    width_of_each_box = bar_width / n_groups
    lst_df_class = []
    for lab in xtick_labs:
        x_idx = lab.get_text()
        try:
            x_idx = float(x_idx)
        except:
            pass
        x_position = lab.get_position()[0]
        # define spacing for the bars
        if n_groups % 2 == 0:  # even number of groups
            even_grp = True
            # center_of_group = x_position
            # center_of_center_left_box = center_of_group - width_of_each_box/2
            futhest_left = (x_position + width_of_each_box / 2) - (
                width_of_each_box * (n_groups / 2)
            )
            # futhest_left = x_position - (length_of_bar_group/n_groups)/2
            futhest_right = futhest_left + width_of_each_box * (n_groups - 1)
        else:
            even_grp = False
            futhest_left = x_position - length_of_bar_group / n_groups
            futhest_right = x_position + length_of_bar_group / n_groups
        # subset relevant confidence intervals
        # df_cis_subset = df_cis[df_cis[x_var] == x_idx]
        x_locs = np.linspace(start=futhest_left, stop=futhest_right, num=n_groups)
        idx = -1
        # loop through each confidence interval to add the bar if there is nonzero flooding; also compute fractions for each classification
        # for grp_idx, df_group in df_cis_subset.groupby(grp_var):
        for grp_idx, df_plt_in_ci_grp in df_plt.groupby(grp_var):
            # sys.exit('made it here')
            idx += 1
            df_flood_events_in_ci_og
            depth_range_m = grp_idx
            subarea_name = x_idx
            lst_impact_vars = [impact_var]
            return_period_yrs = plt_var_val
            df_class = classify_events_for_targeted_return_period(
                df_flood_events_in_ci_og,
                df_weather_events_in_ci_og,
                ds_flood_impacts_by_aoi,
                depth_range_m,
                subarea_name,
                lst_impact_vars,
                return_period_yrs,
                formulation,
                event_stat,
            )
            lb_flood_rtrn, lb_flood_rtrn_rlspc, ub_flood_rtrn, ub_flood_rtrn_rlspc = (
                return_flood_impact_ci_bounds(
                    df_return_pd_cis_flood_impacts_og,
                    df_flood_impacts_by_aoi_subset,
                    depth_range_m,
                    subarea_name,
                    impact_var,
                    return_period_yrs,
                )
            )

            # add indexers and append to list
            lst_df_class.append(df_class)
            # sys.exit("appending")
            # now if there is nonzero flooding for one of the bounds, create a fillbetween plot
            if (lb_flood_rtrn_rlspc == 0) and (ub_flood_rtrn_rlspc == 0):
                continue
            center_x = x_locs[idx]
            ax_bw.fill_between(
                x=(
                    center_x - width_of_shaded_region,
                    center_x + width_of_shaded_region,
                ),
                y1=ub_flood_rtrn,
                y2=lb_flood_rtrn,
                edgecolor="orange",
                facecolor="grey",
                alpha=0.7,
                zorder=100,
                linewidth=2,
            )
    # create top plot with classification fractions
    df_classes_and_n_events = (
        pd.concat(lst_df_class).reset_index(drop=True).set_index([x_var, grp_var])
    )
    s_n_events = df_classes_and_n_events.loc[:, "n_events"].fillna(0).astype(int)
    df_classes = df_classes_and_n_events.loc[:, df_class.columns[0:4]]
    if add_subplot_with_classifications:
        width = width_of_each_box
        multiplier = 0
        x = np.arange(len(df_classes.index.get_level_values(x_var).unique()))
        if even_grp:  # shift so that each x occurs in between the two middle bars
            futhest_left = (x + width_of_each_box / 2) - (
                width_of_each_box * (n_groups / 2)
            )
        else:
            futhest_left = x - length_of_bar_group / n_groups
        x = x + futhest_left[0]
        good_col = "#1a9641"
        bad_col = "#d7191c"
        # dic_cmapping = {"correct":"#1a9641", "overbuild":"#a6d96a", "underbuild":"#fdae61", "omitted":bad_col}
        dic_cmapping = {
            "correct": "k",
            "overbuild": "#fce674",
            "underbuild": bad_col,
            "omitted": bad_col,
        }
        n_mltp = 8
        dic_hatch_mapping = {
            "correct": "." * n_mltp,
            "overbuild": "|" * 6,
            "underbuild": "x" * n_mltp,
            "omitted": "/" * n_mltp,
        }
        for grp_idx, df_group in df_classes.groupby(level=grp_var):
            offset = width * multiplier
            bottom = np.zeros(x.shape)
            n_events_grp = s_n_events.loc[pd.IndexSlice[:, grp_idx]]
            for col_idx, col in df_group.items():
                vals = col.astype(float).values
                last_col = False
                if col_idx == df_group.columns[-1]:
                    last_col = True
                    # sys.exit("work")
                edgecolor = "k"
                facecolor = dic_pallet[grp_idx]
                hatch = dic_hatch_mapping[col_idx]
                if plt_var == "return_period_yrs":  # color the hatches
                    hatchcol = dic_cmapping[col_idx]
                    rects = ax_stckd_bar.bar(
                        x + offset,
                        vals,
                        width,
                        label=col_idx,
                        bottom=bottom,
                        facecolor=facecolor,
                        linewidth=1,
                        edgecolor=edgecolor,
                    )
                    ax_stckd_bar.bar(
                        x + offset,
                        vals,
                        width,
                        label=col_idx,
                        bottom=bottom,
                        facecolor="none",
                        linewidth=0,
                        edgecolor=hatchcol,
                        hatch=hatch,
                        hatch_linewidth=0.5,
                    )
                    if last_col:
                        ax_stckd_bar.bar_label(
                            rects, labels=n_events_grp.to_list(), fontsize="xx-small"
                        )
                else:
                    # commented out code for overlaying different colors and stuff; ended up busying the plot
                    # ax_stckd_bar.bar(x+offset, vals, width, label=col_idx, bottom=bottom, facecolor = facecolor, linewidth = 1, edgecolor=edgecolor)
                    ax_stckd_bar.bar(
                        x + offset,
                        vals,
                        width,
                        label=col_idx,
                        bottom=bottom,
                        facecolor=facecolor,
                        linewidth=1,
                        edgecolor=edgecolor,
                        hatch=hatch,
                        hatch_linewidth=0.5,
                    )
                # ax_stckd_bar.bar(x+offset, vals, width, label=col_idx, bottom=bottom, facecolor = "none", linewidth = 1, edgecolor=edgecolor)
                bottom += vals
            multiplier += 1
        ax_stckd_bar.set_ylim(0, 1.1)
        ax_stckd_bar.set_xticks([])
        ax_stckd_bar.set_xticklabels([])
        ax_stckd_bar.set_xlabel("")
        ax_stckd_bar.set_ylabel(
            "fraction of weather and impact events\nfor targeted return period",
            fontsize="small",
        )
    ax_stckd_bar.grid(
        True, which="major", linestyle="--", linewidth=0.5, axis="y"
    )  # axis='y'

    # annotate the plot (title, legends, etc.)
    if plt_title is not None:
        main_fig.suptitle(f"{plt_title}", x=0.5, y=0.94)
    ax_bw.set_xlabel(xlab)
    ax_bw.set_ylabel("$\\hat{R}_{F}({y})$")
    ax_bw.set_ylim(y_range)
    # create custom legend
    legend_elements = []
    # add the shaded region
    patch = mpatches.Patch(
        label="$\\hat{R}_{F}({y})$ 90% CI",
        edgecolor="orange",
        facecolor="grey",
        alpha=0.7,
    )
    legend_elements.append(patch)
    for key in dic_pallet.keys():
        if dic_legend_name_mapping is None:
            label = key
        else:
            label = dic_legend_name_mapping[key]
        if "_" in label:
            label = label.replace("_", "\n")
        patch = mpatches.Patch(label=label, color=dic_pallet[key])
        legend_elements.append(patch)
    main_fig.legend(
        handles=legend_elements,
        loc="upper center",
        fontsize="small",
        title="",
        title_fontsize="small",
        bbox_to_anchor=(0.97, 0.55),
        ncols=1,
    )
    legend_elements = []
    for key in dic_hatch_mapping.keys():
        if plt_var == "return_period_yrs":  # color
            edgecolor = dic_cmapping[key]
        else:
            edgecolor = "k"
        label = key
        if key == "correct":
            label = "$\\hat{R}_{E} \\approx \\hat{R}_{F}$"
        patch = mpatches.Patch(
            label=label,
            edgecolor=edgecolor,
            facecolor="white",
            hatch=dic_hatch_mapping[key],
            hatch_linewidth=0.5,
        )
        legend_elements.append(patch)
    legend_elements.reverse()
    main_fig.legend(
        handles=legend_elements,
        loc="upper center",
        fontsize="small",
        title="",
        title_fontsize="small",
        bbox_to_anchor=(0.962, 0.875),
        ncols=1,
    )

    return main_fig, ax_stckd_bar, ax_bw


# %% looping over all combinations
val = input(f"type 'yes' to create box and whiskers plots")
create_plots = False
if val.lower() == "yes":
    create_plots = True
    val = input(f"type 'delete' to remove all existing plots first")
    delete_plots = False
    if val.lower() == "delete":
        delete_plots = True

plots_by_aoi = False
skip_multivar = True
# rtrn_pds_to_analyze = [2, 100]
rtrn_pds_to_analyze = None

# plotting parameterss
bar_width = 0.5
df_flood_impacts_by_aoi = (
    ds_flood_impacts_by_aoi.to_dataframe().reset_index().set_index("event_number")
)
y_range = (0.2, flood_rtrn_pd_support)
whisker_alpha = 0.05
dpi = 200
add_subplot_with_classifications = True
# df_flood_events_in_ci_og = df_flood_events_in_ci

main_dir_plots = f"{dir_flood_prob_vs_event_prob}plots/EDA/box_and_whiskers/"
if delete_plots:
    Path(main_dir_plots).mkdir(parents=True, exist_ok=True)
    shutil.rmtree(main_dir_plots)
    Path(main_dir_plots).mkdir(parents=True, exist_ok=True)
if create_plots:
    # %%
    for formulation, df_event_formulation in df_weather_events_in_ci_og.groupby(
        level="formulation"
    ):
        multivar = True
        subfldr = "multivar"
        if "univar" in formulation:
            multivar = False
            subfldr = "univar"
        else:
            if skip_multivar:
                print(
                    f"skipping multivariate formulations because skip_multivar is set to {skip_multivar}"
                )
                continue
        dir_plots = f"{main_dir_plots}{subfldr}/"
        Path(dir_plots).mkdir(parents=True, exist_ok=True)
        for event_stat, df_event_stat in tqdm(
            df_event_formulation.groupby(level="event_stats")
        ):
            for impact_var in lst_impact_vars:
                df_event_return_pds = (
                    df_event_stat.loc[pd.IndexSlice[formulation, event_stat]]
                    .reset_index()
                    .set_index("event_number")
                )
                df_data_for_plotting = df_event_return_pds.join(
                    df_flood_impacts_by_aoi, on="event_number", how="left"
                ).reset_index()  # these are the results of all x-year weather events

                if "flooded_area" in impact_var:
                    # continue
                    df_plt_impact_vars = df_data_for_plotting.filter(
                        like="flooded_area"
                    )
                else:
                    df_plt_impact_vars = df_data_for_plotting.filter(like=impact_var)
                s_impact_return_periods = df_plt_impact_vars.filter(
                    like="return_pd"
                ).iloc[:, 0]
                colname_return = s_impact_return_periods.name
                y_var = colname_return

                if multivar:
                    formulation_title = formulation.split("_")[-1]
                    event_stat_formatted = event_stat
                else:
                    formulation_title = "U"
                    event_stat_formatted = create_bar_label_one_line(event_stat)
                str_formulation = (
                    f"${formulation_title}_" + "{" + f"{event_stat_formatted}" + "}$"
                )
                # create plots grouped by return period
                for return_period_yrs, df_event_rtrn_pd in df_data_for_plotting.groupby(
                    "return_period_yrs"
                ):
                    if rtrn_pds_to_analyze is not None:
                        if return_period_yrs not in rtrn_pds_to_analyze:
                            print(
                                f"Skipping return period {return_period_yrs} because it is not in the list rtrn_pds_to_analyze"
                            )
                            continue
                    # sys.exit("work")
                    dir_plots_rtrn = f"{dir_plots}/by_rtrn/rtrn_{return_period_yrs}_yr/"
                    Path(dir_plots_rtrn).mkdir(parents=True, exist_ok=True)
                    # print(len(df_event_rtrn_pd))
                    plt_var = "return_period_yrs"
                    plt_var_val = return_period_yrs
                    x_var = "subarea_name"
                    grp_var = "depth_range_m"
                    xlab = ""
                    dic_pallet = dic_dpth_color_lookup
                    dic_legend_name_mapping = dic_dpth_dsc_lookup
                    fname_savefig = f"{dir_plots_rtrn}{impact_var}_{formulation}_{event_stat}_{return_period_yrs}_yr.png"
                    # sys.exit("work")

                    plt_title = f"{str_formulation} | {plt_var_val} year event return period | $y=$ {impact_var}"

                    # sys.exit('work')
                    main_fig, ax_stckd_bar, ax_bw = create_box_and_whiskers(
                        ds_flood_impacts_by_aoi=ds_flood_impacts_by_aoi,
                        df_weather_events_in_ci_og=df_weather_events_in_ci_og,
                        df_data_for_plotting=df_data_for_plotting,
                        formulation=formulation,
                        event_stat=event_stat,
                        impact_var=impact_var,
                        plt_var=plt_var,
                        plt_var_val=plt_var_val,
                        x_var=x_var,
                        y_var=y_var,
                        grp_var=grp_var,
                        bar_width=bar_width,
                        df_flood_events_in_ci_og=df_flood_events_in_ci_og,
                        xlab=xlab,
                        y_range=y_range,
                        dic_pallet=dic_pallet,
                        dic_legend_name_mapping=dic_legend_name_mapping,
                        plt_title=plt_title,
                        dpi=dpi,
                        whisker_alpha=whisker_alpha,
                        add_subplot_with_classifications=add_subplot_with_classifications,
                    )
                    ax_bw.set_xticks(ax_bw.get_xticks())
                    xticks = ax_bw.get_xticklabels()
                    newticks = []
                    for lab in xticks:
                        current_text = lab.get_text()
                        newticks.append(current_text.replace("_", "\n"))
                    ax_bw.set_xticklabels(newticks)
                    # fig.tight_layout()
                    # sys.exit("work")
                    plt.savefig(fname_savefig, bbox_inches="tight")
                    plt.clf()
                # create plots by depth range
                if plots_by_aoi:
                    for (
                        depth_range_m,
                        df_event_dpth_range,
                    ) in df_data_for_plotting.groupby("depth_range_m"):
                        dir_plots_dpth = f"{dir_plots}/by_depth/{dic_dpth_dsc_lookup[depth_range_m]}/"
                        Path(dir_plots_dpth).mkdir(parents=True, exist_ok=True)
                        plt_var = "depth_range_m"
                        plt_var_val = depth_range_m
                        # plt_var_for_title = f"{dic_dpth_dsc_lookup[plt_var_val]} {plt_var_val}"
                        x_var = "return_period_yrs"
                        grp_var = "subarea_name"
                        xlab = "$\\hat{R}_{E}(e)$"
                        dic_pallet = dict(
                            east_residential="#a6cee3",
                            monticello_princessanne_intersxn="#1f78b4",
                            nw_commercial="#b2df8a",
                            olney_rd="#33a02c",
                            se_residential="#fb9a99",
                            watershed="#e31a1c",
                        )
                        dic_legend_name_mapping = None
                        fname_savefig = f"{dir_plots_dpth}{impact_var}_{formulation}_{event_stat}_{depth_range_m}.png"
                        plt_title = f"{str_formulation} | {dic_dpth_dsc_lookup[depth_range_m]} {depth_range_m}"
                        main_fig, ax_stckd_bar, ax_bw = create_box_and_whiskers(
                            ds_flood_impacts_by_aoi=ds_flood_impacts_by_aoi,
                            df_weather_events_in_ci_og=df_weather_events_in_ci_og,
                            df_data_for_plotting=df_data_for_plotting,
                            formulation=formulation,
                            event_stat=event_stat,
                            impact_var=impact_var,
                            plt_var=plt_var,
                            plt_var_val=plt_var_val,
                            x_var=x_var,
                            y_var=y_var,
                            grp_var=grp_var,
                            bar_width=bar_width,
                            df_flood_events_in_ci_og=df_flood_events_in_ci_og,
                            xlab=xlab,
                            y_range=y_range,
                            dic_pallet=dic_pallet,
                            dic_legend_name_mapping=dic_legend_name_mapping,
                            plt_title=plt_title,
                            dpi=dpi,
                            whisker_alpha=whisker_alpha,
                            add_subplot_with_classifications=add_subplot_with_classifications,
                        )
                        # fig.tight_layout()
                        # sys.exit("work")
                        plt.savefig(fname_savefig, bbox_inches="tight")
                        plt.clf()
