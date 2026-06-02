"""Live eval preview — run agent code in a sandboxed Docker container.

Accepts agent source code + spec_id, writes them to a temp dir, mounts it
into the forge-eval Docker image, and returns structured eval results.

Requirements on the host:
  - Docker installed and accessible to the forge-api process
  - forge-eval image built: `docker build -t forge-eval .` in the forge repo

Environment variables:
  FORGE_EVAL_IMAGE   — Docker image name (default: forge-eval)
  PREVIEW_TIMEOUT    — Seconds before eval is killed (default: 300)
  FORGE_LLM_KEY      — OpenRouter API key forwarded to LLM agents
  FORGE_MODEL        — Model override forwarded to LLM agents
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import specs as spec_store

router = APIRouter(prefix="/eval", tags=["eval"])

FORGE_EVAL_IMAGE = os.environ.get("FORGE_EVAL_IMAGE", "forge-eval")
PREVIEW_TIMEOUT = int(os.environ.get("PREVIEW_TIMEOUT", "300"))
SPECS_DIR = os.environ.get("SPECS_DIR", "data/specs")
MAX_AGENT_BYTES = 64 * 1024  # 64 KB cap


class PreviewRequest(BaseModel):
    agent_code: str
    spec_id: str


class PreviewResult(BaseModel):
    passed: bool
    score: float | None
    score_metric: str
    score_direction: str
    stage: str
    reason: str
    fea_stress_mpa: float | None = None
    fea_allowable_mpa: float | None = None
    fea_element_count: int | None = None
    fea_load_node_count: int | None = None
    fea_convergence_deviation: float | None = None
    fea_displacement_mm: float | None = None
    similarity: float | None = None
    elapsed_seconds: float = 0.0


@router.post("/preview", response_model=PreviewResult)
async def eval_preview(body: PreviewRequest):
    if len(body.agent_code.encode()) > MAX_AGENT_BYTES:
        raise HTTPException(status_code=413, detail="agent_code exceeds 64 KB limit")

    # Validate spec exists and read raw JSON (preserves all fields for eval harness).
    spec_path = Path(SPECS_DIR) / f"{body.spec_id}.json"
    if not spec_path.exists():
        raise HTTPException(status_code=404, detail=f"Spec '{body.spec_id}' not found")
    spec_raw = spec_path.read_text()

    tmpdir = tempfile.mkdtemp(prefix="forge-preview-")
    try:
        agent_file = os.path.join(tmpdir, "agent.py")
        spec_file = os.path.join(tmpdir, "spec.json")

        with open(agent_file, "w") as f:
            f.write(body.agent_code)
        with open(spec_file, "w") as f:
            f.write(spec_raw)

        cmd = _build_docker_cmd(tmpdir)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Docker not available. "
                    "Install Docker and build the image: `docker build -t forge-eval .` in the forge repo."
                ),
            )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=PREVIEW_TIMEOUT
            )
        except asyncio.TimeoutError:
            proc.kill()
            raise HTTPException(
                status_code=504,
                detail=f"Eval timed out after {PREVIEW_TIMEOUT}s",
            )

        output = stdout.decode().strip()
        if not output:
            raise HTTPException(
                status_code=500,
                detail=f"Eval produced no output. stderr: {stderr.decode()[:500]}",
            )

        # evaluate.py may print warnings before the JSON line; take the last line.
        last_line = output.splitlines()[-1]
        try:
            payload = json.loads(last_line)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=500,
                detail=f"Could not parse eval output: {last_line[:300]}",
            )

        return PreviewResult(**payload)

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _build_docker_cmd(tmpdir: str) -> list[str]:
    cmd = [
        "docker", "run", "--rm",
        "--security-opt", "no-new-privileges",
        "--memory", "4g", "--cpus", "2",
        "-v", f"{tmpdir}:/preview:ro",
    ]
    # Forward LLM credentials so LLM agents can call OpenRouter.
    llm_key = os.environ.get("FORGE_LLM_KEY") or os.environ.get("OPENROUTER_KEY")
    if llm_key:
        cmd += ["-e", f"FORGE_LLM_KEY={llm_key}"]
    model = os.environ.get("FORGE_MODEL")
    if model:
        cmd += ["-e", f"FORGE_MODEL={model}"]
    cmd += [
        FORGE_EVAL_IMAGE,
        "python3", "-m", "benchmark.evaluate",
        "--agent", "/preview/agent.py",
        "--spec", "/preview/spec.json",
        "--json-compact",
    ]
    return cmd
