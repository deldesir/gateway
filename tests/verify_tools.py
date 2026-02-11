
import asyncio
import sys
from typing import Dict, Any

# Add app to path
sys.path.append(".")

from app.graph.tools.registry import ToolRegistry
from app.graph.chains import ConversationChain

# Mock LLM to avoid actual API calls, or use the real one if we want integration test.
# For binding check, we can just inspect the chain's model object if possible, 
# or run the build method and check the steps.

def test_registry():
    print("--- Testing Tool Registry ---")
    all_tools = ToolRegistry.get_all_tool_names()
    print(f"Available Tools: {all_tools}")
    
    assert "rapidpro_dossier" in all_tools
    assert "retrieval" in all_tools
    
    selected = ToolRegistry.get_tools(["rapidpro_dossier"])
    assert len(selected) == 1
    assert selected[0].name == "fetch_dossier"
    print("SUCCESS: Registry lookup working.")

def test_chain_binding():
    print("\n--- Testing Chain Binding ---")
    
    # mock persona vars
    persona_vars = {
        "persona_name": "TestBot", 
        "persona_personality": "X", 
        "persona_style": "Y",
        "allowed_tools": ["rapidpro_dossier"] 
    }
    
    chain = ConversationChain(persona_vars).build()
    
    # In LangChain, the bound tools are hidden in the kwargs of the RunnableBinding
    # chain.steps[-1] is likely the model
    
    # Chain is Prompt | Model
    # It's a RunnableSequence
    model_step = chain.last
    
    # Check if kwargs has tools
    # Depending on LC version, it might be kwargs['tools'] or something
    
    if hasattr(model_step, "kwargs") and "tools" in model_step.kwargs:
         tools = model_step.kwargs["tools"]
         print(f"Bound Tools Structure: {tools}")
         
         # Tools are likely OpenAI-format schemas: {'type': 'function', 'function': {'name': ...}}
         names = []
         for t in tools:
             if isinstance(t, dict) and "function" in t:
                 names.append(t["function"]["name"])
             elif hasattr(t, "name"):
                 names.append(t.name)
        
         print(f"Detected Tool Names: {names}")
         
         if "fetch_dossier" in names and "start_flow" not in names:
             print("SUCCESS: Only allowed tools bound.")
         else:
             print(f"FAILURE: Unexpected tool binding. Found: {names}")
    else:
        print("WARNING: Could not inspect model kwargs directly. Model might not have tools bound or structure differs.")
        print(f"Model Type: {type(model_step)}")

if __name__ == "__main__":
    test_registry()
    test_chain_binding()
