"""Registry of available ss-fha case studies.

Each case study has a HydroShare resource ID that uniquely identifies its
data archive. The Norfolk ID is a placeholder until the HydroShare resource
is created and published. Calling any function that requires the ID before it
is populated will raise a clear ConfigurationError — no silent no-ops.

HydroShare upload and the download infrastructure (SSFHAExample class,
download_norfolk_case_study()) are deferred to work chunk 06A.
"""

from __future__ import annotations

from ss_fha.exceptions import ConfigurationError


# ---------------------------------------------------------------------------
# Norfolk case study
# ---------------------------------------------------------------------------

# Populated when the HydroShare resource is created and published.
# Until then, this sentinel value triggers a clear error on any attempt to use it.
_NORFOLK_HYDROSHARE_RESOURCE_ID_VALUE: str | None = None


def NORFOLK_HYDROSHARE_RESOURCE_ID() -> str:
    """Return the HydroShare resource ID for the Norfolk case study.

    Raises:
        ConfigurationError: If the resource ID has not been populated yet.
            Populate ``_NORFOLK_HYDROSHARE_RESOURCE_ID_VALUE`` in this module
            once the HydroShare resource is created.
    """
    if _NORFOLK_HYDROSHARE_RESOURCE_ID_VALUE is None:
        raise ConfigurationError(
            field="NORFOLK_HYDROSHARE_RESOURCE_ID",
            message=(
                "The Norfolk HydroShare resource ID has not been set. "
                "This will be populated in work chunk 06A once the HydroShare "
                "resource is created and published. "
                "For local development, use the staging directory directly "
                "via the case study YAML configs in cases/norfolk_ssfha_comparison/."
            ),
        )
    return _NORFOLK_HYDROSHARE_RESOURCE_ID_VALUE


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

CASE_STUDY_REGISTRY: dict[str, dict] = {
    "norfolk_ssfha_comparison": {
        "description": (
            "Norfolk, VA — semicontinuous simulation-based flood hazard assessment "
            "comparing SSFHA and BDS approaches across combined, rain-only, and "
            "surge-only driver scenarios."
        ),
        "hydroshare_resource_id_fn": NORFOLK_HYDROSHARE_RESOURCE_ID,
        "config_template": "norfolk_default.yaml",
    },
}
