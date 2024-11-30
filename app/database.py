from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
from functools import lru_cache
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_config: Dict):
        self.pool = SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            **db_config
        )
    
    def get_connection(self):
        return self.pool.getconn()
    
    def put_connection(self, conn):
        self.pool.putconn(conn)
    
    @lru_cache(maxsize=100, ttl=300)
    def get_properties(self) -> List[Dict]:
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, name, address 
                    FROM properties 
                    ORDER BY name
                """)
                return cur.fetchall()
        finally:
            self.put_connection(conn)
    
    def save_request(self, data: Dict) -> str:
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO maintenance_requests 
                    (id, property_id, description, contact_email, 
                     contact_phone, photo_url, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'new')
                    RETURNING id
                """, (
                    data['id'],
                    data['property_id'],
                    data['description'],
                    data['email'],
                    data['phone'],
                    data.get('photo_url')
                ))
                conn.commit()
                return cur.fetchone()[0]
        except Exception as e:
            conn.rollback()
            logger.error(f"Error saving request: {e}")
            raise
        finally:
            self.put_connection(conn)