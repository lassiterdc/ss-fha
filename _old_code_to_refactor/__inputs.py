# %% user inputs
import pandas as pd
from pathlib import Path

PLOT_PARAMS = {
    "font.family": "serif",
    "font.serif": "Arial",
    "font.size": 9,
}


LST_DESIGN_STORM_DURATIONS_TO_SIMULATE = [
    6,
    12,
    24,
]  # basing this on available storm durations for the SCS type II unit hyetograph availabe in PCSWMM
RETURN_PERIODS = [
    1,
    2,
    10,
    100,
]  # this can't be changed because this is all that is available for the tide gage return periods
TIMESERIES_BUFFER_BEFORE_FIRST_RAIN_H = 2  # amount to extend time series to ensure at least 2 hours of simulation before first rainfall timestep
ARBIRARY_START_DATE = pd.to_datetime("2025-8-31")  # for final time series
N_YEARS_SYNTHESIZED = 1000
TARGET_DESIGN_STORM_DURATION_HRS_FOR_COMPARISON = 24
ASSIGN_DUP_VALS_MAX_RETURN = False  # if there are duplicate values when computing empirical return periods, assign the max return period to the group?

# directories
dir_stormy = "D:/Dropbox/_GradSchool/_norfolk/stormy/"
dir_ssr = f"{dir_stormy}stochastic_storm_rescaling/"
dir_ffa = f"{dir_stormy}flood_attribution/"
dir_data = f"{dir_stormy}data/"
dir_data_climate = f"{dir_data}climate/"
dir_data_design_events = f"{dir_data_climate}design_events/"
f_wlevel_return_pds = f"{dir_data_design_events}8638610_tidal_datum.csv"
f_rain_idf_pds = f"{dir_data_design_events}idf_table_noaa_atlas_14_estimates.csv"
f_rain_idf_pds_upperbound = (
    f"{dir_data_design_events}idf_table_noaa_atlas_14_estimates_upper_bounds.csv"
)
f_rain_idf_pds_lowerbound = (
    f"{dir_data_design_events}idf_table_noaa_atlas_14_estimates_lower_bounds.csv"
)

# water level dataset
f_noaa_tide_gage_csv = f"{dir_ssr}a_NOAA_water_levels/a_water-lev_tide_surge.csv"

dir_ffa_scripts_local = f"{dir_ffa}local/"
DIR_FFA_SCRIPTS_LOCAL_OUTPUTS = f"{dir_ffa_scripts_local}outputs/"
dir_ffa_scripts_local_scratch = f"{DIR_FFA_SCRIPTS_LOCAL_OUTPUTS}_scratch/"
DIF_FFA_FLOOD_MAPPING = f"{dir_ffa_scripts_local}outputs/b_flood_mapping/"
dif_ffa_ppct = f"{dir_ffa_scripts_local}outputs/b2_ppct/"
dif_ffa_ppct_plots = f"{dif_ffa_ppct}plots/"
dif_ffa_ppct_bs_sim_cdfs = f"{dir_ffa_scripts_local}outputs/b2_ppct/sim_emp_cdf_bs/"
dif_ffa_ppct_bs_corrs = f"{dir_ffa_scripts_local}outputs/b2_ppct/sim_emp_cdf_bs_corrs/"
dif_ffa_ppct_obs = f"{dif_ffa_ppct}obs_ppct_corrs.zarr"
f_zarr_ds_bs_corrs_and_emp_cdf = (
    f"{dir_ffa_scripts_local_scratch}ds_bs_corrs_and_emp_cdf.zarr"
)
dif_ffa_ppct_obs_pvalues = f"{dif_ffa_ppct}emp_vs_fitted_corrs_pvalues.zarr"
dif_ffa_ppct_rej_threshold = f"{dif_ffa_ppct}emp_vs_fitted_corrs_rej_thresh.zarr"
dir_output_design_storm_tseries = (
    f"{DIR_FFA_SCRIPTS_LOCAL_OUTPUTS}a_design_event_tseries/"
)
f_design_storm_tseries_NOAA = (
    f"{dir_output_design_storm_tseries}design_storm_timeseries_NOAA_Atlas_14.nc"
)
F_DESIGN_STORM_TSERIES_BASED_ON_SSR = (
    f"{dir_output_design_storm_tseries}design_storm_timeseries_SSR.nc"
)
# f_dsgn_tseries = f"{dir_input_weather}design_storm_timeseries.nc"

