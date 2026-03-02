"""Unit tests for ss_fha.core.event_statistics (Work Chunk 02C).

Validation strategy
-------------------
1. ``empirical_multivariate_return_periods`` (vectorized) is tested against
   ``_empirical_multivariate_return_periods_reference`` (apply-based port of old
   code). Results must match to within 1e-12. Discrepancies may indicate a bug
   in the reference implementation, not the vectorized one — the reference was
   ported directly from old code and was never independently validated
   mathematically.

2. The vectorized implementation is benchmarked against the reference and must
   be at least 10× faster. If speedup is ≥10× but <50×, a note is printed
   suggesting further optimization if bootstrap runtime is unacceptable.

3. Sanity check: RP_AND >= RP_OR for every event (follows from the complement-
   space inversion — see module docstring and
   ``_work/figuring_out_multivariate_return_periods.py``).

4. ``compute_univariate_event_return_periods`` is tested against known-good
   return period values computed by hand for a tiny synthetic dataset.

5. Config model validation: comparative analysis configs must reject
   event_statistics, alt_fha_analyses, and toggle_mcds=True.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
import pytest

from ss_fha.core.event_statistics import (
    _empirical_multivariate_return_periods_reference,
    empirical_multivariate_return_periods,
    compute_all_multivariate_return_period_combinations,
    compute_univariate_event_return_periods,
    return_df_of_events_within_ci,
)
from ss_fha.exceptions import ConfigurationError


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_synthetic_events(n: int = 50, seed: int = 42) -> pd.DataFrame:
    """Synthetic bivariate event dataset for multivariate return period tests.

    Returns a DataFrame with columns ``mm_per_hr`` and ``waterlevel_m``,
    indexed by ``(event_type, year, event_id)``.
    """
    rng = np.random.default_rng(seed)
    mm_per_hr = rng.gamma(shape=2.0, scale=12.0, size=n)
    waterlevel_m = np.clip(
        0.35 + 0.018 * mm_per_hr + rng.normal(0.0, 0.10, size=n),
        a_min=0.05,
        a_max=None,
    )
    idx = pd.MultiIndex.from_arrays(
        [
            np.full(n, "combined"),
            np.arange(1, n + 1),
            np.zeros(n, dtype=int),
        ],
        names=["event_type", "year", "event_id"],
    )
    return pd.DataFrame({"mm_per_hr": mm_per_hr, "waterlevel_m": waterlevel_m}, index=idx)


# ---------------------------------------------------------------------------
# Multivariate return periods — vectorized vs. reference
# ---------------------------------------------------------------------------

class TestEmpiricalMultivariateReturnPeriods:

    def test_vectorized_matches_reference_exactly(self):
        """Vectorized implementation must match the apply-based reference to 1e-12.

        Note: discrepancies indicate a bug in the reference, not the vectorized
        version. The reference was ported directly from old code without independent
        mathematical validation.
        """
        df = _make_synthetic_events(n=50)
        alpha, beta = 0.0, 0.0
        n_years = 100

        df_ref = _empirical_multivariate_return_periods_reference(
            df, n_years=n_years, alpha=alpha, beta=beta
        )
        df_vec = empirical_multivariate_return_periods(
            df, n_years=n_years, alpha=alpha, beta=beta
        )

        for col in ["empirical_multivar_cdf_AND", "empirical_multivar_cdf_OR",
                    "empirical_multivar_rtrn_yrs_AND", "empirical_multivar_rtrn_yrs_OR"]:
            assert col in df_vec.columns, f"Missing column: {col}"
            np.testing.assert_allclose(
                df_vec[col].values,
                df_ref[col].values,
                rtol=1e-12,
                atol=1e-12,
                err_msg=(
                    f"Column '{col}': vectorized and reference disagree. "
                    "If this is unexpected, check the reference implementation first — "
                    "it was ported from old code and may contain an error."
                ),
            )

    def test_vectorized_matches_reference_trivariate(self):
        """Exact match also holds for 3-variable inputs."""
        rng = np.random.default_rng(7)
        n = 40
        idx = pd.RangeIndex(n)
        df = pd.DataFrame(
            {
                "v1": rng.gamma(2.0, 5.0, size=n),
                "v2": rng.gamma(3.0, 3.0, size=n),
                "v3": rng.exponential(scale=2.0, size=n),
            },
            index=idx,
        )
        alpha, beta, n_years = 0.0, 0.0, 100

        df_ref = _empirical_multivariate_return_periods_reference(df, n_years, alpha, beta)
        df_vec = empirical_multivariate_return_periods(df, n_years, alpha, beta)

        np.testing.assert_allclose(
            df_vec["empirical_multivar_cdf_AND"].values,
            df_ref["empirical_multivar_cdf_AND"].values,
            rtol=1e-12, atol=1e-12,
        )
        np.testing.assert_allclose(
            df_vec["empirical_multivar_cdf_OR"].values,
            df_ref["empirical_multivar_cdf_OR"].values,
            rtol=1e-12, atol=1e-12,
        )

    def test_vectorized_speedup(self):
        """Vectorized implementation must be at least 10x faster than reference.

        Uses n=200 events — large enough to expose the O(n²) Python overhead
        in the reference while keeping total test time under ~5 seconds.

        If speedup is >=10x but <50x, consider further optimization if multivariate
        bootstrapping (500 samples) becomes a runtime bottleneck.
        """
        df = _make_synthetic_events(n=200, seed=0)
        alpha, beta, n_years = 0.0, 0.0, 1000

        t0 = time.perf_counter()
        _empirical_multivariate_return_periods_reference(df, n_years, alpha, beta)
        t_ref = time.perf_counter() - t0

        t0 = time.perf_counter()
        empirical_multivariate_return_periods(df, n_years, alpha, beta)
        t_vec = time.perf_counter() - t0

        speedup = t_ref / t_vec
        print(f"\nSpeedup: {speedup:.1f}x (ref={t_ref:.3f}s, vec={t_vec:.3f}s)")

        if speedup >= 50:
            print(f"  Excellent speedup ({speedup:.1f}x). Multivariate bootstrapping "
                  "is likely fast enough for single-node execution.")
        elif speedup >= 10:
            print(f"  Adequate speedup ({speedup:.1f}x). If 500-sample bootstrapping "
                  "is still too slow, consider Snakemake parallelization of bootstrap samples.")

        assert speedup >= 10, (
            f"Vectorized implementation is only {speedup:.1f}x faster than reference "
            f"(need >=10x). ref={t_ref:.3f}s, vec={t_vec:.3f}s"
        )


# ---------------------------------------------------------------------------
# Sanity checks: AND/OR ordering
# ---------------------------------------------------------------------------

class TestAndOrSemantics:

    def test_rp_and_ge_rp_or_for_all_events(self):
        """RP_AND >= RP_OR must hold for every event.

        AND exceedance (all drivers simultaneously exceed) is rarer than OR
        exceedance (at least one driver exceeds), so AND return periods must
        always be at least as long as OR return periods.

        See module docstring and _work/figuring_out_multivariate_return_periods.py.
        """
        df = _make_synthetic_events(n=100)
        result = empirical_multivariate_return_periods(df, n_years=1000, alpha=0.0, beta=0.0)

        assert (result["empirical_multivar_rtrn_yrs_AND"] >= result["empirical_multivar_rtrn_yrs_OR"]).all(), (
            "RP_AND < RP_OR for some events. This violates the complement-space inversion "
            "property. AND exceedance (all drivers coincide) must always be rarer than "
            "OR exceedance (any driver)."
        )

    def test_cdf_and_ge_cdf_or_for_all_events(self):
        """F_AND >= F_OR (non-exceedance) must hold for every event."""
        df = _make_synthetic_events(n=100)
        result = empirical_multivariate_return_periods(df, n_years=1000, alpha=0.0, beta=0.0)

        assert (result["empirical_multivar_cdf_AND"] >= result["empirical_multivar_cdf_OR"]).all(), (
            "F_AND < F_OR for some events. This violates the complement-space inversion property."
        )

    def test_or_exceeds_more_often_than_and(self):
        """Mean exceedance probability for OR must exceed that for AND."""
        df = _make_synthetic_events(n=100)
        result = empirical_multivariate_return_periods(df, n_years=1000, alpha=0.0, beta=0.0)

        p_exceed_and = 1.0 - result["empirical_multivar_cdf_AND"]
        p_exceed_or  = 1.0 - result["empirical_multivar_cdf_OR"]

        assert p_exceed_or.mean() >= p_exceed_and.mean(), (
            "Mean OR exceedance probability is less than AND — unexpected."
        )


# ---------------------------------------------------------------------------
# Univariate return periods — known values
# ---------------------------------------------------------------------------

class TestComputeUnivariateEventReturnPeriods:
    """Test compute_univariate_event_return_periods against hand-computed values.

    Uses a minimal synthetic time series xarray Dataset with 4 events and a
    single 1-hour rainfall window, so that expected return periods can be
    computed by hand using the Weibull plotting position formula.
    """

    @pytest.fixture
    def tiny_ds(self):
        """4-event, 3-timestep synthetic Dataset with known rainfall intensities."""
        import xarray as xr

        # 4 events: (year=1,2,3,4), single event_type, single event_id
        # mm_per_hr values: 10, 20, 30, 40 (each over 3 timesteps)
        n_events = 4
        n_tsteps = 3
        years = np.arange(1, n_events + 1)
        event_types = np.array(["combined"])
        event_ids = np.array([0])

        # timestep as timedelta (1-hour steps)
        tsteps = pd.to_timedelta(np.arange(n_tsteps), unit="h")

        intensities = np.array([10.0, 20.0, 30.0, 40.0])  # mm/hr per event
        # Shape: (event_type=1, year=4, event_id=1, timestep=3)
        data = intensities[:, np.newaxis] * np.ones((n_events, n_tsteps))
        data = data[np.newaxis, :, np.newaxis, :]  # (1, 4, 1, 3)

        ds = xr.Dataset(
            {"mm_per_hr": (["event_type", "year", "event_id", "timestep"], data)},
            coords={
                "event_type": event_types,
                "year": years,
                "event_id": event_ids,
                "timestep": tsteps,
            },
        )
        return ds

    def test_rain_return_periods_known_values(self, tiny_ds):
        """Return periods for 4 events with intensities 10/20/30/40 mm/hr.

        With Weibull (alpha=0, beta=0) and n=4 events over n_years=4:
            F_i = i / (n+1)  for i = 1,2,3,4
            F = [0.2, 0.4, 0.6, 0.8]
            lambda = n_events / n_years = 4/4 = 1
            RP_i = 1 / ((1-F_i) * lambda) = [1.25, 1.67, 2.50, 5.00]
        """
        df_rain, df_stage = compute_univariate_event_return_periods(
            ds_sim_tseries=tiny_ds,
            weather_event_indices=["event_type", "year", "event_id"],
            precip_varname="mm_per_hr",
            stage_varname=None,
            rain_windows_min=[60],
            n_years=4,
            alpha=0.0,
            beta=0.0,
        )

        assert df_stage is None

        rtrn_col = [c for c in df_rain.columns if "return_pd_yrs" in c][0]
        rtrn_pds = df_rain[rtrn_col].sort_values().values

        expected = np.array([1.25, 5.0 / 3.0, 2.50, 5.00])
        np.testing.assert_allclose(rtrn_pds, expected, rtol=1e-6)

    def test_cdf_values_match_weibull_formula(self, tiny_ds):
        """Empirical CDF values follow F_i = i/(n+1) exactly (Weibull, alpha=beta=0)."""
        df_rain, _ = compute_univariate_event_return_periods(
            ds_sim_tseries=tiny_ds,
            weather_event_indices=["event_type", "year", "event_id"],
            precip_varname="mm_per_hr",
            stage_varname=None,
            rain_windows_min=[60],
            n_years=4,
            alpha=0.0,
            beta=0.0,
        )
        cdf_col = [c for c in df_rain.columns if "emp_cdf" in c][0]
        cdf_vals = df_rain[cdf_col].sort_values().values
        expected = np.array([1, 2, 3, 4]) / 5.0
        np.testing.assert_allclose(cdf_vals, expected, rtol=1e-10)

    def test_no_hardcoded_index_names(self, tiny_ds):
        """weather_event_indices controls subsetting; passing different names raises."""
        # Using wrong index names should fail gracefully (KeyError or similar),
        # not silently produce wrong results.
        with pytest.raises(Exception):
            compute_univariate_event_return_periods(
                ds_sim_tseries=tiny_ds,
                weather_event_indices=["wrong_type", "wrong_year", "wrong_id"],
                precip_varname="mm_per_hr",
                stage_varname=None,
                rain_windows_min=[60],
                n_years=4,
                alpha=0.0,
                beta=0.0,
            )


# ---------------------------------------------------------------------------
# Config model validation — comparative analysis
# ---------------------------------------------------------------------------

class TestComparativeAnalysisValidation:
    """SsfhaConfig with is_comparative_analysis=True must reject forbidden fields."""

    def _base_comparative_kwargs(self) -> dict:
        from ss_fha.config.model import (
            TritonOutputsConfig, EventDataConfig, ExecutionConfig
        )
        return dict(
            fha_approach="ssfha",
            fha_id="test_comparative",
            project_name="test",
            is_comparative_analysis=True,
            n_years_synthesized=100,
            return_periods=[2, 100],
            toggle_uncertainty=False,
            toggle_mcds=False,
            toggle_ppcct=False,
            toggle_flood_risk=False,
            toggle_design_comparison=False,
            alpha=0.0,
            beta=0.0,
            triton_outputs=TritonOutputsConfig(combined="/tmp/fake.zarr"),
            event_data=EventDataConfig(sim_event_summaries="/tmp/fake.csv"),
            execution=ExecutionConfig(mode="local_concurrent"),
        )

    def test_comparative_analysis_valid_minimal(self):
        """A minimal comparative analysis config should load without error."""
        from ss_fha.config.model import SsfhaConfig
        kwargs = self._base_comparative_kwargs()
        cfg = SsfhaConfig(**kwargs)
        assert cfg.is_comparative_analysis is True

    def test_comparative_analysis_rejects_event_statistics(self):
        """is_comparative_analysis=True must raise if event_statistic_variables is set."""

        from ss_fha.config.model import SsfhaConfig, EventStatisticsConfig, EventStatisticVariableConfig
        kwargs = self._base_comparative_kwargs()
        kwargs["event_statistic_variables"] = EventStatisticsConfig(
            precip_intensity=EventStatisticVariableConfig(
                variable_name="mm_per_hr", units="mm_per_hr", max_intensity_windows_min=[60]
            )
        )
        with pytest.raises(ConfigurationError, match="event_statistic_variables"):
            SsfhaConfig(**kwargs)

    def test_comparative_analysis_rejects_alt_fha_analyses(self):
        """is_comparative_analysis=True must raise if alt_fha_analyses is non-empty."""

        from ss_fha.config.model import SsfhaConfig
        kwargs = self._base_comparative_kwargs()
        kwargs["alt_fha_analyses"] = ["/tmp/other.yaml"]
        with pytest.raises(ConfigurationError, match="alt_fha_analyses"):
            SsfhaConfig(**kwargs)

    def test_comparative_analysis_rejects_toggle_mcds(self):
        """is_comparative_analysis=True must raise if toggle_mcds=True."""

        from ss_fha.config.model import SsfhaConfig
        kwargs = self._base_comparative_kwargs()
        kwargs["toggle_mcds"] = True
        with pytest.raises(ConfigurationError, match="toggle_mcds"):
            SsfhaConfig(**kwargs)

    def test_primary_analysis_requires_event_statistics(self):
        """is_comparative_analysis=False must raise if event_statistic_variables is missing."""

        from ss_fha.config.model import SsfhaConfig
        kwargs = self._base_comparative_kwargs()
        kwargs["is_comparative_analysis"] = False
        kwargs["weather_event_indices"] = ["event_type", "year", "event_id"]
        # event_statistic_variables intentionally omitted
        with pytest.raises(ConfigurationError, match="event_statistic_variables"):
            SsfhaConfig(**kwargs)

    def test_primary_analysis_requires_weather_event_indices(self):
        """is_comparative_analysis=False must raise if weather_event_indices is missing."""

        from ss_fha.config.model import SsfhaConfig, EventStatisticsConfig, EventStatisticVariableConfig
        kwargs = self._base_comparative_kwargs()
        kwargs["is_comparative_analysis"] = False
        kwargs["event_statistic_variables"] = EventStatisticsConfig(
            precip_intensity=EventStatisticVariableConfig(
                variable_name="mm_per_hr", units="mm_per_hr", max_intensity_windows_min=[60]
            )
        )
        # weather_event_indices intentionally omitted
        with pytest.raises(ConfigurationError, match="weather_event_indices"):
            SsfhaConfig(**kwargs)

    def test_primary_analysis_requires_year_in_indices(self):
        """weather_event_indices must contain a year-like index."""

        from ss_fha.config.model import SsfhaConfig, EventStatisticsConfig, EventStatisticVariableConfig
        kwargs = self._base_comparative_kwargs()
        kwargs["is_comparative_analysis"] = False
        kwargs["weather_event_indices"] = ["event_type", "event_id"]  # no year
        kwargs["event_statistic_variables"] = EventStatisticsConfig(
            precip_intensity=EventStatisticVariableConfig(
                variable_name="mm_per_hr", units="mm_per_hr", max_intensity_windows_min=[60]
            )
        )
        with pytest.raises(ConfigurationError, match="year"):
            SsfhaConfig(**kwargs)

    def test_weather_event_indices_accepts_year_alias_yr(self):
        """'yr' is an accepted alias for the year index."""
        from ss_fha.config.model import SsfhaConfig, EventStatisticsConfig, EventStatisticVariableConfig
        kwargs = self._base_comparative_kwargs()
        kwargs["is_comparative_analysis"] = False
        kwargs["weather_event_indices"] = ["event_type", "yr", "event_id"]
        kwargs["event_statistic_variables"] = EventStatisticsConfig(
            precip_intensity=EventStatisticVariableConfig(
                variable_name="mm_per_hr", units="mm_per_hr", max_intensity_windows_min=[60]
            )
        )
        cfg = SsfhaConfig(**kwargs)
        assert "yr" in cfg.weather_event_indices
