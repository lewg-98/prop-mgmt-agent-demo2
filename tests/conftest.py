import sys
import os
import pytest
import asyncio
from pathlib import Path
from typing import Dict, Any
import uuid
import logging
from datetime import datetime

# Add project root to path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from app.config import Settings
from app.database import Database
from agent.crew import DomiCrew

# Configure test logging
logging.basicConfig(level=logging.DEBUG)

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def test_settings():
    """Minimal test settings"""
    return Settings(
        APP_NAME="Domi AI Test",
        ENV="test",
        LOG_LEVEL="DEBUG",
        OPENAI_API_KEY="test-key",
        AWS_ACCESS_KEY="test-key",
        AWS_SECRET_KEY="test-secret",
        S3_BUCKET="test-bucket",
        SMTP_USER="test@example.com",
        SMTP_PASSWORD="test-pass"
    )

@pytest.fixture(scope="session")
async def test_db(test_settings):
    """Setup test database"""
    db = Database(test_settings)
    await db.initialize()
    yield db
    await db.close()

@pytest.fixture
def sample_data():
    """Generate consistent test data"""
    property_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    
    return {
        'property': {
            'id': property_id,
            'name': 'Test Property',
            'address': '123 Test St'
        },
        'request': {
            'id': request_id,
            'property_id': property_id,
            'description': 'Water leak in kitchen',
            'priority': 'high',
            'category': 'plumbing',
            'contact_email': 'test@example.com',
            'created_at': datetime.utcnow()
        },
        'contractor': {
            'id': str(uuid.uuid4()),
            'name': 'Test Plumber',
            'skills': ['plumbing'],
            'available': True
        }
    }

@pytest.fixture
async def populated_db(test_db, sample_data):
    """Database with sample data"""
    await test_db.insert('properties', sample_data['property'])
    await test_db.insert('contractors', sample_data['contractor'])
    await test_db.insert('maintenance_requests', sample_data['request'])
    yield test_db
    # No cleanup needed for test database