import asyncio
import uuid
import sys
# Define a simple client since we can't import app code easily without env setup
import httpx

BASE_URL = "http://127.0.0.1:8085/v1/chat/completions"
HEADERS = {"Content-Type": "application/json"}
ADMIN_USER = "whatsapp:50942614949" # Local Admin

async def run_flow():
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("1. Creating Persona '#persona create integration-bot friendly | Integration Test Bot'")
        
        # 1. Create Persona
        # Command must be sent as a user message
        try:
            resp = await client.post(BASE_URL, json={
                "model": "konex-support",
                "messages": [{"role": "user", "content": "#persona create integration-bot friendly | Integration Test Bot"}],
                "user": ADMIN_USER
            })
            print(f"Response: {resp.text}")
            if "created" not in resp.text:
                print("FAILED to create persona.")
                # It might fail if exists, that's fine.
                if "already exists" not in resp.text:
                    sys.exit(1)
        except Exception as e:
            print(f"FAILED TO CONNECT: {e}")
            sys.exit(1)

        # 2. Assign Channel
        print("\n2. Assigning Channel '#channel assign 509_TEST_CHANNEL integration-bot'")
        resp = await client.post(BASE_URL, json={
            "model": "konex-support",
            "messages": [{"role": "user", "content": "#channel assign 509_TEST_CHANNEL integration-bot"}],
            "user": ADMIN_USER
        })
        print(f"Response: {resp.text}")
        if "Assigned channel" not in resp.text and "Updated channel" not in resp.text:
            print("FAILED to assign channel.")
            sys.exit(1)

        # 3. Simulate Request on Channel
        print("\n3. Sending formatted request with model='509_TEST_CHANNEL'")
        # RapidPro would send model="509_TEST_CHANNEL"
        resp = await client.post(BASE_URL, json={
            "model": "509_TEST_CHANNEL",
            "messages": [{"role": "user", "content": "Hello, who are you?"}],
            "user": "whatsapp:999999"
        })
        
        # The response model should reflect the mapped persona (integration-bot) 
        # OR the content should reflect the persona if we had a way to check content style.
        # But `routes.py` updates `model` in the `ChatResponse`.
        
        print(f"Response JSON: {resp.json()}")
        returned_model = resp.json().get("model")
        print(f"Returned Model: {returned_model}")
        
        if returned_model == "integration-bot":
             print("SUCCESS: Model was swapped to 'integration-bot'.")
        else:
             print(f"FAILED: Model was '{returned_model}', expected 'integration-bot'.")
             sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_flow())
