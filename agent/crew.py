from crewai import Agent, Task, Crew
from typing import Dict, Optional
import logging
import asyncio
from .tools import MaintenanceTools

logger = logging.getLogger(__name__)

class MaintenanceCrew:
    def __init__(self, tools: MaintenanceTools):
        self.tools = tools
        self.setup_logging()
    
    @staticmethod
    def setup_logging():
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def setup_agents(self):
        classifier = Agent(
            role='Issue Classifier',
            goal='Accurately classify maintenance issues',
            backstory='Expert at analyzing maintenance problems',
            tools=[self.tools.classify_issue],
            llm=self.tools.llm
        )
        
        matcher = Agent(
            role='Contractor Matcher',
            goal='Match best contractors to maintenance issues',
            backstory='Expert at contractor selection and scheduling',
            tools=[self.tools.find_contractors],
            llm=self.tools.llm
        )
        
        coordinator = Agent(
            role='Maintenance Coordinator',
            goal='Coordinate maintenance process and communications',
            backstory='Expert at managing maintenance workflows',
            tools=[self.tools.send_notification],
            llm=self.tools.llm
        )
        
        return classifier, matcher, coordinator
    
    async def process_request(self, request_id: str):
        try:
            classifier, matcher, coordinator = self.setup_agents()
            crew = Crew(
                agents=[classifier, matcher, coordinator],
                tasks=self._create_tasks(request_id)
            )
            
            result = await crew.run()
            await self._handle_result(request_id, result)
            
        except Exception as e:
            logger.error(f"Error in crew execution: {e}")
            raise
    
    def _create_tasks(self, request_id: str) -> List[Task]:
        return [
            Task(
                description=f"Classify maintenance request {request_id}",
                agent=self.classifier
            ),
            Task(
                description=f"Match contractors for request {request_id}",
                agent=self.matcher
            ),
            Task(
                description=f"Coordinate maintenance for request {request_id}",
                agent=self.coordinator
            )
        ]
    
    async def _handle_result(self, request_id: str, result: Dict):
        # Update request status and handle notifications
        pass