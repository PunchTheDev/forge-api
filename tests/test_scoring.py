"""Unit tests for scoring.sota_eligible with both minimize and maximize directions."""

import pytest
from app.scoring import sota_eligible, sota_margin_threshold


def test_margin_threshold_decay():
    assert sota_margin_threshold(0) == 0.01
    assert sota_margin_threshold(6) == 0.01
    assert sota_margin_threshold(7) == 0.005
    assert sota_margin_threshold(29) == 0.005
    assert sota_margin_threshold(30) == 0.001
    assert sota_margin_threshold(89) == 0.001
    assert sota_margin_threshold(90) == 0.0
    assert sota_margin_threshold(365) == 0.0


# --- minimize direction ---

def test_minimize_eligible_beats_margin():
    # SOTA = 100g, within first 7 days → need < 99g
    eligible, reason = sota_eligible(98.0, 100.0, 3.0, "minimize")
    assert eligible is True
    assert "Beats" in reason


def test_minimize_ineligible_short_of_margin():
    # SOTA = 100g, new = 99.5g — beats but only by 0.5%, below 1% threshold
    eligible, reason = sota_eligible(99.5, 100.0, 3.0, "minimize")
    assert eligible is False
    assert "short by" in reason


def test_minimize_ineligible_higher_than_sota():
    eligible, reason = sota_eligible(110.0, 100.0, 3.0, "minimize")
    assert eligible is False


def test_minimize_no_threshold_at_90_days():
    # Any improvement wins after 90 days
    eligible, _ = sota_eligible(99.9, 100.0, 91.0, "minimize")
    assert eligible is True


def test_minimize_default_direction():
    # default direction should be 'minimize'
    eligible, _ = sota_eligible(98.0, 100.0, 3.0)
    assert eligible is True


# --- maximize direction ---

def test_maximize_eligible_beats_margin():
    # SOTA = 200, within first 7 days → need > 202
    eligible, reason = sota_eligible(205.0, 200.0, 3.0, "maximize")
    assert eligible is True
    assert "Beats" in reason


def test_maximize_ineligible_short_of_margin():
    # SOTA = 200, new = 201 — beats but only by 0.5%, below 1% threshold
    eligible, reason = sota_eligible(201.0, 200.0, 3.0, "maximize")
    assert eligible is False
    assert "short by" in reason


def test_maximize_ineligible_lower_than_sota():
    eligible, _ = sota_eligible(150.0, 200.0, 3.0, "maximize")
    assert eligible is False


def test_maximize_no_threshold_at_90_days():
    # Any improvement wins after 90 days
    eligible, _ = sota_eligible(200.1, 200.0, 91.0, "maximize")
    assert eligible is True


def test_maximize_equal_to_sota_eligible_after_90_days():
    # After 90 days threshold is 0% — an exact tie is allowed (consistent with minimize)
    eligible, _ = sota_eligible(200.0, 200.0, 91.0, "maximize")
    assert eligible is True


def test_maximize_equal_within_7_days_ineligible():
    # Within 7 days threshold is 1% — exact tie is not an improvement
    eligible, _ = sota_eligible(200.0, 200.0, 3.0, "maximize")
    assert eligible is False
