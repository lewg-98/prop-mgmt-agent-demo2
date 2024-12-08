import sys
import os
import pytest
import asyncio
from pathlib import Path
from typing import AsyncGenerator, Generator, Dict, Any
from unittest.mock import AsyncMock, Mock
import logging
import tempfile

# Add project root to Python path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

# Import application components
from app.config import Settings, get_settings
from app.database import Database
from app.s3 import S3Handler
from agent.crew import DomiCrew

# Configure test logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Provide test configuration settings"""
    return Settings(
        # Use the actual string values instead of Mock objects
        AWS_ACCESS_KEY="test_key",
        AWS_SECRET_KEY="test_secret",
        AWS_REGION="us-east-1",
        S3_BUCKET="test-bucket",
        OPENAI_API_KEY="test_key",
        MODEL_NAME="gpt-4-1106-preview",
        APP_NAME="Domi AI Test",
        LOG_LEVEL="DEBUG",
        ENV="test"
        # Remove the database settings if they're not defined in your Settings model
        # If you need these settings, add them to your Settings model first
    )

@pytest.fixture(scope="session")
async def test_db(test_settings: Settings) -> AsyncGenerator[Database, None]:
    """Provide test database connection"""
    db = Database(test_settings)
    await db.initialize()
    
    # Create test tables
    await db.execute("""
        CREATE TABLE IF NOT EXISTS properties (
            id UUID PRIMARY KEY,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    await db.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_requests (
            id UUID PRIMARY KEY,
            property_id UUID REFERENCES properties(id),
            description TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    yield db
    
    # Cleanup test data
    await db.execute("DROP TABLE IF EXISTS maintenance_requests")
    await db.execute("DROP TABLE IF EXISTS properties")
    await db.close()

@pytest.fixture
def mock_s3() -> Generator[Mock, None, None]:
    """Provide mocked S3 handler"""
    mock = Mock(spec=S3Handler)
    mock.upload_file = AsyncMock(return_value={
        "key": "test_key",
        "url": "https://test-bucket.s3.amazonaws.com/test_key"
    })
    mock.download_file = AsyncMock(return_value=b"test_data")
    mock.generate_presigned_url = AsyncMock(return_value="https://test-url")
    yield mock

@pytest.fixture
def mock_crew() -> Generator[Mock, None, None]:
    """Provide mocked AI crew"""
    mock = Mock(spec=DomiCrew)
    mock.handle_maintenance_request = AsyncMock(return_value={
        "success": True,
        "request_id": "test_id",
        "status": "processed"
    })
    yield mock

@pytest.fixture
def temp_upload_dir() -> Generator[Path, None, None]:
    """Provide temporary directory for file uploads"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)

@pytest.fixture
def sample_request_data() -> Dict[str, Any]:
    """Provide sample maintenance request data"""
    return {
        "property_id": "550e8400-e29b-41d4-a716-446655440000",
        "description": "Test maintenance request",
        "contact_email": "test@example.com",
        "contact_phone": "+1234567890",
        "priority": "medium"
    }

@pytest.fixture
def sample_property_data() -> Dict[str, Any]:
    """Provide sample property data"""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Test Property",
        "address": "123 Test St",
        "units": 10
    }

@pytest.fixture
async def populated_test_db(
    test_db: Database,
    sample_property_data: Dict[str, Any]
) -> AsyncGenerator[Database, None]:
    """Provide database with sample test data"""
    # Insert sample property
    await test_db.execute("""
        INSERT INTO properties (id, name, address)
        VALUES ($1, $2, $3)
    """, sample_property_data["id"], 
        sample_property_data["name"],
        sample_property_data["address"])
    
    yield test_db
    
    # Cleanup
    await test_db.execute("DELETE FROM maintenance_requests")
    await test_db.execute("DELETE FROM properties")

@pytest.fixture
def mock_file_upload() -> Generator[Mock, None, None]:
    """Provide mocked file upload object"""
    mock = Mock()
    mock.name = "test_image.jpg"
    mock.content_type = "image/jpeg"
    mock.read = Mock(return_value=b"test_image_data")
    yield mock

# Helper functions for tests
def async_return(result: Any) -> AsyncMock:
    """Create AsyncMock with specified return value"""
    mock = AsyncMock()
    mock.return_value = result
    return mock

def create_test_file(temp_dir: Path, content: bytes = b"test") -> Path:
    """Create test file with specified content"""
    test_file = temp_dir / "test_file.txt"
    test_file.write_bytes(content)
    return test_file

@pytest.fixture
def mock_factory():
    """Create consistent mock objects"""
    def _create_mock(spec, **kwargs):
        mock = Mock(spec=spec)
        for k, v in kwargs.items():
            setattr(mock, k, v)
        return mock
    return _create_mock

async def seed_test_data(db: Database, data: Dict[str, Any]):
    """Utility for seeding test data"""
    for table, records in data.items():
        for record in records:
            await db.insert(table, record)