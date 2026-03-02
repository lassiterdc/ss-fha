"""Runner scripts for ss-fha workflows.

Each runner is a CLI entry point invocable by Snakemake via
``python -m ss_fha.runners.<name>``. Runners log to stdout
(captured by Snakemake into logfiles) and emit a structured
completion marker on success.
"""
