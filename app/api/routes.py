from typing import Dict, Any, Optional, List
import time
import json
import uuid
import os
from contextlib import asynccontextmanager

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Header, HTTPException, Request
from langchain_core.messages import AIMessageChunk, HumanMessage, AIMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
except ImportError:
    AsyncPostgresSaver = None

from app.api.schemas import ChatRequest, ChatResponse
from app.graph.graph import build_graph

router = APIRouter(prefix="", tags=["chat"])

# Initialize checkpointer configuration
DB_PATH = os.getenv("SQLITE_DB_PATH", "checkpoints.sqlite")
POSTGRES_URI = os.getenv("POSTGRES_URI")

@asynccontextmanager
async def get_checkpointer():
    if POSTGRES_URI and AsyncPostgresSaver:
        async with AsyncPostgresSaver.from_conn_string(POSTGRES_URI) as checkpointer:
            yield checkpointer
    else:
        async with AsyncSqliteSaver.from_conn_string(DB_PATH) as checkpointer:
            yield checkpointer

@router.post("/chat/", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
) -> ChatResponse:
    """
    Non-streaming HTTP chat endpoint (Legacy).
    """
    if x_user_id is None:
        raise HTTPException(status_code=400, detail="X-User-Id header is required")

    session_id = payload.session_id or str(uuid.uuid4())
    thread_id = f"{x_user_id}:{payload.persona}:{session_id}"
    
    config = {"configurable": {"thread_id": thread_id}}

    async with get_checkpointer() as checkpointer:
        graph = build_graph(checkpointer=checkpointer)
        # ... implementation for legacy chat would go here if needed
        pass

    return ChatResponse(response="To be implemented with DB", session_id=session_id, persona=payload.persona)


# --- OpenAI Adapter ---

from pydantic import BaseModel

class OpenAIChatMessage(BaseModel):
    role: str
    content: str

class OpenAIChatRequest(BaseModel):
    model: str
    messages: List[Dict[str, str]] 
    stream: Optional[bool] = False
    temperature: Optional[float] = 0.7
    user: Optional[str] = None

