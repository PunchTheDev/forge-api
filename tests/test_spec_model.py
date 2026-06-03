"""Unit tests for SpecScoring.baseline_score and Spec.tier across all metric types."""
import pytest
from app.models import Spec, SpecScoring


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
    path = Path("tests/fixtures/specs_multi/003_stiffness_spec.json")
    spec = Spec.model_validate(json.loads(path.read_text()))
    assert spec.scoring.metric == "stiffness_to_weight"
    assert spec.scoring.baseline_score == 300.0
    assert spec.scoring.baseline_mass_grams is None


def _make_minimal_spec(spec_id: str) -> dict:
    return {
        "id": spec_id,
        "version": "1.0",
        "name": "Test Bracket",
        "description": "test",
        "material": "pla",
        "constraints": {
            "load_newtons": 100.0,
            "load_point_mm": [50.0, 40.0, 30.0],
            "safety_factor": 1.5,
            "bolt_pattern_mm": [[0.0, 0.0]],
            "bolt_diameter_clearance_mm": 6.5,
            "mount_face_x_mm": 0.0,
            "build_volume_mm": [100.0, 80.0, 60.0],
            "max_overhang_deg": 50.0,
            "min_wall_thickness_mm": 1.0,
        },
        "scoring": {"metric": "mass_grams", "direction": "minimize"},
    }


def test_spec_tier_easy():
    spec = Spec.model_validate(_make_minimal_spec("r01_001_easy"))
    assert spec.tier == "easy"


def test_spec_tier_medium():
    spec = Spec.model_validate(_make_minimal_spec("r01_002_medium"))
    assert spec.tier == "medium"


def test_spec_tier_hard():
    spec = Spec.model_validate(_make_minimal_spec("r02_003_hard"))
    assert spec.tier == "hard"


def test_spec_tier_none_for_legacy_id():
    spec = Spec.model_validate(_make_minimal_spec("001_bracket"))
    assert spec.tier is None


def test_spec_round_id_r01():
    spec = Spec.model_validate(_make_minimal_spec("r01_001_easy"))
    assert spec.round_id == "round_001"


def test_spec_round_id_r02():
    spec = Spec.model_validate(_make_minimal_spec("r02_003_hard"))
    assert spec.round_id == "round_002"


def test_spec_round_id_r10():
    spec = Spec.model_validate(_make_minimal_spec("r10_001_easy"))
    assert spec.round_id == "round_010"


def test_spec_round_id_none_for_legacy():
    spec = Spec.model_validate(_make_minimal_spec("001_bracket"))
    assert spec.round_id is None


def test_spec_round_id_none_for_pub():
    spec = Spec.model_validate(_make_minimal_spec("pub_002_medium"))
    assert spec.round_id is None
