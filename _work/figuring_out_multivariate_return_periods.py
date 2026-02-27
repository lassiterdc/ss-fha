# %%
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


def compute_AND_multivar_return_period_for_sample(
    sample_values, df_all_samples, n_samples, alpha, beta
):
    """
    Empirical non-exceedance for the AND exceedance definition.

    For threshold vector z = (z1, z2):
      AND exceedance event: E_AND = {X1 > z1 AND X2 > z2}
      Complement:           E_AND^c = {X1 <= z1 OR  X2 <= z2}

    This function estimates F_AND(z) = P(E_AND^c), i.e., the non-exceedance
    probability associated with AND exceedance.

    Notes:
    - `.any(axis=1)` is OR logic in complement space.
    - Exceedance probability is p_exceed_AND = 1 - F_AND.
    - Return period is RP_AND = 1 / p_exceed_AND.
    """
    df_exceedance = df_all_samples <= sample_values
    # Complement of AND exceedance: at least one variable is <= threshold.
    n_1_lessthan_or_equal_to = df_exceedance.any(axis=1).sum()
    emp_cdf_val_AND = (n_1_lessthan_or_equal_to - alpha) / (
        n_samples + 1 - alpha - beta
    )
    # Memory aid at same threshold z:
    # F_AND >= F_OR  =>  p_exceed_AND <= p_exceed_OR  =>  RP_AND >= RP_OR
    return emp_cdf_val_AND


def compute_OR_multivar_return_period_for_sample(
    sample_values, df_all_samples, n_samples, alpha, beta
):
    """
    Empirical non-exceedance for the OR exceedance definition.

    For threshold vector z = (z1, z2):
      OR exceedance event: E_OR = {X1 > z1 OR  X2 > z2}
      Complement:          E_OR^c = {X1 <= z1 AND X2 <= z2}

    This function estimates F_OR(z) = P(E_OR^c), i.e., the non-exceedance
    probability associated with OR exceedance.

    Notes:
    - `.all(axis=1)` is AND logic in complement space.
    - Exceedance probability is p_exceed_OR = 1 - F_OR.
    - Return period is RP_OR = 1 / p_exceed_OR.
    """
    df_exceedance = df_all_samples <= sample_values
    # Complement of OR exceedance: all variables are <= threshold.
    n_all_lessthan_or_equal_to = df_exceedance.all(axis=1).sum()
    emp_cdf_val_OR = (n_all_lessthan_or_equal_to - alpha) / (
        n_samples + 1 - alpha - beta
    )
    # Memory aid at same threshold z:
    # F_OR <= F_AND  =>  p_exceed_OR >= p_exceed_AND  =>  RP_OR <= RP_AND
    return emp_cdf_val_OR


def _compute_empirical_results(
    df_events: pd.DataFrame, alpha: float = 0, beta: float = 0
) -> pd.DataFrame:
    """Compute empirical multivariate CDF + exceedance + return period for each event."""
    n_samples = len(df_events)
    out = df_events.copy()

    out["emp_cdf_AND"] = out.apply(
        lambda row: compute_AND_multivar_return_period_for_sample(
            sample_values=row[["mm_per_hr", "waterlevel_m"]],
            df_all_samples=df_events[["mm_per_hr", "waterlevel_m"]],
            n_samples=n_samples,
            alpha=alpha,
            beta=beta,
        ),
        axis=1,
    )

    out["emp_cdf_OR"] = out.apply(
        lambda row: compute_OR_multivar_return_period_for_sample(
            sample_values=row[["mm_per_hr", "waterlevel_m"]],
            df_all_samples=df_events[["mm_per_hr", "waterlevel_m"]],
            n_samples=n_samples,
            alpha=alpha,
            beta=beta,
        ),
        axis=1,
    )

    # Exceedance probabilities from non-exceedance CDF values.
    out["p_exceed_AND"] = 1.0 - out["emp_cdf_AND"]
    out["p_exceed_OR"] = 1.0 - out["emp_cdf_OR"]

    # Return period = 1 / exceedance probability (inf when exceedance is 0).
    out["rp_AND"] = np.where(out["p_exceed_AND"] > 0, 1.0 / out["p_exceed_AND"], np.inf)
    out["rp_OR"] = np.where(out["p_exceed_OR"] > 0, 1.0 / out["p_exceed_OR"], np.inf)

    return out


def main() -> None:
    # Reproducible synthetic dataset (100 events) with positive dependence.
    rng = np.random.default_rng(42)
    n_events = 100

    mm_per_hr = rng.gamma(shape=2.0, scale=12.0, size=n_events)
    waterlevel_m = (
        0.35 + 0.018 * mm_per_hr + rng.normal(loc=0.0, scale=0.10, size=n_events)
    )
    waterlevel_m = np.clip(waterlevel_m, a_min=0.05, a_max=None)

    df_events = pd.DataFrame(
        {
            "event_id": np.arange(1, n_events + 1),
            "mm_per_hr": mm_per_hr,
            "waterlevel_m": waterlevel_m,
        }
    )

    df_results = _compute_empirical_results(df_events=df_events, alpha=0, beta=0)

    print("Synthetic dataset (first 10 rows):")
    print(
        df_results[["event_id", "mm_per_hr", "waterlevel_m"]]
        .head(10)
        .to_string(index=False)
    )

    print("\nComputed empirical CDF / exceedance / return period (first 10 rows):")
    print(
        df_results[
            [
                "event_id",
                "emp_cdf_AND",
                "emp_cdf_OR",
                "p_exceed_AND",
                "p_exceed_OR",
                "rp_AND",
                "rp_OR",
            ]
        ]
        .head(10)
        .to_string(index=False)
    )

    and_ge_or_cdf = bool((df_results["emp_cdf_AND"] >= df_results["emp_cdf_OR"]).all())
    and_le_or_exceed = bool(
        (df_results["p_exceed_AND"] <= df_results["p_exceed_OR"]).all()
    )
    and_ge_or_rp = bool((df_results["rp_AND"] >= df_results["rp_OR"]).all())

    print("\nSanity-check assertions:")
    print(f"- emp_cdf_AND >= emp_cdf_OR for all events: {and_ge_or_cdf}")
    print(f"- p_exceed_AND <= p_exceed_OR for all events: {and_le_or_exceed}")
    print(f"- rp_AND >= rp_OR for all events: {and_ge_or_rp}")

    print("\nSummary statistics:")
    print(
        df_results[["emp_cdf_AND", "emp_cdf_OR", "rp_AND", "rp_OR"]]
        .describe(percentiles=[0.25, 0.5, 0.75])
        .to_string()
    )

    # Plot empirical exceedance probabilities for AND vs OR.
    p_exceed_and_sorted = np.sort(df_results["p_exceed_AND"].to_numpy())[::-1]
    p_exceed_or_sorted = np.sort(df_results["p_exceed_OR"].to_numpy())[::-1]
    rank = np.arange(1, n_events + 1)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(rank, p_exceed_and_sorted, label="AND exceedance", lw=2)
    ax.plot(rank, p_exceed_or_sorted, label="OR exceedance", lw=2)
    ax.set_xlabel("Rank (1 = largest exceedance probability)")
    ax.set_ylabel("Empirical exceedance probability")
    ax.set_title("Empirical exceedance probabilities: AND vs OR")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()

    plot_path = "_work/empirical_exceedance_probabilities.png"
    fig.savefig(plot_path, dpi=150)
    print(f"\nSaved exceedance plot to: {plot_path}")


if __name__ == "__main__":
    main()
