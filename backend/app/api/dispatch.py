from fastapi import APIRouter
from app.models.schemas import RecommendationRequest, RecommendationResponse
from app.services.dispatcher import generate_recommendations
from app.services.mock_data import generate_mock_request_payload

router = APIRouter(prefix="", tags=["dispatch"])


@router.get("/mock-data", response_model=RecommendationRequest)
def mock_data(alerts: int = 10, techs: int = 4, seed: int = 42):
    """
    Returns a complete request payload you can POST to /recommendations.
    """
    return generate_mock_request_payload(num_alerts=alerts, num_techs=techs, seed=seed)


@router.post("/recommendations", response_model=RecommendationResponse)
def recommendations(payload: RecommendationRequest):
    return generate_recommendations(payload)