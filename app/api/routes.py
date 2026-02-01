from typing import Optional
from fastapi import APIRouter, Header, HTTPException, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage

from app.api.schemas import ChatRequest, ChatResponse
from app.api.session import load_session, save_session
from app.graph.graph import build_graph
from app.memory.json_checkpointer import JsonCheckpointer


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
) -> ChatResponse:
    """
    Execute a single conversational turn using HTTP.
    """
    if x_user_id is None:
        raise HTTPException(status_code=400, detail="X-User-Id header is required")

    store = JsonCheckpointer("memory.json")

    state, session_id = load_session(
        store=store,
        user_id=x_user_id,
        persona=payload.persona,
        session_id=payload.session_id,
    )

    state["user_input"] = payload.message

    graph = build_graph()
    result = graph.invoke(state)

    save_session(
        store=store,
        user_id=x_user_id,
        persona=payload.persona,
        session_id=session_id,
        state=result,
    )

    return ChatResponse(
        response=result.final_response,
        session_id=session_id,
        persona=payload.persona,
        metadata={},
    )


@router.websocket("/ws")
async def chat_ws(websocket: WebSocket) -> None:
    """
    Execute conversational turns over a WebSocket connection.
    """
    await websocket.accept()
    store = JsonCheckpointer("memory.json")

    try:
        while True:
            payload = await websocket.receive_json()

            user_id = payload.get("user_id")
            persona = payload.get("persona")
            message = payload.get("message")
            session_id = payload.get("session_id")

            if user_id is None or persona is None or message is None:
                await websocket.send_json({"error": "Invalid payload"})
                continue

            state, session_id = load_session(
                store=store,
                user_id=user_id,
                persona=persona,
                session_id=session_id,
            )

            state["user_input"] = message

            graph = build_graph()
            result = graph.invoke(state)

            save_session(
                store=store,
                user_id=user_id,
                persona=persona,
                session_id=session_id,
                state=result,
            )

            await websocket.send_json(
                {
                    "response": result['final_response'],
                    "session_id": session_id,
                    "persona": persona,
                }
            )

    except WebSocketDisconnect:
        return
