from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import transcribe_router, websocket_router

app = FastAPI(title="Meeting Transcriber MVP")

# CORS 설정 (프론트엔드와 통신을 위해 필요)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vue/React 개발 서버
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 연결
app.include_router(transcribe_router.router)
app.include_router(websocket_router.router)

@app.get("/")
def root():
    return {"message": "Server running successfully"}
