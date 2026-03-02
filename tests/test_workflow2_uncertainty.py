"""Integration tests for Workflow 2: Flood Hazard Uncertainty (Work Chunk 03B).

Tests the analysis module and runner scripts using synthetic test data
produced by ``build_uncertainty_test_case``.

The test case uses:
- 20 synthetic years (n_years_synthesized)
- 5 bootstrap samples (n_bootstrap_samples)
- 10 simulated events (from the TRITON zarr)
- 10x10 spatial grid
- Poisson(λ=5) event arrivals per year in the iloc mapping
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from tests.fixtures.test_case_builder import (
    build_minimal_test_case,
    build_uncertainty_test_case,
)
from tests.utils_for_testing import assert_zarr_valid

# ---------------------------------------------------------------------------
# Helper: run Workflow 1 first so bootstrap runner has inputs
# ---------------------------------------------------------------------------


def _run_workflow1(tmp_path: Path) -> None:
    """Run flood hazard assessment to produce the combined.zarr prerequisite."""
    from ss_fha.analysis.flood_hazard import run_flood_hazard
    from ss_fha.config import load_system_config

    cfg = build_uncertainty_test_case(tmp_path)
    system_cfg = load_system_config(tmp_path / "system.yaml")
    run_flood_hazard(
        config=cfg,
        system_config=system_cfg,
        sim_type="combined",
        overwrite=False,
    )
    return cfg


# ---------------------------------------------------------------------------
# build_synthetic_event_iloc_mapping tests
# ---------------------------------------------------------------------------


def test_iloc_mapping_has_correct_columns() -> None:
    """build_synthetic_event_iloc_mapping returns year and event_iloc columns."""
    from tests.fixtures.test_case_builder import build_synthetic_event_iloc_mapping

    df = build_synthetic_event_iloc_mapping(n_years=20, arrival_rate=5.0, seed=42)
    assert list(df.columns) == ["year", "event_iloc"]


def test_iloc_mapping_event_iloc_is_sequential() -> None:
    """event_iloc values are 0-based sequential integers."""
    from tests.fixtures.test_case_builder import build_synthetic_event_iloc_mapping

    df = build_synthetic_event_iloc_mapping(n_years=20, arrival_rate=5.0, seed=42)
    assert list(df["event_iloc"]) == list(range(len(df)))


def test_iloc_mapping_events_per_year_varies() -> None:
    """Events per year varies — confirms Poisson draws are non-degenerate."""
    from tests.fixtures.test_case_builder import build_synthetic_event_iloc_mapping

    df = build_synthetic_event_iloc_mapping(n_years=50, arrival_rate=5.0, seed=42)
    events_per_year = df.groupby("year").size()
    assert events_per_year.nunique() > 1, "All years have the same event count — Poisson draws may be degenerate"


# ---------------------------------------------------------------------------
# prepare_bootstrap_run tests
# ---------------------------------------------------------------------------


def test_prepare_bootstrap_run_succeeds(tmp_path: Path) -> None:
    """prepare_bootstrap_run passes when all inputs exist."""
    from ss_fha.analysis.flood_hazard import run_flood_hazard
    from ss_fha.analysis.uncertainty import prepare_bootstrap_run
    from ss_fha.config import load_system_config
    from ss_fha.paths import ProjectPaths

    cfg = build_uncertainty_test_case(tmp_path)
    system_cfg = load_system_config(tmp_path / "system.yaml")
    run_flood_hazard(config=cfg, system_config=system_cfg, sim_type="combined", overwrite=False)

    paths = ProjectPaths.from_config(cfg)
    prepare_bootstrap_run(config=cfg, paths=paths)  # should not raise


def test_prepare_bootstrap_run_fails_without_uncertainty_config(tmp_path: Path) -> None:
    """prepare_bootstrap_run raises ConfigurationError when toggle_uncertainty=False."""
    from ss_fha.analysis.uncertainty import prepare_bootstrap_run
    from ss_fha.exceptions import ConfigurationError
    from ss_fha.paths import ProjectPaths

    cfg = build_minimal_test_case(tmp_path)  # toggle_uncertainty=False
    paths = ProjectPaths.from_config(cfg)

    with pytest.raises(ConfigurationError, match="toggle_uncertainty"):
        prepare_bootstrap_run(config=cfg, paths=paths)


def test_prepare_bootstrap_run_fails_without_flood_probs(tmp_path: Path) -> None:
    """prepare_bootstrap_run raises DataError when Workflow 1 zarr is missing."""
    from ss_fha.analysis.uncertainty import prepare_bootstrap_run
    from ss_fha.exceptions import DataError
    from ss_fha.paths import ProjectPaths

    cfg = build_uncertainty_test_case(tmp_path)
    paths = ProjectPaths.from_config(cfg)
    paths.ensure_dirs_exist()
    # Do NOT run Workflow 1 — flood_probs zarr absent

    with pytest.raises(DataError, match="flood probability zarr not found"):
        prepare_bootstrap_run(config=cfg, paths=paths)


# ---------------------------------------------------------------------------
# run_bootstrap_sample tests
# ---------------------------------------------------------------------------


def test_run_bootstrap_sample_produces_valid_output(tmp_path: Path) -> None:
    """run_bootstrap_sample writes a zarr with return_pd_yrs coordinate."""
    from ss_fha.analysis.flood_hazard import run_flood_hazard
    from ss_fha.analysis.uncertainty import run_bootstrap_sample
    from ss_fha.config import load_system_config
    from ss_fha.paths import ProjectPaths

    cfg = build_uncertainty_test_case(tmp_path)
    system_cfg = load_system_config(tmp_path / "system.yaml")
    run_flood_hazard(config=cfg, system_config=system_cfg, sim_type="combined", overwrite=False)

    paths = ProjectPaths.from_config(cfg)
    paths.ensure_dirs_exist()

    output_path = run_bootstrap_sample(
        config=cfg,
        paths=paths,
        sim_type="combined",
        sample_id=0,
        overwrite=False,
    )

    assert output_path.exists()
    assert_zarr_valid(path=output_path, expected_vars=["max_wlevel_m"])

    ds = xr.open_dataset(output_path, engine="zarr")
    assert "return_pd_yrs" in ds.dims or "return_pd_yrs" in ds.coords
    assert "x" in ds.dims
    assert "y" in ds.dims
    ds.close()


def test_run_bootstrap_sample_different_seeds_differ(tmp_path: Path) -> None:
    """Two different sample_ids produce different outputs (different RNG seeds)."""
    from ss_fha.analysis.flood_hazard import run_flood_hazard
    from ss_fha.analysis.uncertainty import run_bootstrap_sample
    from ss_fha.config import load_system_config
    from ss_fha.paths import ProjectPaths

    cfg = build_uncertainty_test_case(tmp_path)
    system_cfg = load_system_config(tmp_path / "system.yaml")
    run_flood_hazard(config=cfg, system_config=system_cfg, sim_type="combined", overwrite=False)

    paths = ProjectPaths.from_config(cfg)
    paths.ensure_dirs_exist()

    path_0 = run_bootstrap_sample(config=cfg, paths=paths, sim_type="combined", sample_id=0, overwrite=False)
    path_1 = run_bootstrap_sample(config=cfg, paths=paths, sim_type="combined", sample_id=1, overwrite=False)

    ds0 = xr.open_dataset(path_0, engine="zarr")
    ds1 = xr.open_dataset(path_1, engine="zarr")

    # Not identical — different seeds produce different resamples
    assert not np.array_equal(
        ds0["max_wlevel_m"].values,
        ds1["max_wlevel_m"].values,
    ), "Samples 0 and 1 are identical — RNG seeding may be broken"

    ds0.close()
    ds1.close()


def test_run_bootstrap_sample_overwrite_false_raises(tmp_path: Path) -> None:
    """Running twice with overwrite=False raises DataError."""
    from ss_fha.analysis.flood_hazard import run_flood_hazard
    from ss_fha.analysis.uncertainty import run_bootstrap_sample
    from ss_fha.config import load_system_config
    from ss_fha.exceptions import DataError
    from ss_fha.paths import ProjectPaths

    cfg = build_uncertainty_test_case(tmp_path)
    system_cfg = load_system_config(tmp_path / "system.yaml")
    run_flood_hazard(config=cfg, system_config=system_cfg, sim_type="combined", overwrite=False)

    paths = ProjectPaths.from_config(cfg)
    paths.ensure_dirs_exist()

    run_bootstrap_sample(config=cfg, paths=paths, sim_type="combined", sample_id=0, overwrite=False)

    with pytest.raises(DataError):
        run_bootstrap_sample(config=cfg, paths=paths, sim_type="combined", sample_id=0, overwrite=False)


def test_run_bootstrap_sample_missing_flood_probs_raises(tmp_path: Path) -> None:
    """run_bootstrap_sample raises DataError when flood probs zarr is absent."""
    from ss_fha.analysis.uncertainty import run_bootstrap_sample
    from ss_fha.exceptions import DataError
    from ss_fha.paths import ProjectPaths

    cfg = build_uncertainty_test_case(tmp_path)
    paths = ProjectPaths.from_config(cfg)
    paths.ensure_dirs_exist()

    with pytest.raises(DataError, match="flood probability zarr not found"):
        run_bootstrap_sample(config=cfg, paths=paths, sim_type="combined", sample_id=0, overwrite=False)


# ---------------------------------------------------------------------------
# combine_and_quantile tests
# ---------------------------------------------------------------------------


def _run_all_samples(tmp_path: Path, n_samples: int = 5) -> tuple:
    """Run Workflow 1 + all bootstrap samples. Returns (cfg, paths)."""
    from ss_fha.analysis.flood_hazard import run_flood_hazard
    from ss_fha.analysis.uncertainty import run_bootstrap_sample
    from ss_fha.config import load_system_config
    from ss_fha.paths import ProjectPaths

    cfg = build_uncertainty_test_case(tmp_path)
    system_cfg = load_system_config(tmp_path / "system.yaml")
    run_flood_hazard(config=cfg, system_config=system_cfg, sim_type="combined", overwrite=False)

    paths = ProjectPaths.from_config(cfg)
    paths.ensure_dirs_exist()

    for i in range(n_samples):
        run_bootstrap_sample(config=cfg, paths=paths, sim_type="combined", sample_id=i, overwrite=False)

    return cfg, paths


def test_combine_and_quantile_produces_valid_output(tmp_path: Path) -> None:
    """combine_and_quantile writes a zarr with quantile and spatial dims."""
    from ss_fha.analysis.uncertainty import combine_and_quantile

    cfg, paths = _run_all_samples(tmp_path)
    output_path = combine_and_quantile(config=cfg, paths=paths, sim_type="combined", overwrite=False)

    assert output_path.exists()
    assert_zarr_valid(path=output_path, expected_vars=["max_wlevel_m"])

    ds = xr.open_dataset(output_path, engine="zarr")
    assert "quantile" in ds.coords
    quantiles_in_output = sorted(ds.coords["quantile"].values.tolist())
    assert quantiles_in_output == sorted(cfg.uncertainty.bootstrap_quantiles)
    assert "x" in ds.dims
    assert "y" in ds.dims
    ds.close()


def test_combine_and_quantile_no_na_values(tmp_path: Path) -> None:
    """Combined CI zarr has no NA values."""
    from ss_fha.analysis.uncertainty import combine_and_quantile

    cfg, paths = _run_all_samples(tmp_path)
    output_path = combine_and_quantile(config=cfg, paths=paths, sim_type="combined", overwrite=False)

    ds = xr.open_dataset(output_path, engine="zarr")
    assert not np.any(np.isnan(ds["max_wlevel_m"].values)), "Combined CI zarr contains NA values"
    ds.close()


def test_combine_and_quantile_missing_sample_raises(tmp_path: Path) -> None:
    """combine_and_quantile raises DataError when a sample zarr is missing."""
    from ss_fha.analysis.flood_hazard import run_flood_hazard
    from ss_fha.analysis.uncertainty import combine_and_quantile, run_bootstrap_sample
    from ss_fha.config import load_system_config
    from ss_fha.exceptions import DataError
    from ss_fha.paths import ProjectPaths

    cfg = build_uncertainty_test_case(tmp_path)
    system_cfg = load_system_config(tmp_path / "system.yaml")
    run_flood_hazard(config=cfg, system_config=system_cfg, sim_type="combined", overwrite=False)

    paths = ProjectPaths.from_config(cfg)
    paths.ensure_dirs_exist()

    # Only run 4 of the 5 expected samples
    for i in range(4):
        run_bootstrap_sample(config=cfg, paths=paths, sim_type="combined", sample_id=i, overwrite=False)

    with pytest.raises(DataError, match="missing"):
        combine_and_quantile(config=cfg, paths=paths, sim_type="combined", overwrite=False)


def test_combine_and_quantile_overwrite_false_raises(tmp_path: Path) -> None:
    """Running combine twice with overwrite=False raises DataError."""
    from ss_fha.analysis.uncertainty import combine_and_quantile
    from ss_fha.exceptions import DataError

    cfg, paths = _run_all_samples(tmp_path)
    combine_and_quantile(config=cfg, paths=paths, sim_type="combined", overwrite=False)

    with pytest.raises(DataError):
        combine_and_quantile(config=cfg, paths=paths, sim_type="combined", overwrite=False)


# ---------------------------------------------------------------------------
# Runner script tests
# ---------------------------------------------------------------------------


def test_bootstrap_runner_returns_zero_on_success(tmp_path: Path) -> None:
    """bootstrap_runner.py returns exit code 0 for a valid sample run."""
    import subprocess

    from ss_fha.analysis.flood_hazard import run_flood_hazard
    from ss_fha.config import load_system_config
    from ss_fha.paths import ProjectPaths

    cfg = build_uncertainty_test_case(tmp_path)
    system_cfg = load_system_config(tmp_path / "system.yaml")
    run_flood_hazard(config=cfg, system_config=system_cfg, sim_type="combined", overwrite=False)
    ProjectPaths.from_config(cfg).ensure_dirs_exist()

    result = subprocess.run(
        [
            "conda",
            "run",
            "-n",
            "ss-fha",
            "python",
            "-m",
            "ss_fha.runners.bootstrap_runner",
            "--config",
            str(tmp_path / "analysis.yaml"),
            "--sample-id",
            "0",
            "--sim-type",
            "combined",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, (
        f"Runner exited with code {result.returncode}.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "COMPLETE: bootstrap_sample combined 0000" in result.stdout


def test_bootstrap_combine_runner_returns_zero_on_success(tmp_path: Path) -> None:
    """bootstrap_combine_runner.py returns exit code 0 after all samples exist."""
    import subprocess

    cfg, paths = _run_all_samples(tmp_path)

    result = subprocess.run(
        [
            "conda",
            "run",
            "-n",
            "ss-fha",
            "python",
            "-m",
            "ss_fha.runners.bootstrap_combine_runner",
            "--config",
            str(tmp_path / "analysis.yaml"),
            "--sim-type",
            "combined",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, (
        f"Runner exited with code {result.returncode}.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "COMPLETE: bootstrap_combine combined" in result.stdout


def test_bootstrap_runner_returns_nonzero_for_missing_config(tmp_path: Path) -> None:
    """bootstrap_runner.py returns exit code 2 when config file does not exist."""
    import subprocess

    result = subprocess.run(
        [
            "conda",
            "run",
            "-n",
            "ss-fha",
            "python",
            "-m",
            "ss_fha.runners.bootstrap_runner",
            "--config",
            str(tmp_path / "nonexistent.yaml"),
            "--sample-id",
            "0",
            "--sim-type",
            "combined",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 2
