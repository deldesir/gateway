"""
End-to-end tests for the RiveBot ↔ AI Gateway integration.

Tests are organised into three suites:

  Suite 1 — RiveBot client (rivebot_client.py)
    - match_intent returns response on match
    - match_intent returns None on no-match
    - match_intent returns None on RiveBot timeout
    - detect_stage_completing_tool detects correct tool
    - detect_stage_completing_tool returns None for non-stage tools
    - advance_topic_if_needed calls set-topic for stage tools
    - advance_topic_if_needed is no-op for non-stage tools

  Suite 2 — Tools router (GET + POST)
    - GET /v1/tools/{name} calls tool with no args
    - POST /v1/tools/{name} calls tool with kwargs
    - POST /v1/tools/{name} with _args maps positionally
    - POST /v1/tools/{name} with _args catch-all on last field
    - GET /v1/tools/unknown returns 404
    - POST /v1/tools/{name} tool exception returns 500

  Suite 3 — openai_chat_completions integration
    - RiveBot match short-circuits LangGraph (zero LLM calls)
    - RiveBot no-match falls through to LangGraph
    - Stage-completing tool triggers advance_topic_if_needed
"""

import asyncio
import json
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
import pytest_asyncio
from httpx import Response, TimeoutException

# ── Helpers ───────────────────────────────────────────────────────────────────

def _tool_message(name: str, content: str = "ok"):
    """Create a mock LangChain ToolMessage."""
    from langchain_core.messages import ToolMessage
    tm = ToolMessage(content=content, tool_call_id="test-id")
    tm.name = name
    return tm


def _mock_resp(status: int, body: dict) -> Response:
    return Response(status_code=status, json=body)


# ══════════════════════════════════════════════════════════════════════════════
# Suite 1 — RiveBot client
# ══════════════════════════════════════════════════════════════════════════════

class TestMatchIntent:
    @pytest.mark.asyncio
    async def test_returns_response_on_match(self):
        from app.api.middleware.rivebot_client import match_intent
        mock_resp = _mock_resp(200, {"matched": True, "response": "📚 Here are your talks"})
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = await match_intent("show my talks", "talkprep", "user1")
        assert result == "📚 Here are your talks"

    @pytest.mark.asyncio
    async def test_returns_none_on_no_match(self):
        from app.api.middleware.rivebot_client import match_intent
        mock_resp = _mock_resp(200, {"matched": False, "response": None})
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = await match_intent("tell me a story", "talkprep", "user1")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_timeout(self):
        from app.api.middleware.rivebot_client import match_intent
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=TimeoutException("timeout")
            )
            result = await match_intent("show my talks", "talkprep", "user1")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self):
        from app.api.middleware.rivebot_client import match_intent
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("connection reset")
            )
            result = await match_intent("show my talks", "talkprep", "user1")
        assert result is None


class TestDetectStageTool:
    def test_detects_import_talk(self):
        from app.api.middleware.rivebot_client import detect_stage_completing_tool
        result = {"messages": [_tool_message("import_talk", "Talk imported")]}
        assert detect_stage_completing_tool(result) == "import_talk"

    def test_detects_last_stage_tool_in_list(self):
        from app.api.middleware.rivebot_client import detect_stage_completing_tool
        result = {"messages": [
            _tool_message("list_publications", "pubs"),   # non-stage
            _tool_message("import_talk", "ok"),            # stage → stage_1
            _tool_message("create_revision", "ok"),        # stage → stage_2 (last)
        ]}
        # Should pick the LAST stage-completing tool (reversed walk)
        assert detect_stage_completing_tool(result) == "create_revision"

    def test_returns_none_for_non_stage_tools(self):
        from app.api.middleware.rivebot_client import detect_stage_completing_tool
        result = {"messages": [_tool_message("list_publications"), _tool_message("cost_report")]}
        assert detect_stage_completing_tool(result) is None

    def test_returns_none_for_empty_messages(self):
        from app.api.middleware.rivebot_client import detect_stage_completing_tool
        assert detect_stage_completing_tool({"messages": []}) is None

    @pytest.mark.parametrize("tool,expected_topic", [
        ("import_talk",         "stage_1"),
        ("select_active_talk",  "stage_1"),
        ("create_revision",     "stage_2"),
        ("develop_section",     "stage_3"),
        ("evaluate_talk",       "stage_4"),
        ("rehearsal_cue",       "stage_5"),
        ("export_talk_summary", "stage_6"),
    ])
    def test_all_stage_tools_covered(self, tool, expected_topic):
        from app.api.middleware.rivebot_client import STAGE_TRANSITIONS
        assert STAGE_TRANSITIONS.get(tool) == expected_topic


