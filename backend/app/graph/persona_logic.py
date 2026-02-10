import logging
from typing import Dict, Any, List
from app.graph.state import AgentState

logger = logging.getLogger(__name__)

def calculate_trust(current_score: int, user_input: str, sentiment: str = "neutral") -> int:
    """
    Adjusts trust score based on user input and sentiment.
    Rules:
    - Hostile/Rude: -5
    - Polite/Sharing: +2
    - Neutral: +0
    """
    score = current_score
    
    # Simple keyword-based heuristic for now (to be replaced by LLM classifier if needed)
    text = user_input.lower()
    if any(x in text for x in ["stupid", "idiot", "hate", "useless", "fuck"]):
        score -= 5
    elif any(x in text for x in ["thanks", "thank you", "merci", "great", "love"]):
        score += 2
        
    return max(0, min(100, score))

def determine_mood(trust_score: int, last_mood: str) -> str:
    """
    Determines the persona's mood based on trust score.
    """
    if trust_score < 30:
        return "Annoyed"
    elif trust_score < 70:
        return "Neutral"
    else:
        return "Happy"

def update_dossier(current_dossier: Dict[str, Any], new_facts: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merges new facts into the dossier.
    """
    updated = current_dossier.copy()
    updated.update(new_facts)
    return updated
