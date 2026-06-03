from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SpecConstraints(BaseModel):
    load_newtons: float
    load_point_mm: list[float]
    safety_factor: float
    bolt_pattern_mm: list[list[float]]
    bolt_diameter_clearance_mm: float
    mount_face_x_mm: float
    build_volume_mm: list[float]
    max_overhang_deg: float
    min_wall_thickness_mm: float


class SpecScoring(BaseModel):
    metric: str
    direction: Literal["minimize", "maximize"]
    baseline_mass_grams: float | None = None
    baseline_stiffness_to_weight: float | None = None
    baseline_deflection_mm: float | None = None

    @property
    def baseline_score(self) -> float | None:
        """Return the baseline value for this spec's primary metric."""
        if self.metric == "mass_grams":
            return self.baseline_mass_grams
        if self.metric == "stiffness_to_weight":
            return self.baseline_stiffness_to_weight
        if self.metric == "deflection_mm":
            return self.baseline_deflection_mm
        return self.baseline_mass_grams


class Spec(BaseModel):
    id: str
    version: str
    name: str
    description: str
    material: str
    constraints: SpecConstraints
    scoring: SpecScoring


class SubmissionCreate(BaseModel):
    spec_id: str
    agent_path: str
    contributor: str
    commit_hash: str
    mass_grams: float
    fea_stress_mpa: float
    fea_allowable_mpa: float
    passed: bool
    pr_number: int | None = None
    notes: str | None = None
    # Base64-encoded STEP bytes; stored server-side, not echoed back in responses.
    step_b64: str | None = None
    # Generic score for multi-objective benchmarks; defaults to mass_grams when absent.
    score: float | None = None
    score_metric: str = "mass_grams"
    score_direction: Literal["minimize", "maximize"] = "minimize"


class Submission(BaseModel):
    id: UUID
    spec_id: str
    agent_path: str
    contributor: str
    commit_hash: str
    mass_grams: float
    fea_stress_mpa: float
    fea_allowable_mpa: float
    passed: bool
    pr_number: int | None = None
    notes: str | None = None
    submitted_at: datetime
    has_step: bool = False
    sota_eligible: bool | None = None
    score: float | None = None
    score_metric: str = "mass_grams"
    score_direction: str = "minimize"

    model_config = {"from_attributes": True}


class LeaderboardEntry(BaseModel):
    rank: int
    submission_id: str
    contributor: str
    agent_path: str
    mass_grams: float
    score: float
    score_metric: str
    score_direction: str
    fea_stress_mpa: float
    commit_hash: str
    submitted_at: datetime
    pr_number: int | None = None
    has_step: bool = False


class Leaderboard(BaseModel):
    spec_id: str
    entries: list[LeaderboardEntry]


class OverallBestEntry(BaseModel):
    """A contributor's best result on a single spec, used in the overall leaderboard."""

    spec_id: str
    rank: int
    mass_grams: float
    score: float  # canonical score value for this spec's metric
    score_metric: str  # e.g. "mass_grams", "stiffness_to_weight", "deflection_mm"
    normalized_score: float  # score / baseline_score (or baseline_score / score for maximize)
    submission_id: str
    submitted_at: datetime


class OverallLeaderboardEntry(BaseModel):
    rank: int
    contributor: str
    specs_entered: int
    total_wins: int  # number of specs where this contributor holds rank 1
    avg_rank: float  # mean rank position across entered specs (display only)
    overall_score: float = 1.0  # mean normalized score across ALL active specs; < 1.0 = beating baseline; primary sort key
    best: list[OverallBestEntry]


class OverallLeaderboard(BaseModel):
    total_specs: int
    entries: list[OverallLeaderboardEntry]


class SotaEligibility(BaseModel):
    eligible: bool
    required_improvement_pct: float
    current_score: float
    margin_grams: float
    reason: str


class SotaHistoryPoint(BaseModel):
    """A moment when the SOTA improved — used to draw a progressive score chart."""

    score: float
    contributor: str
    agent_path: str
    submitted_at: datetime


class SotaRecord(BaseModel):
    spec_id: str
    submission_id: str  # UUID of the SOTA submission — use with GET /submissions/{id}/step for 3D viewer
    has_step: bool = False  # true if a STEP file is stored for this submission
    score_grams: float  # kept for backward compat — equals score when metric is mass_grams
    score: float
    score_metric: str
    score_direction: str  # "minimize" or "maximize"
    agent: str
    contributor: str
    fea_stress_mpa: float
    fea_allowable_mpa: float
    commit_hash: str
    submitted_at: datetime
    note: str | None = None
