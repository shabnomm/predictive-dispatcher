import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

import pandas as pd
import requests
import streamlit as st


# ----------------------------
# Config
# ----------------------------
st.set_page_config(
    page_title="Predictive Field Service Dispatcher (PoC)",
    layout="wide",
)

# Default backend for deployed app (Render)
DEFAULT_API_BASE = os.getenv("BACKEND_URL", "https://predictive-dispatcher.onrender.com")
API_BASE = st.sidebar.text_input("Backend API Base URL", value=DEFAULT_API_BASE).rstrip("/")

st.title("Predictive Field Service Dispatcher (PoC)")
st.caption("PoC: risk scoring + technician assignment + route plan + AI reasoning summary")


# ----------------------------
# Helpers
# ----------------------------
def safe_json_loads(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")


def call_get_mock_data(n_alerts: int, n_techs: int, seed: int) -> Dict[str, Any]:
    """
    Attempts to call /mock-data with query params. If backend doesn't support them,
    it falls back to calling /mock-data without params.
    """
    url = f"{API_BASE}/mock-data"
    try:
        r = requests.get(
            url,
            params={"alerts": n_alerts, "technicians": n_techs, "seed": seed},
            timeout=30,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass

    # Fallback: no params
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()

    # Best-effort local trim
    if isinstance(data, dict):
        if "alerts" in data and isinstance(data["alerts"], list):
            data["alerts"] = data["alerts"][:n_alerts]
        if "technicians" in data and isinstance(data["technicians"], list):
            data["technicians"] = data["technicians"][:n_techs]
    return data


def post_recommendations(payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{API_BASE}/recommendations"
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_session_state():
    if "payload" not in st.session_state:
        st.session_state.payload = None
    if "payload_text" not in st.session_state:
        st.session_state.payload_text = ""
    if "alerts" not in st.session_state:
        st.session_state.alerts = []
    if "technicians" not in st.session_state:
        st.session_state.technicians = []
    if "policy" not in st.session_state:
        # matches backend Policy model defaults reasonably
        st.session_state.policy = {
            "max_jobs_per_tech": 4,
            "prefer_high_skill_for_critical": True,
        }
    if "last_result" not in st.session_state:
        st.session_state.last_result = None


init_session_state()


# ----------------------------
# Normalizers (safe UI)
# ----------------------------
ALLOWED_SKILLS = {"engine", "fuel", "electrical", "general"}


def normalize_skill_name(x) -> str:
    if isinstance(x, str):
        return x.strip().lower()
    if isinstance(x, dict):
        # backend Skill model: {"name": "...", "level": ...}
        if "name" in x and isinstance(x["name"], str):
            return x["name"].strip().lower()
        for k in ("skill", "value", "id"):
            if k in x and isinstance(x[k], str):
                return x[k].strip().lower()
        return "general"
    return str(x).strip().lower()


def normalize_skill_level(x, default_level: int = 2) -> int:
    try:
        lv = int(x)
    except Exception:
        lv = default_level
    return max(1, min(3, lv))


def skills_to_str(skills: List[Dict[str, Any]]) -> str:
    parts = []
    for s in skills or []:
        name = normalize_skill_name(s)
        level = normalize_skill_level(s.get("level", 2) if isinstance(s, dict) else 2)
        parts.append(f"{name}(L{level})")
    return ", ".join(parts)


# ----------------------------
# 1) Get Demo Data
# ----------------------------
st.header("1) Get Demo Data")

col_a, col_b = st.columns([1, 1])

with col_a:
    n_alerts = st.slider("Number of Alerts", min_value=3, max_value=25, value=10, step=1)
    n_techs = st.slider("Number of Technicians", min_value=2, max_value=10, value=4, step=1)
    seed = st.number_input("Seed", min_value=0, value=42, step=1)

    if st.button("Generate Demo Payload", type="primary"):
        try:
            data = call_get_mock_data(n_alerts, n_techs, seed)
            st.session_state.payload = data
            st.session_state.payload_text = json.dumps(data, indent=2)

            st.session_state.alerts = data.get("alerts", []) if isinstance(data.get("alerts", []), list) else []
            st.session_state.technicians = (
                data.get("technicians", []) if isinstance(data.get("technicians", []), list) else []
            )
            if "policy" in data and isinstance(data["policy"], dict):
                st.session_state.policy = data["policy"]

            st.success("Demo payload generated.")
        except Exception as e:
            st.error(f"Failed to fetch demo payload: {e}")

with col_b:
    st.subheader("Backend Status")
    if st.button("Check /health"):
        try:
            r = requests.get(f"{API_BASE}/health", timeout=10)
            st.code(r.text)
        except Exception as e:
            st.error(f"Health check failed: {e}")


# ----------------------------
# Manager Inputs UI
# ----------------------------
st.header("Manager Inputs")

ui_col1, ui_col2 = st.columns([1, 1])

# ----- Technicians -----
with ui_col1:
    st.subheader("Technicians (Schema-Compatible)")

    with st.expander("Add Technician", expanded=False):
        t_id = st.text_input("Technician ID", key="tech_id_input")
        t_name = st.text_input("Technician Name", key="tech_name_input")

        t_lat = st.number_input("Start Latitude", value=23.78, format="%.6f", key="tech_lat_input")
        t_lon = st.number_input("Start Longitude", value=90.39, format="%.6f", key="tech_lon_input")

        # Skills in backend are [{name, level}]
        st.caption("Skills: choose names + levels (1=junior, 2=mid, 3=senior)")
        skill_1_name = st.selectbox("Skill 1", sorted(ALLOWED_SKILLS), index=0, key="s1_name")
        skill_1_level = st.selectbox("Skill 1 Level", [1, 2, 3], index=1, key="s1_level")

        add_second = st.checkbox("Add Skill 2", value=True, key="add_s2")
        if add_second:
            skill_2_name = st.selectbox("Skill 2", sorted(ALLOWED_SKILLS), index=1, key="s2_name")
            skill_2_level = st.selectbox("Skill 2 Level", [1, 2, 3], index=1, key="s2_level")
        else:
            skill_2_name, skill_2_level = None, None

        add_third = st.checkbox("Add Skill 3", value=False, key="add_s3")
        if add_third:
            skill_3_name = st.selectbox("Skill 3", sorted(ALLOWED_SKILLS), index=2, key="s3_name")
            skill_3_level = st.selectbox("Skill 3 Level", [1, 2, 3], index=1, key="s3_level")
        else:
            skill_3_name, skill_3_level = None, None

        max_jobs = st.number_input("Capacity: Max jobs", min_value=1, value=4, step=1, key="cap_max")
        assigned_jobs = st.number_input("Capacity: Already assigned", min_value=0, value=0, step=1, key="cap_assigned")

        shift_start = st.text_input("Shift Start (HH:MM)", value="09:00", key="shift_start")
        shift_end = st.text_input("Shift End (HH:MM)", value="18:00", key="shift_end")

        if st.button("Add Technician", key="add_tech_btn"):
            if not t_id or not t_name:
                st.warning("Please provide Technician ID and Name.")
            elif assigned_jobs > max_jobs:
                st.warning("Assigned jobs cannot exceed max jobs.")
            else:
                skills = [{"name": skill_1_name, "level": int(skill_1_level)}]
                if add_second and skill_2_name:
                    skills.append({"name": skill_2_name, "level": int(skill_2_level)})
                if add_third and skill_3_name:
                    skills.append({"name": skill_3_name, "level": int(skill_3_level)})

                # remove duplicates by name, keep highest level
                merged: Dict[str, int] = {}
                for s in skills:
                    nm = normalize_skill_name(s)
                    lv = normalize_skill_level(s.get("level", 2))
                    merged[nm] = max(merged.get(nm, 1), lv)
                skills = [{"name": nm, "level": lv} for nm, lv in merged.items()]

                st.session_state.technicians.append(
                    {
                        "tech_id": t_id,
                        "name": t_name,
                        "start_gps": {"lat": float(t_lat), "lon": float(t_lon)},
                        "skills": skills,
                        "capacity": {"max_jobs": int(max_jobs), "assigned": int(assigned_jobs)},
                        "shift": {"start": shift_start, "end": shift_end},
                    }
                )
                st.success("Technician added.")

    if st.session_state.technicians:
        tech_rows = []
        for t in st.session_state.technicians:
            gps = t.get("start_gps", {}) if isinstance(t.get("start_gps", {}), dict) else {}
            tech_rows.append(
                {
                    "tech_id": t.get("tech_id"),
                    "name": t.get("name"),
                    "skills": skills_to_str(t.get("skills", [])),
                    "lat": gps.get("lat"),
                    "lon": gps.get("lon"),
                    "capacity": f'{t.get("capacity", {}).get("assigned", 0)}/{t.get("capacity", {}).get("max_jobs", 0)}',
                    "shift": f'{t.get("shift", {}).get("start", "09:00")}–{t.get("shift", {}).get("end", "18:00")}',
                }
            )

        st.dataframe(pd.DataFrame(tech_rows), use_container_width=True, height=260)

        remove_idx = st.number_input(
            "Remove technician by index",
            min_value=0,
            max_value=len(st.session_state.technicians) - 1,
            value=0,
        )
        if st.button("Remove Technician", key="remove_tech_btn"):
            st.session_state.technicians.pop(int(remove_idx))
            st.success("Removed.")
    else:
        st.info("No technicians added yet (generate demo payload or add manually).")


# ----- Alerts -----
with ui_col2:
    st.subheader("Alerts")

    with st.expander("Add Alert", expanded=False):
        a_id = st.text_input("Alert ID", key="alert_id_input")
        v_id = st.text_input("Vehicle ID", key="vehicle_id_input")

        a_lat = st.number_input("Vehicle Latitude", value=23.788, format="%.6f", key="alert_lat_input")
        a_lon = st.number_input("Vehicle Longitude", value=90.381, format="%.6f", key="alert_lon_input")

        engine_temp = st.number_input("Engine Temp (°C)", value=92.4, format="%.1f", key="engine_temp_input")
        fuel_rate = st.number_input("Fuel Rate (L/h)", value=8.3, format="%.1f", key="fuel_rate_input")
        vibration = st.number_input("Vibration RMS", value=1.83, format="%.2f", key="vibration_input")
        battery = st.number_input("Battery Voltage", value=13.3, format="%.1f", key="battery_input")

        duration_min = st.number_input("Anomaly duration (minutes)", min_value=0, value=10, step=1, key="duration_min")
        odometer_km = st.number_input("Odometer (km)", min_value=0, value=50000, step=100, key="odometer_km")
        vehicle_type = st.text_input("Vehicle Type", value="van", key="vehicle_type")

        st.caption("Optional trend fields (7 points) to support 'predictive risk scoring (PoC)'.")
        temp_trend = st.text_input(
            "Engine Temp Trend (7 comma values)",
            value="88,89,90,91,92,93,94",
            key="temp_trend_input",
        )
        fuel_trend = st.text_input(
            "Fuel Rate Trend (7 comma values)",
            value="7.0,7.1,7.3,7.5,7.7,8.0,8.3",
            key="fuel_trend_input",
        )

        flags_text = st.text_input(
            "Flags (optional, comma separated e.g. HIGH_ENGINE_TEMP,FUEL_SPIKE)",
            value="",
            key="flags_input",
        )

        def parse_trend(s: str) -> List[float]:
            try:
                vals = [float(x.strip()) for x in s.split(",") if x.strip()]
                return vals[:7]
            except Exception:
                return []

        if st.button("Add Alert", key="add_alert_btn"):
            if not a_id or not v_id:
                st.warning("Please provide Alert ID and Vehicle ID.")
            else:
                flags = [f.strip() for f in flags_text.split(",") if f.strip()] if flags_text else []
                st.session_state.alerts.append(
                    {
                        "alert_id": a_id,
                        "vehicle_id": v_id,
                        "timestamp": utc_now_iso(),
                        "gps": {"lat": float(a_lat), "lon": float(a_lon)},
                        "sensors": {
                            "engine_temp_c": float(engine_temp),
                            "fuel_rate_lph": float(fuel_rate),
                            "vibration_rms": float(vibration),
                            "battery_v": float(battery),
                            "engine_temp_trend": parse_trend(temp_trend),
                            "fuel_rate_trend": parse_trend(fuel_trend),
                        },
                        "flags": flags,
                        "meta": {
                            "duration_min": int(duration_min),
                            "odometer_km": int(odometer_km),
                            "vehicle_type": vehicle_type,
                        },
                    }
                )
                st.success("Alert added.")

    if st.session_state.alerts:
        rows = []
        for a in st.session_state.alerts:
            sensors = a.get("sensors", {}) if isinstance(a.get("sensors", {}), dict) else {}
            gps = a.get("gps", {}) if isinstance(a.get("gps", {}), dict) else {}
            meta = a.get("meta", {}) if isinstance(a.get("meta", {}), dict) else {}
            rows.append(
                {
                    "alert_id": a.get("alert_id"),
                    "vehicle_id": a.get("vehicle_id"),
                    "lat": gps.get("lat"),
                    "lon": gps.get("lon"),
                    "engine_temp_c": sensors.get("engine_temp_c"),
                    "fuel_rate_lph": sensors.get("fuel_rate_lph"),
                    "duration_min": meta.get("duration_min"),
                }
            )

        st.dataframe(pd.DataFrame(rows), use_container_width=True, height=260)

        remove_a_idx = st.number_input(
            "Remove alert by index",
            min_value=0,
            max_value=len(st.session_state.alerts) - 1,
            value=0,
        )
        if st.button("Remove Alert", key="remove_alert_btn"):
            st.session_state.alerts.pop(int(remove_a_idx))
            st.success("Removed.")
    else:
        st.info("No alerts added yet (generate demo payload or add manually).")


# ----------------------------
# Policy Editor (optional)
# ----------------------------
st.header("Policy (Optional)")

pcol1, pcol2 = st.columns([1, 1])
with pcol1:
    st.session_state.policy["max_jobs_per_tech"] = st.number_input(
        "Policy: max_jobs_per_tech",
        min_value=1,
        value=int(st.session_state.policy.get("max_jobs_per_tech", 4)),
        step=1,
    )
with pcol2:
    st.session_state.policy["prefer_high_skill_for_critical"] = st.checkbox(
        "Policy: prefer_high_skill_for_critical",
        value=bool(st.session_state.policy.get("prefer_high_skill_for_critical", True)),
    )


# ----------------------------
# 2) Payload Editor (JSON)
# ----------------------------
st.header("2) Payload Editor (JSON)")
st.write("You can edit the generated JSON before sending it to the backend.")

use_manager_inputs = st.checkbox(
    "Build payload from Manager Inputs (alerts + technicians) instead of using generated demo payload",
    value=False,
)

if use_manager_inputs:
    payload_obj = {
        "alerts": st.session_state.alerts,
        "technicians": st.session_state.technicians,
        "policy": st.session_state.policy,
    }
    st.session_state.payload_text = json.dumps(payload_obj, indent=2)
    st.session_state.payload = payload_obj

payload_text = st.text_area(
    "Request Payload",
    value=st.session_state.payload_text,
    height=420,
)
st.session_state.payload_text = payload_text


# ----------------------------
# 3) Generate Recommendations
# ----------------------------
st.header("3) Generate Recommendations")

if st.button("Call /recommendations", type="primary"):
    try:
        payload = safe_json_loads(st.session_state.payload_text)
        st.session_state.payload = payload

        result = post_recommendations(payload)
        st.session_state.last_result = result
        st.success("Dispatch plan generated.")
    except Exception as e:
        st.error(f"Failed to generate recommendations: {e}")


# ----------------------------
# Results Viewer
# ----------------------------
result = st.session_state.last_result
if result:
    st.subheader("Manager Summary")
    st.write(result.get("manager_summary", ""))

    c1, c2, c3 = st.columns([1, 1, 1])

    with c1:
        st.subheader("Ranked Alerts")
        ranked = result.get("ranked_alerts", [])
        if ranked:
            st.dataframe(pd.DataFrame(ranked), use_container_width=True, height=360)
        else:
            st.info("No ranked alerts returned.")

    with c2:
        st.subheader("Assignments")
        assignments = result.get("assignments", [])
        if assignments:
            st.dataframe(pd.DataFrame(assignments), use_container_width=True, height=360)
        else:
            st.info("No assignments returned.")

    with c3:
        st.subheader("Routes")
        routes = result.get("routes", [])
        if routes:
            for r in routes:
                tech_title = (
                    f"{r.get('tech_name', 'Technician')} ({r.get('tech_id', '-')}) — "
                    f"Total: {r.get('total_distance_km', 0)} km"
                )
                st.markdown(f"**{tech_title}**")
                stops = r.get("stops", [])
                if stops:
                    st.dataframe(pd.DataFrame(stops), use_container_width=True)
                else:
                    st.caption("No stops.")
                st.divider()
        else:
            st.info("No routes returned.")

    with st.expander("Raw Response JSON"):
        st.code(json.dumps(result, indent=2), language="json")
else:
    st.caption("Generate a payload and click **Call /recommendations** to see results.")