FORMULATION_FOR_MC_DSGN_STRM_SEL_MULTIVAR_AND = "empirical_multivar_rtrn_yrs_AND"
EVENT_STAT_FOR_MC_DSGN_STRM_SEL_MULTIVAR_AND = "1hr,w"
FORMULATION_FOR_MC_DSGN_STRM_SEL_MULTIVAR_OR = "empirical_multivar_rtrn_yrs_OR"
EVENT_STAT_FOR_MC_DSGN_STRM_SEL_MULTIVAR_OR = (
    "24hr,w"  # minimizes MAE; {2hr,w} minimizes MSE
)
FORMULATION_FOR_MC_DSGN_STRM_SEL_UNIVAR = "empirical_univar_return_pd_yrs"
EVENT_STAT_FOR_MC_DSGN_STRM_SEL_UNIVAR = "max_2hr_0min_mm"


# unit hyetographs
f_unit_hyetograph_6hr = f"{dir_data_design_events}unit_hyetograph_scs_tp2_6hr.csv"
f_unit_hyetograph_12hr = f"{dir_data_design_events}unit_hyetograph_scs_tp2_12hr.csv"
f_unit_hyetograph_24hr = f"{dir_data_design_events}unit_hyetograph_scs_tp2_24hr.csv"
COMPRESSION_LEVEL = 5  # for netcdfs
# constants
feet_per_meter = 3.28084
mm_per_inch = 25.4
ALPHA, BETA = 0, 0  # weibull plotting position for empirical quaantiles
target_tstep = "5min"
NUISANCE_THRESHOLD = 0.03  # meters; for flooding plots
MIN_THRESH_FLDING = 0.0025

LST_FLOOD_DEPTH_BIN_EDGES = [0.03, 0.10, 0.30, 1.00]

LST_KEY_FLOOD_THRESHOLDS = [
    MIN_THRESH_FLDING,
    NUISANCE_THRESHOLD,
    0.15,
    0.3,
]  # 0.15 is about 5 inches;
LST_KEY_FLOOD_THRESHOLDS_FOR_SENSITIVITY_ANALYSIS = [
    0.03,
    0.10,
]  # , .3] # nuisance, moderate, major
DIC_DPTH_DSC_LOOKUP = {
    "[0.03,0.1)": "nuisance",
    "[0.1,inf)": "severe",
}  # , "[0.3,inf)":"major"}
DIC_DPTH_COLOR_LOOKUP = {
    "[0.03,0.1)": "#deebf7",
    "[0.1,inf)": "#3182bd",
}  # , "[0.3,inf)":"#3182bd"} # #9ecae1 - middle color
DIC_EVENT_FORM_LABEL_LOOKUP = dict(
    multivar_AND="$AND$", multivar_OR="$OR$", univar="$U$"
)
LST_RTRNS = [2, 10, 100]
LST_RTRN_PD_COLORS = ["#ffeda0", "#feb24c", "#f03b20"]
LST_RTRNS_ALL = [1, 2, 10, 100]
# LST_RTRN_PD_COLORS = ["#ffffd4", "#fed98e", "#fe9929", "#cc4c02"]
ppct_alpha = 0.05
N_BS_SAMPLES = 500  # for ppct
max_return_period_to_plot = 100  # based on the total number of simulations run
FLD_RTRN_PD_ALPHA = 0.1  # this corresponds to a 90% confidence interval which is what is reported in NOAA Atlas 14 IDF tables
RAIN_WINDOWS_MIN = [
    5,
    15,
    30,
    1 * 60,
    2 * 60,
    4 * 60,
    6 * 60,
    12 * 60,
    24 * 60,
    48 * 60,
]  # for relating event return periods to flood return periods
FLOOD_RTRN_PD_SUPPORT = 300  # ignore flood return periods above this threshold

# model outputs
dir_model_scenarios = f"{dir_ffa}model_scenarios/"
F_TRITON_OUTPUTS = f"{dir_model_scenarios}triton_tritonswmm_allsims_sim_triton.zarr"
F_TRITON_OUTPUTS_OBS = f"{dir_model_scenarios}triton_tritonswmm_allsims_obs_triton.zarr"
F_TRITON_OUTPUTS_DSGN = (
    f"{dir_model_scenarios}triton_tritonswmm_allsims_dsgn_triton.zarr"
)
# f_triton_outputs = f"{dir_ffa}tritonswmm_allsims_triton.zarr"
dir_temp_zarrs = f"{dir_ffa}_scratch/zarrs/"

