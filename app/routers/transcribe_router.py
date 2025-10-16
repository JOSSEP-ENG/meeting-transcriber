from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/transcribe", tags=["Transcribe"])

@router.get("/ping")
def ping():
    return {"message": "Transcribe router is connected successfully"}
