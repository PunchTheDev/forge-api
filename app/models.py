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
    baseline_mass_grams: float


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

    model_config = {"from_attributes": True}


class LeaderboardEntry(BaseModel):
    rank: int
    contributor: str
    agent_path: str
    mass_grams: float
    fea_stress_mpa: float
    commit_hash: str
    submitted_at: datetime
    pr_number: int | None = None


class Leaderboard(BaseModel):
    spec_id: str
    entries: list[LeaderboardEntry]


class SotaRecord(BaseModel):
    spec_id: str
    score_grams: float
    agent: str
    contributor: str
    fea_stress_mpa: float
    fea_allowable_mpa: float
    commit_hash: str
    submitted_at: datetime
    note: str | None = None
