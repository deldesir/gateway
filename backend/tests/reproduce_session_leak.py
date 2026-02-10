import requests
import json
import sys

BASE_URL = "http://localhost:8085/v1/chat/completions"

def chat(user_id, message):
    payload = {
        "model": "konex-support",
        "messages": [{"role": "user", "content": message}],
        # "user": user_id  <-- user field might be missing
    }
    if user_id:
        payload["user"] = user_id
        
    response = requests.post(BASE_URL, json=payload)
    if response.status_code != 200:
        print(f"Error: {response.text}")
        return None
    return response.json()['choices'][0]['message']['content']

def run_test():
    print("--- Starting Session Isolation Test (Missing User Field) ---")
    
    # Anonymous User A
    print("Anon User A says: 'My name is Alice.'")
    resp_a1 = chat(None, "My name is Alice.")
    
    if resp_a1 is None:
        print("\n[PASS] Server rejected anonymous user (Correct Behavior).")
        return

    print(f"Agent to A: {resp_a1}")
    
    # Anonymous User B
    print("\nAnon User B says: 'What is my name?'")
    resp_b1 = chat(None, "What is my name?")
    print(f"Agent to B: {resp_b1}")
    
    if "Alice" in resp_b1:
        print("\n[FAIL] Session Leak Detected! Anon User B was identified as Alice.")
        # sys.exit(1) # Don't exit yet, we expect this to fail
    else:
        print("\n[PASS] Sessions appear isolated (Unexpected).")

if __name__ == "__main__":
    run_test()
