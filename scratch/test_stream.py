import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import openai
from unittest.mock import MagicMock

# 1. MOCK THE ORIGINAL BEFORE PATCHING
class MockDetails:
    cached_tokens = 500

class MockUsage:
    prompt_tokens = 1000
    completion_tokens = 200
    prompt_tokens_details = MockDetails()

class MockDelta:
    content = "Hello, streaming world!"

class MockChoice:
    delta = MockDelta()

class MockChunk:
    choices = [MockChoice()]
    usage = MockUsage()

def mock_stream_create(*args, **kwargs):
    def generator():
        yield MockChunk()
    return generator()

openai.resources.chat.completions.Completions = MagicMock()
openai.resources.chat.completions.Completions.create = mock_stream_create

# 2. PATCH
from llm_radar.storage.db import LLMStorage
from llm_radar.interceptors.openai import patch_openai

storage = LLMStorage(":memory:")
patch_openai(storage)

# 3. RUN IT
response = openai.resources.chat.completions.Completions.create(
    None, # Simulate self_client
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hi"}],
    stream=True
)

print("Reading stream chunks...")
for chunk in response:
    pass

# 4. VERIFY DB
calls = storage.get_calls()
print("Recorded Calls:", calls)
if not calls:
    print("FAILED: No calls recorded.")
    sys.exit(1)

call = calls[0]
print(f"Model: {call['model']}")
print(f"Input Tokens: {call['input_tokens']}")
print(f"Cached Tokens: {call['cached_tokens']}")
print(f"Output Tokens: {call['output_tokens']}")
print(f"Cost USD: ${call['cost_usd']:.4f}")
print(f"Savings USD: ${call['savings_usd']:.4f}")
print(f"Response text: {call['response_preview']}")
print("SUCCESS!")
