"""
FastAPI /chat (streaming) -> chat_core.stream_answer.
Buat run lokal / Docker (bukan yang dipake di HF Space gratis - itu app_gradio.py).

Run:
    uvicorn app:app --reload

Wajib set GROQ_API_KEY (lihat .env.example).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from chat_core import stream_answer

app = FastAPI(title="Indonesia Labor RAG - PP 35/2021")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ganti ke domain Vercel spesifik pas udah deploy
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


@app.post("/chat")
def chat(req: ChatRequest):
    return StreamingResponse(stream_answer(req.message), media_type="text/plain")


@app.get("/health")
def health():
    return {"status": "ok"}
