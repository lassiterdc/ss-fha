"""Workflow 2 runner: Bootstrap Combine + Quantile.

CLI entry point for combining all per-sample bootstrap zarrs and computing
0.05/0.50/0.95 quantile confidence intervals. Invoked once after all
bootstrap_runner.py fan-out jobs complete.

Usage::

    python -m ss_fha.runners.bootstrap_combine_runner \\
        --config cases/norfolk/analysis_ssfha_combined.yaml \\
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
    """Main entry point for the bootstrap combine runner."""
    parser = argparse.ArgumentParser(description="Combine bootstrap sample zarrs and compute quantile CIs")
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to the analysis configuration YAML file",
    )
    parser.add_argument(
        "--sim-type",
        type=str,
        required=True,
        choices=["combined", "surge_only", "rain_only", "triton_only_combined"],
        help="Simulation type to combine",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Overwrite existing combined CI zarr if it exists",
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
        from ss_fha.analysis.uncertainty import combine_and_quantile
        from ss_fha.config import load_config
        from ss_fha.config.model import SsfhaConfig
        from ss_fha.paths import ProjectPaths

        logger.info("Loading analysis config: %s", args.config)
        config = load_config(args.config)

        if not isinstance(config, SsfhaConfig):
            logger.error(
                "bootstrap_combine_runner requires fha_approach='ssfha', got '%s'.",
                config.fha_approach,
            )
            return 1

        paths = ProjectPaths.from_config(config)

        logger.info("Starting bootstrap combine: sim_type=%s", args.sim_type)
        output_path = combine_and_quantile(
            config=config,
            paths=paths,
            sim_type=args.sim_type,
            overwrite=args.overwrite,
        )

        logger.info("Output written to: %s", output_path)
        logger.info("COMPLETE: bootstrap_combine %s", args.sim_type)
        return 0

    except Exception as e:
        logger.error("Exception during bootstrap combine: %s", e)
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
