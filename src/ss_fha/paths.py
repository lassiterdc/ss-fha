"""Output path dataclasses for ss-fha.

`ProjectPaths` is the sole path management class. It organises all *output*
directories derived from a loaded `SSFHAConfig`. Input data paths (zarr files,
shapefiles, CSVs) are stored directly on the config model and are not
represented here.

Path structure::

    output_dir/               ← shared project root (multiple FHA analyses may share this)
        {fha_id}/             ← per-analysis root (fha_dir); all workflow outputs live here
            logs/
            flood_probabilities/
            bootstrap/
                samples/
            ppcct/
            flood_risk/
            event_statistics/
            figures/

Scoping workflow outputs under ``fha_id`` prevents collisions when multiple
analysis configs (e.g. ``ssfha_combined`` and ``ssfha_triton_only_combined``)
share the same ``output_dir``. This matches the Snakemake wildcard design in
the master refactor plan (``{output_dir}/{fha_id}/flood_probabilities/...``).

Usage::

    from ss_fha.config import load_config
    from ss_fha.paths import ProjectPaths

    cfg = load_config("cases/norfolk/analysis_ssfha_combined.yaml")
    paths = ProjectPaths.from_config(cfg)
    paths.ensure_dirs_exist()
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ss_fha.exceptions import ConfigurationError

if TYPE_CHECKING:
    from ss_fha.config.model import BdsConfig, SsfhaConfig

    SSFHAConfig = SsfhaConfig | BdsConfig


@dataclass
class ProjectPaths:
    """Resolved output directory paths for a single FHA analysis.

    All fields are absolute `Path` objects. Instantiate via
    `ProjectPaths.from_config(config)` — never directly.
    """

    # Root
    output_dir: Path  # shared project output root (output_dir from config)

    # Per-analysis root — all workflow dirs are nested under this
    fha_dir: Path  # output_dir / fha_id

    # Shared infrastructure
    logs_dir: Path  # fha_dir / "logs"

    # Workflow 1: Flood hazard
    flood_probs_dir: Path  # fha_dir / "flood_probabilities"

    # Workflow 2: Uncertainty (bootstrap)
    bootstrap_dir: Path  # fha_dir / "bootstrap"
    bootstrap_samples_dir: Path  # bootstrap_dir / "samples"

    # Workflow 3: PPCCT validation
    ppcct_dir: Path  # fha_dir / "ppcct"

    # Workflow 4: Flood risk
    flood_risk_dir: Path  # fha_dir / "flood_risk"

    # Shared outputs
    event_stats_dir: Path  # fha_dir / "event_statistics"
    figures_dir: Path  # fha_dir / "figures"

    @classmethod
    def from_config(cls, config: SSFHAConfig) -> ProjectPaths:
        """Construct `ProjectPaths` from a loaded analysis config.

        Parameters
        ----------
        config:
            A fully loaded `SsfhaConfig` or `BdsConfig` instance. The loader
            guarantees `output_dir` is set; if it is `None` (e.g., config was
            constructed manually without going through the loader), a
            `ConfigurationError` is raised immediately.

        Raises
        ------
        ConfigurationError
            If `config.output_dir` is `None`.
        """
        if config.output_dir is None:
            raise ConfigurationError(
                field="output_dir",
                message=(
                    "output_dir is None. Load the config via "
                    "ss_fha.config.load_config() so that output_dir is "
                    "resolved automatically from the YAML file location."
                ),
            )

        out = config.output_dir
        fha_dir = out / config.fha_id
        bootstrap_dir = fha_dir / "bootstrap"

        return cls(
            output_dir=out,
            fha_dir=fha_dir,
            logs_dir=fha_dir / "logs",
            flood_probs_dir=fha_dir / "flood_probabilities",
            bootstrap_dir=bootstrap_dir,
            bootstrap_samples_dir=bootstrap_dir / "samples",
            ppcct_dir=fha_dir / "ppcct",
            flood_risk_dir=fha_dir / "flood_risk",
            event_stats_dir=fha_dir / "event_statistics",
            figures_dir=fha_dir / "figures",
        )

    def ensure_dirs_exist(self) -> None:
        """Create all output directories if they do not already exist.

        Uses `dataclasses.fields()` to find every field whose name ends with
        `_dir`, so newly added `_dir` fields are automatically included without
        updating this method.
        """
        for field in dataclasses.fields(self):
            if field.name.endswith("_dir"):
                path: Path = getattr(self, field.name)
                path.mkdir(parents=True, exist_ok=True)
