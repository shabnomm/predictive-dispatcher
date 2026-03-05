from fastapi import FastAPI
from app.api.dispatch import router as dispatch_router

app = FastAPI(title="Predictive Field Service Dispatcher PoC", version="0.1.0")
app.include_router(dispatch_router)


@app.get("/health")
def health():
    return {"status": "ok"}