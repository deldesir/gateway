import asyncio
import os
from app.services.channel import resolve_persona
from app.services.auth import check_admin_permissions

async def verify():
    print("--- Verifying Services ---")
    
    # 1. Channel Service
    # Assuming no data, should return phone as persona
    pid, override = await resolve_persona("5091112222")
    print(f"Resolve '5091112222' -> Persona: {pid}, Override: {override}")
    assert pid == "5091112222"
    assert override is None

    # 2. Auth Service
    # Without ADMIN_PHONE set, and no DB, should trigger warning or fail or depend on default
    # If ADMIN_PHONE is not set, dev mode might be allowed or not?
    # In auth.py: if not admin_phones: warning -> allow.
    
    # Force Env for testing
    os.environ["ADMIN_PHONE"] = "5098888888"
    
    # Test Authorized
    allowed = await check_admin_permissions("5098888888", "test")
    print(f"Auth '5098888888' (Admin) -> {allowed}")
    assert allowed == True
    
    # Test Unauthorized
    denied = await check_admin_permissions("5091112222", "test")
    print(f"Auth '5091112222' (User) -> {denied}")
    assert denied == False
    
    print("✅ Services Verified")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(verify())