# for validation in norfolk
f_tritonswmm_obs = (
    f"{dir_ffa}norfolk_tritonswmm_validation/tritonswmm_sim_rslts_obsrvd.zarr"
)

SUBAREAS_FOR_COMPUTING_IMPACT_RETURN_PDS = ["watershed"]
# flood mapping
PATTERN_EVENT_NUMBER_MAPPING = DIF_FFA_FLOOD_MAPPING + "event_number_mapping_{}_{}.csv"
F_SIM_FLOOD_PROBS_COMPARE = f"{DIF_FFA_FLOOD_MAPPING}flood_probs_sim_comparison.zarr"
F_SIM_FLOOD_PROBS = f"{DIF_FFA_FLOOD_MAPPING}flood_probs_sim.zarr"
F_SIM_FLOOD_PROBS_SURGEONLY = f"{DIF_FFA_FLOOD_MAPPING}flood_probs_sim_surgeonly.zarr"
F_SIM_FLOOD_PROBS_RAINONLY = f"{DIF_FFA_FLOOD_MAPPING}flood_probs_sim_rainonly.zarr"
F_SIM_FLOOD_PROBS_TRITON = f"{DIF_FFA_FLOOD_MAPPING}flood_probs_sim_triton.zarr"
# f_sim_max_wlevel_stacked = f"{DIF_FFA_FLOOD_MAPPING}max_wlevel_sim_stacked.zarr"
F_SIM_FLOOD_PROBS_EVENT_NUMBER_MAPPING = (
    f"{DIF_FFA_FLOOD_MAPPING}flood_probs_sim_event_number_mapping.csv"
)
F_SIM_FLOOD_PROBS_BOOTSTRAPPED = (
    f"{DIF_FFA_FLOOD_MAPPING}flood_probs_sim_bootstrapped.zarr"
)
F_SIM_FLOOD_PROBS_BOOTSTRAPPED_CIS = (
    f"{DIF_FFA_FLOOD_MAPPING}flood_probs_sim_bootstrapped_CIs.zarr"
)
F_SIM_FLOOD_PROBS_BOOTSTRAPPED_CIS_TRITONONLY = (
    f"{DIF_FFA_FLOOD_MAPPING}flood_probs_sim_bootstrapped_CIs_tritononly.zarr"
)

F_SIM_FLOOD_PROBS_BOOTSTRAPPED_TRITONONLY = (
    f"{DIF_FFA_FLOOD_MAPPING}flood_probs_sim_bootstrapped_tritononly.zarr"
)
F_SIM_FLOOD_PROBS_CI = f"{DIF_FFA_FLOOD_MAPPING}flood_probs_sim_ci.zarr"
f_obs_flood_probs = f"{DIF_FFA_FLOOD_MAPPING}flood_probs_obs.zarr"
F_OBS_FLOOD_PROBS_EVENT_NUMBER_MAPPING = (
    f"{DIF_FFA_FLOOD_MAPPING}event_number_mapping_obs_compound.csv"
)

F_RTRN_PDS_RAINFALL = (
    f"{DIF_FFA_FLOOD_MAPPING}empirical_ensemble_rainfall_return_periods.csv"
)
F_RTRN_PDS_SEA_WATER_LEVEL = (
    f"{DIF_FFA_FLOOD_MAPPING}empirical_ensemble_seawlevel_return_periods.csv"
)

F_SIM_MULTIVAR_RETURN_PERIODS = (
    f"{DIF_FFA_FLOOD_MAPPING}sim_multivariate_return_periods.zarr"
)

# f_flooded_areas_return_pds_by_aoi_and_dpth_rnge = f"{DIF_FFA_FLOOD_MAPPING}flooded_areas_by_event_and_aoi.zarr"
F_FLOOD_IMPACT_RETURN_PERIODS_BY_AOI = (
    f"{DIF_FFA_FLOOD_MAPPING}flood_impact_return_periods_by_aoi.zarr"
)
F_IMPACTED_FEATURE_MIN_RETURN_PDS = (
    f"{DIF_FFA_FLOOD_MAPPING}impacted_feature_min_return_pds.zarr"
)


# bootstrapped confidence intervals
DIR_SIM_FLOOD_PROBS_BOOTSTRAPPING = f"{DIF_FFA_FLOOD_MAPPING}bs_samples_ensemble/"
DIR_SIM_FLOOD_PROBS_BOOTSTRAPPING_TRITONONLY = (
    f"{DIF_FFA_FLOOD_MAPPING}bs_samples_ensemble_tritononly/"
)
# dif_bs_ = f"{dir_ffa_scripts_local}outputs/b2_ppct/sim_emp_cdf_bs/"


