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
from app.services.channel import resolve_persona
from app.services.auth import check_admin_permissions

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
    # Delegate to Service
    model_persona, system_prompt_override = await resolve_persona(model_persona)
    # --- END CHANNEL LOOKUP ---
    # 2. Setup Session/Thread
    # We use the user_id (phone number) as the stable thread_id
    thread_id = f"whatsapp:{user_id}"

    # --- ADMIN COMMAND INTERCEPTOR ---
    # Handle commands via Modular Registry
    # The message has been cleaned above (prefix stripped), so we can check startswith.
    if last_user_message.strip().startswith(("/", "#")):
        # 1. Extract Command (e.g., "#user")
        parts = last_user_message.strip().split()
        if not parts:
            # Handle empty message after strip
            api_logger.warning("Message is empty after stripping.")
            command_root = ""
        else:
            command_root = parts[0].lower().replace("#", "").replace("/", "") # "user"
            
        # 2. Check Permissions via Service
        is_allowed = await check_admin_permissions(user_id, command_root)
        
        from app.commands.registry import CommandRegistry
        
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
            pass
        
        if is_allowed:
            from app.commands.registry import CommandRegistry, CommandContext
            
            # Build Context
            async with get_checkpointer() as checkpointer:
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
                "messages": [HumanMessage(content=last_user_message)],
                "system_prompt_override": system_prompt_override
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
