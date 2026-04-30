"""
Standalone FastAPI + OpenAI example.
Run: uvicorn basic_openai:app --reload
Dashboard: http://localhost:8000/__llm_radar
"""

from fastapi import FastAPI
from llm_radar import LLMRadar
import openai

app = FastAPI()
radar = LLMRadar(app)

client = openai.OpenAI()  # uses OPENAI_API_KEY env var


@app.get("/chat")
async def chat(message: str = "Tell me a joke"):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": message}],
    )
    return {"reply": response.choices[0].message.content}
