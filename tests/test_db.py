import pytest
from typing import Dict
from datetime import datetime
import uuid
from app.database import Database, DatabaseError

@pytest.mark.asyncio
class TestDatabase:
    """Test core database operations"""
    
    async def test_connection(self, test_db: Database):
        """Verify database connectivity"""
        is_healthy = await test_db.health_check()
        assert is_healthy is True

    async def test_maintenance_workflow(self, populated_db: Database, sample_data: Dict):
        """Test complete maintenance request flow"""
        # Create new request
        request_data = {
            'id': str(uuid.uuid4()),
            'property_id': sample_data['property']['id'],
            'description': 'Test leak',
            'priority': 'high',
            'category': 'plumbing',
            'status': 'new',
            'contact_email': 'test@example.com'
        }
        
        # Insert request
        created = await populated_db.insert('maintenance_requests', request_data)
        assert created['id'] == request_data['id']
        
        # Update status
        await populated_db.update(
            'maintenance_requests',
            created['id'],
            {'status': 'processing'}
        )
        
        # Verify update
        updated = await populated_db.fetch_one(
            'maintenance_requests',
            {'id': created['id']}
        )
        assert updated['status'] == 'processing'

    async def test_contractor_assignment(self, populated_db: Database, sample_data: Dict):
        """Test contractor assignment"""
        request = await populated_db.fetch_one(
            'maintenance_requests',
            {'id': sample_data['request']['id']}
        )
        
        # Find available contractor
        contractor = await populated_db.fetch_one(
            'contractors',
            {'skills': ['plumbing'], 'available': True}
        )
        
        # Assign contractor
        await populated_db.update(
            'maintenance_requests',
            request['id'],
            {
                'assigned_contractor_id': contractor['id'],
                'status': 'scheduled'
            }
        )
        
        # Verify assignment
        updated = await populated_db.fetch_one(
            'maintenance_requests',
            {'id': request['id']}
        )
        assert updated['assigned_contractor_id'] == contractor['id']
        assert updated['status'] == 'scheduled'

    async def test_error_handling(self, populated_db: Database):
        """Test basic error cases"""
        with pytest.raises(DatabaseError):
            await populated_db.fetch_one('invalid_table', {})
            
        with pytest.raises(DatabaseError):
            await populated_db.insert('maintenance_requests', {})