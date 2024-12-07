from typing import Dict, Any
import asyncio
import logging
from datetime import datetime
import sys
from pathlib import Path
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import Settings, get_settings
from app.database import Database
from app.s3 import S3Handler
from agent.crew import DomiCrew

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

async def check_database() -> bool:
    """Quick database connectivity check"""
    try:
        logger.info("Testing database connection...")
        db = Database(get_settings())
        await db.initialize()
        
        # Basic health check
        is_healthy = await db.health_check()
        if not is_healthy:
            raise Exception("Database health check failed")
            
        # Test simple query
        await db.fetch_one("SELECT 1")
        
        logger.info("✅ Database connection successful")
        await db.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Database check failed: {str(e)}")
        return False

async def check_s3() -> bool:
    """Quick S3 connectivity check"""
    try:
        logger.info("Testing S3 connection...")
        s3 = S3Handler(get_settings())
        
        # Test listing bucket contents
        await s3.list_files(prefix="test", max_items=1)
        
        logger.info("✅ S3 connection successful")
        return True
        
    except Exception as e:
        logger.error(f"❌ S3 check failed: {str(e)}")
        return False

async def check_ai_agent() -> bool:
    """Quick AI agent functionality check"""
    try:
        logger.info("Testing AI agent...")
        crew = DomiCrew(get_settings())
        
        # Check agent status
        status = await crew.get_agent_status()
        if not all(agent["status"] == "active" for agent in status.values()):
            raise Exception("Not all agents are active")
            
        logger.info("✅ AI agent check successful")
        return True
        
    except Exception as e:
        logger.error(f"❌ AI agent check failed: {str(e)}")
        return False

async def check_configuration() -> Dict[str, bool]:
    """Verify critical configuration settings"""
    try:
        logger.info("Checking configuration...")
        settings = get_settings()
        
        checks = {
            "database_url": bool(settings.DATABASE_URL),
            "openai_key": bool(settings.OPENAI_API_KEY.get_secret_value()),
            "aws_access": bool(settings.AWS_ACCESS_KEY.get_secret_value()),
            "aws_secret": bool(settings.AWS_SECRET_KEY.get_secret_value()),
            "s3_bucket": bool(settings.S3_BUCKET)
        }
        
        if all(checks.values()):
            logger.info("✅ Configuration check successful")
        else:
            missing = [k for k, v in checks.items() if not v]
            logger.warning(f"⚠️ Missing configuration: {', '.join(missing)}")
            
        return checks
        
    except Exception as e:
        logger.error(f"❌ Configuration check failed: {str(e)}")
        return {}

async def run_quick_test() -> bool:
    """Run all quick tests and return overall status"""
    start_time = datetime.now()
    logger.info("Starting quick system check...")
    
    # Run all checks
    config_ok = await check_configuration()
    db_ok = await check_database()
    s3_ok = await check_s3()
    ai_ok = await check_ai_agent()
    
    # Calculate duration
    duration = (datetime.now() - start_time).total_seconds()
    
    # Print summary
    logger.info("\nTest Summary:")
    logger.info("-------------")
    logger.info(f"Configuration: {'✅' if all(config_ok.values()) else '❌'}")
    logger.info(f"Database: {'✅' if db_ok else '❌'}")
    logger.info(f"S3 Storage: {'✅' if s3_ok else '❌'}")
    logger.info(f"AI Agent: {'✅' if ai_ok else '❌'}")
    logger.info(f"Duration: {duration:.2f} seconds")
    
    # Overall status
    success = all([all(config_ok.values()), db_ok, s3_ok, ai_ok])
    logger.info(f"\nOverall Status: {'✅ PASSED' if success else '❌ FAILED'}")
    
    return success

def main():
    """Main entry point with proper error handling"""
    try:
        # Ensure event loop is available
        if sys.platform.startswith('win'):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            
        success = asyncio.run(run_quick_test())
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.info("\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()