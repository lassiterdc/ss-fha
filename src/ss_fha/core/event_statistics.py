"""Core event statistics computation functions.

All functions here are pure computation — no I/O, no file operations,
no side effects. They operate on already-loaded pandas objects and return
pandas objects or numpy arrays.

Multivariate return period semantics
--------------------------------------
Two exceedance definitions are supported for multivariate return periods.
Both are computed in complement (non-exceedance) space and converted to
return periods via ``calculate_return_period`` from ``empirical_frequency_analysis``.

For threshold vector z = (z1, z2, ...):

AND exceedance
    E_AND = {X1 > z1 AND X2 > z2 AND ...}  — all drivers simultaneously exceed.
    Complement: E_AND^c = {X1 <= z1 OR X2 <= z2 OR ...}
    Implemented with ``.any(axis=1)`` (OR logic in complement space).
    F_AND >= F_OR  =>  p_exceed_AND <= p_exceed_OR  =>  RP_AND >= RP_OR
    AND gives the *longer* (rarer) return period.

OR exceedance
    E_OR = {X1 > z1 OR X2 > z2 OR ...}  — at least one driver exceeds.
    Complement: E_OR^c = {X1 <= z1 AND X2 <= z2 AND ...}
    Implemented with ``.all(axis=1)`` (AND logic in complement space).
    F_OR <= F_AND  =>  p_exceed_OR >= p_exceed_AND  =>  RP_OR <= RP_AND
    OR gives the *shorter* (more common) return period.

The naming is counterintuitive because the boolean operator refers to the
exceedance event, but the implementation operates on the complement. See
``_work/figuring_out_multivariate_return_periods.py`` for a worked example
and sanity-check assertions.

Duplicate value handling
------------------------
``ASSIGN_DUP_VALS_MAX_RETURN`` (from ``ss_fha.constants``) controls whether
events with identical statistic values are all assigned the maximum return
period of their group (True) or receive progressively increasing CDF values
(False). Always False for Norfolk. The semantically correct choice for other
case studies is unresolved. Promote to ``SsfhaConfig`` when resolved.
"""

from __future__ import annotations

import sys
from itertools import combinations
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd

from ss_fha.constants import ASSIGN_DUP_VALS_MAX_RETURN, WEATHER_EVENT_INDEX_YEAR_ALIASES
from ss_fha.core.empirical_frequency_analysis import (
    calculate_return_period,
    compute_return_periods_for_series,
)
from ss_fha.exceptions import ComputationError

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _shorten_rain_stat_name(varname: str) -> str:
    """Convert a rainfall statistic column name to a compact label.

    Examples
    --------
    ``"max_24hr_0min_mm"``  →  ``"24hr"``
    ``"max_0hr_5min_mm"``   →  ``"5min"``
    """
    # Strip leading "max_" and trailing "_mm"
    core = varname
    if core.startswith("max_"):
        core = core[4:]
    if core.endswith("_mm"):
        core = core[:-3]
    # Collapse "0hr_Xmin" → "Xmin" and "Xhr_0min" → "Xhr"
    if core.startswith("0hr_"):
        core = core[4:]   # e.g. "5min"
    elif core.endswith("_0min"):
        core = core[:-5]  # e.g. "24hr"
    return core


# ---------------------------------------------------------------------------
# AND / OR multivariate return period (reference — apply-based, O(n²) in Python)
# ---------------------------------------------------------------------------

def _compute_AND_multivar_return_period_for_sample(
    sample_values: pd.Series,
    df_all_samples: pd.DataFrame,
    n_samples: int,
    alpha: float,
    beta: float,
) -> float:
    """Empirical non-exceedance for the AND exceedance definition.

    For threshold vector z = (z1, z2, ...):
      AND exceedance event: E_AND = {X1 > z1 AND X2 > z2 AND ...}
      Complement:           E_AND^c = {X1 <= z1 OR  X2 <= z2 OR ...}

    This function estimates F_AND(z) = P(E_AND^c), i.e., the non-exceedance
    probability associated with AND exceedance.

    Notes
    -----
    - ``.any(axis=1)`` is OR logic in complement space.
    - Exceedance probability is p_exceed_AND = 1 - F_AND.
    - Return period is RP_AND = 1 / p_exceed_AND.
    - At the same threshold z: F_AND >= F_OR => RP_AND >= RP_OR.
      AND gives the *longer* (rarer) return period.
    """
    df_exceedance = df_all_samples <= sample_values
    # Complement of AND exceedance: at least one variable is <= threshold.
    n_1_lessthan_or_equal_to = df_exceedance.any(axis=1).sum()
    emp_cdf_val_AND = (n_1_lessthan_or_equal_to - alpha) / (
        n_samples + 1 - alpha - beta
    )
    return emp_cdf_val_AND