class TestAdvanceTopic:
    @pytest.mark.asyncio
    async def test_calls_set_topic_for_stage_tool(self):
        from app.api.middleware.rivebot_client import advance_topic_if_needed
        mock_resp = _mock_resp(200, {"ok": True, "topic": "stage_2"})
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            await advance_topic_if_needed("create_revision", "talkprep", "user1")
            MockClient.return_value.__aenter__.return_value.post.assert_called_once()
            call_kwargs = MockClient.return_value.__aenter__.return_value.post.call_args
            assert "set-topic" in call_kwargs[0][0]
            assert call_kwargs[1]["json"]["topic"] == "stage_2"

    @pytest.mark.asyncio
    async def test_noop_for_non_stage_tool(self):
        from app.api.middleware.rivebot_client import advance_topic_if_needed
        with patch("httpx.AsyncClient") as MockClient:
            await advance_topic_if_needed("list_publications", "talkprep", "user1")
            MockClient.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_not_raise_on_error(self):
        from app.api.middleware.rivebot_client import advance_topic_if_needed
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("network error")
            )
            # Should not raise — always fire-and-forget
            await advance_topic_if_needed("evaluate_talk", "talkprep", "user1")


# ══════════════════════════════════════════════════════════════════════════════
# Suite 2 — Tools router
# ══════════════════════════════════════════════════════════════════════════════

class TestToolsRouter:
    @pytest.mark.asyncio
    async def test_get_calls_tool_no_args(self):
        from app.api.adapters.tools import _invoke_tool
        mock_tool = MagicMock()
        mock_tool.ainvoke = AsyncMock(return_value="status: ok")
        with patch("app.api.adapters.tools.ToolRegistry.get", return_value=mock_tool):
            result = await _invoke_tool("talkmaster_status", {}, "user1")
        assert result == "status: ok"
        mock_tool.ainvoke.assert_called_once_with({})

    @pytest.mark.asyncio
    async def test_post_with_kwargs(self):
        from app.api.adapters.tools import _invoke_tool
        mock_tool = MagicMock()
        mock_tool.ainvoke = AsyncMock(return_value="imported")
        mock_tool.args_schema = None
        with patch("app.api.adapters.tools.ToolRegistry.get", return_value=mock_tool):
            result = await _invoke_tool("import_talk", {"pub_code": "s-34"}, "user1")
        mock_tool.ainvoke.assert_called_once_with({"pub_code": "s-34"})

    @pytest.mark.asyncio
    async def test_positional_args_mapped_to_schema(self):
        """_args=[\"s-34\",\"Courage\"] → {pub_code:\"s-34\", topic_name:\"Courage\"}"""
        from app.api.adapters.tools import _invoke_tool
        mock_schema = MagicMock()
        mock_schema.model_fields = {"pub_code": None, "topic_name": None}
        mock_tool = MagicMock()
        mock_tool.ainvoke = AsyncMock(return_value="ok")
        mock_tool.args_schema = mock_schema
        with patch("app.api.adapters.tools.ToolRegistry.get", return_value=mock_tool):
            await _invoke_tool("import_talk", {"_args": ["s-34", "Courage"]}, "user1")
        mock_tool.ainvoke.assert_called_once_with({"pub_code": "s-34", "topic_name": "Courage"})

    @pytest.mark.asyncio
    async def test_last_positional_arg_is_catch_all(self):
        """_args=[\"s-34\",\"Faith\",\"in\",\"times\"] → theme=\"Faith in times\" """
        from app.api.adapters.tools import _invoke_tool
        mock_schema = MagicMock()
        mock_schema.model_fields = {"pub_code": None, "theme": None}
        mock_tool = MagicMock()
        mock_tool.ainvoke = AsyncMock(return_value="ok")
        mock_tool.args_schema = mock_schema
        with patch("app.api.adapters.tools.ToolRegistry.get", return_value=mock_tool):
            await _invoke_tool("import_talk", {"_args": ["s-34", "Faith", "in", "times"]}, "user1")
        mock_tool.ainvoke.assert_called_once_with({"pub_code": "s-34", "theme": "Faith in times"})

    @pytest.mark.asyncio
    async def test_unknown_tool_raises_404(self):
        from fastapi import HTTPException
        from app.api.adapters.tools import _invoke_tool
        with patch("app.api.adapters.tools.ToolRegistry.get", side_effect=ValueError("not found")):
            with pytest.raises(HTTPException) as exc_info:
                await _invoke_tool("nonexistent", {}, "user1")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_tool_exception_raises_500(self):
        from fastapi import HTTPException
        from app.api.adapters.tools import _invoke_tool
        mock_tool = MagicMock()
        mock_tool.ainvoke = AsyncMock(side_effect=RuntimeError("DB down"))
        with patch("app.api.adapters.tools.ToolRegistry.get", return_value=mock_tool):
            with pytest.raises(HTTPException) as exc_info:
                await _invoke_tool("talkmaster_status", {}, "user1")
        assert exc_info.value.status_code == 500


