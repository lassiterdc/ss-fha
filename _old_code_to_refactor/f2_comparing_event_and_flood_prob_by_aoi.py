# %%
import xarray as xr
import os
import sys

sys.path.insert(0, os.getcwd())
# from local.__inputs import (
#     # F_EXPERIMENT_DESIGN,
#     # DIR_FFA_SCRIPTS_LOCAL_OUTPUTS,
# )
from local.__inputs import (
    F_SIM_TSERIES,
    F_FLOOD_IMPACT_RETURN_PERIODS_BY_AOI,
    F_SIM_MULTIVAR_RETURN_PERIODS,
    F_SIM_FLOOD_PROBS_EVENT_NUMBER_MAPPING,
    F_RTRN_PDS_SEA_WATER_LEVEL,
    F_RTRN_PDS_RAINFALL,
    F_BS_UNCERTAINTY_EVENTS_IN_CI,
    DIC_EVENT_FORM_LABEL_LOOKUP,
    F_FLOOD_IMPACT_BS_UNCERTAINTY_EVENTS_IN_CI,
    F_FLOOD_IMPACT_BS_UNCERTAINTY_CI,
    F_WEATHER_EVENT_VS_IMPACT_EVENT_CLASSIFICATION,
    DIC_DPTH_COLOR_LOOKUP,
    DIC_DPTH_DSC_LOOKUP,
    DIR_FLOOD_PROB_VS_EVENT_PROB,
    LST_RTRNS,
    FLD_RTRN_PD_ALPHA,
    FLOOD_RTRN_PD_SUPPORT,
    F_DESIGN_STORM_TSERIES_BASED_ON_SSR,
    F_UNIVAR_BS_UNCERTAINTY_CI,
    F_SIM_SMRIES,
    F_MULTIVAR_BS_UNCERTAINTY_CI,
    DIR_PLOTS_FLOOD_VS_EVENT_PROB,
    F_CORRS_UNIVARIATE_EVENT_VS_FLOOD_RETURN_PDS_BY_AOI,
    F_CORRS_MULTIVAR_EVENT_VS_FLOOD_RETURN_PDS_BY_AOI,
    F_ERRS_UNIVARIATE_EVENT_VS_FLOOD_RETURN_PDS_BY_AOI,
    F_ERRS_MULTIVAR_EVENT_VS_FLOOD_RETURN_PDS_BY_AOI,
    LST_CORRS_IDX,
    LST_ERRS_IDX,
    # TARGET_DESIGN_STORM_DURATION_HRS_FOR_COMPARISON,
)

from local.__utils import (
    delete_directory,
    compute_corrs_in_2col_df,
    compute_sse_and_mse_in_2col_df,
)

from local.__plotting import (
    plot_ensemle_vs_mc_design_storms_vs_conventional_design_storms,
    create_hexbin_weather_vs_impact_rtrn,
    analyze_flood_impact_rtrn_pd,
    plot_mcds_events,
    plot_conventional_design_storms_against_ensemble,
    create_event_scatterplot_with_CDS_and_MCDS,
)

from hpc.python.__filepaths_andes import constant_head_val

# from __utils import
import pandas as pd
from pathlib import Path
from tqdm import tqdm
import matplotlib.pyplot as plt
import numpy as np

# rewrite_intermediate_results_if_files_exist = False
pearson_on_log = True  # before taking the pearson correlation coefficient, first take the log of the data
prompt_for_plot_deletion = False