def _compute_OR_multivar_return_period_for_sample(
    sample_values: pd.Series,
    df_all_samples: pd.DataFrame,
    n_samples: int,
    alpha: float,
    beta: float,
) -> float:
    """Empirical non-exceedance for the OR exceedance definition.

    For threshold vector z = (z1, z2, ...):
      OR exceedance event: E_OR = {X1 > z1 OR  X2 > z2 OR ...}
      Complement:          E_OR^c = {X1 <= z1 AND X2 <= z2 AND ...}

    This function estimates F_OR(z) = P(E_OR^c), i.e., the non-exceedance
    probability associated with OR exceedance.

    Notes
    -----
    - ``.all(axis=1)`` is AND logic in complement space.
    - Exceedance probability is p_exceed_OR = 1 - F_OR.
    - Return period is RP_OR = 1 / p_exceed_OR.
    - At the same threshold z: F_OR <= F_AND => RP_OR <= RP_AND.
      OR gives the *shorter* (more common) return period.
    """
    df_exceedance = df_all_samples <= sample_values
    # Complement of OR exceedance: all variables are <= threshold simultaneously.
    n_all_lessthan_or_equal_to = df_exceedance.all(axis=1).sum()
    emp_cdf_val_OR = (n_all_lessthan_or_equal_to - alpha) / (
        n_samples + 1 - alpha - beta
    )
    return emp_cdf_val_OR


def _empirical_multivariate_return_periods_reference(
    df_samples: pd.DataFrame,
    n_years: int,
    alpha: float,
    beta: float,
) -> pd.DataFrame:
    """Compute empirical multivariate return periods using the apply-based reference method.

    PORTED FUNCTION FOR TESTING THE REFACTORING. This is the direct port of the
    original implementation from ``_old_code_to_refactor/__utils.py``. It is O(n²)
    in Python function-call overhead and is kept only for validation against the
    vectorized implementation. Do not use in production code.

    See ``empirical_multivariate_return_periods`` for the public vectorized version.
    """
    n_samples = len(df_samples)
    s_emp_cdf_AND = df_samples.apply(
        _compute_AND_multivar_return_period_for_sample,
        axis=1,
        df_all_samples=df_samples,
        n_samples=n_samples,
        alpha=alpha,
        beta=beta,
    )
    s_emp_cdf_OR = df_samples.apply(
        _compute_OR_multivar_return_period_for_sample,
        axis=1,
        df_all_samples=df_samples,
        n_samples=n_samples,
        alpha=alpha,
        beta=beta,
    )
    s_emp_cdf_AND.name = "empirical_multivar_cdf_AND"
    s_emp_cdf_OR.name = "empirical_multivar_cdf_OR"

    if ASSIGN_DUP_VALS_MAX_RETURN:
        val_cols = list(df_samples.columns)
        df_result = pd.concat([df_samples, s_emp_cdf_AND, s_emp_cdf_OR], axis=1)
        idx_max_rtrn_by_val = df_result.groupby(val_cols).idxmax()
        df_result_maxcdf_OR = (
            df_result.loc[
                idx_max_rtrn_by_val[s_emp_cdf_OR.name], val_cols + [s_emp_cdf_OR.name]
            ]
            .reset_index(drop=True)
            .set_index(val_cols)
        )
        df_result_maxcdf_AND = (
            df_result.loc[
                idx_max_rtrn_by_val[s_emp_cdf_AND.name], val_cols + [s_emp_cdf_AND.name]
            ]
            .reset_index(drop=True)
            .set_index(val_cols)
        )
        s_emp_cdf_OR = df_samples.join(df_result_maxcdf_OR, how="left", on=val_cols)[
            s_emp_cdf_OR.name
        ]
        s_emp_cdf_AND = df_samples.join(df_result_maxcdf_AND, how="left", on=val_cols)[
            s_emp_cdf_AND.name
        ]

    rtrn_pds_AND = calculate_return_period(
        s_emp_cdf_AND.to_numpy(), n_years=n_years, n_events=n_samples
    )
    rtrn_pds_OR = calculate_return_period(
        s_emp_cdf_OR.to_numpy(), n_years=n_years, n_events=n_samples
    )

    df_out = pd.concat([s_emp_cdf_AND, s_emp_cdf_OR], axis=1)
    df_out["empirical_multivar_rtrn_yrs_AND"] = rtrn_pds_AND
    df_out["empirical_multivar_rtrn_yrs_OR"] = rtrn_pds_OR
    return df_out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def empirical_multivariate_return_periods(
    df_samples: pd.DataFrame,
    n_years: int,
    alpha: float,
    beta: float,
) -> pd.DataFrame:
    """Compute empirical multivariate return periods using a vectorized numpy implementation.

    For each event, computes the AND and OR non-exceedance CDF values and
    their corresponding return periods. See module docstring for AND/OR semantics.

    The vectorized implementation replaces the O(n²) Python ``apply`` loop with a
    single numpy broadcast operation, achieving ~50–200× speedup for typical
    ensemble sizes (n ≈ 1000).

    Memory note: the intermediate boolean array is shape (n, n, n_vars). At n=1000
    and 3 variables this is ~3 MB. At n=10,000 it reaches ~3 GB — consider chunked
    processing if ensemble sizes approach that scale.

    Parameters
    ----------
    df_samples:
        DataFrame where each row is an event and each column is a weather driver
        statistic (e.g. max rainfall intensity, peak water level). Index must be
        the weather event multi-index.
    n_years:
        Total synthesized years in the weather model run. Denominator for return
        period calculations.
    alpha:
        Plotting position parameter (Weibull: 0.0).
    beta:
        Plotting position parameter (Weibull: 0.0).

    Returns
    -------
    pd.DataFrame
        Same index as ``df_samples``. Columns:
        ``empirical_multivar_cdf_AND``, ``empirical_multivar_cdf_OR``,
        ``empirical_multivar_rtrn_yrs_AND``, ``empirical_multivar_rtrn_yrs_OR``.
    """
    n_samples = len(df_samples)
    vals = df_samples.values  # (n, n_vars)

    # Broadcast pairwise comparison: comparisons[i, j, v] is True when
    # event j's variable v is <= event i's variable v (i.e. j is "not more
    # extreme than i" in variable v).
    # Shape: (n_events, n_events, n_vars)
    comparisons = vals[np.newaxis, :, :] <= vals[:, np.newaxis, :]

    # AND non-exceedance: for event i, count events j where any variable of j
    # is <= i (complement of "all variables of j exceed i").
    and_counts = comparisons.any(axis=2).sum(axis=1).astype(float)  # (n,)

    # OR non-exceedance: for event i, count events j where all variables of j
    # are <= i simultaneously (complement of "at least one variable of j exceeds i").
    or_counts = comparisons.all(axis=2).sum(axis=1).astype(float)   # (n,)

    emp_cdf_AND = (and_counts - alpha) / (n_samples + 1 - alpha - beta)
    emp_cdf_OR  = (or_counts  - alpha) / (n_samples + 1 - alpha - beta)

    if ASSIGN_DUP_VALS_MAX_RETURN:
        val_cols = list(df_samples.columns)
        s_and = pd.Series(emp_cdf_AND, index=df_samples.index, name="empirical_multivar_cdf_AND")
        s_or  = pd.Series(emp_cdf_OR,  index=df_samples.index, name="empirical_multivar_cdf_OR")
        df_result = pd.concat([df_samples, s_and, s_or], axis=1)
        idx_max_and = df_result.groupby(val_cols)[s_and.name].idxmax()  # type: ignore[index]
        idx_max_or  = df_result.groupby(val_cols)[s_or.name].idxmax()   # type: ignore[index]
        df_maxand = df_result.loc[idx_max_and, val_cols + [s_and.name]].reset_index(drop=True).set_index(val_cols)
        df_maxor  = df_result.loc[idx_max_or,  val_cols + [s_or.name]].reset_index(drop=True).set_index(val_cols)
        emp_cdf_AND = cast(np.ndarray, df_samples.join(df_maxand, how="left", on=val_cols)[s_and.name].to_numpy())
        emp_cdf_OR  = cast(np.ndarray, df_samples.join(df_maxor,  how="left", on=val_cols)[s_or.name].to_numpy())

    rtrn_pds_AND = calculate_return_period(emp_cdf_AND, n_years=n_years, n_events=n_samples)
    rtrn_pds_OR  = calculate_return_period(emp_cdf_OR,  n_years=n_years, n_events=n_samples)

    return pd.DataFrame(
        {
            "empirical_multivar_cdf_AND": emp_cdf_AND,
            "empirical_multivar_cdf_OR":  emp_cdf_OR,
            "empirical_multivar_rtrn_yrs_AND": rtrn_pds_AND,
            "empirical_multivar_rtrn_yrs_OR":  rtrn_pds_OR,
        },
        index=df_samples.index,
    )


