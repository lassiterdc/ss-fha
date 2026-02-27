"""Project-wide constants for ss-fha.

All module-level constants that are not case-study-specific belong here.
Case-study-specific values (e.g. n_years_synthesized, return_periods,
rain windows) are defined in user YAML configs, not here.

Convention: all names are UPPER_SNAKE_CASE (public) or _UPPER_SNAKE_CASE
(private to this package, not part of the public API).
"""

# ---------------------------------------------------------------------------
# Weather event index
# ---------------------------------------------------------------------------

# Accepted aliases for the year dimension in weather event multi-indices.
# Any of these values in weather_event_indices satisfies the "year required"
# validation rule. The actual string used in subsetting is always whatever
# the user specified — no normalization is performed.
WEATHER_EVENT_INDEX_YEAR_ALIASES: frozenset[str] = frozenset({"year", "yr", "y"})


# ---------------------------------------------------------------------------
# Empirical CDF duplicate handling
# ---------------------------------------------------------------------------

# When True, events with identical statistic values are all assigned the
# maximum return period of their group rather than progressively increasing
# CDF values. Always False for Norfolk. The semantically correct choice for
# other case studies is unresolved. Promote to SsfhaConfig when resolved.
ASSIGN_DUP_VALS_MAX_RETURN: bool = False
