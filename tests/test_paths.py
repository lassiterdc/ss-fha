"""Tests for ss_fha.paths (Work Chunk 01C)."""

import dataclasses
from pathlib import Path

import pytest

from ss_fha.config import load_config_from_dict
from ss_fha.exceptions import ConfigurationError
from ss_fha.paths import ProjectPaths


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

_MINIMAL_SSFHA_DICT = {
    "fha_id": "test_ssfha",
    "fha_approach": "ssfha",
    "project_name": "test_project",
    "is_comparative_analysis": True,  # avoids requiring event_statistic_variables
    "n_years_synthesized": 1000,
    "return_periods": [1, 2, 10, 100],
    "toggle_uncertainty": False,
    "toggle_mcds": False,
    "toggle_ppcct": False,
    "toggle_flood_risk": False,
    "toggle_design_comparison": False,
    "alpha": 0.0,
    "beta": 0.0,
    "triton_outputs": {"combined": "/tmp/fake_combined.zarr"},
    "event_data": {"sim_event_summaries": "/tmp/fake_summaries.csv"},
    "execution": {"mode": "local_concurrent"},
}


@pytest.fixture
def ssfha_config_with_output(tmp_path):
    """SsfhaConfig with output_dir set to a real temp directory."""
    d = dict(_MINIMAL_SSFHA_DICT)
    d["output_dir"] = str(tmp_path / "outputs")
    return load_config_from_dict(d)


@pytest.fixture
def ssfha_config_no_output():
    """SsfhaConfig with output_dir left as None (bypasses loader default)."""
    return load_config_from_dict(_MINIMAL_SSFHA_DICT)


# ---------------------------------------------------------------------------
# Import check
# ---------------------------------------------------------------------------

def test_project_paths_importable():
    """ProjectPaths can be imported from ss_fha.paths."""
    from ss_fha.paths import ProjectPaths  # noqa: F401


# ---------------------------------------------------------------------------
# from_config: path resolution
# ---------------------------------------------------------------------------

def test_paths_from_config(ssfha_config_with_output, tmp_path):
    """from_config() resolves all expected paths from output_dir."""
    paths = ProjectPaths.from_config(ssfha_config_with_output)
    out = tmp_path / "outputs"

    assert paths.output_dir == out
    assert paths.logs_dir == out / "logs"
    assert paths.flood_probs_dir == out / "flood_probabilities"
    assert paths.bootstrap_dir == out / "bootstrap"
    assert paths.bootstrap_samples_dir == out / "bootstrap" / "samples"
    assert paths.ppcct_dir == out / "ppcct"
    assert paths.flood_risk_dir == out / "flood_risk"
    assert paths.event_stats_dir == out / "event_statistics"
    assert paths.figures_dir == out / "figures"


def test_paths_are_path_objects(ssfha_config_with_output):
    """All fields on ProjectPaths are Path instances."""
    paths = ProjectPaths.from_config(ssfha_config_with_output)
    for field in dataclasses.fields(paths):
        assert isinstance(getattr(paths, field.name), Path), (
            f"Field '{field.name}' is not a Path"
        )


def test_bootstrap_samples_nested_under_bootstrap(ssfha_config_with_output):
    """bootstrap_samples_dir is a subdirectory of bootstrap_dir."""
    paths = ProjectPaths.from_config(ssfha_config_with_output)
    assert paths.bootstrap_samples_dir.parent == paths.bootstrap_dir


def test_all_dirs_are_under_output_dir(ssfha_config_with_output):
    """Every _dir field (except output_dir itself) is under output_dir."""
    paths = ProjectPaths.from_config(ssfha_config_with_output)
    for field in dataclasses.fields(paths):
        if field.name == "output_dir":
            continue
        if field.name.endswith("_dir"):
            value: Path = getattr(paths, field.name)
            assert paths.output_dir in value.parents, (
                f"Field '{field.name}' ({value}) is not under output_dir ({paths.output_dir})"
            )


# ---------------------------------------------------------------------------
# from_config: None output_dir raises
# ---------------------------------------------------------------------------

def test_from_config_raises_if_output_dir_is_none(ssfha_config_no_output):
    """from_config() raises ConfigurationError when output_dir is None."""
    assert ssfha_config_no_output.output_dir is None  # confirm precondition
    with pytest.raises(ConfigurationError) as exc_info:
        ProjectPaths.from_config(ssfha_config_no_output)
    assert "output_dir" in str(exc_info.value)


# ---------------------------------------------------------------------------
# ensure_dirs_exist
# ---------------------------------------------------------------------------

def test_ensure_dirs_creates_directories(ssfha_config_with_output):
    """ensure_dirs_exist() creates all _dir directories on the filesystem."""
    paths = ProjectPaths.from_config(ssfha_config_with_output)
    paths.ensure_dirs_exist()

    for field in dataclasses.fields(paths):
        if field.name.endswith("_dir"):
            path: Path = getattr(paths, field.name)
            assert path.is_dir(), f"Directory not created: {field.name} = {path}"


def test_ensure_dirs_idempotent(ssfha_config_with_output):
    """ensure_dirs_exist() can be called multiple times without error."""
    paths = ProjectPaths.from_config(ssfha_config_with_output)
    paths.ensure_dirs_exist()
    paths.ensure_dirs_exist()  # should not raise


def test_ensure_dirs_creates_nested_paths(ssfha_config_with_output):
    """ensure_dirs_exist() creates nested paths (bootstrap/samples) correctly."""
    paths = ProjectPaths.from_config(ssfha_config_with_output)
    paths.ensure_dirs_exist()
    assert paths.bootstrap_samples_dir.is_dir()
    assert paths.bootstrap_samples_dir.parent.is_dir()
