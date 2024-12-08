import pytest
from unittest.mock import AsyncMock, Mock, patch
import uuid
from datetime import datetime
from typing import Dict, Any
import asyncio

from agent.crew import DomiCrew, MaintenanceRequest, RequestStatus
from agent.tools import MaintenanceTools
from app.config import Settings

# Test data
SAMPLE_REQUEST = {
    "id": str(uuid.uuid4()),
    "property_id": str(uuid.uuid4()),
    "description": "Water leak under kitchen sink",
    "contact_email": "tenant@example.com",
    "contact_phone": "+1234567890",
    "status": "new",
    "created_at": datetime.utcnow()
}

@pytest.mark.asyncio
class TestMaintenanceTools:
    """Test suite for maintenance tools"""

    @pytest.fixture
    def tools(self, test_settings: Settings) -> MaintenanceTools:
        """Initialize maintenance tools with test configuration"""
        return MaintenanceTools(test_settings)

    async def test_classify_issue(self, tools: MaintenanceTools):
        """Test maintenance issue classification"""
        # Test plumbing issue
        result = await tools.classify_issue("Water leak under kitchen sink")
        assert result["category"] == "plumbing"
        assert "priority" in result
        assert "estimated_hours" in result
        
        # Test electrical issue
        result = await tools.classify_issue("Power outlet not working in bedroom")
        assert result["category"] == "electrical"
        
        # Test structural issue
        result = await tools.classify_issue("Crack in living room ceiling")
        assert result["category"] == "structural"
        assert result["priority"] == "high"

    async def test_find_contractors(self, tools: MaintenanceTools):
        """Test contractor matching"""
        result = await tools.find_contractors("plumbing", 2)
        assert len(result) > 0
        assert all(c["skills"].get("plumbing") for c in result)
        
        # Test emergency contractor search
        emergency_result = await tools.find_contractors("electrical", 1, emergency=True)
        assert all(c["emergency_available"] for c in emergency_result)

    async def test_send_notification(self, tools: MaintenanceTools):
        """Test notification sending"""
        result = await tools.send_notification(
            "test@example.com",
            "Maintenance Request Update",
            "Your request has been processed"
        )
        assert result is True

@pytest.mark.asyncio
class TestDomiCrew:
    """Test suite for AI crew orchestration"""

    @pytest.fixture
    def crew(self, test_settings: Settings) -> DomiCrew:
        """Initialize AI crew with test configuration"""
        return DomiCrew(test_settings)

    async def test_handle_maintenance_request(self, crew: DomiCrew):
        """Test complete request handling flow"""
        request = MaintenanceRequest(**SAMPLE_REQUEST)
        
        result = await crew.handle_maintenance_request(request)
        
        assert result["success"] is True
        assert "request_id" in result
        assert result["status"] in [s.value for s in RequestStatus]

    async def test_request_analysis(self, crew: DomiCrew):
        """Test maintenance request analysis"""
        request = MaintenanceRequest(
            **{**SAMPLE_REQUEST, "description": "Emergency: Gas smell in kitchen"}
        )
        
        result = await crew.handle_maintenance_request(request)
        
        assert result["priority"] == "emergency"
        assert "safety_notes" in result
        assert result["requires_license"] is True

    async def test_contractor_coordination(self, crew: DomiCrew):
        """Test contractor coordination"""
        request = MaintenanceRequest(**SAMPLE_REQUEST)
        
        result = await crew.handle_maintenance_request(request)
        
        assert "assigned_contractor" in result
        assert "scheduled_time" in result
        assert "estimated_cost" in result

    async def test_error_handling(self, crew: DomiCrew):
        """Test error handling in request processing"""
        # Test invalid property
        with pytest.raises(ValueError):
            await crew.handle_maintenance_request(
                MaintenanceRequest(**{**SAMPLE_REQUEST, "property_id": "invalid"})
            )
        
        # Test missing contact info
        with pytest.raises(ValueError):
            await crew.handle_maintenance_request(
                MaintenanceRequest(**{
                    **SAMPLE_REQUEST,
                    "contact_email": None,
                    "contact_phone": None
                })
            )

    async def test_agent_status(self, crew: DomiCrew):
        """Test agent status monitoring"""
        status = await crew.get_agent_status()
        
        assert "analyzer" in status
        assert "coordinator" in status
        assert all("status" in agent for agent in status.values())

    async def test_ai_timeout(self, crew: DomiCrew):
        """Test AI operation timeout"""
        with pytest.raises(asyncio.TimeoutError):
            async with asyncio.timeout(1.0):
                await crew.handle_maintenance_request(request)

    async def test_rate_limiting(self, crew: DomiCrew):
        """Test rate limiting behavior"""
        requests = [MaintenanceRequest(**SAMPLE_REQUEST) for _ in range(10)]
        results = await asyncio.gather(*[
            crew.handle_maintenance_request(r) for r in requests
        ])
        assert len(results) == 10

class TestIntegration:
    """Integration tests for complete request flow"""

    @pytest.fixture
    async def setup_test_env(self, test_settings: Settings, populated_test_db):
        """Set up test environment with sample data"""
        crew = DomiCrew(test_settings)
        tools = MaintenanceTools(test_settings)
        return crew, tools, populated_test_db

    @pytest.mark.asyncio
    async def test_complete_request_flow(self, setup_test_env):
        """Test complete maintenance request flow"""
        crew, tools, db = setup_test_env
        
        # Create request
        request = MaintenanceRequest(**SAMPLE_REQUEST)
        
        # Process request
        result = await crew.handle_maintenance_request(request)
        assert result["success"] is True
        
        # Verify database state
        db_request = await db.fetch_one(
            "SELECT * FROM maintenance_requests WHERE id = $1",
            request.id
        )
        assert db_request is not None
        assert db_request["status"] != "new"
        
        # Verify contractor assignment
        assert "assigned_contractor" in result
        
        # Verify notifications
        notifications = await db.fetch_all(
            "SELECT * FROM notifications WHERE request_id = $1",
            request.id
        )
        assert len(notifications) > 0

    @pytest.mark.asyncio
    async def test_emergency_request_flow(self, setup_test_env):
        """Test emergency maintenance request flow"""
        crew, tools, db = setup_test_env
        
        # Create emergency request
        emergency_request = MaintenanceRequest(
            **{
                **SAMPLE_REQUEST,
                "description": "Gas leak in apartment",
                "priority": "emergency"
            }
        )
        
        # Process request
        result = await crew.handle_maintenance_request(emergency_request)
        assert result["success"] is True
        assert result["priority"] == "emergency"
        
        # Verify rapid response
        assert "response_time" in result
        assert float(result["response_time"]) < 1.0  # Less than 1 hour
        
        # Verify emergency contractor
        contractor = await db.fetch_one(
            "SELECT * FROM contractors WHERE id = $1",
            result["assigned_contractor"]
        )
        assert contractor["emergency_available"] is True