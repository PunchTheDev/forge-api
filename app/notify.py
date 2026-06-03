"""Discord notifications for Forge competition milestones."""
import logging
import os

import httpx

logger = logging.getLogger(__name__)

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

_METRIC_UNIT = {
    "mass_grams": "g",
    "stiffness_to_weight": "N/(mm·g)",
    "deflection_mm": "mm",
}


def _fmt(score: float, metric: str) -> str:
    unit = _METRIC_UNIT.get(metric, "")
    if metric == "mass_grams":
        return f"{score:.2f} {unit}"
    return f"{score:.4f} {unit}"


async def send_sota_alert(
    spec_id: str,
    metric: str,
    direction: str,
    new_score: float,
    old_score: float | None,
    contributor: str,
) -> None:
    """Post a SOTA milestone to Discord. Silent no-op when DISCORD_WEBHOOK_URL is unset."""
    if not WEBHOOK_URL:
        return

    new_fmt = _fmt(new_score, metric)

    if old_score is None:
        title = f"\U0001f3c6 First SOTA — `{spec_id}`"
        description = f"**{contributor}** opened the board: {new_fmt}"
    else:
        old_fmt = _fmt(old_score, metric)
        if direction == "maximize":
            pct = (new_score - old_score) / abs(old_score) * 100
        else:
            pct = (old_score - new_score) / abs(old_score) * 100
        title = f"\U0001f525 New SOTA — `{spec_id}`"
        description = f"**{contributor}** took the lead: {old_fmt} \u2192 {new_fmt} ({pct:+.2f}%)"

    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": 0x00C851,
                "footer": {"text": "Forge \u2022 PunchTheDev/forge"},
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(WEBHOOK_URL, json=payload)
            resp.raise_for_status()
    except Exception as exc:
        logger.warning("Discord SOTA notification failed: %s", exc)
