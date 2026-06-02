"""Unit tests for SpecScoring.baseline_score across all metric types."""
import pytest
from app.models import SpecScoring


def make_scoring(**kwargs) -> SpecScoring:
    base = {"metric": "mass_grams", "direction": "minimize"}
    return SpecScoring.model_validate({**base, **kwargs})


def test_baseline_score_mass_grams():
    s = make_scoring(baseline_mass_grams=180.0)
    assert s.baseline_score == 180.0


def test_baseline_score_stiffness_to_weight():
    s = make_scoring(metric="stiffness_to_weight", direction="maximize",
                     baseline_stiffness_to_weight=258.96)
    assert s.baseline_score == 258.96


def test_baseline_score_deflection_mm():
    s = make_scoring(metric="deflection_mm", baseline_deflection_mm=0.00218)
    assert s.baseline_score == pytest.approx(0.00218)


def test_baseline_score_missing_returns_none():
    # Spec with no baseline fields set
    s = make_scoring()
    assert s.baseline_score is None


def test_round002_spec_loads_without_error():
    """Round_002 stiffness spec must load and have correct baseline_score."""
    import json
    from pathlib import Path
    from app.models import Spec
    path = Path("tests/fixtures/specs_multi/003_stiffness_spec.json")
    spec = Spec.model_validate(json.loads(path.read_text()))
    assert spec.scoring.metric == "stiffness_to_weight"
    assert spec.scoring.baseline_score == 300.0
    assert spec.scoring.baseline_mass_grams is None
