"""Workflow 1 runner: Flood Hazard Assessment.

CLI entry point for computing flood probabilities from TRITON outputs.
Designed to be invoked by Snakemake or directly from the command line.

Usage::

    python -m ss_fha.runners.flood_hazard_runner \\
        --config cases/norfolk/analysis_ssfha_combined.yaml \\
        --system-config cases/norfolk/system.yaml \\
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
    """Main entry point for the flood hazard runner."""
    parser = argparse.ArgumentParser(description="Compute flood probabilities from TRITON model outputs")
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to the analysis configuration YAML file",
    )
    parser.add_argument(
        "--system-config",
        type=Path,
        required=True,
        help="Path to the system configuration YAML file",
    )
    parser.add_argument(
        "--sim-type",
        type=str,
        required=True,
        choices=["combined", "surge_only", "rain_only", "triton_only_combined"],
        help="Simulation type to process",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Overwrite existing output zarr if it exists",
    )

    try:
        args = parser.parse_args()
    except SystemExit as e:
        if e.code != 0:
            logger.error("Failed to parse command-line arguments")
            return 2
        return 0

    # Validate paths exist
    if not args.config.exists():
        logger.error("Analysis config not found: %s", args.config)
        return 2
    if not args.system_config.exists():
        logger.error("System config not found: %s", args.system_config)
        return 2

    try:
        from ss_fha.analysis.flood_hazard import run_flood_hazard
        from ss_fha.config import load_config, load_system_config

        logger.info("Loading system config: %s", args.system_config)
        system_cfg = load_system_config(args.system_config)

        logger.info("Loading analysis config: %s", args.config)
        config = load_config(args.config)

        # Validate that the loaded config is an SSFHA config
        from ss_fha.config.model import SsfhaConfig

        if not isinstance(config, SsfhaConfig):
            logger.error(
                "Analysis config has fha_approach='%s' but flood_hazard_runner requires fha_approach='ssfha'.",
                config.fha_approach,
            )
            return 1

        logger.info("Starting flood hazard assessment: sim_type=%s", args.sim_type)
        output_path = run_flood_hazard(
            config=config,
            system_config=system_cfg,
            sim_type=args.sim_type,
            overwrite=args.overwrite,
        )

        logger.info("Output written to: %s", output_path)
        logger.info("COMPLETE: flood_hazard %s", args.sim_type)
        return 0

    except Exception as e:
        logger.error("Exception during flood hazard assessment: %s", e)
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
