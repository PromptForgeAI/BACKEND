from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/health")
def health_check():
    # You can add DB ping or other checks here
    return JSONResponse(content={"status": "ok"})
