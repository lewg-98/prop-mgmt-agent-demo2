import streamlit as st
import asyncio
from typing import Dict, Any
import pandas as pd
from datetime import datetime
import logging
from app.config import get_settings
from app.database import Database
from app.s3 import S3Handler
from agent.crew import DomiCrew, RequestStatus
from app.validators import RequestValidator
from utils.logger import setup_logger

# Configure logger
logger = setup_logger("app.streamlit", log_file="logs/streamlit.log")

class DomiInterface:
    """Streamlined property maintenance demo interface"""
    
    def __init__(self):
        """Initialize demo components"""
        try:
            self.settings = get_settings()
            self.db = Database(self.settings)
            self.s3 = S3Handler(self.settings)
            self.crew = DomiCrew(self.settings)
            self.validator = RequestValidator()
            self._init_session_state()
            logger.info("Demo interface initialized")
        except Exception as e:
            st.error("⚠️ Setup Error: Please check configuration")
            logger.error(f"Initialization failed: {str(e)}")

    def _init_session_state(self):
        """Initialize essential session state"""
        if 'active_request' not in st.session_state:
            st.session_state.active_request = None
        if 'last_refresh' not in st.session_state:
            st.session_state.last_refresh = datetime.now()

    def run(self):
        """Main demo interface"""
        st.set_page_config(
            page_title="Domi AI Demo",
            page_icon="🏢",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        st.title("🏢 Domi AI Property Maintenance Demo")
        
        # Demo navigation
        tabs = st.tabs(["📊 Dashboard", "📝 New Request", "👷 Contractor View", "💰 Resolution"])
        
        with tabs[0]:
            self.render_dashboard()
        with tabs[1]:
            self.render_maintenance_form()
        with tabs[2]:
            self.render_contractor_portal()
        with tabs[3]:
            self.render_resolution()

    async def load_requests(self) -> pd.DataFrame:
        """Load maintenance requests"""
        try:
            requests = await self.db.fetch_all("maintenance_requests")
            properties = await self.db.fetch_all("properties")
            
            # Handle empty results
            if not requests or not properties:
                return pd.DataFrame()
            
            # Merge property details
            df_requests = pd.DataFrame(requests)
            df_properties = pd.DataFrame(properties)
            
            return pd.merge(
                df_requests,
                df_properties[['id', 'name']],
                left_on='property_id',
                right_on='id',
                suffixes=('', '_property'),
                how='left'  # Keep all requests even if property not found
            )
        except Exception as e:
            logger.error(f"Failed to load requests: {str(e)}")
            return pd.DataFrame()

    def render_dashboard(self):
        """Main dashboard view"""
        col1, col2 = st.columns([4, 1])
        with col2:
            if st.button("🔄 Refresh"):
                st.session_state.last_refresh = datetime.now()
                st.experimental_rerun()
        
        # Load data
        requests = asyncio.run(self.load_requests())
        
        if not requests.empty:
            # Metrics
            self._render_metrics(requests)
            
            # Request list
            st.subheader("Maintenance Requests")
            for _, request in requests.iterrows():
                self._render_request_card(request)
        else:
            st.info("No maintenance requests found")

    def _render_metrics(self, requests: pd.DataFrame):
        """Display key metrics"""
        cols = st.columns(3)
        
        with cols[0]:
            active = len(requests[requests['status'].isin(['new', 'processing'])])
            st.metric("Active Requests", active)
        
        with cols[1]:
            pending = len(requests[requests['status'] == 'scheduled'])
            st.metric("Pending Completion", pending)
        
        with cols[2]:
            avg_time = "2.5h"  # Demo value
            st.metric("Avg Resolution Time", avg_time)

    def _render_request_card(self, request: Dict):
        """Display request card"""
        with st.expander(
            f"{request['name']} - {request['description'][:50]}...",
            expanded=(st.session_state.active_request == request['id'])
        ):
            cols = st.columns(2)
            
            with cols[0]:
                st.write(f"**Description:** {request['description']}")
                st.write(f"**Priority:** {request['priority']}")
                st.write(f"**Status:** {request['status']}")
                st.write(f"**Created:** {request['created_at']}")
            
            with cols[1]:
                self._render_status_badge(request['status'])
                if request.get('completion_details'):
                    with st.expander("📋 Completion Details"):
                        st.write(request['completion_details'])

    def _render_status_badge(self, status: str):
        """Render colored status badge"""
        colors = {
            'new': 'blue',
            'processing': 'orange',
            'scheduled': 'green',
            'completed': 'gray',
            'failed': 'red'
        }
        
        color = colors.get(status.lower(), 'gray')
        
        st.markdown(f"""
            <div style="
                background-color: {colors.get(status, 'gray')};
                padding: 0.5rem;
                border-radius: 0.5rem;
                text-align: center;
                color: white;
                margin: 0.5rem 0;
            ">
                {status.upper()}
            </div>
        """, unsafe_allow_html=True)

    def render_maintenance_form(self):
        """Maintenance request submission form"""
        st.header("Submit New Request")
        
        properties = asyncio.run(self.db.fetch_all("properties"))
        
        if not properties:
            st.error("No properties available")
            return
            
        with st.form("maintenance_request"):
            property_id = st.selectbox(
                "Select Property",
                options=[p['id'] for p in properties],
                format_func=lambda x: next((p['name'] for p in properties if p['id'] == x), 'Unknown')
            )
            
            description = st.text_area(
                "Describe the Issue",
                placeholder="Example: Water leak under kitchen sink..."
            )
            
            priority = st.select_slider(
                "Priority",
                options=["low", "medium", "high", "urgent"],
                value="medium"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                email = st.text_input("Contact Email")
            with col2:
                phone = st.text_input("Contact Phone (optional)")
            
            submitted = st.form_submit_button("Submit Request")
            
            if submitted:
                self._handle_request_submission(
                    property_id, description, priority,
                    email, phone
                )

    def _handle_request_submission(self, property_id, description, priority, email, phone):
        """Process new request submission"""
        try:
            # Validate inputs
            if not description.strip():
                st.error("⚠️ Please provide a description")
                return
                
            if not email or '@' not in email:
                st.error("⚠️ Please provide a valid email")
                return
            
            # Show processing steps
            with st.status("🤖 Processing Request...") as status:
                st.write("Analyzing request details...")
                asyncio.sleep(1)
                
                st.write("Finding available contractor...")
                asyncio.sleep(1)
                
                st.write("Scheduling maintenance...")
                asyncio.sleep(1)
                
                # Create request
                request_data = {
                    "property_id": property_id,
                    "description": description,
                    "priority": priority,
                    "contact_email": email,
                    "contact_phone": phone,
                    "status": RequestStatus.NEW,
                    "created_at": datetime.utcnow()
                }
                
                result = asyncio.run(self.crew.handle_maintenance_request(request_data))
                
                if result and result.get('success'):
                    status.update(label="✅ Request Processed!", state="complete")
                    st.session_state.active_request = result.get('request_id')
                    st.success("Request submitted successfully!")
                    st.balloons()
                else:
                    st.error("Failed to process request")
                
        except Exception as e:
            st.error("⚠️ Something went wrong")
            logger.error(f"Submission failed: {str(e)}")

    def render_contractor_portal(self):
        """Contractor view for job completion"""
        st.header("Contractor Portal")
        
        if not st.session_state.active_request:
            st.info("Please select a request from the dashboard")
            return
        
        request = asyncio.run(self.db.fetch_one(
            "maintenance_requests",
            {"id": st.session_state.active_request}
        ))
        
        if not request:
            st.error("Request not found")
            return
        
        # Job details
        st.subheader("Job Details")
        st.write(f"**Property:** {request.get('property_name', 'Unknown')}")
        st.write(f"**Issue:** {request.get('description', 'No description')}")
        st.write(f"**Priority:** {request.get('priority', 'Not set')}")
        
        # Completion form
        with st.form("completion_form"):
            notes = st.text_area(
                "Work Performed",
                value=self._get_suggested_notes(request),
                height=100
            )
            
            parts = st.text_input(
                "Parts Used",
                value=self._get_suggested_parts(request)
            )
            
            labor_hours = st.number_input(
                "Labor Hours",
                min_value=0.5,
                max_value=8.0,
                value=1.5,
                step=0.5
            )
            
            submitted = st.form_submit_button("Complete Job")
            
            if submitted:
                self._handle_job_completion(request['id'], notes, parts, labor_hours)

    def render_resolution(self):
        """Resolution and payment summary"""
        st.header("Resolution Summary")
        
        if not st.session_state.active_request:
            st.info("No active request selected")
            return
        
        request = asyncio.run(self.db.fetch_one(
            "maintenance_requests",
            {"id": st.session_state.active_request}
        ))
        
        if not request:
            st.error("Request not found")
            return
            
        if not request.get('completion_details'):
            st.warning("Request not yet completed")
            return
        
        # Status banner
        st.success("✅ Maintenance Request Completed")
        
        # Cost breakdown
        st.subheader("Cost Breakdown")
        completion = request['completion_details']
        
        try:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Labor Cost", f"${completion.get('costs', {}).get('labor', 0):.2f}")
            with col2:
                st.metric("Parts Cost", f"${completion.get('costs', {}).get('parts', 0):.2f}")
            
            total = (completion.get('costs', {}).get('labor', 0) + 
                    completion.get('costs', {}).get('parts', 0))
            st.metric("Total Cost", f"${total:.2f}")
            
            # Work details
            st.subheader("Work Details")
            st.write(f"**Work Performed:** {completion.get('work_performed', 'Not specified')}")
            st.write(f"**Parts Used:** {completion.get('parts_used', 'None')}")
        except Exception as e:
            logger.error(f"Error displaying completion details: {str(e)}")
            st.error("Error displaying completion details")

    def _get_suggested_notes(self, request: Dict) -> str:
        """Get AI-suggested completion notes"""
        try:
            return asyncio.run(self.crew.generate_completion_notes(
                request.get('description', ''),
                request.get('issue_type', 'general')
            ))
        except Exception as e:
            logger.error(f"Error generating notes: {str(e)}")
            return ""

    def _get_suggested_parts(self, request: Dict) -> str:
        """Get AI-suggested parts list"""
        try:
            return asyncio.run(self.crew.generate_parts_list(
                request.get('issue_type', 'general')
            ))
        except Exception as e:
            logger.error(f"Error generating parts list: {str(e)}")
            return ""

if __name__ == "__main__":
    app = DomiInterface()
    app.run()