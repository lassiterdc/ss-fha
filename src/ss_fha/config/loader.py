"""YAML loading and config instantiation for ss-fha.

Public API:
    load_system_config(yaml_path)     -> SystemConfig
    load_config(yaml_path)            -> SsfhaConfig | BdsConfig
    load_config_from_dict(d)          -> SsfhaConfig | BdsConfig

Template placeholder support:
    YAML files may contain {{key}} placeholders. Pass a `placeholders` dict
    to load_system_config / load_config to substitute values before parsing.

System-merge behaviour:
    If an analysis YAML contains a `study_area_config` key, load_config reads
    the referenced system.yaml and merges its fields into the analysis dict
    before Pydantic parsing. Analysis-level fields always win over system fields.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import TypeAdapter, ValidationError as PydanticValidationError

from ss_fha.config.model import (
    SSFHAConfig,
    SystemConfig,
)
from ss_fha.exceptions import ConfigurationError, DataError


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fill_placeholders(raw: str, placeholders: dict[str, str]) -> str:
    """Replace all {{key}} occurrences in *raw* with values from *placeholders*."""
    for key, value in placeholders.items():
        raw = raw.replace(f"{{{{{key}}}}}", value)
    # Warn if any unfilled placeholders remain
    remaining = re.findall(r"\{\{[^}]+\}\}", raw)
    if remaining:
        raise ConfigurationError(
            field="template_placeholders",
            message=(
                f"Unfilled template placeholder(s) in YAML: {remaining}. "
                "Pass a 'placeholders' dict to fill them before parsing."
            ),
        )
    return raw


def _read_yaml(yaml_path: Path, placeholders: dict[str, str] | None = None) -> dict:
    """Read a YAML file, optionally filling template placeholders."""
    try:
        raw = yaml_path.read_text(encoding="utf-8")
    except OSError as e:
        raise DataError(
            operation="read YAML",
            filepath=yaml_path,
            reason=str(e),
        ) from e

    if placeholders:
        raw = _fill_placeholders(raw, placeholders)
    elif re.search(r"\{\{[^}]+\}\}", raw):
        # Placeholders present but no substitutions provided — fail fast
        found = re.findall(r"\{\{[^}]+\}\}", raw)
        raise ConfigurationError(
            field="template_placeholders",
            message=(
                f"YAML contains template placeholder(s) {found} "
                "but no 'placeholders' dict was provided."
            ),
        )

    return yaml.safe_load(raw) or {}


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge *override* into *base*, with override values winning.

    Nested dicts are merged recursively; all other types are replaced.
    """
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_system_config(
    yaml_path: Path | str,
    placeholders: dict[str, str] | None = None,
) -> SystemConfig:
    """Load a system.yaml file into a SystemConfig model.

    Args:
        yaml_path: Path to the system YAML file.
        placeholders: Optional dict of {{key}} -> value substitutions.

    Returns:
        Validated SystemConfig instance.

    Raises:
        DataError: If the file cannot be read.
        ConfigurationError: If template placeholders are unfilled or FEMA
            fields are inconsistently specified.
        pydantic.ValidationError: If required fields are missing or have
            wrong types.
    """
    yaml_path = Path(yaml_path)
    data = _read_yaml(yaml_path, placeholders)
    return SystemConfig.model_validate(data)


def load_config(
    yaml_path: Path | str,
    placeholders: dict[str, str] | None = None,
) -> SsfhaConfig | BdsConfig:  # type: ignore[name-defined]
    """Load an analysis YAML file into an SSFHAConfig (SsfhaConfig or BdsConfig).

    If the YAML contains a ``study_area_config`` key, the referenced system.yaml
    is loaded and its fields are merged into the analysis dict before Pydantic
    parsing. Analysis-level fields always override system-level fields.

    After parsing, if ``output_dir`` is None it is set to the YAML file's
    parent directory.

    Args:
        yaml_path: Path to the analysis YAML file.
        placeholders: Optional dict of {{key}} -> value substitutions.

    Returns:
        Validated SsfhaConfig or BdsConfig instance.

    Raises:
        DataError: If any YAML file cannot be read.
        ConfigurationError: If template placeholders are unfilled or toggle
            dependencies are violated.
        pydantic.ValidationError: If required fields are missing or have
            wrong types.
    """
    yaml_path = Path(yaml_path)
    analysis_data = _read_yaml(yaml_path, placeholders)

    # Merge system config if referenced
    system_config_path = analysis_data.get("study_area_config")
    if system_config_path is not None:
        system_path = Path(system_config_path)
        if not system_path.is_absolute():
            # Try yaml-parent-relative first; fall back to CWD-relative.
            # CWD-relative supports project-root-relative paths (the common pattern
            # when users run `ssfha.run()` from the project root).
            candidate = yaml_path.parent / system_path
            system_path = candidate if candidate.exists() else Path.cwd() / system_path
        system_data = _read_yaml(system_path, placeholders)
        # System fields are the base; analysis fields win on conflict
        analysis_data = _deep_merge(system_data, analysis_data)

    cfg = load_config_from_dict(analysis_data)

    # Set output_dir to yaml parent if not specified
    if cfg.output_dir is None:
        object.__setattr__(cfg, "output_dir", yaml_path.parent)

    return cfg


def load_config_from_dict(d: dict[str, Any]) -> SsfhaConfig | BdsConfig:  # type: ignore[name-defined]
    """Instantiate an SSFHAConfig from a plain dict.

    Uses the Pydantic v2 discriminated union TypeAdapter to select
    SsfhaConfig or BdsConfig based on the ``fha_approach`` field.

    Args:
        d: Dict matching the SSFHAConfig schema.

    Returns:
        Validated SsfhaConfig or BdsConfig instance.

    Raises:
        ConfigurationError: If ``fha_approach`` is missing or unrecognised.
        pydantic.ValidationError: If required fields are missing or invalid.
    """
    if "fha_approach" not in d:
        raise ConfigurationError(
            field="fha_approach",
            message=(
                "'fha_approach' is required and must be one of: 'ssfha', 'bds'. "
                "It was not found in the provided dict."
            ),
        )

    adapter: TypeAdapter = TypeAdapter(SSFHAConfig)
    return adapter.validate_python(d)
