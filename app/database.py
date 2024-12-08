# database.py

from typing import Optional, Dict, Any, List
import logging
from supabase import Client, create_client
from .config import Settings
from utils.logger import setup_logger

logger = setup_logger("app.database", log_file="logs/database.log")

class DatabaseError(Exception):
    """Simple exception for database errors"""
    pass

class Database:
    """
    Simple database interface for MVP demo.
    Handles basic Supabase operations with error handling.
    """
    
    def __init__(self, settings: Settings):
        """Initialize database with settings"""
        self.settings = settings
        self.supabase = None
        self._initialized = False

    async def initialize(self) -> None:
        """Set up database connection"""
        if not self._initialized:
            try:
                self.supabase = create_client(
                    self.settings.SUPABASE_URL,
                    self.settings.SUPABASE_KEY.get_secret_value()
                )
                self._initialized = True
                logger.info("Database connection initialized")
            except Exception as e:
                logger.error(f"Database initialization failed: {str(e)}")
                raise DatabaseError("Failed to connect to database")

    async def fetch_one(self, table: str, filters: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Fetch a single record"""
        try:
            if not self._initialized:
                await self.initialize()

            query = self.supabase.table(table)
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)

            result = await query.limit(1).execute()
            return result.data[0] if result.data else None

        except Exception as e:
            logger.error(f"Query failed: {str(e)}")
            raise DatabaseError(f"Failed to fetch record from {table}")

    async def fetch_all(self, table: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch multiple records"""
        try:
            if not self._initialized:
                await self.initialize()

            query = self.supabase.table(table)
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)

            result = await query.execute()
            return result.data

        except Exception as e:
            logger.error(f"Query failed: {str(e)}")
            raise DatabaseError(f"Failed to fetch records from {table}")

    async def insert(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new record"""
        try:
            if not self._initialized:
                await self.initialize()

            result = await self.supabase.table(table).insert(data).execute()
            return result.data[0] if result.data else None

        except Exception as e:
            logger.error(f"Insert failed: {str(e)}")
            raise DatabaseError(f"Failed to insert record into {table}")

    async def update(self, table: str, record_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing record"""
        try:
            if not self._initialized:
                await self.initialize()

            result = await self.supabase.table(table).update(data).eq('id', record_id).execute()
            return result.data[0] if result.data else None

        except Exception as e:
            logger.error(f"Update failed: {str(e)}")
            raise DatabaseError(f"Failed to update record in {table}")

    async def health_check(self) -> bool:
        """Simple health check for demo"""
        try:
            if not self._initialized:
                await self.initialize()
            await self.fetch_one("health_check")
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Clean up database connection"""
        self._initialized = False
        logger.info("Database connection closed")