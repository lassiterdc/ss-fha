"""Workflow 2 runner: Single Bootstrap Sample.

CLI entry point for computing return-period-indexed flood depths for one
bootstrap resample. Designed to be invoked by Snakemake once per sample_id
in a fan-out pattern — each invocation is fully independent.

Usage::

    python -m ss_fha.runners.bootstrap_runner \\
        --config cases/norfolk/analysis_ssfha_combined.yaml \\
        --sample-id 0 \\
        --sim-type combined

Exit codes:
    0: Success
    1: Failure (exception occurred)
    2: Invalid arguments
"""

from __future__ import annotations

import argparse
import logging
import sys
import traceback
from pathlib import Path

# Configure logging to stdout (Snakemake captures stdout into logfiles)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def main() -> int:
    """Main entry point for the bootstrap sample runner."""
    parser = argparse.ArgumentParser(
        description="Compute return-period-indexed flood depths for one bootstrap resample"
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to the analysis configuration YAML file",
    )
    parser.add_argument(
        "--sample-id",
        type=int,
        required=True,
        help="Zero-based bootstrap sample index (determines RNG seed)",
    )
    parser.add_argument(
        "--sim-type",
        type=str,
        required=True,
        choices=["combined", "surge_only", "rain_only", "triton_only_combined"],
        help="Simulation type to bootstrap",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Overwrite existing sample zarr if it exists",
    )

    try:
        args = parser.parse_args()
    except SystemExit as e:
        if e.code != 0:
            logger.error("Failed to parse command-line arguments")
            return 2
        return 0

    if not args.config.exists():
        logger.error("Analysis config not found: %s", args.config)
        return 2

    try:
        from ss_fha.analysis.uncertainty import run_bootstrap_sample
        from ss_fha.config import load_config
        from ss_fha.config.model import SsfhaConfig
        from ss_fha.paths import ProjectPaths

        logger.info("Loading analysis config: %s", args.config)
        config = load_config(args.config)

        if not isinstance(config, SsfhaConfig):
            logger.error(
                "bootstrap_runner requires fha_approach='ssfha', got '%s'.",
                config.fha_approach,
            )
            return 1

        paths = ProjectPaths.from_config(config)
        paths.ensure_dirs_exist()

        logger.info(
            "Starting bootstrap sample: sample_id=%d, sim_type=%s",
            args.sample_id,
            args.sim_type,
        )
        output_path = run_bootstrap_sample(
            config=config,
            paths=paths,
            sim_type=args.sim_type,
            sample_id=args.sample_id,
            overwrite=args.overwrite,
        )

        logger.info("Output written to: %s", output_path)
        logger.info("COMPLETE: bootstrap_sample %s %04d", args.sim_type, args.sample_id)
        return 0

    except Exception as e:
        logger.error("Exception during bootstrap sample: %s", e)
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