# input weather
dir_input_weather = f"{dir_ffa}weather/"
# dir_input_weather = f"{dir_ffa}weather/2024-12-16_archive/"
# print("Warning: using archived weather data during process development")
F_SIM_SMRIES = f"{dir_input_weather}combined_simulation_summaries.csv"
F_SIM_TSERIES = f"{dir_input_weather}combined_simulation_time_series.nc"


f_obs_smries = (
    f"{dir_input_weather}obs_event_summaries_from_yrs_with_complete_coverage.csv"
)
F_OBS_TSERIES = (
    f"{dir_input_weather}obs_event_tseries_from_yrs_with_complete_coverage.nc"
)

dif_ffa_ppct = f"{dir_ffa_scripts_local}outputs/b2_ppct/"

COORD_EPSG = "32147"
ENSEMBLE_RETURN_PD_UB = (
    125  # this is the upper bound of the return periods included in some plots
)
# watershed shapefile
# f_wshed_shp = f"{dir_stormy}triton-swmm/inputs/swmm/watershed/norfolk_wshed_epsg32147_state_plane_m.shp"
F_WSHED_SHP = f"{dir_stormy}data/geospatial/watershed.shp"
F_RASTER_FEMA_100YR_DEPTHS = f"{dir_stormy}data/geospatial/fema/100yr_depths_m.tif"
#
dir_ensemble_design_events = f"{dir_ffa}/ensemble_derived_design_events/"
dir_ensemble_flood_map_rasters = f"{dir_ensemble_design_events}rasters_flood_maps/"
F_MITIGATION_AOIS = f"{dir_ensemble_design_events}aoi_shapefile/aoi.shp"
dir_scratch_zarr_files = f"{dir_ensemble_design_events}_scratch_zarrs/"

FPATH_ENSEMBLE_DESIGN_FLOODS = (
    f"{dir_ensemble_design_events}ensemble_based_return_pd_floods.nc"
)

FPATH_MC_DESIGN_FLOODS_MULTIVAR_AND = (
    f"{dir_ensemble_design_events}mcds_return_pd_floods_multivar.nc"
)

FPATH_MC_DESIGN_FLOODS_MULTIVAR_OR = (
    f"{dir_ensemble_design_events}mcds_return_pd_floods_multivar_OR.nc"
)

FPATH_MC_DESIGN_FLOODS_UNIVAR = (
    f"{dir_ensemble_design_events}mcds_return_pd_floods_univar.nc"
)

MC_QUANTS_FOR_FLOOD_MAPPING = [0.05, 0.5, 0.95]

# flood metric shapefiles
dir_geospatial_data = (
    "D:/Dropbox/_GradSchool/_norfolk/norfolk_ffa/data/processed/for_flood_metrics/"
)
F_ROADS = f"{dir_geospatial_data}roads_clipped.shp"

# f_roads = f"{dir_geospatial_data}roads_clipped_buffered.shp"
F_BUILDINGS_NO_BUFFER = f"{dir_geospatial_data}va_buildings_clipped.shp"
F_BUILDINGS = f"{dir_geospatial_data}va_buildings_clipped_buffered.shp"


F_PARCELS = f"{dir_geospatial_data}parcels_clipped.shp"

F_SIDEWALKS = f"{dir_geospatial_data}sidewalks_clipped.shp"


# comparing event return periods to flood return periods
## correlatoins between flooded areas by depth and location and different event return period formulations
LST_CORRS_IDX = [
    "impact_var",
    "subarea_name",
    "event_stat_type",
    "depth_range_m",
    "corr_method",
]
LST_ERRS_IDX = [
    "impact_var",
    "subarea_name",
    "event_stat_type",
    "depth_range_m",
    "err_method",
]

