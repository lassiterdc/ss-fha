"""Domain-agnostic empirical frequency analysis primitives.

All three functions in this module have zero flood/hydrology domain knowledge.
They are tracked as utility package candidates in
``docs/planning/utility_package_candidates.md``.

Consumers: ``flood_probability.py``, ``event_statistics.py``, ``geospatial.py``
all import from here.

Plotting positions
------------------
``calculate_positions`` delegates to ``scipy.stats.mstats.plotting_positions``,
which implements the generalized Hazen family:

    F_i = (i - alpha) / (n + 1 - alpha - beta)

where ``i`` is the rank (1-indexed) and ``n`` is the sample size. Common
named methods and their (alpha, beta) parameters:

    Weibull       (0.0,  0.0)   — unbiased for any distribution; used in this project by default
    Hazen         (0.5,  0.5)   — midpoint of each class interval
    Cunnane       (0.4,  0.4)   — approximately unbiased for normal distribution
    Gringorten    (0.44, 0.44)  — approximately unbiased for Gumbel (EV1) distribution
    Blom          (0.375, 0.375) — approximately unbiased for normal distribution

See scipy.stats.mstats.plotting_positions documentation for full details.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats.mstats import plotting_positions

from ss_fha.exceptions import SSFHAError


def calculate_positions(
    data: np.ndarray,
    alpha: float,
    beta: float,
    fillna_val: float,
) -> np.ndarray:
    """Compute empirical CDF plotting positions for a 1D array.

    Uses ``scipy.stats.mstats.plotting_positions`` to compute the generalized
    Hazen-family plotting positions. See module docstring for the formula and
    named method (alpha, beta) mappings.

    NaN handling: pass ``fillna_val`` to substitute a fill value for NaNs
    before computing positions. After computation, all positions that
    correspond to originally-NaN entries are set to the maximum computed
    position in their group (i.e., NaN values are treated as if they tied
    for the highest rank). Pass ``np.nan`` as ``fillna_val`` to disable NaN
    filling — an error will be raised if any NaNs remain in the data.

    Parameters
    ----------
    data:
        1D array of values. Must not contain NaN unless ``fillna_val`` is
        provided (i.e., not ``np.nan``).
    alpha:
        Plotting position parameter. See module docstring for named methods.
    beta:
        Plotting position parameter. See module docstring for named methods.
    fillna_val:
        Value to substitute for NaNs before computing positions. Pass
        ``np.nan`` to indicate no fill (NaNs will raise an error).

    Returns
    -------
    np.ndarray
        1D array of plotting positions (empirical CDF values) in the same
        order as the input data (not sorted).

    Raises
    ------
    SSFHAError
        If any NaN values remain after applying ``fillna_val``.
    """
    data = data.copy()
    idx_null = np.isnan(data)
    na_vals_present = idx_null.sum() > 0

    if na_vals_present:
        if np.isnan(fillna_val):
            raise SSFHAError(
                f"calculate_positions: {idx_null.sum()} of {len(data)} values are NaN. "
                "Pass a numeric fillna_val to substitute NaNs before computing "
                "plotting positions."
            )
        data[idx_null] = fillna_val

    result = plotting_positions(data, alpha=alpha, beta=beta)

    if na_vals_present:
        result[idx_null] = result[idx_null].max()

    return result


def calculate_return_period(
    positions: np.ndarray,
    n_years: int,
    n_events: int,
) -> np.ndarray:
    """Convert empirical CDF plotting positions to return periods.

    Return period is defined as the average recurrence interval in years:

        T = 1 / (P_exceedance * lambda)

    where ``lambda = n_events / n_years`` is the average event rate per year
    and ``P_exceedance = 1 - F`` is the exceedance probability.

    Does not require the positions to be sorted.

    Parameters
    ----------
    positions:
        1D array of empirical CDF values (plotting positions), in [0, 1].
        Values are clipped to [1e-10, 1 - 1e-10] to avoid divide-by-zero.
    n_years:
        Number of synthetic years in the simulation ensemble.
    n_events:
        Total number of events in the sample (length of the stacked event
        dimension, after removing all-NaN events).

    Returns
    -------
    np.ndarray
        1D array of return periods in years, same order as ``positions``.
    """
    positions = positions.clip(min=1e-10, max=1 - 1e-10)
    events_per_year = n_events / n_years
    exceedance_prob = 1 - positions
    return 1 / (exceedance_prob * events_per_year)


def compute_return_periods_for_series(
    s: pd.Series,
    n_years: int,
    alpha: float,
    beta: float,
    assign_dup_vals_max_return: bool,
    varname: str | None = None,
) -> pd.DataFrame:
    """Compute empirical CDF and return periods for a 1-D pandas Series.

    Parameters
    ----------
    s:
        Series of event statistic values indexed by the weather event
        multi-index (e.g. ``(event_type, year, event_id)``).
    n_years:
        Total number of synthesized years in the weather model run.
        Used as the denominator for return period calculations.
    alpha:
        Plotting position parameter (Weibull: 0.0).
    beta:
        Plotting position parameter (Weibull: 0.0).
    assign_dup_vals_max_return:
        If ``True``, events with identical statistic values are all assigned
        the maximum return period of their group. If ``False``, duplicate
        values receive progressively increasing CDF values. Pass
        ``ASSIGN_DUP_VALS_MAX_RETURN`` from ``ss_fha.constants`` explicitly
        to make constant usage visible at the call site.
    varname:
        Column name for the statistic values in the returned DataFrame.
        Defaults to ``s.name``.

    Returns
    -------
    pd.DataFrame
        Columns: ``[varname, f"{varname}_emp_cdf", f"{varname}_return_pd_yrs"]``.
        Indexed by the original index of ``s``, sorted ascending by statistic value.
    """
    if varname is None:
        varname = str(s.name)
    og_name = str(s.name)
    s = s.copy()
    s.name = varname

    s_sorted = s.sort_values()
    og_idx = s_sorted.index
    s_sorted = s_sorted.reset_index(drop=True)

    n_events = len(s_sorted)
    plt_pos = calculate_positions(s_sorted.to_numpy(), alpha=alpha, beta=beta, fillna_val=0.0)
    rtrn_pds = calculate_return_period(plt_pos, n_years=n_years, n_events=n_events)

    s_plt_pos = pd.Series(plt_pos, name=f"{varname}_emp_cdf")
    s_rtrn = pd.Series(rtrn_pds, name=f"{varname}_return_pd_yrs")
    df = pd.concat([s_sorted, s_plt_pos, s_rtrn], axis=1)
    df.index = og_idx

    if assign_dup_vals_max_return:
        idx_max_rtrn_by_val = df.groupby(varname).idxmax().iloc[:, 0]
        df_maxrtrn = (
            df.loc[idx_max_rtrn_by_val, :]
            .reset_index(drop=True)
            .set_index(varname)
        )
        df = s.to_frame().join(df_maxrtrn, how="left", on=varname)

    df = df.rename(columns={varname: og_name})
    return df.sort_index()