def compute_univariate_event_return_periods(
    ds_sim_tseries,
    weather_event_indices: list[str],
    precip_varname: str,
    stage_varname: str | None,
    rain_windows_min: list[int],
    n_years: int,
    alpha: float,
    beta: float,
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Compute empirical univariate return periods for rainfall and surge event statistics.

    For each rainfall accumulation window in ``rain_windows_min``, computes the
    maximum accumulated depth over that window for every event and derives its
    empirical return period. If ``stage_varname`` is provided, also computes the
    peak boundary stage return period.

    Parameters
    ----------
    ds_sim_tseries:
        xarray Dataset with a timestep dimension and weather event dimensions
        matching ``weather_event_indices``. Must contain ``precip_varname`` and
        optionally ``stage_varname``.
    weather_event_indices:
        List of dimension names identifying weather events (e.g.
        ``["event_type", "year", "event_id"]``). Used for all subsetting — these
        names are never hardcoded.
    precip_varname:
        Variable name for precipitation intensity in ``ds_sim_tseries``
        (e.g. ``"mm_per_hr"``).
    stage_varname:
        Variable name for boundary stage in ``ds_sim_tseries``
        (e.g. ``"waterlevel_m"``). Pass ``None`` for rain-only analyses.
    rain_windows_min:
        List of rolling-window durations in minutes for rainfall accumulation.
    n_years:
        Total synthesized years in the weather model run. Denominator for return
        period calculations.
    alpha:
        Plotting position parameter (Weibull: 0.0).
    beta:
        Plotting position parameter (Weibull: 0.0).

    Returns
    -------
    df_rain_return_pds:
        DataFrame indexed by weather event multi-index with columns for each
        rain window statistic value, empirical CDF, and return period.
    df_stage_return_pds:
        DataFrame indexed by weather event multi-index with peak stage statistic,
        empirical CDF, and return period. ``None`` if ``stage_varname`` is ``None``.
    """
    # Determine valid events: those with at least one non-NaN precip value
    idx_valid_events = (
        ds_sim_tseries.isel(timestep=0)[precip_varname]
        .to_dataframe()[precip_varname]
        .dropna()
        .index
    )

    # Compute timestep duration in hours from the time series
    tstep_vals = ds_sim_tseries.timestep.values
    sim_tstep_hr = float(
        pd.Series(tstep_vals).diff().mode().iloc[0] / np.timedelta64(1, "h")
    )

    lst_df_rain: list[pd.DataFrame] = []
    for rain_window_min in rain_windows_min:
        rain_window_h = rain_window_min / 60
        # Build a compact variable name from window duration
        if rain_window_h >= 1:
            sfx = f"{int(rain_window_h)}hr_0min"
        else:
            sfx = f"0hr_{int(rain_window_min)}min"
        varname = f"max_{sfx}_mm"

        tsteps_per_window = int(rain_window_h / sim_tstep_hr)
        da_max_depth = (
            (ds_sim_tseries[precip_varname] * sim_tstep_hr)
            .fillna(0)
            .rolling(timestep=tsteps_per_window, min_periods=1)
            .sum()
            .max(dim="timestep")
        )
        _df_max = cast(
            pd.DataFrame,
            da_max_depth.to_dataframe()[precip_varname]
            .reset_index()
            .drop_duplicates()
            .set_index(weather_event_indices)
            .loc[idx_valid_events],
        )
        s_max = _df_max[precip_varname]
        s_max.name = varname
        df_rain = compute_return_periods_for_series(
            s_max, n_years, alpha, beta, assign_dup_vals_max_return=ASSIGN_DUP_VALS_MAX_RETURN
        )
        lst_df_rain.append(df_rain)

    df_rain_return_pds = pd.concat(lst_df_rain, axis=1)

    if stage_varname is None:
        return df_rain_return_pds, None

    s_peak_stage = (
        ds_sim_tseries[stage_varname]
        .max("timestep")
        .to_dataframe()[stage_varname]
        .dropna()
    )
    s_peak_stage.name = f"max_{stage_varname}"
    df_stage_return_pds = compute_return_periods_for_series(
        s_peak_stage, n_years, alpha, beta, assign_dup_vals_max_return=ASSIGN_DUP_VALS_MAX_RETURN
    )
    return df_rain_return_pds, df_stage_return_pds


def compute_all_multivariate_return_period_combinations(
    df_rain_return_pds: pd.DataFrame,
    df_stage_return_pds: pd.DataFrame | None,
    n_years: int,
    alpha: float,
    beta: float,
) -> pd.DataFrame:
    """Compute empirical multivariate return periods for all bi- and tri-variate combinations.

    Generates all unique combinations of 2 and 3 event statistics (rain windows
    and optionally boundary stage) and computes AND/OR joint return periods for each.
    There is no constraint on which variables must appear — all combinations are
    computed. For large numbers of event statistics this can be computationally
    intensive; use the timing infrastructure in runner scripts to monitor wall-clock cost.

    Parameters
    ----------
    df_rain_return_pds:
        Output of ``compute_univariate_event_return_periods`` for rainfall.
    df_stage_return_pds:
        Output of ``compute_univariate_event_return_periods`` for boundary stage.
        Pass ``None`` for rain-only analyses (only rainfall combinations computed).
    n_years:
        Total synthesized years. Denominator for return period calculations.
    alpha:
        Plotting position parameter (Weibull: 0.0).
    beta:
        Plotting position parameter (Weibull: 0.0).

    Returns
    -------
    pd.DataFrame
        MultiIndex: ``(event_stats, *weather_event_index_levels)``.
        Columns: ``empirical_multivar_cdf_AND``, ``empirical_multivar_cdf_OR``,
        ``empirical_multivar_rtrn_yrs_AND``, ``empirical_multivar_rtrn_yrs_OR``.
    """
    # Extract value columns (not emp_cdf or return_pd)
    def _val_cols(df: pd.DataFrame) -> list[str]:
        return [
            c for c in df.columns
            if ("emp_cdf" not in c) and ("return_pd_yrs" not in c)
        ]

    rain_val_cols = _val_cols(df_rain_return_pds)
    df_rain_vals = df_rain_return_pds[rain_val_cols]

    if df_stage_return_pds is not None:
        if df_stage_return_pds.isna().any().any():
            raise ComputationError(
                "compute_all_multivariate_return_period_combinations: NaN values in stage return periods."
            )
        stage_val_cols = _val_cols(df_stage_return_pds)
        df_stage_vals = df_stage_return_pds[stage_val_cols]
        # Combined pool of all statistics
        df_all_vals = pd.concat([df_stage_vals, df_rain_vals], axis=1)
    else:
        df_all_vals = df_rain_vals

    if df_rain_return_pds.isna().any().any():
        raise ComputationError(
            "compute_all_multivariate_return_period_combinations: NaN values in rain return periods."
        )

    all_stat_cols = list(df_all_vals.columns)

    # Shorten column names to compact event_stat labels
    def _label(col: str) -> str:
        # stage column: "max_waterlevel_m" → "w"
        if col.startswith("max_") and col.endswith("_m") and "mm" not in col:
            return "w"
        return _shorten_rain_stat_name(col)

    col_to_label = {col: _label(col) for col in all_stat_cols}

    dic_multivar = {}
    for r in (2, 3):
        for combo in combinations(all_stat_cols, r):
            labels = [col_to_label[c] for c in combo]
            # Sort labels so that shorter windows appear first; "w" sorts last
            def _minutes(lbl: str) -> int:
                if lbl == "w":
                    return sys.maxsize
                if "hr" in lbl:
                    return int(lbl.replace("hr", "")) * 60
                return int(lbl.replace("min", ""))
            labels_sorted = sorted(labels, key=_minutes)
            stat_name = ",".join(labels_sorted)
            if stat_name in dic_multivar:
                continue  # already computed (same label order from different column order)
            df_combo = df_all_vals.loc[:, list(combo)]
            dic_multivar[stat_name] = empirical_multivariate_return_periods(
                df_combo, n_years=n_years, alpha=alpha, beta=beta
            )

    lst_df = []
    for event_stat, df_rp in dic_multivar.items():
        df_rp = df_rp.copy()
        df_rp["event_stats"] = event_stat
        df_rp = df_rp.reset_index().set_index(
            ["event_stats"] + list(df_rain_return_pds.index.names)
        )
        lst_df.append(df_rp)

    return pd.concat(lst_df)


def bs_samp_of_univar_event_return_period(
    bs_id: int,
    ds_sim_tseries,
    df_rain_return_pds_og: pd.DataFrame,
    df_stage_return_pds_og: pd.DataFrame | None,
    weather_event_indices: list[str],
    precip_varname: str,
    stage_varname: str | None,
    rain_windows_min: list[int],
    n_years: int,
    alpha: float,
    beta: float,
    target_return_periods: list[int | float],
) -> pd.DataFrame:
    """Draw one bootstrap sample of univariate event return periods.

    Resamples years with replacement, recomputes univariate return periods on
    the resampled ensemble, and for each event statistic and target return period
    identifies the event closest to that return period in the bootstrap sample.

    Parameters
    ----------
    bs_id:
        Bootstrap sample identifier (integer, 0-indexed).
    ds_sim_tseries:
        Full simulated weather time series Dataset.
    df_rain_return_pds_og:
        Original (non-bootstrapped) rain return period DataFrame, used to look
        up original return period values for the selected events.
    df_stage_return_pds_og:
        Original stage return period DataFrame. ``None`` for rain-only.
    weather_event_indices:
        Dimension names identifying weather events. Used for subsetting.
    precip_varname:
        Precipitation intensity variable name in ``ds_sim_tseries``.
    stage_varname:
        Stage variable name. ``None`` for rain-only.
    rain_windows_min:
        Rolling window durations in minutes.
    n_years:
        Total synthesized years.
    alpha:
        Plotting position parameter.
    beta:
        Plotting position parameter.
    target_return_periods:
        Return period targets (years) at which to identify representative events.

    Returns
    -------
    pd.DataFrame
        Indexed by ``(bs_id, formulation, event_stat, return_period_yrs)``.
    """
    # Identify the year index name from the user-supplied indices
    year_col = next(
        idx for idx in weather_event_indices
        if idx in WEATHER_EVENT_INDEX_YEAR_ALIASES
    )

    ar_sim_years = np.arange(n_years)
    resampled_years = pd.Series(
        np.random.choice(ar_sim_years, size=n_years, replace=True)
    )
    # Keep only years that exist in the dataset
    resampled_years = resampled_years[
        resampled_years.isin(ds_sim_tseries[year_col].to_series())
    ]
    ds_bs = ds_sim_tseries.sel({year_col: resampled_years.values}).load()

    df_rain_bs, df_stage_bs = compute_univariate_event_return_periods(
        ds_bs,
        weather_event_indices=weather_event_indices,
        precip_varname=precip_varname,
        stage_varname=stage_varname,
        rain_windows_min=rain_windows_min,
        n_years=n_years,
        alpha=alpha,
        beta=beta,
    )

    df_all_bs = pd.concat(
        [df_rain_bs] + ([df_stage_bs] if df_stage_bs is not None else []), axis=1
    )
    df_all_og = pd.concat(
        [df_rain_return_pds_og] + ([df_stage_return_pds_og] if df_stage_return_pds_og is not None else []),
        axis=1,
    )

    # Value columns (no CDF or return period)
    cols_vals = [
        c for c in df_all_bs.columns
        if ("emp_cdf" not in c) and ("return_pd" not in c)
    ]

    formulation = "empirical_univar_return_pd_yrs"
    lst_df: list[pd.DataFrame] = []
    for event_stat in cols_vals:
        relevant_cols = [c for c in df_all_bs.columns if event_stat in c]
        df_stat_bs = df_all_bs.loc[:, relevant_cols]
        for trgt_rtrn in target_return_periods:
            rtrn_col = df_stat_bs.filter(like="return_pd").columns[0]
            idx_rtrn = int(
                (df_stat_bs[rtrn_col] - trgt_rtrn)
                .reset_index(drop=True)
                .abs()
                .idxmin()
            )
            s_row = df_stat_bs.iloc[idx_rtrn].copy()
            event_idx = df_stat_bs.index[idx_rtrn]

            # Encode event index as dot-separated string for storage
            if hasattr(event_idx, "__iter__") and not isinstance(event_idx, str):
                event_idx_colname = ".".join(str(n) for n in df_stat_bs.index.names)
                event_idx_str = ".".join(str(v) for v in event_idx)
            else:
                event_idx_colname = str(df_stat_bs.index.name)
                event_idx_str = str(event_idx)

            s_row[event_idx_colname] = event_idx_str
            s_row["return_period_yrs"] = trgt_rtrn
            s_row["formulation"] = formulation
            s_row["event_stat"] = event_stat

            # Look up original return period for the selected event
            s_og = df_all_og.loc[event_idx, relevant_cols].drop(event_stat)  # type: ignore[index]
            s_og.index = [f"{i}_og" for i in s_og.index]

            df_out = (
                pd.concat([s_row, s_og], axis=0).to_frame().T
                .reset_index(drop=True)
                .set_index(["formulation", "event_stat", "return_period_yrs"])
            )
            colnames = sorted(df_out.columns.tolist())
            lst_df.append(cast(pd.DataFrame, df_out.loc[:, colnames]))

    df_bs = pd.concat(lst_df).sort_index()
    df_bs["bs_id"] = bs_id
    idx_cols = ["bs_id"] + df_bs.index.names
    df_bs = df_bs.reset_index().set_index(idx_cols)
    return df_bs


def bs_samp_of_multivar_event_return_period(
    bs_id: int,
    df_multivar_return_periods_og: pd.DataFrame,
    ds_sim_tseries,
    df_rain_return_pds: pd.DataFrame,
    df_stage_return_pds: pd.DataFrame | None,
    weather_event_indices: list[str],
    precip_varname: str,
    n_years: int,
    alpha: float,
    beta: float,
    target_return_periods: list[int | float],
) -> pd.DataFrame:
    """Draw one bootstrap sample of multivariate event return periods.

    Resamples years with replacement, subsets the pre-computed return period
    DataFrames to the bootstrap events, recomputes all multivariate combinations,
    and for each event statistic combination and target return period identifies
    the event closest to that return period in the bootstrap sample.

    Parameters
    ----------
    bs_id:
        Bootstrap sample identifier.
    df_multivar_return_periods_og:
        Original multivariate return period DataFrame from
        ``compute_all_multivariate_return_period_combinations``.
    ds_sim_tseries:
        Full simulated weather time series Dataset. Used only to identify
        which events are present in the bootstrap year sample.
    df_rain_return_pds:
        Original rain return period DataFrame. Subsetted to bootstrap events
        and passed directly to ``compute_all_multivariate_return_period_combinations``.
    df_stage_return_pds:
        Original stage return period DataFrame. ``None`` for rain-only.
    weather_event_indices:
        Dimension names identifying weather events.
    precip_varname:
        Precipitation intensity variable name. Used to identify valid events
        in the bootstrap sample via non-NaN check.
    n_years:
        Total synthesized years.
    alpha:
        Plotting position parameter.
    beta:
        Plotting position parameter.
    target_return_periods:
        Return period targets (years).

    Returns
    -------
    pd.DataFrame
        Indexed by ``(bs_id, formulation, event_stat, return_period_yrs)``.
    """
    year_col = next(
        idx for idx in weather_event_indices
        if idx in WEATHER_EVENT_INDEX_YEAR_ALIASES
    )

    ar_sim_years = np.arange(n_years)
    resampled_years = pd.Series(
        np.random.choice(ar_sim_years, size=n_years, replace=True)
    )
    resampled_years = resampled_years[
        resampled_years.isin(ds_sim_tseries[year_col].to_series())
    ]
    ds_bs = ds_sim_tseries.sel({year_col: resampled_years.values})

    # Identify bootstrap event index
    idx_events_bs = (
        ds_bs.isel(timestep=0)[precip_varname]
        .to_dataframe()
        .dropna()
        .sort_index()
        .index
    )

    # Subset original return period DataFrames to bootstrap events
    df_rain_bs = cast(pd.DataFrame, df_rain_return_pds.loc[idx_events_bs, :])
    df_stage_bs = (
        cast(pd.DataFrame, df_stage_return_pds.loc[idx_events_bs, :])
        if df_stage_return_pds is not None
        else None
    )

    df_multivar_bs = compute_all_multivariate_return_period_combinations(
        df_rain_bs,
        df_stage_bs,
        n_years=n_years,
        alpha=alpha,
        beta=beta,
    )

    lst_df: list[pd.DataFrame] = []
    for event_stat, df_stat in df_multivar_bs.groupby(level="event_stats"):
        df_stat = cast(pd.DataFrame, df_stat.loc[pd.IndexSlice[event_stat]])  # type: ignore[index]
        rtrn_pd_cols = [c for c in df_stat.columns if "rtrn_yrs" in c]

        for trgt_rtrn in target_return_periods:
            for rtrn_pd_form in rtrn_pd_cols:
                idx_rtrn = (df_stat[rtrn_pd_form] - trgt_rtrn).abs().idxmin()
                s_row = df_stat.loc[pd.IndexSlice[idx_rtrn]].copy().drop_duplicates()  # type: ignore[index]

                if hasattr(idx_rtrn, "__iter__") and not isinstance(idx_rtrn, str):
                    event_idx_colname = ".".join(str(n) for n in df_stat.index.names)
                    event_idx_str = ".".join(str(v) for v in idx_rtrn)  # type: ignore[union-attr]
                else:
                    event_idx_colname = str(df_stat.index.name)
                    event_idx_str = str(idx_rtrn)

                s_row[event_idx_colname] = event_idx_str
                s_row["return_period_yrs"] = trgt_rtrn
                s_row["formulation"] = rtrn_pd_form
                s_row["event_stat"] = event_stat

                # Original multivariate return periods for selected event
                df_og = cast(
                    pd.DataFrame,
                    df_multivar_return_periods_og.loc[
                        pd.IndexSlice[event_stat, :, :, :]  # type: ignore[index]
                    ].loc[pd.IndexSlice[idx_rtrn], :],  # type: ignore[index]
                ).copy()
                df_og.columns = [f"{c}_og" for c in df_og.columns]

                df_out = (
                    pd.concat([s_row.to_frame().T, df_og], axis=1)
                    .reset_index(drop=True)
                    .set_index(["formulation", "event_stat", "return_period_yrs"])
                )
                lst_df.append(df_out)

    df_bs = pd.concat(lst_df).sort_index()
    df_bs["bs_id"] = bs_id
    idx_cols = ["bs_id"] + df_bs.index.names
    df_bs = df_bs.reset_index().set_index(idx_cols)
    return df_bs


def analyze_bootstrapped_samples(
    lst_files_processed: list[str | Path],
    colname_event_idx: str,
    lst_idx: list[str],
    df_event_all_stats: pd.DataFrame,
    fld_rtrn_pd_alpha: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aggregate bootstrapped sample CSVs into confidence interval summaries.

    Parameters
    ----------
    lst_files_processed:
        Paths to per-sample CSV files produced by ``bs_samp_of_univar_event_return_period``
        or ``bs_samp_of_multivar_event_return_period``.
    colname_event_idx:
        Column name encoding the event multi-index as a dot-separated string
        (e.g. ``"event_type.year.event_id"``).
    lst_idx:
        Index column names in the CSV files
        (e.g. ``["bs_id", "formulation", "event_stat", "return_period_yrs"]``).
    df_event_all_stats:
        DataFrame of event statistic values (non-CDF, non-return-period columns)
        indexed by the weather event multi-index.
    fld_rtrn_pd_alpha:
        Significance level for confidence intervals (e.g. 0.1 for 90% CI).
        Quantiles computed at ``alpha/2``, ``0.5``, ``1 - alpha/2``.

    Returns
    -------
    df_return_pd_cis:
        Confidence interval quantiles per formulation / event_stat / return_period_yrs.
    df_unique_events:
        All unique events that were selected across bootstrap samples, with
        their associated event statistic values (q1, q2, q3).
    """
    df_bs = pd.concat(
        [pd.read_csv(f, index_col=lst_idx) for f in lst_files_processed]
    )
    mask_non_dups = ~df_bs.reset_index().duplicated()
    df_bs = df_bs[mask_non_dups.values]
    ds_bs = df_bs.to_xarray()

    # Value-only columns for event stats
    cols_vals = [
        c for c in df_event_all_stats.columns
        if ("emp_cdf" not in c) and ("return_pd" not in c)
    ]
    df_event_stats = df_event_all_stats.loc[:, cols_vals]

    formulations = ds_bs["formulation"].values
    lst_df_cis: list[pd.DataFrame] = []
    lst_df_unique: list[pd.DataFrame] = []

    for form in formulations:
        df_ci = (
            ds_bs.sel(formulation=form)[f"{form}_og"]
            .quantile(
                [fld_rtrn_pd_alpha / 2, 0.5, 1 - fld_rtrn_pd_alpha / 2],
                dim="bs_id",
                method="linear",
            )
            .to_dataframe()
        )
        lst_df_cis.append(df_ci)

        df_unique = (
            ds_bs.sel(formulation=form)[colname_event_idx]
            .to_dataframe()
            .reset_index()
            .drop(columns=["bs_id"])
            .drop_duplicates()
            .reset_index(drop=True)
        )
        event_ids = df_unique[colname_event_idx].apply(
            lambda x: pd.Series(x.split("."), index=colname_event_idx.split("."))
        )
        df_unique = pd.concat(
            [df_unique.drop(columns=colname_event_idx), event_ids], axis=1
        )
        event_stats = cast(
            pd.DataFrame,
            df_unique.apply(
                _return_vars_associated_with_event_stat,
                df_event_stats=df_event_stats,
                axis=1,
            ),
        )
        df_unique = pd.concat([df_unique, event_stats], axis=1)
        lst_df_unique.append(df_unique)

    df_return_pd_cis = pd.concat(lst_df_cis, axis=1).sort_index()
    df_unique_events = (
        pd.concat(lst_df_unique, axis=0)
        .set_index(["formulation", "return_period_yrs", "event_stat"])
        .sort_index()
        .dropna(axis=1, how="all")
    )
    return df_return_pd_cis, df_unique_events


def _return_vars_associated_with_event_stat(
    s_row: pd.Series,
    df_event_stats: pd.DataFrame,
) -> pd.Series:
    """Look up q1/q2/q3 statistic values for a row from a bootstrap unique-events table.

    Each row has an ``event_stat`` field (e.g. ``"5min,w"``) encoding which
    statistic combination the event represents, plus ``event_type``, ``year``,
    ``event_id`` columns identifying the event.
    """
    lst_of_stats = s_row.filter(like="event_stat").iloc[0].split(",")
    s_result = pd.Series(index=["q1", "q2", "q3"], dtype=float)

    for q_idx, substat in enumerate(lst_of_stats):
        if substat in df_event_stats.columns:
            col = substat
        elif substat == "w":
            stage_cols = [c for c in df_event_stats.columns if c.startswith("max_") and c.endswith("_m") and "mm" not in c]
            if len(stage_cols) != 1:
                raise ComputationError(
                    f"_return_vars_associated_with_event_stat: could not uniquely identify "
                    f"stage column for substat 'w'. Candidates: {stage_cols}"
                )
            col = stage_cols[0]
        else:
            rain_cols = [c for c in df_event_stats.columns if f"_{substat}" in c]
            if len(rain_cols) != 1:
                raise ComputationError(
                    f"_return_vars_associated_with_event_stat: could not uniquely identify "
                    f"rain column for substat '{substat}'. Candidates: {rain_cols}"
                )
            col = rain_cols[0]

        # Build event index from available index columns
        idx_names = [str(n) for n in df_event_stats.index.names]
        idx_vals = tuple(s_row[n] for n in idx_names)
        event_idx = idx_vals[0] if len(idx_vals) == 1 else idx_vals
        s_result.iloc[q_idx] = df_event_stats.loc[event_idx, col]

    return s_result


def return_df_of_events_within_ci(
    all_event_return_pds,
    df_return_pd_cis: pd.DataFrame,
    stat: str,
    form: str,
    lst_trgt_return_pds: list[int | float],
    df_event_all_stats: pd.DataFrame,
) -> pd.DataFrame:
    """Find all events whose return period falls within the bootstrapped confidence interval.

    Parameters
    ----------
    all_event_return_pds:
        Either a pandas DataFrame (univariate) or xarray Dataset (multivariate)
        containing the original (non-bootstrapped) return periods.
    df_return_pd_cis:
        Confidence interval DataFrame from ``analyze_bootstrapped_samples``.
    stat:
        Event statistic name (e.g. ``"5min,w"``).
    form:
        Formulation name (e.g. ``"empirical_univar_return_pd_yrs"`` or
        ``"empirical_multivar_rtrn_yrs_AND"``).
    lst_trgt_return_pds:
        Target return periods to find events within.
    df_event_all_stats:
        Full event statistics DataFrame.

    Returns
    -------
    pd.DataFrame
        Events within the CI for each target return period, with q1/q2/q3
        statistic values and ``return_period_yrs`` column.
    """
    if "multivar" in form:
        df_events = (
            all_event_return_pds.sel(event_stats=stat)[form].to_dataframe().dropna()
        )
    else:
        df_events = all_event_return_pds.loc[:, stat].to_frame()
        df_events.columns = [form]
        df_events["event_stats"] = stat

    s_bounds = (
        df_return_pd_cis.loc[pd.IndexSlice[:, stat, lst_trgt_return_pds]]  # type: ignore[index]
        .filter(like=form)
        .iloc[:, 0]
    )

    cols_vals = [
        c for c in df_event_all_stats.columns
        if ("emp_cdf" not in c) and ("return_pd" not in c)
    ]
    df_event_stats = df_event_all_stats.loc[:, cols_vals]

    lst_dfs = []
    for rtrn in lst_trgt_return_pds:
        s_bounds_rtrn = s_bounds.loc[pd.IndexSlice[:, :, rtrn]]
        idx_in_ci = (df_events[form] >= s_bounds_rtrn.min()) & (
            df_events[form] <= s_bounds_rtrn.max()
        )
        df_in_ci = df_events[idx_in_ci]
        if len(df_in_ci) == 0:
            raise ComputationError(
                f"return_df_of_events_within_ci: no events found within CI for "
                f"stat='{stat}', form='{form}', return_period={rtrn}. "
                f"CI bounds: [{s_bounds_rtrn.min():.2f}, {s_bounds_rtrn.max():.2f}]"
            )
        event_stats = cast(
            pd.DataFrame,
            df_in_ci.reset_index().apply(
                _return_vars_associated_with_event_stat,
                df_event_stats=df_event_stats,
                axis=1,
            ),
        )
        event_stats = event_stats.set_index(df_in_ci.index)
        df_combined = pd.concat([df_in_ci, event_stats], axis=1)
        df_combined["return_period_yrs"] = rtrn
        lst_dfs.append(df_combined)

    return pd.concat(lst_dfs).reset_index()
