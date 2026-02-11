import os
import json
from sqlmodel import select
from app.db import get_session
from app.models import Admin
from app.logger import logger

api_logger = logger.bind(name="AuthService")

async def check_admin_permissions(user_id: str, command_root: str) -> bool:
    """
    Check if a user is authorized to execute a specific command.
    Checks:
    1. Environment Variable (Superuser)
    2. Database (Role-based)
    """
    # 1. Superuser Check (Env Var)
    admin_phones = os.getenv("ADMIN_PHONE", "").replace(" ", "").split(",")
    if not admin_phones or admin_phones == [""]:
         api_logger.warning("No ADMIN_PHONE configured! Dev Mode: ALLOWED.")
         return True
         
    for admin in admin_phones:
        # Flexible match (handle + prefix variations)
        if admin in user_id or (admin.replace("+", "") in user_id.replace("+", "")):
            api_logger.info(f"User {user_id} authorized via ADMIN_PHONE.")
            return True

    # 2. Database Check
    try:
        async for session in get_session():
            query = select(Admin).where(Admin.user_phone == user_id)
            result = await session.exec(query)
            admin_records = result.all()
            
            if not admin_records:
                continue
                
            for record in admin_records:
                perms = json.loads(record.permissions) if record.permissions != "*" else ["*"]
                if "*" in perms or command_root in perms:
                    api_logger.info(f"User {user_id} authorized via DB (Perms: {perms}).")
                    return True
            break
    except Exception as e:
        api_logger.error(f"Error checking admin permissions: {e}")
        
    return False
