from fastapi import FastAPI
from app.routers import transcribe_router

app = FastAPI(title="Meeting Transcriber MVP")

# 라우터 연결
app.include_router(transcribe_router.router)

@app.get("/")
def root():
    return {"message": "Server running successfully"}
