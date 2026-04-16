import pytest
from fastapi.testclient import TestClient
from app.api.app import app

client = TestClient(app)

def test_health_endpoint():
    """Verify health endpoint respects dynamic downstream dependencies."""
    response = client.get("/health")
    assert response.status_code in [200, 503], "Health check failed contract"
    
    data = response.json()
    assert "version" in data
    assert "services" in data
    assert "litellm" in data["services"]
    assert "db" in data["services"]

def test_tool_registry_loaded():
    """Verify the V2 Hermes registry loaded tools without Pydantic reflection errors."""
    from app.hermes.tools import get_hermes_tools
    tools = get_hermes_tools()
    
    assert len(tools) > 20, "Hermes registry failed to load gateway tools"
    
    # Check that a few critical Gateway tools are explicitly mapped
    assert "fetch_dossier" in tools
    assert "start_flow" in tools
    assert "evaluate_talk" in tools

def test_tool_execution_endpoint_get():
    """Verify the FastApi /v1/tools router intercepts GET requests."""
    # 'talkmaster_status' is a tool that requires no arguments
    response = client.get(
        "/v1/tools/talkmaster_status",
        headers={"X-User-Id": "pytest"}
    )
    assert response.status_code == 200
    
    data = response.json()
    assert "result" in data
    # talkmaster_status should return the status of the DB. 
    # Whether it defaults to empty or throws depends on the DB, but "result" must exist securely.

def test_tool_execution_endpoint_post_schema_resolution():
    """Verify RiveBot's positional macros are correctly intercepted into kwargs using Schemas."""
    response = client.post(
        "/v1/tools/fetch_dossier",
        headers={"X-User-Id": "pytest"},
        json={"_args": ["whatsapp:123456789"]}
    )
    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    
def test_unknown_tool_404():
    """Verify execution of phantom tools is aggressively blocked."""
    response = client.get("/v1/tools/phantom_tool_that_does_not_exist")
    assert response.status_code == 404
