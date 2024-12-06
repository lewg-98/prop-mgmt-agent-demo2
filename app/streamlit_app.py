import streamlit as st
import asyncio
from typing import Dict, Optional, List, Any
import logging
import pandas as pd
from datetime import datetime
import altair as alt
from app.config import get_settings
from app.database import Database
from app.s3 import S3Handler, S3Error
from agent.crew import DomiCrew, MaintenanceRequest
from app.validators import RequestValidator

# Configure logging
logger = logging.getLogger(__name__)

class DomiInterface:
    """
    Streamlit interface for Domi AI property management system.
    Provides user interface for maintenance request management.
    """
    
    # Constants for UI
    PRIORITY_COLORS = {
        'emergency': 'red',
        'high': 'orange',
        'medium': 'blue',
        'low': 'green'
    }
    
    def __init__(self):
        """Initialize application components and session state"""
        self.settings = get_settings()
        self.db = Database(self.settings)
        self.s3 = S3Handler(self.settings)
        self.crew = DomiCrew(self.settings)
        self.validator = RequestValidator()
        
        # Initialize session state
        self._init_session_state()
        
    def _init_session_state(self):
        """Initialize Streamlit session state variables"""
        defaults = {
            'authenticated': False,
            'user_role': None,
            'selected_property': None,
            'active_requests': [],
            'notifications': [],
            'last_refresh': None
        }
        
        for key, default_value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default_value

    def setup_page(self):
        """Configure page layout and styling"""
        st.set_page_config(
            page_title="Domi AI Property Management",
            page_icon="🏢",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Custom CSS for better UI
        st.markdown("""
            <style>
            .stApp {
                max-width: 1200px;
                margin: 0 auto;
            }
            .status-card {
                padding: 1rem;
                border-radius: 0.5rem;
                margin: 1rem 0;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .priority-badge {
                padding: 0.25rem 0.5rem;
                border-radius: 0.25rem;
                font-weight: bold;
            }
            .metrics-container {
                display: flex;
                justify-content: space-between;
                margin: 1rem 0;
            }
            </style>
        """, unsafe_allow_html=True)

    async def load_properties(self) -> pd.DataFrame:
        """Load and cache property data"""
        try:
            @st.cache_data(ttl=300)  # Cache for 5 minutes
            async def fetch_properties():
                properties = await self.db.fetch_all("properties")
                requests = await self.db.fetch_all("maintenance_requests", {"status": "neq.completed"})
                
                # Convert to DataFrame
                df = pd.DataFrame(properties)
                
                # Count active requests per property
                request_counts = pd.DataFrame(requests).groupby('property_id').size().reset_index(name='active_requests')
                df = df.merge(request_counts, left_on='id', right_on='property_id', how='left')
                df['active_requests'] = df['active_requests'].fillna(0)
                
                return df.sort_values('name')
            
            return await fetch_properties()
            
        except Exception as e:
            logger.error(f"Failed to load properties: {str(e)}")
            raise

    async def load_maintenance_requests(
        self,
        property_id: Optional[str] = None,
        status: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Load filtered maintenance requests"""
        try:
            query = {}
            if property_id:
                query["property_id"] = property_id
            if status:
                query["status"] = f"in.({','.join(status)})"
                
            requests = await self.db.fetch_all("maintenance_requests", query)
            properties = await self.db.fetch_all("properties")
            
            # Convert to DataFrames and merge
            requests_df = pd.DataFrame(requests)
            properties_df = pd.DataFrame(properties)
            
            merged_df = requests_df.merge(
                properties_df[['id', 'name', 'address']],
                left_on='property_id',
                right_on='id',
                suffixes=('', '_property')
            )
            
            merged_df = merged_df.rename(columns={
                'name': 'property_name',
                'address': 'property_address'
            })
            
            return merged_df.sort_values('created_at', ascending=False)
            
        except Exception as e:
            logger.error(f"Failed to load requests: {str(e)}")
            raise

    def render_maintenance_form(self):
        """Render maintenance request submission form with validation"""
        st.header("🔧 Submit Maintenance Request")
        
        with st.form("maintenance_request", clear_on_submit=True):
            # Property selection
            properties = asyncio.run(self.load_properties())
            property_id = st.selectbox(
                "Select Property",
                options=properties['id'].tolist(),
                format_func=lambda x: f"{properties[properties['id'] == x]['name'].iloc[0]} "
                                    f"({properties[properties['id'] == x]['address'].iloc[0]})"
            )
            
            # Request details
            description = st.text_area(
                "Description",
                help="Provide detailed description of the maintenance issue",
                max_chars=1000
            )
            
            priority = st.select_slider(
                "Priority",
                options=list(self.PRIORITY_COLORS.keys()),
                value='medium',
                help="Select the urgency level of this request"
            )
            
            # Contact information
            col1, col2 = st.columns(2)
            with col1:
                email = st.text_input("Contact Email", help="For updates and notifications")
            with col2:
                phone = st.text_input("Contact Phone", help="For urgent communications")
                
            # Photo upload
            photos = st.file_uploader(
                "Upload Photos (Max 5)",
                accept_multiple_files=True,
                type=['png', 'jpg', 'jpeg', 'heic'],
                help="Upload photos of the maintenance issue"
            )
            
            if photos and len(photos) > 5:
                st.warning("Maximum 5 photos allowed")
                photos = photos[:5]
            
            submitted = st.form_submit_button("Submit Request")
            
            if submitted:
                self._handle_request_submission(
                    property_id, description, priority,
                    email, phone, photos
                )

    async def _handle_request_submission(
        self,
        property_id: str,
        description: str,
        priority: str,
        email: str,
        phone: str,
        photos: List[Any]
    ):
        """Handle maintenance request submission with progress tracking"""
        try:
            with st.spinner("Processing your request..."):
                # Validate input
                request_data = {
                    "property_id": property_id,
                    "description": description,
                    "priority": priority,
                    "contact_email": email,
                    "contact_phone": phone
                }
                
                if not self.validator.validate_request(request_data):
                    st.error("Please check your input and try again")
                    return
                
                # Handle photo uploads with progress
                photo_urls = []
                if photos:
                    progress = st.progress(0)
                    for i, photo in enumerate(photos):
                        try:
                            result = await self.s3.upload_file(
                                photo,
                                f"maintenance_photos/{property_id}/{datetime.now().strftime('%Y%m%d')}_{photo.name}"
                            )
                            photo_urls.append(result['url'])
                            progress.progress((i + 1) / len(photos))
                        except S3Error as e:
                            st.warning(f"Failed to upload photo {photo.name}: {str(e)}")
                
                # Create maintenance request
                request = MaintenanceRequest(
                    property_id=property_id,
                    description=description,
                    priority=priority,
                    contact_email=email,
                    contact_phone=phone,
                    photo_urls=photo_urls
                )
                
                # Process with AI crew
                result = await self.crew.handle_maintenance_request(request)
                
                if result['success']:
                    st.success("✅ Maintenance request submitted successfully!")
                    st.balloons()
                else:
                    st.error("❌ Failed to process request")
                    
        except Exception as e:
            logger.error(f"Request submission failed: {str(e)}")
            st.error("Failed to submit request. Please try again later.")

    def render_dashboard(self):
        """Render interactive management dashboard"""
        st.header("📊 Property Management Dashboard")
        
        # Refresh button
        col1, col2 = st.columns([4, 1])
        with col2:
            if st.button("🔄 Refresh Data"):
                st.session_state.last_refresh = datetime.now()
                st.experimental_rerun()
        
        # Summary metrics
        self._render_summary_metrics()
        
        # Filters
        self._render_dashboard_filters()
        
        # Request table
        self._render_request_table()

    def _render_summary_metrics(self):
        """Render key metrics and charts"""
        try:
            metrics = asyncio.run(self._calculate_metrics())
            
            cols = st.columns(4)
            with cols[0]:
                st.metric("Active Requests", metrics['active_requests'])
            with cols[1]:
                st.metric("Avg Response Time", f"{metrics['avg_response_time']:.1f}h")
            with cols[2]:
                st.metric("Completion Rate", f"{metrics['completion_rate']:.1f}%")
            with cols[3]:
                st.metric("Emergency Cases", metrics['emergency_count'])
                
        except Exception as e:
            logger.error(f"Failed to render metrics: {str(e)}")
            st.error("Failed to load metrics")

    async def _calculate_metrics(self) -> Dict[str, Any]:
        """Calculate dashboard metrics"""
        # Implementation depends on your specific metrics needs
        pass

    def run(self):
        """Main application entry point"""
        try:
            self.setup_page()
            
            if not st.session_state.authenticated:
                self._render_login()
                return
            
            # Navigation
            self._render_navigation()
            
        except Exception as e:
            logger.error(f"Application error: {str(e)}")
            st.error("An unexpected error occurred. Please refresh the page.")

if __name__ == "__main__":
    app = DomiInterface()
    app.run()