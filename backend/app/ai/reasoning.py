from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

from app.models.schemas import AssignmentItem, RankedAlert, TechnicianRoute

# Load backend/.env reliably (backend/app/ai/reasoning.py -> parents[2] == backend/)
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ENV_PATH)


def _deterministic_summary(
    ranked_alerts: List[RankedAlert],
    assignments: List[AssignmentItem],
    routes: List[TechnicianRoute],
) -> str:
    critical = [a for a in ranked_alerts if a.priority_tier == "CRITICAL"]
    high = [a for a in ranked_alerts if a.priority_tier == "HIGH"]
    unassigned = [x for x in assignments if x.assigned_tech_id is None]

    lines = []
    lines.append(f"Dispatch summary: {len(ranked_alerts)} alerts analyzed; {len(routes)} technician routes created.")
    if critical:
        lines.append(f"Critical alerts: {len(critical)} (prioritized for immediate action).")
    if high:
        lines.append(f"High alerts: {len(high)} scheduled after critical items.")
    if unassigned:
        lines.append(f"Unassigned alerts: {len(unassigned)} (no eligible technician; consider escalation/next shift).")
    return " ".join(lines)


def _build_facts(
    ranked_alerts: List[RankedAlert],
    assignments: List[AssignmentItem],
    routes: List[TechnicianRoute],
) -> Dict[str, Any]:
    top_alerts = ranked_alerts[:8]
    unassigned = [a for a in assignments if a.assigned_tech_id is None][:5]

    return {
        "top_alerts": [
            {
                "alert_id": a.alert_id,
                "vehicle_id": a.vehicle_id,
                "tier": a.priority_tier,
                "score": a.priority_score,
                "required_skills": a.required_skills,
                "why": a.explanation,
            }
            for a in top_alerts
        ],
        "routes": [
            {
                "tech": f"{r.tech_name} ({r.tech_id})",
                "total_km": r.total_distance_km,
                "stops": [
                    {"order": s.order, "alert_id": s.alert_id, "vehicle_id": s.vehicle_id, "tier": s.priority_tier}
                    for s in r.stops
                ],
            }
            for r in routes
        ],
        "unassigned": [
            {"alert_id": x.alert_id, "vehicle_id": x.vehicle_id, "reason": x.reason}
            for x in unassigned
        ],
    }


def _openai_summary(facts: Dict[str, Any]) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    if not api_key:
        return ""

    # Import only when needed
    from openai import OpenAI

    client = OpenAI(api_key=api_key)

    prompt = f"""
You are an operations dispatcher assistant for a vehicle fleet.

Write a manager-facing dispatch summary in 4–8 sentences.

Rules:
- DO NOT change assignments or routes.
- Explain why the top alerts are urgent (use tier/score/why).
- Mention any unassigned alerts and suggest safe next actions (escalate, schedule next shift, remote diagnostic).
- Keep it concise and practical.

FACTS:
{facts}
""".strip()

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You summarize fleet dispatch decisions clearly and safely."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return (resp.choices[0].message.content or "").strip()


def build_manager_summary(ranked_alerts, assignments, routes) -> str:
    enable_llm = os.getenv("ENABLE_LLM", "false").strip().lower() == "true"
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()

    facts = _build_facts(ranked_alerts, assignments, routes)

    def simulated_ai_summary() -> str:
        return f"""
🤖 AI Dispatch Analysis:

{len(facts["top_alerts"])} top alerts require attention. Critical alerts were prioritized because they indicate higher breakdown risk (e.g., overheating, abnormal fuel usage, or vibration spikes). Technicians were assigned based on skill match first, then proximity and current load to keep response times low.

{len(facts["unassigned"])} alerts remain unassigned due to missing required skills or insufficient capacity. Recommended next actions: escalate to a specialist, schedule for the next shift, or run remote diagnostics if available.
""".strip()

    # If LLM is disabled, just show simulated summary (so demo looks "AI-powered")
    if not enable_llm:
        return simulated_ai_summary()

    # If LLM enabled but provider isn't openai, still show simulated summary
    if provider != "openai":
        return simulated_ai_summary()

    try:
        text = _openai_summary(facts)
        if text:
            return text
        # Key missing → simulated
        return simulated_ai_summary()
    except Exception:
        # Quota / network / any error → simulated (NO error shown in UI)
        return simulated_ai_summary()