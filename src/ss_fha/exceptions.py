"""Custom exception hierarchy for ss-fha.

All ss-fha exceptions inherit from SSFHAError, allowing users to catch
all package errors with a single except clause while still providing
specific error types for different failure modes.

Each exception stores contextual attributes (file paths, field names,
operation descriptions) to enable programmatic error handling and
actionable error messages.

Note on naming: SSFHAValidationError is used internally (instead of
ValidationError) to avoid shadowing pydantic.ValidationError in
modules that import from both packages.
"""

from pathlib import Path


class SSFHAError(Exception):
    """Base exception for all ss-fha errors.

    Catch this to handle all package-specific exceptions.
    """
    pass


class ConfigurationError(SSFHAError):
    """Invalid configuration values or missing required fields.

    Raised when:
    - Required fields are missing based on toggle states
    - Configuration values fail validation rules
    - Conflicting options are specified together

    Attributes:
        field: The configuration field that failed validation
    """
    def __init__(self, field: str, message: str):
        self.field = field

        super().__init__(f"Configuration error in field '{field}'\n  {message}")


class DataError(SSFHAError):
    """Data loading, parsing, or I/O failure.

    Raised when reading input data fails (zarr, NetCDF, CSV, shapefile)
    or when data does not meet expected structural requirements.

    Attributes:
        operation: Description of the operation that failed
        filepath: Path to the file being read or written
        reason: Detailed error reason (typically str(e) from the caught exception)
    """
    def __init__(self, operation: str, filepath: Path, reason: str):
        self.operation = operation
        self.filepath = filepath
        self.reason = reason

        super().__init__(
            f"Data error during: {operation}\n"
            f"  File: {filepath}\n"
            f"  Reason: {reason}"
        )


class BootstrapError(SSFHAError):
    """Bootstrap sampling failure.

    Raised when a bootstrap sample cannot be drawn or processed,
    e.g., due to degenerate inputs or index out of range.

    Attributes:
        sample_id: The bootstrap sample index that failed
        reason: Detailed error reason (typically str(e) from the caught exception)
    """
    def __init__(self, sample_id: int, reason: str):
        self.sample_id = sample_id
        self.reason = reason

        super().__init__(
            f"Bootstrap error for sample_id={sample_id}\n"
            f"  Reason: {reason}"
        )


class WorkflowError(SSFHAError):
    """Snakemake workflow execution failure.

    Raised when a Snakemake workflow phase fails. `stderr` is the captured
    subprocess output and should always be forwarded — it is what gets
    collected by Snakemake into runner log files.

    Attributes:
        phase: Which workflow phase failed (e.g., 'flood_hazard', 'bootstrap')
        stderr: Captured stderr from the Snakemake process
    """
    def __init__(self, phase: str, stderr: str):
        self.phase = phase
        self.stderr = stderr

        lines = [f"Workflow failed during '{phase}' phase"]
        if stderr.strip():
            lines.append(f"  Error output:\n{self._indent(stderr)}")

        super().__init__("\n".join(lines))

    @staticmethod
    def _indent(text: str, prefix: str = "    ") -> str:
        """Indent multi-line text for error message formatting."""
        return "\n".join(prefix + line for line in text.split("\n"))


class SSFHAValidationError(SSFHAError):
    """Validation failure with a list of specific issues.

    Raised when one or more validation checks fail simultaneously,
    allowing all issues to be reported at once rather than one at a time.

    Named SSFHAValidationError (not ValidationError) to avoid shadowing
    pydantic.ValidationError. At any use site that imports from both packages,
    alias one explicitly: `from pydantic import ValidationError as PydanticValidationError`.

    Attributes:
        issues: List of human-readable validation issue descriptions
    """
    def __init__(self, issues: list[str]):
        self.issues = issues

        header = f"Validation failed with {len(issues)} issue(s):"
        formatted = "\n".join(f"  - {issue}" for issue in issues)

        super().__init__(f"{header}\n{formatted}")
