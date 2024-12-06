# app/database.py

from app.config import Settings
from typing import Optional, Dict, Any
from supabase import Client, create_client
import logging

class Database:
    """
    Database interface for Supabase connections.
    Handles all database operations with proper error handling and logging.
    """
    
    def __init__(self, settings: Settings, supabase_client: Optional[Client] = None):
        """
        Initialize database interface.
        
        Args:
            settings: Application configuration
            supabase_client: Optional pre-configured Supabase client
        """
        self.settings = settings
        self.supabase = supabase_client
        self._initialized = False
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        """
        Initialize database connection if not already done.
        Creates Supabase client if one wasn't provided.
        """
        if not self._initialized:
            try:
                if not self.supabase:
                    self.supabase = create_client(
                        self.settings.SUPABASE_URL,
                        self.settings.SUPABASE_KEY
                    )
                self._initialized = True
                self.logger.info("Database connection initialized successfully")
            except Exception as e:
                self.logger.error(f"Failed to initialize database: {str(e)}")
                raise DatabaseError("Database initialization failed")

    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """
        Execute a query and return a single row result.
        
        Args:
            query: SQL query to execute
            *args: Query parameters
            
        Returns:
            Dictionary containing row data if found, None otherwise
            
        Raises:
            DatabaseError: If query execution fails
        """
        try:
            # Execute query through Supabase RPC
            result = await self.supabase.rpc(
                'execute_query',
                {'query_text': query, 'query_params': args}
            ).execute()
            
            # Return first row if exists
            return result.data[0] if result.data else None
            
        except Exception as e:
            self.logger.error(f"Query failed: {str(e)}")
            raise DatabaseError(f"Failed to execute query: {str(e)}")

    async def close(self):
        """
        Clean up database resources.
        For Supabase, this mainly resets the initialization state.
        """
        self._initialized = False
        self.logger.info("Database connection closed")