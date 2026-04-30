# 📡 LLM Radar

[![PyPI](https://img.shields.io/pypi/v/llm-radar)](https://pypi.org/project/llm-radar/)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Real-time observability dashboard for LLM applications.**
Track every prompt, token count, cost, and latency across OpenAI and Anthropic — with one line of code.

```python
from llm_radar import LLMRadar
radar = LLMRadar(app)  # that's it
```

Dashboard → **http://localhost:8000/__llm_radar**

---

## Installation

```bash
pip install llm-radar
```

With provider SDKs:

```bash
pip install "llm-radar[openai]"       # + openai
pip install "llm-radar[anthropic]"    # + anthropic
pip install "llm-radar[all]"          # + both
```

---

## Quick Start

### OpenAI

```python
from fastapi import FastAPI
from llm_radar import LLMRadar
import openai

app = FastAPI()
radar = LLMRadar(app)          # intercepts all openai calls automatically

client = openai.OpenAI()

@app.get("/chat")
async def chat(message: str):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": message}],
    )
    return {"reply": response.choices[0].message.content}
```

### Anthropic

```python
from fastapi import FastAPI
from llm_radar import LLMRadar
import anthropic

app = FastAPI()
radar = LLMRadar(app)

client = anthropic.Anthropic()

@app.get("/summarize")
async def summarize(text: str):
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{"role": "user", "content": text}],
    )
    return {"summary": response.content[0].text}
```

---

## Use with fastapi-radar

llm-radar works alongside [fastapi-radar](https://github.com/doganarif/fastapi-radar) — one app, two dashboards.

```python
from fastapi import FastAPI
from fastapi_radar import Radar
from llm_radar import LLMRadarPlugin

app = FastAPI()

radar = Radar(app)               # HTTP + SQL monitoring → /__radar/
llm   = LLMRadarPlugin(app)      # LLM monitoring       → /__llm_radar
```

---

## What Gets Tracked

| Signal | Captured |
|--------|----------|
| Prompt preview | ✅ First 500 chars of last user message |
| Response preview | ✅ First 500 chars of response |
| Input tokens | ✅ |
| Output tokens | ✅ |
| Cost (USD) | ✅ Auto-calculated from current pricing |
| Latency (ms) | ✅ End-to-end wall time |
| Model name | ✅ |
| Provider | ✅ openai / anthropic |
| Errors | ✅ With message |
| Async calls | ✅ |

---

## Configuration

```python
radar = LLMRadar(
    app,
    dashboard_path="/__llm_radar",   # Custom path
    max_calls=1000,                   # Max records to keep
    retention_hours=24,               # Data retention window
    db_path="/var/data/llm",          # Custom DB location
    auth_dependency=my_auth_fn,       # Optional FastAPI dependency
    track_openai=True,
    track_anthropic=True,
)
```

### Securing the Dashboard

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

def verify_token(creds: HTTPAuthorizationCredentials = Depends(security)):
    if creds.credentials != "your-secret-token":
        raise HTTPException(status_code=401, detail="Unauthorized")

radar = LLMRadar(app, auth_dependency=verify_token)
```

---

## Supported Models & Pricing

Auto-detects cost for:

- **OpenAI**: gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo, o1, o3-mini, o4-mini
- **Anthropic**: claude-opus-4, claude-sonnet-4, claude-haiku-4, claude-3.5-sonnet, claude-3-opus

Unrecognized models record 0 cost (no crash).

---

## Contributing

```bash
git clone https://github.com/ganeshmandakapu/llm-radar
cd llm-radar
pip install -e ".[dev]"
```

## License

MIT — [Ganesh Mandakapu](https://github.com/ganeshmandakapu)