# ══════════════════════════════════════════════════════════════════════════════
# Suite 3 — openai_chat_completions integration
# ══════════════════════════════════════════════════════════════════════════════

class MockFastAPIRequest:
    def __init__(self, body: dict):
        self._body = body

    async def json(self):
        return self._body


def _make_request(message: str, persona: str = "talkprep", user: str = "+509") -> MockFastAPIRequest:
    return MockFastAPIRequest({
        "model": persona,
        "messages": [{"role": "user", "content": message}],
        "user": f"urn:whatsapp:{user}",
    })


class TestOpenAIIntegration:
    @pytest.mark.asyncio
    async def test_rivebot_match_skips_langgraph(self):
        """When RiveBot matches, LangGraph should NOT be called."""
        from app.api.adapters.openai import openai_chat_completions

        with patch("app.api.middleware.rivebot_client.match_intent",
                   new_callable=AsyncMock, return_value="📚 Here are your talks") as mock_match, \
             patch("app.api.adapters.openai.build_graph") as mock_graph:

            req = _make_request("show my talks")
            resp = await openai_chat_completions(req)

        mock_match.assert_called_once()
        mock_graph.assert_not_called()
        body = json.loads(resp.body)
        # RiveBot responses use the "chatcmpl-rs-" prefix
        assert body["id"].startswith("chatcmpl-rs-")
        assert "Here are your talks" in body["choices"][0]["message"]["content"]
        # Zero LLM token usage
        assert body["usage"]["completion_tokens"] == 0

    @pytest.mark.asyncio
    async def test_rivebot_no_match_calls_langgraph(self):
        """When RiveBot doesn't match, LangGraph should be invoked."""
        from app.api.adapters.openai import openai_chat_completions
        from langchain_core.messages import AIMessage

        mock_result = {
            "final_response": "Here is the AI response",
            "messages": [],
            "usage_metadata": {},
        }

        with patch("app.api.middleware.rivebot_client.match_intent",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.api.adapters.openai.build_graph") as mock_graph, \
             patch("app.api.adapters.openai.get_checkpointer") as mock_cp:

            mock_cp.return_value.__aenter__ = AsyncMock(return_value=MagicMock(setup=AsyncMock()))
            mock_cp.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_graph.return_value.ainvoke = AsyncMock(return_value=mock_result)

            req = _make_request("write me a poem")
            resp = await openai_chat_completions(req)

        mock_graph.assert_called_once()
        body = json.loads(resp.body)
        assert "AI response" in body["choices"][0]["message"]["content"]

    @pytest.mark.asyncio
    async def test_stage_tool_triggers_topic_advance(self):
        """After LangGraph runs import_talk, advance_topic_if_needed must be called."""
        from app.api.adapters.openai import openai_chat_completions

        tool_msg = _tool_message("import_talk", "Talk imported successfully")
        mock_result = {
            "final_response": "Your talk has been imported.",
            "messages": [tool_msg],
            "usage_metadata": {},
        }

        with patch("app.api.middleware.rivebot_client.match_intent",
                   new_callable=AsyncMock, return_value=None), \
             patch("app.api.adapters.openai.build_graph") as mock_graph, \
             patch("app.api.adapters.openai.get_checkpointer") as mock_cp, \
             patch("app.api.middleware.rivebot_client.advance_topic_if_needed",
                   new_callable=AsyncMock) as mock_advance:

            mock_cp.return_value.__aenter__ = AsyncMock(return_value=MagicMock(setup=AsyncMock()))
            mock_cp.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_graph.return_value.ainvoke = AsyncMock(return_value=mock_result)

            req = _make_request("import talk s-34 Faith")
            await openai_chat_completions(req)

        mock_advance.assert_called_once()
        args = mock_advance.call_args[0]
        assert args[0] == "import_talk"
        assert args[2] is not None  # user_id passed
