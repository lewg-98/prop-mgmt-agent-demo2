import pytest
from datetime import datetime
from typing import Dict, Any
from agent.crew import DomiCrew, RequestStatus, MaintenanceRequest
from agent.tools import MaintenanceRequestError

class AgentError(Exception):
    """Base error for agent operations"""
    pass

class ToolError(AgentError):
    """Tool-specific errors"""
    pass

class CrewError(AgentError):
    """Crew orchestration errors"""
    pass

@pytest.mark.asyncio
class TestDomiCrew:
    """Test AI agent maintenance request handling"""
    
    async def test_basic_request_handling(self, test_settings, sample_data):
        """Test standard maintenance request processing"""
        crew = DomiCrew(test_settings)
        request = MaintenanceRequest(
            id=sample_data['request']['id'],
            property_id=sample_data['property']['id'],
            description="Water leak under kitchen sink",
            contact_email="test@example.com",
            status=RequestStatus.NEW,
            created_at=datetime.utcnow()
        )
        
        try:
            result = await crew.handle_maintenance_request(request)
            
            assert result['success'] is True
            assert result['status'] == RequestStatus.SCHEDULED
            assert 'contractor' in result
            assert result['issue_type'] == 'plumbing'
            
        except MaintenanceRequestError as e:
            pytest.fail(f"Tool error: {str(e)}")
        except CrewError as e:
            pytest.fail(f"Crew error: {str(e)}")
        except Exception as e:
            pytest.fail(f"Unexpected error: {str(e)}")

    async def test_tool_errors(self, test_settings, sample_data):
        """Test tool error handling"""
        crew = DomiCrew(test_settings)
        
        # Test classification tool
        with pytest.raises(MaintenanceRequestError, match="classification failed"):
            await crew.tools['issue_classification']._run("")
            
        # Test contractor tool
        with pytest.raises(MaintenanceRequestError, match="contractor not found"):
            await crew.tools['contractor_booking']._run("invalid", "high")
            
        # Test notification tool
        with pytest.raises(MaintenanceRequestError, match="notification failed"):
            await crew.tools['notification']._run("invalid@email", {}, "")

    async def test_agent_recovery(self, test_settings, sample_data):
        """Test agent error recovery"""
        crew = DomiCrew(test_settings)
        request = MaintenanceRequest(
            id=sample_data['request']['id'],
            property_id=sample_data['property']['id'],
            description="Test request",
            contact_email="test@example.com",
            status=RequestStatus.NEW
        )
        
        # Force tool error then retry
        with patch.object(crew.tools['issue_classification'], '_run') as mock_tool:
            mock_tool.side_effect = [
                MaintenanceRequestError("First try failed"),
                {"category": "plumbing", "priority": "medium"}
            ]
            
            result = await crew.handle_maintenance_request(request)
            assert result['success'] is True
            assert mock_tool.call_count == 2

    async def test_crew_status(self, test_settings):
        """Test crew health monitoring"""
        crew = DomiCrew(test_settings)
        
        try:
            status = await crew.get_agent_status()
            assert status['status'] == 'active'
            assert all(tool in status['available_tools'] for tool in [
                'issue_classification',
                'contractor_booking',
                'notification'
            ])
        except Exception as e:
            pytest.fail(f"Status check failed: {e}")