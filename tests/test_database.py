import pytest
from app.database import Database, DatabaseConnection
from datetime import datetime

@pytest.fixture
def db():
    return Database()

def test_database_connection():
    """Test database connection"""
    with DatabaseConnection.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()
            assert result[0] == 1

def test_get_properties(db):
    """Test properties retrieval"""
    properties = db.get_properties()
    assert isinstance(properties, list)
    if len(properties) > 0:
        assert 'id' in properties[0]
        assert 'name' in properties[0]

def test_save_request(db):
    """Test request saving"""
    test_data = {
        'property_id': 'test-id',
        'description': 'Test request',
        'email': 'test@example.com',
        'phone': '1234567890'
    }
    request_id = db.save_request(test_data)
    assert request_id is not None