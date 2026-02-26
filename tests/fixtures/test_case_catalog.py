"""Test case catalog for ss-fha.

HydroShare integration is deferred until the HPC implementation phase.
The ``retrieve_norfolk_case_study`` function is stubbed here so that the
catalog module is importable and the ``@pytest.mark.slow`` machinery works,
but calling it raises ``NotImplementedError``.
"""

import pytest

from tests.utils_for_testing import skip_if_no_hydroshare


@pytest.mark.slow
@skip_if_no_hydroshare
def retrieve_norfolk_case_study(start_from_scratch: bool) -> None:
    """Download the Norfolk case study from HydroShare and set up test data.

    .. note::
        **Not yet implemented.** HydroShare download is deferred until the HPC
        implementation phase. This stub ensures the catalog is importable and
        that the ``@pytest.mark.slow`` / ``skip_if_no_hydroshare`` machinery
        is in place for when the implementation lands.

    Parameters
    ----------
    start_from_scratch:
        If True, re-download and overwrite any existing local copy.

    Raises
    ------
    NotImplementedError
        Always — implementation is deferred to the HPC phase.
    """
    raise NotImplementedError(
        "retrieve_norfolk_case_study is not yet implemented. "
        "HydroShare download is deferred to the HPC implementation phase."
    )
