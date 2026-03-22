"""
Tool registry — maps string IDs to LangChain tool callables.

All tools are registered here and assigned to personas in prompts.py.
"""

from app.graph.tools.rapidpro import fetch_dossier, start_flow
from app.graph.tools.retrieval import retrieve_context
from app.graph.tools.mocks import check_stock, order_delivery, schedule_viewing
from app.graph.tools.talkprep import (
    get_talkprep_help,
    talkmaster_status,
    select_active_talk,
    list_publications,
    list_topics,
    import_talk,
    create_revision,
    develop_section,
    evaluate_talk,
    get_evaluation_scores,
    rehearsal_cue,
    export_talk_summary,
    cost_report,
    generate_anki_deck,
    push_to_siyuan,
)
from app.graph.tools.upload import upload_jwpub


class ToolRegistry:
    _TOOLS = {
        # Generic
        "fetch_dossier": fetch_dossier,
        "start_flow": start_flow,
        "retrieval": retrieve_context,
        "check_stock": check_stock,
        "order_delivery": order_delivery,
        "schedule_viewing": schedule_viewing,
        # TalkPrep — Stage 0: Status & Help
        "get_talkprep_help": get_talkprep_help,
        "talkmaster_status": talkmaster_status,
        "select_active_talk": select_active_talk,
        # TalkPrep — Stage 1: Import
        "list_publications": list_publications,
        "list_topics": list_topics,
        "import_talk": import_talk,
        # TalkPrep — Stage 2: Revision
        "create_revision": create_revision,
        # TalkPrep — Stage 3: Development
        "develop_section": develop_section,
        # TalkPrep — Stage 4: Evaluation
        "evaluate_talk": evaluate_talk,
        "get_evaluation_scores": get_evaluation_scores,
        # TalkPrep — Stage 5: Rehearsal
        "rehearsal_cue": rehearsal_cue,
        # TalkPrep — Stage 6: Export
        "export_talk_summary": export_talk_summary,
        # Cost & reporting
        "cost_report": cost_report,
        # JWLinker integration
        "generate_anki_deck": generate_anki_deck,
        "push_to_siyuan": push_to_siyuan,
        # File upload
        "upload_jwpub": upload_jwpub,
    }

    @classmethod
    def get(cls, tool_id: str):
        if tool_id not in cls._TOOLS:
            raise ValueError(f"Unknown tool: '{tool_id}'. Available: {list(cls._TOOLS)}")
        return cls._TOOLS[tool_id]

    @classmethod
    def get_many(cls, tool_ids: list[str]) -> list:
        return [cls.get(t) for t in tool_ids]

    @classmethod
    def all_ids(cls) -> list[str]:
        return list(cls._TOOLS.keys())

    @classmethod
    def get_tools(cls, tool_ids: list[str]) -> list:
        """Return tool instances for a list of IDs, silently skipping unknowns.

        Used by ConversationChain to bind persona-specific tools to the LLM.
        Unknown IDs are skipped (logged) rather than raising, so a misconfigured
        persona doesn't break the whole conversation.
        """
        result = []
        for tid in tool_ids:
            if tid in cls._TOOLS:
                result.append(cls._TOOLS[tid])
            else:
                import logging
                logging.getLogger(__name__).warning(
                    f"[ToolRegistry] Unknown tool ID '{tid}' in persona config — skipping."
                )
        return result

    @classmethod
    def all_tools(cls) -> list:
        """Return all registered tool instances (used for the universal ToolNode)."""
        return list(cls._TOOLS.values())
