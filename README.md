🚚 Predictive Field Service Dispatcher (AI-Powered)








An AI-powered field service optimization system that predicts vehicle issues, prioritizes service alerts, assigns technicians, optimizes routes, and generates an AI-powered operational summary for managers.

This project demonstrates how AI + optimization + dashboards can support real-world fleet maintenance and dispatch operations.

🧠 System Architecture
Vehicles → Sensor Alerts
           ↓
Risk Scoring Engine
           ↓
Technician Matching
           ↓
Route Optimization
           ↓
AI Manager Summary (LLM)
           ↓
Streamlit Dashboard
🌐 Live Demo
Streamlit Dashboard

https://predictive-dispatcher-7euzkgvrt3cebfrhlk64q7.streamlit.app/

Backend API (FastAPI Docs)

https://predictive-dispatcher.onrender.com/docs

⚙️ How the System Works
1️⃣ Vehicle Telemetry → Alerts

Vehicle sensors generate anomaly alerts such as:

engine temperature spike

abnormal fuel consumption

excessive vibration

battery voltage issues

These alerts trigger maintenance analysis.

2️⃣ Risk Scoring Engine

Each alert is evaluated using rule-based predictive scoring:

Factors include:

anomaly duration

sensor trends

severity thresholds

vehicle metadata

Alerts are ranked based on failure risk probability.

3️⃣ Technician Matching

The system assigns technicians using:

skill matching

technician workload

technician location

technician shift availability

The best technician is selected for each alert.

4️⃣ Route Optimization

Once technicians are assigned, the system generates an optimized service route minimizing travel distance.

Output includes:

stop order

distance estimation

technician workload balance

5️⃣ AI Manager Summary (LLM)

An LLM generates a human-readable explanation of the dispatch plan.

Example:

"Alert A102 was prioritized due to high engine temperature and sustained anomaly duration. Technician Rahim was selected because of engine repair specialization and closest proximity to the vehicle."

6️⃣ Streamlit Dashboard

Operations managers can interact with the system through an intuitive dashboard.

Features include:

demo data generation

technician management

alert simulation

dispatch plan generation

AI reasoning explanation

visualization of assignments and routes

🖥️ Streamlit Dashboard Features

Generate realistic demo fleet alerts

Add or modify technicians

Adjust service policies

Generate dispatch recommendations

View ranked alerts

See technician assignments

Inspect optimized routes

Read AI-generated manager summary

🔧 Tech Stack
Backend

FastAPI

Pydantic

Python

AI Reasoning

OpenAI API

LLM explanation engine

Data Processing

Pandas

Frontend

Streamlit

Deployment

Render (FastAPI backend)

Streamlit Cloud (dashboard)

📡 Backend API

The backend handles:

alert processing

risk scoring

technician assignment

route planning

AI explanation generation

API Documentation

https://predictive-dispatcher.onrender.com/docs
📂 Project Structure
predictive-dispatcher
│
├── backend
│   ├── app
│   ├── services
│   ├── models
│   └── main.py
│
├── frontend
│   └── streamlit_app.py
│
├── requirements.txt
└── README.md
📊 Example Output

The system generates:

Ranked Alerts

Alerts prioritized by predicted failure risk.

Technician Assignments

Optimal technician for each alert.

Route Plan

Optimized route for technicians.

AI Summary

LLM explanation for dispatch decisions.

🚀 Future Improvements

Machine learning–based predictive maintenance model

Real-time fleet telemetry ingestion

Google Maps / OSRM routing integration

SLA-aware dispatch scheduling

Multi-city fleet optimization
