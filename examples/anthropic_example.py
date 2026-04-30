"""
FastAPI + Anthropic example.
Run: uvicorn anthropic_example:app --reload
Dashboard: http://localhost:8000/__llm_radar
"""

from fastapi import FastAPI
from llm_radar import LLMRadar
import anthropic

app = FastAPI()
radar = LLMRadar(app)

client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY env var


@app.get("/summarize")
async def summarize(text: str = "FastAPI is a modern Python web framework."):
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{"role": "user", "content": f"Summarize in one sentence: {text}"}],
    )
    return {"summary": response.content[0].text}