DIR_FLOOD_PROB_VS_EVENT_PROB = (
    f"{DIR_FFA_SCRIPTS_LOCAL_OUTPUTS}comparing_flood_probs_to_event_probs/"
)
F_CORRS_UNIVARIATE_EVENT_VS_FLOOD_RETURN_PDS_BY_AOI = (
    f"{DIR_FLOOD_PROB_VS_EVENT_PROB}corrs_univar_event_vs_fld_rtrn_pds_by_aoi.csv"
)
F_CORRS_MULTIVAR_EVENT_VS_FLOOD_RETURN_PDS_BY_AOI = (
    f"{DIR_FLOOD_PROB_VS_EVENT_PROB}corrs_multivar_event_vs_fld_rtrn_pds_by_aoi.csv"
)
F_ERRS_UNIVARIATE_EVENT_VS_FLOOD_RETURN_PDS_BY_AOI = (
    f"{DIR_FLOOD_PROB_VS_EVENT_PROB}errs_univar_event_vs_fld_rtrn_pds_by_aoi.csv"
)
F_ERRS_MULTIVAR_EVENT_VS_FLOOD_RETURN_PDS_BY_AOI = (
    f"{DIR_FLOOD_PROB_VS_EVENT_PROB}errs_multivar_event_vs_fld_rtrn_pds_by_aoi.csv"
)

DIR_PLOTS_FLOOD_VS_EVENT_PROB = f"{DIR_FLOOD_PROB_VS_EVENT_PROB}plots/"
Path(DIR_PLOTS_FLOOD_VS_EVENT_PROB).mkdir(parents=True, exist_ok=True)

F_WEATHER_EVENT_VS_IMPACT_EVENT_CLASSIFICATION = (
    f"{DIR_FLOOD_PROB_VS_EVENT_PROB}weather_event_vs_impact_event_classification.csv"
)

# scratch folders
scrtch_dirname = "_scratch"
# scrtch_dirname = "_scratch_backup_2025-3-12"
# print("warning: using archived data for confidence intervals while bootstrap samples are being redrawn")

DIR_SCRATCH_MULTVAR_EVENT_RTRN_BS = (
    f"{DIR_FLOOD_PROB_VS_EVENT_PROB}{scrtch_dirname}/multivar_event_bs_samps/"
)
DIR_SCRATCH_UNIVAR_EVENT_RTRN_BS = (
    f"{DIR_FLOOD_PROB_VS_EVENT_PROB}{scrtch_dirname}/univar_event_bs_samps/"
)
F_SCRATCH_FLOODAREA_RTRN_BS = (
    f"{DIR_FLOOD_PROB_VS_EVENT_PROB}{scrtch_dirname}/flood_area_bs_samps.csv"
)

Path(DIR_SCRATCH_MULTVAR_EVENT_RTRN_BS).mkdir(parents=True, exist_ok=True)
Path(DIR_SCRATCH_UNIVAR_EVENT_RTRN_BS).mkdir(parents=True, exist_ok=True)

F_MULTIVAR_BS_UNCERTAINTY_CI = (
    f"{DIR_FLOOD_PROB_VS_EVENT_PROB}bs_uncertainty_multivar_ci.csv"
)
# f_multivar_bs_uncertainty_events_in_ci = f"{DIR_FLOOD_PROB_VS_EVENT_PROB}bs_uncertainty_multivar_ci_events.csv"
# f_multivar_bs_uncertainty_all_unique_events = f"{DIR_FLOOD_PROB_VS_EVENT_PROB}bs_uncertainty_multivar_unique_events.csv"


F_UNIVAR_BS_UNCERTAINTY_CI = (
    f"{DIR_FLOOD_PROB_VS_EVENT_PROB}bs_uncertainty_univar_ci.csv"
)
# f_univar_bs_uncertainty_all_unique_events = f"{DIR_FLOOD_PROB_VS_EVENT_PROB}bs_uncertainty_univar_unique_events.csv"

F_BS_UNCERTAINTY_EVENTS_IN_CI = (
    f"{DIR_FLOOD_PROB_VS_EVENT_PROB}bs_uncertainty_ci_events.csv"
)

F_FLOOD_IMPACT_BS_UNCERTAINTY_CI = (
    f"{DIR_FLOOD_PROB_VS_EVENT_PROB}bs_uncertainty_flood_impact_ci.csv"
)
# f_floodarea_bs_uncertainty_all_unique_events = f"{DIR_FLOOD_PROB_VS_EVENT_PROB}bs_uncertainty_floodareea_unique_events.csv"
F_FLOOD_IMPACT_BS_UNCERTAINTY_EVENTS_IN_CI = (
    f"{DIR_FLOOD_PROB_VS_EVENT_PROB}bs_uncertainty_flood_impact_events_in_ci.csv"
)


DIR_IMPACT_BASED_FFA = f"{dir_ffa_scripts_local}outputs/impact_based_ffa/"


# experimental design stuff
F_EXPERIMENT_DESIGN = (
    f"{dir_model_scenarios}experiment_setups_for_parallel_axis_plots.xlsx"
)
