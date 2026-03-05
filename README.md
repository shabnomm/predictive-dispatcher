# Predictive Field Service Dispatcher (PoC)

## What this is
A minimal proof-of-concept system that:
- Generates mock fleet alerts + technicians
- Prioritizes alerts (predictive-maintenance style scoring)
- Assigns technicians based on skills + distance + workload
- Builds a simple route per technician (nearest neighbor)
- Shows everything in a Streamlit dashboard

## Run Backend (FastAPI)
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# Optional: copy env
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux

uvicorn app.main:app --reload