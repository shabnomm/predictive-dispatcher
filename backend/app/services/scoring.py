from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.models.schemas import Alert, PriorityTier


@dataclass
class ScoreResult:
    score: int
    tier: PriorityTier
    required_skills: List[str]
    explanation: str


def _tier_from_score(score: int) -> PriorityTier:
    if score >= 80:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 25:
        return "MEDIUM"
    return "LOW"


def _required_skills_from_flags(flags: List[str]) -> List[str]:
    """
    Map alert flags to technician skills.
    Make sure these skills align with what technicians actually have.
    """
    skills = set()
    for f in flags:
        if "ENGINE" in f or "TEMP" in f:
            skills.add("engine")
        if "FUEL" in f:
            skills.add("fuel")
        if "VIBRATION" in f:
            skills.add("engine")  # vibration often mechanical/engine in PoC
        if "BATTERY" in f or "ELECT" in f:
            skills.add("electrical")

    # IMPORTANT: don't return a skill that no technician has.
    # Use "general" as default skill for basic inspections.
    if not skills:
        skills.add("general")

    return sorted(skills)


# -------------------------
# Trend utilities (PoC)
# -------------------------
def _safe_float_list(v) -> List[float]:
    """
    Convert list-like to float list safely; ignore bad values.
    """
    if not isinstance(v, list):
        return []
    out: List[float] = []
    for x in v:
        try:
            out.append(float(x))
        except Exception:
            continue
    return out


def _trend_slope(values: List[float]) -> float:
    """
    Simple slope proxy: last - first.
    This is intentionally minimal for PoC.
    """
    if len(values) < 2:
        return 0.0
    return float(values[-1]) - float(values[0])


def score_alert(alert: Alert) -> ScoreResult:
    flags = set(alert.flags)
    s = alert.sensors
    duration = alert.meta.duration_min

    score = 0
    reasons: List[str] = []

    # -------------------------
    # 1) Score based on flags
    # -------------------------
    if "HIGH_ENGINE_TEMP" in flags:
        score += 70
        reasons.append("Engine temperature is above critical threshold.")
    elif "ENGINE_TEMP_WARNING" in flags:
        score += 40
        reasons.append("Engine temperature is in warning range.")

    if "FUEL_SPIKE" in flags:
        score += 25
        reasons.append("Fuel consumption spike detected.")

    if "HIGH_VIBRATION" in flags:
        score += 20
        reasons.append("High vibration suggests mechanical stress.")

    if "LOW_BATTERY" in flags:
        score += 20
        reasons.append("Low battery voltage suggests electrical risk.")

    # -------------------------
    # 2) If no flags, infer from raw sensors
    # -------------------------
    if not flags:
        if s.engine_temp_c > 110:
            score += 70
            reasons.append("Engine temp inferred critical from sensor value.")
            flags.add("HIGH_ENGINE_TEMP")
        elif s.engine_temp_c >= 106:
            score += 40
            reasons.append("Engine temp inferred warning from sensor value.")
            flags.add("ENGINE_TEMP_WARNING")

        if s.fuel_rate_lph > 18:
            score += 25
            reasons.append("Fuel spike inferred from sensor value.")
            flags.add("FUEL_SPIKE")

        if s.vibration_rms > 3.0:
            score += 20
            reasons.append("High vibration inferred from sensor value.")
            flags.add("HIGH_VIBRATION")

        if s.battery_v < 11.8:
            score += 20
            reasons.append("Low battery inferred from sensor value.")
            flags.add("LOW_BATTERY")

    # -------------------------
    # 3) Predictive trend bonus (PoC)
    # -------------------------
    # These fields are OPTIONAL. If your schema doesn't include them yet,
    # add them as Optional[List[float]] in Sensors.
    temp_trend = _safe_float_list(getattr(s, "engine_temp_trend", []))
    fuel_trend = _safe_float_list(getattr(s, "fuel_rate_trend", []))

    temp_slope = _trend_slope(temp_trend)
    fuel_slope = _trend_slope(fuel_trend)

    # Engine temperature rising fast => increased failure risk
    if temp_slope >= 8.0:
        score += 15
        reasons.append(f"Engine temp rising quickly (+{temp_slope:.1f}°C over recent readings).")
        # ensure skill mapping catches this
        flags.add("ENGINE_TEMP_WARNING")

    # Fuel consumption trending upward => potential leak/inefficiency
    if fuel_slope >= 4.0:
        score += 10
        reasons.append(f"Fuel rate trending upward (+{fuel_slope:.1f} L/h over recent readings).")
        flags.add("FUEL_SPIKE")

    # -------------------------
    # 4) Duration bonus
    # -------------------------
    if duration >= 30:
        score += 20
        reasons.append(f"Anomaly persisted for {duration} minutes (>=30).")
    elif duration >= 15:
        score += 10
        reasons.append(f"Anomaly persisted for {duration} minutes (>=15).")

    tier = _tier_from_score(score)
    required_skills = _required_skills_from_flags(list(flags))

    explanation = " ".join(reasons) if reasons else "No significant anomalies detected; schedule general inspection."
    return ScoreResult(score=score, tier=tier, required_skills=required_skills, explanation=explanation)