@router.post("/v1/chat/completions")
async def openai_chat_completions(request: OpenAIChatRequest, raw_request: Request):
    """
    OpenAI-compatible endpoint for RapidPro.
    """
    # 1. Extract parameters
    import json
    from app.logger import logger
    
    api_logger = logger.bind(name="API")
    api_logger.info(f"Incoming Chat Request | Payload: {request.model_dump_json()}")
    api_logger.info(f"Incoming Headers: {raw_request.headers}")
    
    messages = request.messages
    if not messages:
        raise HTTPException(status_code=400, detail="No messages provided")
    
    last_user_message = messages[-1]["content"] 
    
    # 1. Try explicit 'user' field
    user_id = request.user

    # 2. Fallback: Parse URN from message content (e.g., "tel:+12345 Hello")
    if not user_id:
        import re
        # Look for tel:+... or whatsapp:...
        # Updated to handle optional +, and handle format like (whatsapp:1234)
        match = re.search(r"(tel|whatsapp|telegram):(\+?\d+)", last_user_message)
        if match:
            # Reconstruct URN, e.g. whatsapp:12345
            user_id = f"{match.group(1)}:{match.group(2)}"
            api_logger.info(f"Extracted User ID from content: {user_id}")

    # 3. Message Cleaning & Channel Extraction
    # Expected Format: "Name (URN > Channel) says: Content"
    # Regex captures URN and optional Channel
    import re
    # allow optional > channel part
    # Group 'urn': The user's ID
    # Group 'channel': The channel ID (optional)
    prefix_pattern = r"^.*?\((?P<urn>(?:(?:tel|whatsapp|telegram):)?\+?\d+)(?:\s*>\s*(?P<channel>\+?\d+))?\) says:\s+"
    
    match = re.search(prefix_pattern, last_user_message)
    if match:
        clean_content = re.sub(prefix_pattern, "", last_user_message, count=1)
        api_logger.info(f"Cleaned Message Content: '{clean_content}'")
        
        # Extracted data
        extracted_urn = match.group("urn")
        extracted_channel = match.group("channel")
        
        # Update user_id if not already set (or if we trust the content more?)
        # Usually valid-user-check happened in Step 2 unless fallthrough.
        # But this is more precise.
        if not user_id and extracted_urn:
             user_id = extracted_urn
             api_logger.info(f"Extracted User ID from complex prefix: {user_id}")
             
        if extracted_channel:
             clean_channel = extracted_channel.lstrip("+")
             api_logger.info(f"Extracted Channel ID from prefix: {extracted_channel} -> {clean_channel}")
             # OVERRIDE the model with the channel ID
             # This allows the downstream "Channel Config Lookup" to find the persona
             # regardless of what model was passed in the JSON body.
             request.model = clean_channel
        
        # Update content
        request.messages[-1]["content"] = clean_content
        last_user_message = clean_content
    
    # Enforce User ID for Session Isolation
    if not user_id:
        raise HTTPException(
            status_code=400, 
            detail="Field 'user' is required for session isolation (e.g. phone number)."
        )
    model_persona = request.model or "konex-support"
    
    # --- CHANNEL CONFIG LOOKUP ---
    # Check if 'model' passed is actually a Channel Phone Number (e.g. "50912345678")
    # If so, look up the assigned Persona.
    try:
        from app.models import ChannelConfig, Persona
        from app.db import get_session
        from sqlmodel import select

        # We need a synchronous way to check this, OR use the async session.
        # Since we are in an async function, we can use a new session context.
        async for session in get_session():
            # Check for exact match on channel_phone
            # request.model might be "509..." or "whatsapp:509..."
            # Let's try as-is first.
            query = select(ChannelConfig).where(ChannelConfig.channel_phone == model_persona)
            result = await session.exec(query)
            channel_config = result.first()
            
            if channel_config:
                # Found a channel config! Load the persona.
                persona_res = await session.get(Persona, channel_config.persona_id)
                if persona_res:
                    api_logger.info(f"Channel Lookup: Mapped '{model_persona}' -> Persona '{persona_res.name}' ({persona_res.id})")
                    model_persona = persona_res.id
                    # Future: Inject system_prompt_override or knowledge_base_id into Thread State?
                    # For now, just mapping the name ensures the Graph loads the right persona logic.
                else:
                    api_logger.warning(f"Channel Config found for '{model_persona}' but Persona ID '{channel_config.persona_id}' is missing.")
            else:
                 # Clean up potential "whatsapp:" prefix if passed in model?
                 # Usually model is just "konex-support" or a number on WhatsApp business API mapping.
                 pass
            break # Only need one session iteration
    except Exception as e:
        api_logger.error(f"Error looking up ChannelConfig: {e}")
    # --- END CHANNEL LOOKUP ---
    
    # 2. Setup Session/Thread
    # We use the user_id (phone number) as the stable thread_id
    thread_id = f"whatsapp:{user_id}"

    # --- ADMIN COMMAND INTERCEPTOR ---
    # Handle commands via Modular Registry
    # --- ADMIN COMMAND INTERCEPTOR ---
    # Handle commands via Modular Registry
    # The message has been cleaned above (prefix stripped), so we can check startswith.
    if last_user_message.strip().startswith(("/", "#")):
        # SECURITY CHECK: Granular Admin Authorization
        import os
        from app.db import get_session
        from app.models import Admin
        from sqlmodel import select
        import json

        # 1. Start with Deny
        is_allowed = False
        
        # 2. Extract Command (e.g., "#user")
        parts = last_user_message.strip().split()
        if not parts:
            # Handle empty message after strip
            api_logger.warning("Message is empty after stripping.")
            command_root = ""
        else:
            command_root = parts[0].lower().replace("#", "").replace("/", "") # "user"
            api_logger.info(f"Checking authorization for command '{command_root}' (User: {user_id})")

        # 3. Superuser Check (Environment Variable)
        admin_phones = os.getenv("ADMIN_PHONE", "").replace(" ", "").split(",")
        
        if not admin_phones or admin_phones == [""]:
             api_logger.warning("No ADMIN_PHONE configured! Dev Mode: ALLOWED.")
             is_allowed = True
        else:
            for admin in admin_phones:
                # Debug comparison
                if admin in user_id or (admin.replace("+", "") in user_id.replace("+", "")):
                    is_allowed = True
                    api_logger.info(f"User {user_id} authorized via ADMIN_PHONE.")
                    break
        
        # 4. Database Check (If not already allowed as Superuser)
        # We check if the user is an admin for ANY channel.
        # Since we don't receive the channel ID in the request, we can't enforce channel-scoping strictly.
        # Design Decision: If you are an admin (stored in DB), you are authorized.
        
        if not is_allowed:
             async for session in get_session():
                # Flexible match: Check if user_id (e.g. whatsapp:123) matches any admin record
                # We could try exact match first
                query = select(Admin).where(Admin.user_phone == user_id)
                result = await session.exec(query)
                admin_records = result.all()
                
                # If found, check permissions in ANY of their admin records
                # This effectively gives them union of permissions across all channels they manage
                for record in admin_records:
                    perms = json.loads(record.permissions) if record.permissions != "*" else ["*"]
                    if "*" in perms or command_root in perms:
                        is_allowed = True
                        api_logger.info(f"User {user_id} authorized via DB (Perms: {perms}).")
                        break
                
                # If not found by exact match, maybe try partial? (e.g. + vs no +)
                # For now, rely on robust storage (cmd_admin cleans URNs) and robust input (routes cleans URNs)
                # routes.py L104 reconstructs user_id as "scheme:number"
                # cmd_admin L25 cleans to "scheme:number" (mostly whatsapp:)
                # So exact match should work if schemes align.

        from app.commands.registry import CommandRegistry
        
        # KEY FIX: Prevent fallthrough to AI for known commands if auth fails
        try:
            has_cmd = CommandRegistry.has_command(command_root)
            api_logger.info(f"Command '{command_root}' exists in registry: {has_cmd}")
            
            if has_cmd:
                 if not is_allowed:
                     # It's a real command, but user is not allowed. STOP HERE.
                     api_logger.warning(f"Access Denied for command '{command_root}' from {user_id}")
                     return {
                        "id": f"chatcmpl-deny-{uuid.uuid4()}",
                        "object": "chat.completion",
                        "created": int(time.time()),
                        "model": model_persona,
                        "choices": [{"index": 0, "message": {"role": "assistant", "content": "🚫 Permission Denied."}, "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                    }
        except Exception as e:
            api_logger.error(f"Error checking command registry: {e}")
            # Fallthrough to safe behavior (AI or Error?)
            # If registry check fails, better to let AI handle it or ignore it.
            pass
        
        if is_allowed:
            from app.commands.registry import CommandRegistry, CommandContext
            
            # Build Context
            async with get_checkpointer() as checkpointer:
                # Checkpointer setup usually done in build_graph, but good to ensure here if hitting DB directly
                if hasattr(checkpointer, "setup"): await checkpointer.setup()
                
                ctx = CommandContext(
                user_id=user_id,
                thread_id=thread_id,
                persona=model_persona,
                args=[], # populated in execute
                checkpointer=checkpointer,
                raw_message=last_user_message
            )
            
            # Execute
            admin_response = await CommandRegistry.execute(last_user_message, ctx)
            
            # If a response came back, it was a valid command
            if admin_response:
                 return {
                    "id": f"chatcmpl-admin-{uuid.uuid4()}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": model_persona,
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": admin_response}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                }
    # --- END ADMIN COMMANDS ---
    
    # 3. Graph Execution
    async with get_checkpointer() as checkpointer:
        # Initialize Postgres tables if needed (idempotent)
        if hasattr(checkpointer, "setup"):
            await checkpointer.setup()

        graph = build_graph(checkpointer=checkpointer)
        
        config = {"configurable": {"thread_id": thread_id}}
        
        # Prepare input state
        initial_state = {
            "persona": model_persona,
            "user_input": last_user_message,
            "messages": [HumanMessage(content=last_user_message)]
        }

        # Invoke
        result = await graph.ainvoke(initial_state, config=config)
        
        # 4. Extract Response
        final_text = result.get("final_response") or "Mwen pa konprann."

    # 5. Format OpenAI Response
    return {
        "id": f"chatcmpl-{uuid.uuid4()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_persona,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": final_text
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
    }
