import asyncio
from app.api.adapters.openai import openai_chat_completions
from fastapi import Request

class MockRequest:
    async def json(self):
        return {
            "model": "talkprep",
            "messages": [{"role": "user", "content": "montre talk mwen"}],
            "user": "urn:whatsapp:5091234567"
        }

async def test():
    req = MockRequest()
    try:
        resp = await openai_chat_completions(req)
        print("E2E Response OK:", str(resp)[:200])
        # Did it come from rivebot?
        body = resp.body.decode()
        if "chatcmpl-rs" in body:
             print("✅ Success: Response is from Rivebot")
             print(body)
        else:
             print("❌ Failed: Fallthrough to LLM or errored")
    except Exception as e:
        print("E2E Error:", e)

asyncio.run(test())
