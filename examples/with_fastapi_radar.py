"""
llm-radar alongside fastapi-radar.
Run: uvicorn with_fastapi_radar:app --reload

fastapi-radar dashboard: http://localhost:8000/__radar/
llm-radar dashboard:     http://localhost:8000/__llm_radar
"""

from fastapi import FastAPI
from sqlalchemy import create_engine
import openai
import anthropic

# fastapi-radar
from fastapi_radar import Radar

# llm-radar plugin
from llm_radar import LLMRadarPlugin

app = FastAPI()
engine = create_engine("sqlite:///./app.db")

# Mount fastapi-radar (HTTP + SQL monitoring)
radar = Radar(app, db_engine=engine)
radar.create_tables()

# Mount llm-radar alongside it (LLM call monitoring)
llm = LLMRadarPlugin(app)

openai_client = openai.OpenAI()
anthropic_client = anthropic.Anthropic()


@app.get("/ask-openai")
async def ask_openai(q: str = "What is FastAPI?"):
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": q}],
    )
    return {"answer": resp.choices[0].message.content}


@app.get("/ask-claude")
async def ask_claude(q: str = "What is FastAPI?"):
    resp = anthropic_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{"role": "user", "content": q}],
    )
    return {"answer": resp.content[0].text}
