import pytest
import asyncio
from typing import Any, Dict, List
import uuid
from datetime import datetime, timezone
from app.database import Database, DatabaseError

# Test data
SAMPLE_PROPERTY = {
    "id": str(uuid.uuid4()),
    "name": "Test Property", 
    "address": "123 Test St",
    "units": 10,
    "created_at": datetime.now(timezone.utc)
}

SAMPLE_MAINTENANCE_REQUEST = {
    "id": str(uuid.uuid4()),
    "description": "Test maintenance request",
    "status": "new",
    "priority": "medium"
}

@pytest.mark.asyncio
class TestDatabase:
    """Test suite for database operations"""

    @pytest.mark.asyncio
    async def test_connection(self, test_db: Database):
        """Test database connection and health check"""
        try:
            is_healthy = await test_db.health_check()
            assert is_healthy is True
        except Exception as e:
            pytest.fail(f"Database connection failed: {str(e)}")

    async def test_fetch_one(self, test_db: Database):
        """Test fetching single record"""
        # Insert test property
        property_data = {
            "id": SAMPLE_PROPERTY["id"],
            "name": SAMPLE_PROPERTY["name"],
            "address": SAMPLE_PROPERTY["address"],
            "units": SAMPLE_PROPERTY["units"]
        }
        await test_db.insert("properties", property_data)

        # Fetch and verify
        result = await test_db.fetch_one("properties", {"id": SAMPLE_PROPERTY["id"]})
        
        assert result is not None
        assert result["name"] == SAMPLE_PROPERTY["name"]
        assert result["address"] == SAMPLE_PROPERTY["address"]

    async def test_fetch_all(self, test_db: Database):
        """Test fetching multiple records"""
        # Insert multiple properties
        properties = [
            {
                "id": str(uuid.uuid4()),
                "name": f"Property {i}",
                "address": SAMPLE_PROPERTY["address"],
                "units": SAMPLE_PROPERTY["units"]
            }
            for i in range(3)
        ]
        
        for prop in properties:
            await test_db.insert("properties", prop)

        # Fetch and verify
        results = await test_db.fetch_all("properties")
        assert len(results) >= 3
        assert all(isinstance(r, dict) for r in results)

    async def test_insert_and_update(self, test_db: Database):
        """Test insert and update operations"""
        property_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())

        # Create property
        property_data = {
            "id": property_id,
            "name": "Transaction Test Property",
            "address": "456 Test Ave"
        }
        await test_db.insert("properties", property_data)

        # Create maintenance request
        request_data = {
            "id": request_id,
            "property_id": property_id,
            "description": "Test request",
            "status": "new"
        }
        await test_db.insert("maintenance_requests", request_data)

        # Verify both records were created
        property_result = await test_db.fetch_one("properties", {"id": property_id})
        request_result = await test_db.fetch_one("maintenance_requests", {"id": request_id})

        assert property_result is not None
        assert request_result is not None
        assert request_result["property_id"] == property_id

    async def test_batch_insert(self, test_db: Database):
        """Test batch operations"""
        # Prepare batch data
        properties = [
            {
                "id": str(uuid.uuid4()),
                "name": f"Batch Property {i}",
                "address": f"{i} Batch St",
                "units": 5
            }
            for i in range(5)
        ]

        # Insert properties
        for prop in properties:
            await test_db.insert("properties", prop)

        # Verify batch insert
        results = await test_db.fetch_all("properties", {"name": "like.Batch Property%"})
        assert len(results) == 5

    async def test_error_handling(self, test_db: Database):
        """Test database error handling"""
        # Test invalid table
        with pytest.raises(DatabaseError):
            await test_db.fetch_one("nonexistent_table", {"id": "123"})

        # Test duplicate key
        with pytest.raises(DatabaseError):
            await test_db.insert("properties", {
                "id": SAMPLE_PROPERTY["id"],  # Using existing ID should fail
                "name": "Duplicate Property",
                "address": "789 Test St"
            })

    @pytest.mark.parametrize("batch_size", [1, 5, 10])
    async def test_concurrent_operations(self, test_db: Database, batch_size: int):
        """Test concurrent operations"""
        async def run_query(i: int):
            data = {
                "id": str(uuid.uuid4()),
                "name": f"Concurrent Property {i}",
                "address": f"{i} Concurrent St",
                "units": i
            }
            return await test_db.insert("properties", data)

        results = await asyncio.gather(
            *[run_query(i) for i in range(batch_size)]
        )
        assert len(results) == batch_size
        assert all(r is not None for r in results)

    async def test_cleanup(self, test_db: Database):
        """Test database cleanup"""
        # Clean up test data
        await test_db.delete("maintenance_requests", {})
        await test_db.delete("properties", {})

        # Verify cleanup
        properties = await test_db.fetch_all("properties")
        requests = await test_db.fetch_all("maintenance_requests")
        
        assert len(properties) == 0
        assert len(requests) == 0