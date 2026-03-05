from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


PriorityTier = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]


class GPS(BaseModel):
    lat: float
    lon: float


class Sensors(BaseModel):
    engine_temp_c: float
    fuel_rate_lph: float
    vibration_rms: float
    battery_v: float

    # ✅ Trend fields (optional) for predictive scoring PoC
    engine_temp_trend: Optional[List[float]] = None
    fuel_rate_trend: Optional[List[float]] = None


class AlertMeta(BaseModel):
    duration_min: int = Field(ge=0)
    odometer_km: int = Field(ge=0)
    vehicle_type: str = "van"


class Alert(BaseModel):
    alert_id: str
    vehicle_id: str
    timestamp: str  # ISO string
    gps: GPS
    sensors: Sensors
    flags: List[str] = []
    meta: AlertMeta


class Skill(BaseModel):
    name: str
    level: int = Field(ge=1, le=3)  # 1=junior, 2=mid, 3=senior


class Capacity(BaseModel):
    max_jobs: int = Field(ge=1)
    assigned: int = Field(ge=0)


class Shift(BaseModel):
    start: str = "09:00"
    end: str = "18:00"


class Technician(BaseModel):
    tech_id: str
    name: str
    start_gps: GPS
    skills: List[Skill]
    capacity: Capacity
    shift: Shift


class Policy(BaseModel):
    max_jobs_per_tech: int = 4
    prefer_high_skill_for_critical: bool = True


class RecommendationRequest(BaseModel):
    alerts: List[Alert]
    technicians: List[Technician]
    policy: Policy = Policy()


class RankedAlert(BaseModel):
    alert_id: str
    vehicle_id: str
    priority_score: int
    priority_tier: PriorityTier
    required_skills: List[str]
    explanation: str


class AssignmentItem(BaseModel):
    alert_id: str
    vehicle_id: str
    assigned_tech_id: Optional[str] = None
    assigned_tech_name: Optional[str] = None
    reason: str


class RouteStop(BaseModel):
    order: int
    alert_id: str
    vehicle_id: str
    gps: GPS
    priority_tier: PriorityTier


class TechnicianRoute(BaseModel):
    tech_id: str
    tech_name: str
    stops: List[RouteStop]
    total_distance_km: float


class RecommendationResponse(BaseModel):
    ranked_alerts: List[RankedAlert]
    assignments: List[AssignmentItem]
    routes: List[TechnicianRoute]
    manager_summary: str