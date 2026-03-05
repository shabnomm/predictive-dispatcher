from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

from app.models.schemas import (
    AssignmentItem,
    RecommendationRequest,
    RecommendationResponse,
    RankedAlert,
    RouteStop,
    TechnicianRoute,
)
from app.services.scoring import score_alert
from app.services.assignment import choose_technician, apply_assignment
from app.services.routing import build_route_nearest_neighbor
from app.ai.reasoning import build_manager_summary


def generate_recommendations(payload: RecommendationRequest) -> RecommendationResponse:
    # 1) Score + rank alerts
    scored = []
    for a in payload.alerts:
        sr = score_alert(a)
        scored.append((a, sr))

    scored.sort(key=lambda x: x[1].score, reverse=True)

    ranked_alerts: List[RankedAlert] = [
        RankedAlert(
            alert_id=a.alert_id,
            vehicle_id=a.vehicle_id,
            priority_score=sr.score,
            priority_tier=sr.tier,
            required_skills=sr.required_skills,
            explanation=sr.explanation,
        )
        for a, sr in scored
    ]

    # 2) Assign technicians (greedy by priority)
    tech_by_id = {t.tech_id: t for t in payload.technicians}
    assignments: List[AssignmentItem] = []
    assigned_map: Dict[str, str] = {}  # alert_id -> tech_id

    for a, sr in scored:
        choice = choose_technician(
            alert=a,
            required_skills=sr.required_skills,
            tier=sr.tier,
            technicians=payload.technicians,
            policy_max_jobs=payload.policy.max_jobs_per_tech,
            prefer_high_skill_for_critical=payload.policy.prefer_high_skill_for_critical,
        )

        if choice is None:
            assignments.append(
                AssignmentItem(
                    alert_id=a.alert_id,
                    vehicle_id=a.vehicle_id,
                    assigned_tech_id=None,
                    assigned_tech_name=None,
                    reason=f"No eligible technician found for required skills={sr.required_skills}. Consider escalation or scheduling next shift.",
                )
            )
            continue

        tech, reason = choice
        apply_assignment(tech, payload.policy.max_jobs_per_tech)
        assigned_map[a.alert_id] = tech.tech_id

        assignments.append(
            AssignmentItem(
                alert_id=a.alert_id,
                vehicle_id=a.vehicle_id,
                assigned_tech_id=tech.tech_id,
                assigned_tech_name=tech.name,
                reason=reason,
            )
        )

    # 3) Build routes per technician
    jobs_by_tech: Dict[str, List[Tuple[int, str]]] = defaultdict(list)
    # store rank index to help keep critical jobs earlier if distances tie
    rank_index = {ra.alert_id: idx for idx, ra in enumerate(ranked_alerts)}
    alert_lookup = {a.alert_id: a for a in payload.alerts}
    tier_lookup = {ra.alert_id: ra.priority_tier for ra in ranked_alerts}

    for alert_id, tech_id in assigned_map.items():
        jobs_by_tech[tech_id].append((rank_index[alert_id], alert_id))

    routes: List[TechnicianRoute] = []
    for tech_id, jobs in jobs_by_tech.items():
        tech = tech_by_id[tech_id]
        # Keep jobs list stable by rank index first
        jobs.sort(key=lambda x: x[0])
        alerts_for_tech = [alert_lookup[aid] for _, aid in jobs]

        stops_gps = [a.gps for a in alerts_for_tech]
        order_idxs, total_km = build_route_nearest_neighbor(tech.start_gps, stops_gps)

        stops: List[RouteStop] = []
        for seq, idx in enumerate(order_idxs, start=1):
            a = alerts_for_tech[idx]
            stops.append(
                RouteStop(
                    order=seq,
                    alert_id=a.alert_id,
                    vehicle_id=a.vehicle_id,
                    gps=a.gps,
                    priority_tier=tier_lookup[a.alert_id],
                )
            )

        routes.append(
            TechnicianRoute(
                tech_id=tech.tech_id,
                tech_name=tech.name,
                stops=stops,
                total_distance_km=round(total_km, 2),
            )
        )

    # 4) Manager summary (LLM optional)
    manager_summary = build_manager_summary(ranked_alerts, assignments, routes)

    return RecommendationResponse(
        ranked_alerts=ranked_alerts,
        assignments=assignments,
        routes=routes,
        manager_summary=manager_summary,
    )