from pathlib import Path
import sys
import pytest
import asyncio
from typing import AsyncGenerator, Generator
import logging

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
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Provide test configuration settings"""
    return Settings(
        AWS_ACCESS_KEY="test_key",
        AWS_SECRET_KEY="test_secret", 
        AWS_REGION="us-east-1",
        S3_BUCKET="test-bucket",
        OPENAI_API_KEY="test_key",
        MODEL_NAME="gpt-4-1106-preview",
        APP_NAME="Domi AI Test",
        LOG_LEVEL="DEBUG",
        ENV="test"
    )

@pytest.fixture(scope="session")
async def test_db(test_settings: Settings) -> AsyncGenerator[Database, None]:
    """Provide test database connection"""
    db = Database(test_settings)
    await db.initialize()
    try:
        yield db
    finally:
        await db.close()