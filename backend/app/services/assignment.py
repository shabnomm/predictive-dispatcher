from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from app.models.schemas import Alert, Technician, PriorityTier
from app.services.routing import haversine_km


def _tech_skill_level(tech: Technician, skill_name: str) -> int:
    for s in tech.skills:
        if s.name == skill_name:
            return s.level
    return 0


def _has_required_skills(tech: Technician, required: List[str]) -> bool:
    # inspection can be done by anyone in this PoC
    for r in required:
        if r == "inspection":
            continue
        if _tech_skill_level(tech, r) <= 0:
            return False
    return True


def _available(tech: Technician, policy_max_jobs: int) -> bool:
    max_jobs = min(tech.capacity.max_jobs, policy_max_jobs)
    return tech.capacity.assigned < max_jobs


def choose_technician(
    alert: Alert,
    required_skills: List[str],
    tier: PriorityTier,
    technicians: List[Technician],
    policy_max_jobs: int,
    prefer_high_skill_for_critical: bool,
) -> Optional[Tuple[Technician, str]]:
    candidates = [t for t in technicians if _available(t, policy_max_jobs) and _has_required_skills(t, required_skills)]
    if not candidates:
        return None

    # Weighted scoring
    # - For CRITICAL/HIGH: skill matters more
    # - For MEDIUM/LOW: distance matters more
    best: Optional[Tuple[float, Technician, str]] = None

    for t in candidates:
        dist = haversine_km(t.start_gps.lat, t.start_gps.lon, alert.gps.lat, alert.gps.lon)

        # Skill score = avg level across required skills (1..3) scaled to 0..100
        levels = []
        for r in required_skills:
            if r == "inspection":
                levels.append(1)
            else:
                levels.append(_tech_skill_level(t, r))
        avg_level = sum(levels) / max(1, len(levels))
        skill_score = (avg_level / 3.0) * 100.0

        # Distance score (simple): closer is better, cap at 30km
        dist_score = max(0.0, 100.0 * (1.0 - min(dist, 30.0) / 30.0))

        # Load score: more remaining capacity is better
        max_jobs = min(t.capacity.max_jobs, policy_max_jobs)
        remaining = max_jobs - t.capacity.assigned
        load_score = (remaining / max_jobs) * 100.0 if max_jobs > 0 else 0.0

        if tier in ("CRITICAL", "HIGH"):
            total = 0.55 * skill_score + 0.30 * dist_score + 0.15 * load_score
            if prefer_high_skill_for_critical and tier == "CRITICAL":
                # extra boost for level 3 on any required skill
                if any(_tech_skill_level(t, r) == 3 for r in required_skills if r != "inspection"):
                    total += 5.0
        else:
            total = 0.45 * dist_score + 0.35 * skill_score + 0.20 * load_score

        reason = (
            f"SkillScore={skill_score:.1f}, Distance={dist:.2f}km, DistanceScore={dist_score:.1f}, "
            f"LoadScore={load_score:.1f} → Total={total:.1f}"
        )

        if best is None or total > best[0]:
            best = (total, t, reason)
        elif best is not None and abs(total - best[0]) < 1e-9:
            # Tie-breakers: higher avg skill, then closer, then stable by tech_id
            best_t = best[1]
            best_dist = haversine_km(best_t.start_gps.lat, best_t.start_gps.lon, alert.gps.lat, alert.gps.lon)
            if avg_level > (sum([_tech_skill_level(best_t, r) if r != "inspection" else 1 for r in required_skills]) / max(1, len(required_skills))):
                best = (total, t, reason)
            elif dist < best_dist:
                best = (total, t, reason)
            elif t.tech_id < best_t.tech_id:
                best = (total, t, reason)

    return (best[1], best[2]) if best else None


def apply_assignment(tech: Technician, policy_max_jobs: int) -> None:
    # Mutate assigned count safely
    max_jobs = min(tech.capacity.max_jobs, policy_max_jobs)
    if tech.capacity.assigned < max_jobs:
        tech.capacity.assigned += 1