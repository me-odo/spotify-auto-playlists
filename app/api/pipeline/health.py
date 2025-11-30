from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def pipeline_health() -> dict:
    return {"status": "ok"}
