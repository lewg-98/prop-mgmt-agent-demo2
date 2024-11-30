from langchain_openai import ChatOpenAI
from typing import Dict, List, Optional
from functools import lru_cache
import json
import asyncio
import aiosmtplib
from email.mime.text import MIMEText
from retry import retry
import logging

logger = logging.getLogger(__name__)

class MaintenanceTools:
    def __init__(self, db_pool, email_config: Dict):
        self.db_pool = db_pool
        self.email_config = email_config
        self._setup_llm()
        
    def _setup_llm(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            cache=True,
            max_retries=3
        )
    
    @lru_cache(maxsize=100, ttl=3600)
    def classify_issue(self, description: str) -> Dict:
        prompt = f"""
        Classify this maintenance issue: {description}
        Return JSON with:
        - category: [plumbing|electrical|structural|appliance|other]
        - priority: [urgent|high|medium|low]
        - estimated_hours: int
        """
        try:
            response = self.llm.predict(prompt)
            return json.loads(response)
        except Exception as e:
            logger.error(f"Classification error: {e}")
            raise
    
    @retry(tries=3, delay=1, backoff=2)
    async def find_contractors(self, category: str, hours: int) -> List[Dict]:
        conn = self.db_pool.getconn()
        try:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT id, name, skills, 
                           availability->>'hours_available' as hours_available,
                           rating
                    FROM contractors 
                    WHERE skills ? %s
                    AND availability->>'hours_available' >= %s
                    ORDER BY rating DESC
                    LIMIT 5
                """, (category, hours))
                return await cur.fetchall()
        finally:
            self.db_pool.putconn(conn)
    
    @retry(tries=3, delay=1, backoff=2)
    async def send_notification(self, recipient: str, subject: str, body: str):
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = self.email_config['sender']
        msg['To'] = recipient
        
        async with aiosmtplib.SMTP(
            hostname=self.email_config['host'],
            port=587,
            use_tls=True
        ) as server:
            await server.login(
                self.email_config['user'],
                self.email_config['password']
            )
            await server.send_message(msg)