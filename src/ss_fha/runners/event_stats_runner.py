"""Event statistics runner: univariate and multivariate event return periods.

CLI entry point for computing event return periods from weather event time series.
Designed to be invoked by Snakemake or directly from the command line.

Usage::

    python -m ss_fha.runners.event_stats_runner \\
        --config cases/norfolk/analysis_ssfha_combined.yaml \\
        --system-config cases/norfolk/system.yaml \\
        --output-format zarr

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
    """Main entry point for the event statistics runner."""
    parser = argparse.ArgumentParser(
        description="Compute univariate and multivariate event return periods from weather time series"
    )
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
        "--output-format",
        type=str,
        required=True,
        choices=["zarr", "netcdf"],
        help="Output format: 'zarr' (primary) or 'netcdf' (secondary)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Overwrite existing output if it exists",
    )

    try:
        args = parser.parse_args()
    except SystemExit as e:
        if e.code != 0:
            logger.error("Failed to parse command-line arguments")
            return 2
        return 0

    # Validate paths exist before importing heavy dependencies
    if not args.config.exists():
        logger.error("Analysis config not found: %s", args.config)
        return 2
    if not args.system_config.exists():
        logger.error("System config not found: %s", args.system_config)
        return 2

    try:
        from ss_fha.analysis.event_comparison import run_event_comparison
        from ss_fha.config import load_config, load_system_config
        from ss_fha.config.model import SsfhaConfig

        logger.info("Loading system config: %s", args.system_config)
        load_system_config(args.system_config)  # validates system config; result not used here

        logger.info("Loading analysis config: %s", args.config)
        config = load_config(args.config)

        if not isinstance(config, SsfhaConfig):
            logger.error(
                "Analysis config has fha_approach='%s' but event_stats_runner requires fha_approach='ssfha'.",
                config.fha_approach,
            )
            return 1

        logger.info(
            "Starting event statistics computation: fha_id=%s, output_format=%s",
            config.fha_id,
            args.output_format,
        )

        output_path = run_event_comparison(
            config=config,
            output_format=args.output_format,
            overwrite=args.overwrite,
        )

        logger.info("Output written to: %s", output_path)
        logger.info("COMPLETE: event_stats")
        return 0

    except Exception as e:
        logger.error("Exception during event statistics computation: %s", e)
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
