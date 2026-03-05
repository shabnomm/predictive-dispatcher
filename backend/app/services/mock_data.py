from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import List

from app.models.schemas import (
    Alert,
    AlertMeta,
    Capacity,
    GPS,
    Policy,
    RecommendationRequest,
    Sensors,
    Shift,
    Skill,
    Technician,
)

BDT = timezone(timedelta(hours=6))


def _rand_gps(center_lat: float, center_lon: float, spread: float, rng: random.Random) -> GPS:
    return GPS(
        lat=center_lat + rng.uniform(-spread, spread),
        lon=center_lon + rng.uniform(-spread, spread),
    )


def _make_flags(sensors: Sensors) -> List[str]:
    flags = []
    if sensors.engine_temp_c > 110:
        flags.append("HIGH_ENGINE_TEMP")
    elif sensors.engine_temp_c >= 106:
        flags.append("ENGINE_TEMP_WARNING")
    if sensors.fuel_rate_lph > 18:
        flags.append("FUEL_SPIKE")
    if sensors.vibration_rms > 3.0:
        flags.append("HIGH_VIBRATION")
    if sensors.battery_v < 11.8:
        flags.append("LOW_BATTERY")
    return flags


def generate_mock_request_payload(num_alerts: int = 10, num_techs: int = 4, seed: int = 42) -> RecommendationRequest:
    rng = random.Random(seed)

    # Dhaka-ish center (feel free to change)
    center_lat, center_lon = 23.7800, 90.4100

    # Alerts
    alerts: List[Alert] = []
    now = datetime.now(BDT).replace(microsecond=0)

    for i in range(num_alerts):
        gps = _rand_gps(center_lat, center_lon, spread=0.03, rng=rng)

        # Start with normal values
        engine_temp = rng.uniform(88, 104)
        fuel_rate = rng.uniform(7, 13)
        vibration = rng.uniform(0.8, 2.2)
        battery_v = rng.uniform(12.1, 13.8)

        # Inject anomalies with some probability
        p = rng.random()
        if p < 0.10:
            # multi-anomaly (more critical)
            engine_temp = rng.uniform(111, 118)
            fuel_rate = rng.uniform(18.5, 23)
            vibration = rng.uniform(3.1, 4.5)
        elif p < 0.25:
            # single anomaly
            choice = rng.choice(["engine", "fuel", "vibration", "battery"])
            if choice == "engine":
                engine_temp = rng.uniform(106, 116)
            elif choice == "fuel":
                fuel_rate = rng.uniform(18.2, 22)
            elif choice == "vibration":
                vibration = rng.uniform(3.1, 4.2)
            else:
                battery_v = rng.uniform(11.2, 11.7)

        duration = rng.choice([6, 10, 18, 25, 35, 50])
        sensors = Sensors(
            engine_temp_c=round(engine_temp, 1),
            fuel_rate_lph=round(fuel_rate, 1),
            vibration_rms=round(vibration, 2),
            battery_v=round(battery_v, 1),
        )
        flags = _make_flags(sensors)

        alerts.append(
            Alert(
                alert_id=f"A-{i+1:04d}",
                vehicle_id=f"V-{rng.randint(100, 299)}",
                timestamp=(now - timedelta(minutes=rng.randint(0, 45))).isoformat(),
                gps=gps,
                sensors=sensors,
                flags=flags,
                meta=AlertMeta(duration_min=duration, odometer_km=rng.randint(10000, 180000), vehicle_type=rng.choice(["van", "truck", "car"])),
            )
        )

    # Technicians
    skill_pool = ["engine", "fuel", "electrical"]
    techs: List[Technician] = []

    for j in range(num_techs):
        start = _rand_gps(center_lat, center_lon, spread=0.02, rng=rng)
        # Each tech gets 1-2 skills
        k = rng.randint(1, 2)
        chosen = rng.sample(skill_pool, k=k)
        skills = [Skill(name=s, level=rng.randint(1, 3)) for s in chosen]

        techs.append(
            Technician(
                tech_id=f"T-{j+1:02d}",
                name=rng.choice(["Alex", "Maria", "Sam", "Nadia", "Rafi", "Tania", "Imran", "Joya"]) + f" {j+1}",
                start_gps=start,
                skills=skills,
                capacity=Capacity(max_jobs=4, assigned=rng.randint(0, 1)),
                shift=Shift(start="09:00", end="18:00"),
            )
        )

    return RecommendationRequest(alerts=alerts, technicians=techs, policy=Policy())