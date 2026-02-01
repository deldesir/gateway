from typing import Dict, Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Header, HTTPException
from langchain_core.messages import AIMessageChunk

from app.api.session import load_session, save_session
from app.api.schemas import ChatRequest, ChatResponse
from app.graph.graph import build_graph
from app.memory.json_checkpointer import JsonCheckpointer

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
) -> ChatResponse:
    """
    Non-streaming HTTP chat endpoint.
    """
    if x_user_id is None:
        raise HTTPException(status_code=400, detail="X-User-Id header is required")

    store = JsonCheckpointer("memory.json")
    graph = build_graph()

    state, session_id = load_session(
        store=store,
        user_id=x_user_id,
        persona=payload.persona,
        session_id=payload.session_id,
    )

    state["user_input"] = payload.message

    config = {
        "configurable": {"thread_id": f"{x_user_id}:{payload.persona}:{session_id}"}
    }

    result = await graph.ainvoke(state, config=config)

    save_session(
        store=store,
        user_id=x_user_id,
        persona=payload.persona,
        session_id=session_id,
        state=result,
    )

    return ChatResponse(
        response=result.get("final_response", ""),
        session_id=session_id,
        persona=payload.persona,
        metadata={},
    )


@router.websocket("/ws")
async def chat_ws(websocket: WebSocket) -> None:
    """
    Streaming chat endpoint using LangGraph-native streaming.
    """
    await websocket.accept()

    store = JsonCheckpointer("memory.json")
    graph = build_graph()

    try:
        while True:
            payload: Dict[str, Any] = await websocket.receive_json()

            user_id = payload.get("user_id")
            persona = payload.get("persona")
            message = payload.get("message")
            session_id = payload.get("session_id")

            if user_id is None or persona is None or message is None:
                await websocket.send_json(
                    {"type": "error", "message": "user_id, persona, message required"}
                )
                continue

            state, session_id = load_session(
                store=store,
                user_id=user_id,
                persona=persona,
                session_id=session_id,
            )

            state["user_input"] = message

            config = {
                "configurable": {"thread_id": f"{user_id}:{persona}:{session_id}"}
            }

            streamed_tokens = []
            final_state = None

            async for chunk, meta in graph.astream(
                input=state,
                config=config,
                stream_mode="messages",
            ):
                if meta.get("langgraph_node") == "conversation_node" and isinstance(
                    chunk, AIMessageChunk
                ):
                    if chunk.content:
                        streamed_tokens.append(chunk.content)
                        await websocket.send_json(
                            {"type": "token", "content": chunk.content}
                        )

                final_state = meta.get("state", final_state)

            if final_state is None:
                final_state = state

            save_session(
                store=store,
                user_id=user_id,
                persona=persona,
                session_id=session_id,
                state=final_state,
            )

            await websocket.send_json(
                {
                    "type": "done",
                    "response": "".join(streamed_tokens),
                    "persona": persona,
                    "session_id": session_id,
                }
            )

    except WebSocketDisconnect:
        return
