"""Scoring utilities for SOTA eligibility."""


def sota_margin_threshold(current_sota_age_days: float) -> float:
    """Return the required fractional improvement to take the SOTA spot.

    Step function that decays with age so early leaders are protected but
    eventually any improvement can win.

    Age        Required improvement
    --------   --------------------
    0–7 days   1.0%
    7–30 days  0.5%
    30–90 days 0.1%
    90+ days   0% (any improvement wins)
    """
    if current_sota_age_days < 7:
        return 0.01
    if current_sota_age_days < 30:
        return 0.005
    if current_sota_age_days < 90:
        return 0.001
    return 0.0


def sota_eligible(
    new_score: float,
    current_score: float,
    current_sota_age_days: float,
    direction: str = "minimize",
) -> tuple[bool, str]:
    """Return (is_eligible, reason).

    A submission is eligible when it beats current_score by the required margin.
    direction='minimize': lower is better (mass, volume).
    direction='maximize': higher is better (stiffness_to_weight).
    """
    threshold_pct = sota_margin_threshold(current_sota_age_days)
    required_improvement = abs(current_score) * threshold_pct

    if direction == "maximize":
        required_score = current_score + required_improvement
        if new_score >= required_score:
            return True, (
                f"Beats current SOTA by {new_score - current_score:.4f} "
                f"(required {required_improvement:.4f}, {threshold_pct * 100:.1f}%)"
            )
        shortfall = required_score - new_score
        return False, (
            f"Needs to beat current SOTA by {required_improvement:.4f} "
            f"({threshold_pct * 100:.1f}%); short by {shortfall:.4f}"
        )

    # minimize
    required_score = current_score - required_improvement
    if new_score <= required_score:
        return True, (
            f"Beats current SOTA by {current_score - new_score:.4f} "
            f"(required {required_improvement:.4f}, {threshold_pct * 100:.1f}%)"
        )
    shortfall = new_score - required_score
    return False, (
        f"Needs to beat current SOTA by {required_improvement:.4f} "
        f"({threshold_pct * 100:.1f}%); short by {shortfall:.4f}"
    )
