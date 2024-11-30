import pytest
from agent.main import MaintenanceAgent
from agent.tools import MaintenanceTools

@pytest.fixture
def agent():
    tools = MaintenanceTools()
    return MaintenanceAgent(tools)

@pytest.mark.asyncio
async def test_issue_classification(agent):
    """Test issue classification"""
    result = await agent.classify_issue("Water leak under sink")
    assert 'category' in result
    assert 'priority' in result

@pytest.mark.asyncio
async def test_contractor_matching(agent):
    """Test contractor matching"""
    contractors = await agent.find_contractors('plumbing', 2)
    assert isinstance(contractors, list)
    if len(contractors) > 0:
        assert 'id' in contractors[0]