ds_sim_tseries = xr.open_dataset(F_SIM_TSERIES).chunk(
    dict(timestep=-1, year=-1, event_type=1, event_id=-1)
)
sim_idx_names = ds_sim_tseries.coords.to_index().names
event_idx_names = [name for name in sim_idx_names if name != "timestep"]
f_dsgn_tseries = F_DESIGN_STORM_TSERIES_BASED_ON_SSR
ds_dsgn_tseries = xr.open_dataset(f_dsgn_tseries)
df_sim_flood_probs_event_num_mapping = pd.read_csv(
    F_SIM_FLOOD_PROBS_EVENT_NUMBER_MAPPING
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

ds_multivar_return_periods = xr.open_dataset(
    F_SIM_MULTIVAR_RETURN_PERIODS, engine="zarr"
).chunk("auto")
df_wlevel_return_pds = pd.read_csv(
    F_RTRN_PDS_SEA_WATER_LEVEL, index_col=event_idx_names
)
df_rain_rtrn_pds = pd.read_csv(F_RTRN_PDS_RAINFALL, index_col=event_idx_names)

df_event_stats_and_univar_return_periods_og = pd.concat(
    [df_wlevel_return_pds, df_rain_rtrn_pds], axis=1
)

# create dataframe with univarite return periods
cols_rain_stats = ["return_pd_yrs" in col for col in df_rain_rtrn_pds.columns]
df_univariate_rain_return_pds = df_rain_rtrn_pds.loc[:, cols_rain_stats]
cols_wlevel_stats = ["return_pd_yrs" in col for col in df_wlevel_return_pds.columns]
df_sea_wlevel_return_pds = df_wlevel_return_pds.loc[:, cols_wlevel_stats]

## combine into single dataframe and fill na values with a value very close to zero (these correspond to fields where the event statistic did not meet the threshold)
df_univariate_return_pds_og = pd.concat(
    [df_univariate_rain_return_pds, df_sea_wlevel_return_pds], axis=1
)

# loading results of bootstrapping to represent uncertainty
## events
# "D:/Dropbox/_GradSchool/_norfolk/stormy/flood_attribution/local/outputs/comparing_flood_probs_to_event_probs/bs_uncertainty_multivar_ci_copy.csv"

lst_idx = ["quantile", "event_stat", "return_period_yrs"]
df_return_pd_cis_multivar_og = pd.read_csv(
    F_MULTIVAR_BS_UNCERTAINTY_CI, index_col=lst_idx
)
df_return_pd_cis_univar_og = pd.read_csv(F_UNIVAR_BS_UNCERTAINTY_CI, index_col=lst_idx)
lst_idx = ["formulation", "return_period_yrs", "event_stat"]
# df_all_bs_events_by_rtrn_pd_multivar = pd.read_csv(f_multivar_bs_uncertainty_all_unique_events, index_col = lst_idx)
# df_all_bs_events_by_rtrn_pd_univar = pd.read_csv(f_univar_bs_uncertainty_all_unique_events, index_col = lst_idx)
## flood impacts
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
# lst_idx = ["subarea_name", "depth_range_m", "return_period_yrs", "event_number"]
# df_all_bs_events_by_rtrn_pd_flood_impacts = pd.read_csv(f_flood_impact_bs_uncertainty_all_unique_events, index_col = lst_idx)

df_sim_summaries = pd.read_csv(F_SIM_SMRIES)

df_weather_events_in_ci_og = pd.read_csv(
    F_BS_UNCERTAINTY_EVENTS_IN_CI, index_col=[0, 1, 2, 3]
)


dir_plots_event_vs_flood_impact_rtrn = (
    f"{DIR_PLOTS_FLOOD_VS_EVENT_PROB}weather_vs_impact_return_periods/"
)
use_aep = True
delete_plots = False

if prompt_for_plot_deletion:
    val = input(f"type 'delete' to clear the plots folder before re-creating them.")
    if val.lower() != "delete":
        delete_plots = False

dir_plots_event_return_periods = (
    f"{DIR_PLOTS_FLOOD_VS_EVENT_PROB}MC_design_storm_selection/"
)

Path(dir_plots_event_vs_flood_impact_rtrn).mkdir(parents=True, exist_ok=True)
if delete_plots:
    delete_directory(dir_plots_event_vs_flood_impact_rtrn, attempt_time_limit_s=10)
    Path(dir_plots_event_vs_flood_impact_rtrn).mkdir(parents=True, exist_ok=True)
    delete_directory(dir_plots_event_return_periods, attempt_time_limit_s=10)
    Path(dir_plots_event_return_periods).mkdir(parents=True, exist_ok=True)
    print("deleted existing plots")

df_weather_vs_impact_retrn_pd_classification = pd.read_csv(
    F_WEATHER_EVENT_VS_IMPACT_EVENT_CLASSIFICATION, index_col=[0, 1, 2, 3, 4, 5]
)
subarea_name = "watershed"
lst_impact_vars = [
    "flooded_area_sqm",
    "n_building_id_impacted",
    "n_road_segment_id_impacted",
]

lst_depth_ranges = df_weather_vs_impact_retrn_pd_classification.reset_index()[
    "depth_range_m"
].unique()

idx_best = (
    df_weather_vs_impact_retrn_pd_classification.groupby(
        [
            "impact_var",
            "subarea_name",
            "depth_range_m",
            "formulation",
            "return_period_yrs",
        ]
    )["correct"]
    .idxmax()
    .values
)
df_classification_best_aoi = df_weather_vs_impact_retrn_pd_classification.loc[
    idx_best
].loc[pd.IndexSlice[lst_impact_vars, :, :, subarea_name, :, :, :]]
# subset for nonzero flood impact events
df_classification_best_aoi = df_classification_best_aoi[
    df_classification_best_aoi["n_impact_events_nonzero_flooding"] > 0
]

# %%
# plotting monte carlo design storms
from local.__inputs import (
    FORMULATION_FOR_MC_DSGN_STRM_SEL_MULTIVAR_AND,
    FORMULATION_FOR_MC_DSGN_STRM_SEL_UNIVAR,
    EVENT_STAT_FOR_MC_DSGN_STRM_SEL_MULTIVAR_AND,
    EVENT_STAT_FOR_MC_DSGN_STRM_SEL_UNIVAR,
    FORMULATION_FOR_MC_DSGN_STRM_SEL_MULTIVAR_OR,
    EVENT_STAT_FOR_MC_DSGN_STRM_SEL_MULTIVAR_OR,
)

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

fname_savefig = f"{dir_plots_event_return_periods}mcds_storms.pdf"

# and and univar formulation
plot_mcds_events(
    df_rain_rtrn_pds,
    df_wlevel_return_pds,
    df_weather_events_in_ci_og,
    ds_multivar_return_periods,
    df_sim_flood_probs_event_num_mapping,
    use_aep,
    dir_plots_event_return_periods,
    df_univariate_return_pds_og,
    dict_forms_and_stats,
    clf=False,
    fname_savefig=fname_savefig,
)

# or formulation
dict_forms_and_stats = dict(
    formulations=[
        FORMULATION_FOR_MC_DSGN_STRM_SEL_MULTIVAR_OR,
    ],
    stats=[
        EVENT_STAT_FOR_MC_DSGN_STRM_SEL_MULTIVAR_OR,
    ],
)

fname_savefig = f"{dir_plots_event_return_periods}mcds_OR_storms.pdf"

dict_legend_items, lst_axes = plot_mcds_events(
    df_rain_rtrn_pds,
    df_wlevel_return_pds,
    df_weather_events_in_ci_og,
    ds_multivar_return_periods,
    df_sim_flood_probs_event_num_mapping,
    use_aep,
    dir_plots_event_return_periods,
    df_univariate_return_pds_og,
    dict_forms_and_stats,
    clf=False,
    fname_savefig=fname_savefig,
)

# design storms
constant_sea_water_level_boundary = constant_head_val
plot_conventional_design_storms_against_ensemble(
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
)

# multivariate AND and conventional design storms

create_event_scatterplot_with_CDS_and_MCDS(
    df_rain_rtrn_pds,
    df_wlevel_return_pds,
    df_weather_events_in_ci_og,
    ds_multivar_return_periods,
    df_sim_flood_probs_event_num_mapping,
    use_aep,
    dir_plots_event_return_periods,
    df_univariate_return_pds_og,
    ds_dsgn_tseries,
    constant_sea_water_level_boundary=constant_head_val,
)


# %%

#  compute correlations and loss functions of event return period vs. flood_impact return period
# generate correlations between event return period and flood return period
val = input(
    f"type 'yes' to re-calculate correlations and loss functions between event return period and flooded area return period event if they already exist."
)
rewrite_intermediate_results_if_files_exist = True
if val.lower() != "yes":
    rewrite_intermediate_results_if_files_exist = False

print(
    "These calculations only consider flood events with nonzero flood impacts. If there are rare weather events that do not generate flooding, they will not be included."
)

if (rewrite_intermediate_results_if_files_exist == False) and (
    (Path(F_ERRS_UNIVARIATE_EVENT_VS_FLOOD_RETURN_PDS_BY_AOI).exists())
    and (Path(F_ERRS_MULTIVAR_EVENT_VS_FLOOD_RETURN_PDS_BY_AOI).exists())
    and (Path(F_CORRS_UNIVARIATE_EVENT_VS_FLOOD_RETURN_PDS_BY_AOI).exists())
    and (Path(F_CORRS_MULTIVAR_EVENT_VS_FLOOD_RETURN_PDS_BY_AOI).exists())
):
    print(
        f"loading flood/event probability correlations and errors since rewrite_intermediate_results_if_files_exist is set to {rewrite_intermediate_results_if_files_exist}"
    )
    df_univar_corrs = pd.read_csv(
        F_CORRS_UNIVARIATE_EVENT_VS_FLOOD_RETURN_PDS_BY_AOI, index_col=LST_CORRS_IDX
    )
    df_multivar_corrs = pd.read_csv(
        F_CORRS_MULTIVAR_EVENT_VS_FLOOD_RETURN_PDS_BY_AOI, index_col=LST_CORRS_IDX
    )
    df_univar_errs = pd.read_csv(
        F_ERRS_UNIVARIATE_EVENT_VS_FLOOD_RETURN_PDS_BY_AOI, index_col=LST_ERRS_IDX
    )
    df_multivar_errs = pd.read_csv(
        F_ERRS_MULTIVAR_EVENT_VS_FLOOD_RETURN_PDS_BY_AOI, index_col=LST_ERRS_IDX
    )
else:
    print(
        "Analyzing correlations and loss functions of flood probability and formulations of event probability"
    )
    lst_df_multivar_corrs = []
    lst_df_univar_corrs = []
    lst_df_multivar_errs = []
    lst_df_univar_errs = []
    for subarea in tqdm(ds_flood_impacts_by_aoi.subarea_name.values):
        for depth_range in ds_flood_impacts_by_aoi.depth_range_m.values:
            ds_fld_impact_subset = ds_flood_impacts_by_aoi.sel(
                subarea_name=subarea, depth_range_m=depth_range
            )
            df_fld_impact_subset = ds_fld_impact_subset.to_dataframe()
            for impact_var in lst_impact_vars:
                if "flooded_area" in impact_var:
                    df_subset_impact = df_fld_impact_subset.filter(like="flooded_area")
                else:
                    df_subset_impact = df_fld_impact_subset.filter(like=impact_var)
                # subset events that meet the flooded area threshold
                df_subset_impact = df_subset_impact[df_subset_impact[impact_var] > 0]
                # extrac return periods
                s_flood_impact_rtrn_pd_nonzero = df_subset_impact.filter(
                    like="return_pd"
                ).iloc[:, 0]
                # s_flood_impact_rtrn_pd_nonzero = s_flood_impact_rtrn_pd_nonzero[s_flood_impact_rtrn_pd_nonzero<=flood_rtrn_pd_support]

                s_flood_impact_rtrn_pd_nonzero = (
                    s_flood_impact_rtrn_pd_nonzero.to_frame()
                    .join(
                        df_sim_flood_probs_event_num_mapping.set_index("event_number"),
                        how="left",
                    )
                    .set_index(event_idx_names)[s_flood_impact_rtrn_pd_nonzero.name]
                )
                # sys.exit("work")
                # idx_events_considered_nonzero = s_flood_impact_rtrn_pd_nonzero.index
                lst_s_univar_corrs_area_dpth = []
                lst_s_univar_errs_area_dpth = []
                for univar_colname, s_univar in df_univariate_return_pds_og.items():
                    if len(s_univar.dropna()) < len(
                        df_sim_flood_probs_event_num_mapping
                    ):
                        sys.exit("check univariate return period length")
                    s_univar_subset = s_univar  # .loc[idx_events_considered_nonzero]
                    df_univar_comp = pd.concat(
                        [s_flood_impact_rtrn_pd_nonzero, s_univar_subset], axis=1
                    ).dropna()  # this removes rows that had zero flooding
                    s_univar_corrs = compute_corrs_in_2col_df(
                        df_univar_comp, pearson_on_log=pearson_on_log
                    )
                    s_univar_corrs.name = univar_colname.split("_return_pd_yrs")[0]
                    s_univar_errs = compute_sse_and_mse_in_2col_df(df_univar_comp)
                    s_univar_errs.name = univar_colname.split("_return_pd_yrs")[0]
                    lst_s_univar_corrs_area_dpth.append(s_univar_corrs)
                    lst_s_univar_errs_area_dpth.append(s_univar_errs)
                    # df_univar_comp.plot.scatter(colname_return, univar_colname)
                lst_multivar_corrs_area_dpth_OR = []
                lst_multivar_corrs_area_dpth_AND = []
                lst_multivar_errs_area_dpth_OR = []
                lst_multivar_errs_area_dpth_AND = []
                for multivar_stat in ds_multivar_return_periods.event_stats.values:
                    # print(multivar_stat)
                    ds_multivar_stat_subset = ds_multivar_return_periods.sel(
                        event_stats=multivar_stat
                    )[
                        [
                            "empirical_multivar_rtrn_yrs_AND",
                            "empirical_multivar_rtrn_yrs_OR",
                        ]
                    ]
                    df_multivar_stat_subset = (
                        ds_multivar_stat_subset.to_dataframe().dropna()
                    )  # .loc[idx_events_considered_nonzero, :]
                    s_OR = df_multivar_stat_subset["empirical_multivar_rtrn_yrs_OR"]
                    s_AND = df_multivar_stat_subset["empirical_multivar_rtrn_yrs_AND"]
                    # if (len(s_OR.dropna()) < len(idx_events_considered_nonzero)) or (len(s_AND.dropna()) < len(idx_events_considered_nonzero)):
                    #     sys.exit("check multivariate return period length")
                    # combine with flood area return periods
                    df_or_comp = pd.concat(
                        [s_flood_impact_rtrn_pd_nonzero, s_OR], axis=1
                    ).dropna()  # this removes rows that had zero flooding
                    df_and_comp = pd.concat(
                        [s_flood_impact_rtrn_pd_nonzero, s_AND], axis=1
                    ).dropna()  # this removes rows that had zero flooding
                    # analyze correlations
                    # sys.exit('work')
                    s_multivar_or_corrs = compute_corrs_in_2col_df(
                        df_or_comp, pearson_on_log=pearson_on_log
                    )
                    s_multivar_or_corrs.name = multivar_stat  # .replace(".", "|")
                    s_multivar_or_errs = compute_sse_and_mse_in_2col_df(df_or_comp)
                    s_multivar_or_errs.name = multivar_stat
                    s_multivar_and_corrs = compute_corrs_in_2col_df(
                        df_and_comp, pearson_on_log=pearson_on_log
                    )
                    s_multivar_and_corrs.name = multivar_stat  # .replace(".", "&")
                    s_multivar_and_errs = compute_sse_and_mse_in_2col_df(df_and_comp)
                    s_multivar_and_errs.name = multivar_stat
                    lst_multivar_corrs_area_dpth_OR.append(s_multivar_or_corrs)
                    lst_multivar_corrs_area_dpth_AND.append(s_multivar_and_corrs)
                    lst_multivar_errs_area_dpth_OR.append(s_multivar_or_errs)
                    lst_multivar_errs_area_dpth_AND.append(s_multivar_and_errs)
                # combine correlations into dataframes
                df_multivar_corrs_OR = pd.concat(
                    lst_multivar_corrs_area_dpth_OR, axis=1
                )
                df_multivar_corrs_OR["event_stat_type"] = "multivar_OR"
                df_multivar_corrs_AND = pd.concat(
                    lst_multivar_corrs_area_dpth_AND, axis=1
                )
                df_multivar_corrs_AND["event_stat_type"] = "multivar_AND"
                df_multivar_corrs = pd.concat(
                    [df_multivar_corrs_OR, df_multivar_corrs_AND]
                )
                df_univar_corrs = pd.concat(lst_s_univar_corrs_area_dpth, axis=1)
                # reset indices for later concatenation
                df_multivar_corrs["impact_var"] = impact_var
                df_multivar_corrs["depth_range_m"] = depth_range
                df_multivar_corrs["subarea_name"] = subarea
                df_univar_corrs["impact_var"] = impact_var
                df_univar_corrs["depth_range_m"] = depth_range
                df_univar_corrs["subarea_name"] = subarea
                df_univar_corrs["event_stat_type"] = "univar"
                df_multivar_corrs.index.name = "corr_method"
                df_univar_corrs.index.name = "corr_method"
                df_multivar_corrs = df_multivar_corrs.reset_index().set_index(
                    LST_CORRS_IDX
                )
                df_univar_corrs = df_univar_corrs.reset_index().set_index(LST_CORRS_IDX)
                # append
                lst_df_multivar_corrs.append(df_multivar_corrs)
                lst_df_univar_corrs.append(df_univar_corrs)

                # combine error/loss functionos into dataframes
                df_multivar_errs_OR = pd.concat(lst_multivar_errs_area_dpth_OR, axis=1)
                df_multivar_errs_OR["event_stat_type"] = "multivar_OR"
                df_multivar_errs_AND = pd.concat(
                    lst_multivar_errs_area_dpth_AND, axis=1
                )
                df_multivar_errs_AND["event_stat_type"] = "multivar_AND"
                df_multivar_errs = pd.concat(
                    [df_multivar_errs_OR, df_multivar_errs_AND]
                )
                df_univar_errs = pd.concat(lst_s_univar_errs_area_dpth, axis=1)
                # reset indices for later concatenation
                df_multivar_errs["impact_var"] = impact_var
                df_multivar_errs["depth_range_m"] = depth_range
                df_multivar_errs["subarea_name"] = subarea
                df_univar_errs["impact_var"] = impact_var
                df_univar_errs["depth_range_m"] = depth_range
                df_univar_errs["subarea_name"] = subarea
                df_univar_errs["event_stat_type"] = "univar"
                df_multivar_errs.index.name = "err_method"
                df_univar_errs.index.name = "err_method"
                df_multivar_errs = df_multivar_errs.reset_index().set_index(
                    LST_ERRS_IDX
                )
                df_univar_errs = df_univar_errs.reset_index().set_index(LST_ERRS_IDX)
                # append
                # sys.exit("work")
                lst_df_multivar_errs.append(df_multivar_errs)
                lst_df_univar_errs.append(df_univar_errs)
    # combining correlation calculations
    df_univar_corrs = pd.concat(lst_df_univar_corrs)
    df_multivar_corrs = pd.concat(lst_df_multivar_corrs)
    # saving to files
    df_univar_corrs.to_csv(F_CORRS_UNIVARIATE_EVENT_VS_FLOOD_RETURN_PDS_BY_AOI)
    df_multivar_corrs.to_csv(F_CORRS_MULTIVAR_EVENT_VS_FLOOD_RETURN_PDS_BY_AOI)
    # combining correlation calculations
    df_univar_errs = pd.concat(lst_df_univar_errs)
    df_multivar_errs = pd.concat(lst_df_multivar_errs)
    # saving to files
    df_univar_errs.to_csv(F_ERRS_UNIVARIATE_EVENT_VS_FLOOD_RETURN_PDS_BY_AOI)
    df_multivar_errs.to_csv(F_ERRS_MULTIVAR_EVENT_VS_FLOOD_RETURN_PDS_BY_AOI)


#  plotting mcds hexbin plots (univariate and multivariate)
# from local.__inputs import (
#     FORMULATION_FOR_MC_DSGN_STRM_SEL_MULTIVAR_AND,
#     EVENT_STAT_FOR_MC_DSGN_STRM_SEL_MULTIVAR_AND,
#     FORMULATION_FOR_MC_DSGN_STRM_SEL_UNIVAR,
#     EVENT_STAT_FOR_MC_DSGN_STRM_SEL_UNIVAR,
# )
# %% AND formulation
from local.__plotting import mcds_hexbin_weather_vs_impact_rtrn

# %%
depth_range_m = lst_depth_ranges[1]

str_fig_title = ""
fname_savefig = (
    f"{dir_plots_event_vs_flood_impact_rtrn}MCDS_event_vs_impact_frequency.pdf"
)

multivar_formulation = "AND"
dpi = 300
impact_var = "flooded_area_sqm"

mcds_hexbin_weather_vs_impact_rtrn(
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
    fname_savefig=fname_savefig,
    dpi=300,
)

# %% plotting for OR formulation
from local.__inputs import (
    FORMULATION_FOR_MC_DSGN_STRM_SEL_MULTIVAR_OR,
    EVENT_STAT_FOR_MC_DSGN_STRM_SEL_MULTIVAR_OR,
)

formulation = FORMULATION_FOR_MC_DSGN_STRM_SEL_MULTIVAR_OR
stats = EVENT_STAT_FOR_MC_DSGN_STRM_SEL_MULTIVAR_OR
multivar_formulation = "OR"

depth_range_m = lst_depth_ranges[1]

fname_savefig = f"{dir_plots_event_vs_flood_impact_rtrn}{impact_var}.{subarea_name}.{DIC_DPTH_DSC_LOOKUP[depth_range_m]}_v_{formulation}_{stats}.png"
str_fig_title = f"{stats} vs. {impact_var}\n{DIC_DPTH_DSC_LOOKUP[depth_range_m]} flood depths ({subarea_name})"

dpi = 300

create_hexbin_weather_vs_impact_rtrn(
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
    event_idx_names=event_idx_names,
    str_fig_title=str_fig_title,
    fname_savefig=fname_savefig,
    multivar_formulation=multivar_formulation,
    dpi=dpi,
)
# %% plotting ALL hexbin impact vs driver return period
multivar_formulation = "AND"

for grp_id, df_grp in df_classification_best_aoi.groupby(
    ["formulation", "event_stats"]
):
    formulation, stats = grp_id
    for impact_var in lst_impact_vars:
        for depth_range_m in lst_depth_ranges:
            # for grp_idx, df_grp in df_classification_best_aoi.groupby(["formulation", "event_stats"]):
            #     formulation, stat = grp_idx

            # for stats in df_classification_best_aoi.reset_index()["event_stats"].unique():
            #     for impact_var in lst_impact_vars:
            fname_savefig = f"{dir_plots_event_vs_flood_impact_rtrn}{impact_var}.{subarea_name}.{DIC_DPTH_DSC_LOOKUP[depth_range_m]}_v_{formulation}_{stats}.png"
            str_fig_title = f"{stats} vs. {impact_var}\n{DIC_DPTH_DSC_LOOKUP[depth_range_m]} flood depths ({subarea_name})"
            # if (impact_var == "n_road_segment_id_impacted") and (DIC_DPTH_DSC_LOOKUP[depth_range_m] == "severe"):

            # else:
            #     continue
            dpi = 300

            create_hexbin_weather_vs_impact_rtrn(
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
                event_idx_names=event_idx_names,
                str_fig_title=str_fig_title,
                fname_savefig=fname_savefig,
                multivar_formulation=multivar_formulation,
                dpi=dpi,
            )

            plt.clf()

print(f"created plots in {dir_plots_event_vs_flood_impact_rtrn}")
# %% plottinga all MC design storms
clf = True
mc_dsgn_event_plot_legend_ncols = 1

for grp_id, df_grp in df_classification_best_aoi.groupby(
    ["formulation", "event_stats"]
):
    formulation, stats = grp_id
    plot_ensemle_vs_mc_design_storms_vs_conventional_design_storms(
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
        constant_sea_water_level_boundary=constant_head_val,
        clf=clf,
    )

# %% plotting params
sys.exit("this code chunks doesnt work")
import shutil

zoomed_in_subplots = False
dpi = 150
lst_group_idx = ["impact_var", "subarea_name", "event_stat_type", "depth_range_m"]
bin_labs_rtrn = [1, 2, 5, 10, 25, 50, 100, 200]
ord_mag = 1e3
rtrn_range_for_zoomed_in_plots = 0.1
f_best_format = "\\ddot"
lst_df_ER_FR_relationships = [df_univar_errs, df_multivar_errs]
dir_plots_event_vs_flood_impact_rtrn = (
    f"{DIR_PLOTS_FLOOD_VS_EVENT_PROB}EDA/event_vs_flood_impact_errs/"
)
minimize = True
chosen_perf_metric = "mae"
lst_subareas_to_include = [
    "watershed"
]  # ds_flood_impacts_by_aoi.subarea_name.to_series().to_list()

# remove existing plots
Path(dir_plots_event_vs_flood_impact_rtrn).mkdir(parents=True, exist_ok=True)
shutil.rmtree(dir_plots_event_vs_flood_impact_rtrn)
Path(dir_plots_event_vs_flood_impact_rtrn).mkdir(parents=True, exist_ok=True)
analyze_flood_impact_rtrn_pd(
    ds_flood_impacts_by_aoi,
    lst_subareas_to_include,
    lst_df_ER_FR_relationships,
    dir_plots_event_vs_flood_impact_rtrn,
    minimize,
    dpi,
    lst_group_idx,
    bin_labs_rtrn,
    ord_mag,
    LST_RTRNS,
    f_best_format,
    DIC_EVENT_FORM_LABEL_LOOKUP,
    df_return_pd_cis_multivar_og,
    df_return_pd_cis_univar_og,
    df_return_pd_cis_flood_impacts_og,
    zoomed_in_subplots,
    chosen_perf_metric,
)

f_best_format = "\\dot"
lst_df_ER_FR_relationships = [df_univar_corrs, df_multivar_corrs]
dir_plots_event_vs_flood_impact_rtrn = (
    f"{DIR_PLOTS_FLOOD_VS_EVENT_PROB}EDA/event_vs_flood_impact_corrs/"
)
minimize = False
chosen_perf_metric = "pearson"
Path(dir_plots_event_vs_flood_impact_rtrn).mkdir(parents=True, exist_ok=True)
shutil.rmtree(dir_plots_event_vs_flood_impact_rtrn)
Path(dir_plots_event_vs_flood_impact_rtrn).mkdir(parents=True, exist_ok=True)
analyze_flood_impact_rtrn_pd(
    ds_flood_impacts_by_aoi,
    lst_subareas_to_include,
    lst_df_ER_FR_relationships,
    dir_plots_event_vs_flood_impact_rtrn,
    minimize,
    dpi,
    lst_group_idx,
    bin_labs_rtrn,
    ord_mag,
    LST_RTRNS,
    f_best_format,
    DIC_EVENT_FORM_LABEL_LOOKUP,
    df_return_pd_cis_multivar_og,
    df_return_pd_cis_univar_og,
    df_return_pd_cis_flood_impacts_og,
    zoomed_in_subplots,
    chosen_perf_metric,
)

# %% plotting function for investigating all the top correlations
print(
    "stuff from this point on i consider parts of my EDA and are at this point out of date (and would probably take some tweaking to even work)"
)
sys.exit(0)


# %% creating a scatterplot matrix of impact return periods

sys.exit(
    "I am not using the scatterplot matrix plot for now because I don't think it's a good visual on the spatial variability in flood-inducing conditions. Also, it needs some debugging since computing multiple types of flood impacts."
)


# format so that each column is an AOI
# import seaborn as sns
def hexbin_wrapper(
    ax, x, y, flood_rtrn_pd_support, lst_rtrns, df_return_pd_cis_flood_impacts
):
    x_aoi = x.name
    y_aoi = y.name
    min_x, min_y = 0.5, 0.5
    """Hexbin plotting function for PairGrid"""
    # ax = plt.gca()
    ax.set_yscale("log")
    ax.set_xscale("log")
    ax.set_ylim(min_y, flood_rtrn_pd_support)
    ax.set_xlim(min_x, flood_rtrn_pd_support)
    x_line = np.logspace(-1, 3, 100)  # Ensure the x values cover the range of your data
    ax.plot(x_line, x_line, color="red", linestyle="--", label="1:1 Line")
    ax.hexbin(
        x,
        y,
        gridsize=50,
        xscale="log",
        yscale="log",
        bins="log",
        mincnt=1,
        alpha=0.92,
        edgecolors="none",
        extent=(
            np.log10(min_y),
            np.log10(flood_rtrn_pd_support),
            np.log10(min_y),
            np.log10(flood_rtrn_pd_support),
        ),
    )  #
    for idx_rtrn, trgt_rtrn in enumerate(lst_rtrns):
        s_flood_impact_lims_x = df_return_pd_cis_flood_impacts.loc[
            pd.IndexSlice[:, x_aoi, depth_range_m, trgt_rtrn]
        ]
        flood_rtrn_ci_x = (
            s_flood_impact_lims_x.values.min(),
            s_flood_impact_lims_x.values.max(),
        )

        s_flood_impact_lims_y = df_return_pd_cis_flood_impacts.loc[
            pd.IndexSlice[:, y_aoi, depth_range_m, trgt_rtrn]
        ]
        flood_rtrn_ci_y = (
            s_flood_impact_lims_y.values.min(),
            s_flood_impact_lims_y.values.max(),
        )

        ax.fill_between(
            [flood_rtrn_ci_x[0], flood_rtrn_ci_x[1]], 1000, color="grey", alpha=0.3
        )
        ax.fill_betweenx(
            [flood_rtrn_ci_y[0], flood_rtrn_ci_y[1]], 1000, color="grey", alpha=0.3
        )

    ax.grid(True, axis="y")
    # Add major and minor y-axis gridlines
    ax.grid(True, which="major", linestyle="-", linewidth=0.8, axis="y")  # axis='y'
    ax.grid(True, which="minor", linestyle="--", linewidth=0.5, axis="y")  # axis='y'
    ax.grid(True, which="major", linestyle="-", linewidth=0.8, axis="x")  # axis='y'


def pearson_corr(ax, x, y):
    pearson_corr = np.corrcoef(np.log10(x), np.log10(y))[0, 1]
    lab = f"{pearson_corr:.2f}"
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    ax.set_ylabel("")
    ax.set_xlabel("")
    ax.annotate(
        lab,
        xy=(0.5, 0.5),
        xycoords="axes fraction",
        verticalalignment="center",
        horizontalalignment="center",
        fontsize="x-large",
    )


def flood_impact_vs_return_pd(
    ax, x, df_wide_flood_impact, lst_rtrns, df_return_pd_cis_flood_impacts, impact_var
):
    min_y = 0.5
    x_aoi = x.name
    y_aoi = y.name
    flood_impact = df_wide_flood_impact[x_aoi]
    flood_impact.name = impact_var

    df_plot = (
        pd.concat([x, flood_impact], axis=1).sort_values(x.name).reset_index(drop=True)
    )

    ax.set_yscale("log")
    ax.set_xscale("linear")

    ax.plot(df_plot[flood_impact.name], df_plot[x.name])

    # xlab = "$y$ ("
    # for substring in flood_impact.name.split("_"):
    #     if "sqm" in substring:
    #         xlab += f"$10^{np.log10(ord_mag):.0f}$ m$^2$)"
    #     else:
    #         xlab += f"{substring} "

    ax.set_title(impact_var)
    ax.set_ylim(min_y, flood_rtrn_pd_support)
    ax.grid(True, axis="y")
    # Add major and minor y-axis gridlines
    ax.grid(True, which="major", linestyle="-", linewidth=0.8, axis="y")  # axis='y'
    ax.grid(True, which="minor", linestyle="--", linewidth=0.5, axis="y")  # axis='y'
    ax.grid(True, which="major", linestyle="-", linewidth=0.8, axis="x")  # axis='y'

    rtrn_mapping_xlims = ax.get_xlim()
    ax.set_xlim(0, rtrn_mapping_xlims[1])

    for idx_rtrn, trgt_rtrn in enumerate(lst_rtrns):
        # s_flood_impact_lims_x = df_return_pd_cis_flood_impacts.loc[pd.IndexSlice[:,x_aoi, depth_range_m, trgt_rtrn]]
        # flood_rtrn_ci_x = (s_flood_impact_lims_x.values.min(), s_flood_impact_lims_x.values.max())

        s_flood_impact_lims_y = df_return_pd_cis_flood_impacts.loc[
            pd.IndexSlice[:, y_aoi, depth_range_m, trgt_rtrn]
        ]
        flood_rtrn_ci_y = (
            s_flood_impact_lims_y.values.min(),
            s_flood_impact_lims_y.values.max(),
        )

        # ax.fill_between([flood_rtrn_ci_x[0], flood_rtrn_ci_x[1]], 1000, color='grey', alpha=0.3)
        ax.fill_betweenx(
            [flood_rtrn_ci_y[0], flood_rtrn_ci_y[1]],
            x1=rtrn_mapping_xlims[1],
            x2=0,
            color="grey",
            alpha=0.3,
        )


def label_xticks_target_return_pd(ax, lst_rtrns, blank=False):
    ax.set_xticks(lst_rtrns)
    newlabs_x = []
    for idx, lab in enumerate(ax.get_xticklabels()):
        if blank:
            lab.set_text("")
        else:
            lab.set_text(str(lst_rtrns[idx]))
        newlabs_x.append(lab)
    ax.set_xticklabels(newlabs_x)


def label_yticks_target_return_pd(ax, lst_rtrns, blank=False):
    ax.set_yticks(lst_rtrns)
    newlabs_y = []
    for idx, lab in enumerate(ax.get_yticklabels()):
        if blank:
            lab.set_text("")
        else:
            lab.set_text(str(lst_rtrns[idx]))
        newlabs_y.append(lab)
    ax.set_yticklabels(newlabs_y)


dir_plots_impact_return_pd_aoi_matrix = (
    f"{DIR_PLOTS_FLOOD_VS_EVENT_PROB}EDA/impact_return_pd_aoi_matrix/"
)
Path(dir_plots_impact_return_pd_aoi_matrix).mkdir(parents=True, exist_ok=True)
min_ax_val = 0.6
n_min_events_worth_plotting = 5

for depth_range_m in ds_flood_impacts_by_aoi.depth_range_m.to_series():
    for impact_var in lst_impact_vars:
        # only keep the last zero flooded index
        df_flood_impacts_by_aoi_depth_range = ds_flood_impacts_by_aoi.sel(
            depth_range_m=depth_range_m
        ).to_dataframe()

        if "flooded_area" in impact_var:
            df_flood_impacts_subset = df_flood_impacts_by_aoi_depth_range.filter(
                like="flooded_area"
            )

        else:
            df_flood_impacts_subset = df_flood_impacts_by_aoi_depth_range.filter(
                like=impact_var
            )
        s_rtrn_pds = df_flood_impacts_by_aoi_depth_range.filter(like="return_pd").iloc[
            :, 0
        ]
        s_impact_val = df_flood_impacts_by_aoi_depth_range[impact_var]
        colname_return = s_rtrn_pds.name

        df_wide = (
            df_flood_impacts_by_aoi_depth_range[colname_return]
            .drop(columns=["depth_range_m"])
            .unstack()
        )  # .T#.droplevel(0)
        df_wide_flood_impact = (
            df_flood_impacts_by_aoi_depth_range[impact_var]
            .drop(columns=["depth_range_m"])
            .unstack()
        )  # .T#.droplevel(0)

        n_events_to_plot = (
            len(df_wide_flood_impact) - (df_wide_flood_impact == 0).sum()
            >= n_min_events_worth_plotting
        )

        df_wide = df_wide.loc[:, n_events_to_plot]
        df_wide_flood_impact = df_wide_flood_impact.loc[:, n_events_to_plot]

        # maximum return period associated with zero flooding
        idx_zero_flooding = s_impact_val[s_impact_val == 0].index
        s_max_rtrn_of_zero_flding = (
            s_rtrn_pds.loc[idx_zero_flooding].groupby(level="subarea_name").max()
        )

        nrows, ncols = df_wide.shape[1], df_wide.shape[1]
        fig, axes = plt.subplots(
            nrows=nrows, ncols=ncols, figsize=(3 * nrows, 3 * ncols), dpi=200
        )

        for row_idx in np.arange(df_wide.shape[1]):
            for col_idx in np.arange(df_wide.shape[1]):
                ax = axes[row_idx, col_idx]
                df_flood_impacts = pd.concat(
                    [
                        df_wide_flood_impact.iloc[:, row_idx],
                        df_wide_flood_impact.iloc[:, col_idx],
                    ],
                    axis=1,
                )
                y = df_wide.iloc[:, row_idx]
                x = df_wide.iloc[:, col_idx]

                # print(f"x and y name at the beginning of the loop: {x.name}, {y.name}")
                max_rtrn_of_zero_flooding_x = s_max_rtrn_of_zero_flding.loc[x.name]
                max_rtrn_of_zero_flooding_y = s_max_rtrn_of_zero_flding.loc[y.name]

                first_column = col_idx == 0
                bottom_row = row_idx == (len(df_wide.columns) - 1)

                if bottom_row:
                    ax.set_xlabel(x.name)
                if first_column:
                    ax.set_ylabel(y.name)

                if row_idx > col_idx:
                    s_nonzero_flooding = df_flood_impacts.sum(axis=1) != 0
                    df_flood_impacts_nonzero = df_wide[s_nonzero_flooding]
                    x_filled_zeros = df_flood_impacts_nonzero.loc[:, x.name].replace(
                        max_rtrn_of_zero_flooding_x, min_ax_val
                    )
                    y_filled_zeros = df_flood_impacts_nonzero.loc[:, y.name].replace(
                        max_rtrn_of_zero_flooding_y, min_ax_val
                    )

                    s_max_rtrn_of_zero_flding
                    # sys.exit("")
                    hexbin_wrapper(
                        ax,
                        x_filled_zeros,
                        y_filled_zeros,
                        flood_rtrn_pd_support,
                        lst_rtrns,
                        df_return_pd_cis_flood_impacts,
                    )
                    if bottom_row:
                        label_xticks_target_return_pd(ax, lst_rtrns, blank=False)
                    else:
                        label_xticks_target_return_pd(ax, lst_rtrns, blank=True)
                    if first_column:
                        label_yticks_target_return_pd(ax, lst_rtrns, blank=False)
                    else:
                        label_yticks_target_return_pd(ax, lst_rtrns, blank=True)
                elif row_idx == col_idx:
                    flood_impact_vs_return_pd(
                        ax,
                        x,
                        df_wide_flood_impact,
                        lst_rtrns,
                        df_return_pd_cis_flood_impacts,
                        impact_var,
                    )
                    if first_column:
                        label_yticks_target_return_pd(ax, lst_rtrns, blank=False)
                    else:
                        label_yticks_target_return_pd(ax, lst_rtrns, blank=True)
                else:
                    pearson_corr(ax, x, y)
                # label axes
                # print(f"x and y name at the end of the loop: {x.name}, {y.name}")
        fig.suptitle(
            f"{dic_dpth_dsc_lookup[depth_range_m]} - {depth_range_m}",
            fontsize="xx-large",
        )
        fig.supylabel("$\\hat{R}_{F}({y})$", fontsize="x-large", x=0)
        fig.supxlabel("$\\hat{R}_{F}({y})$", fontsize="x-large", y=0.01)
        fig.tight_layout()
        sys.exit("work")
        plt.savefig(
            f"{dir_plots_impact_return_pd_aoi_matrix}{dic_dpth_dsc_lookup[depth_range_m]}",
            bbox_inches="tight",
        )
        plt.clf()
