import streamlit as st
import uuid
from datetime import datetime
from typing import Optional
import asyncio
from .config import get_settings
from .database import Database
from .s3 import S3Handler
from .validators import RequestValidator

class MaintenanceApp:
    def __init__(self):
        self.settings = get_settings()
        self.db = Database(self.settings['db_config'])
        self.s3 = S3Handler(self.settings['aws_config'])
        self.validator = RequestValidator()
        
    async def handle_file_upload(self, file) -> Optional[str]:
        if file:
            file_bytes = file.getvalue()
            filename = f"{uuid.uuid4()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            return await self.s3.upload_photo(file_bytes, filename)
        return None
        
    async def submit_request(self, data: dict) -> bool:
        is_valid, message = self.validator.validate_request(data)
        if not is_valid:
            st.error(message)
            return False
            
        try:
            data['id'] = str(uuid.uuid4())
            data['photo_url'] = await self.handle_file_upload(data.get('photo'))
            request_id = self.db.save_request(data)
            
            st.success(f"""
                Request submitted successfully!
                Reference number: {request_id}
                We will contact you shortly.
            """)
            return True
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            return False

def main():
    st.set_page_config(
        page_title="Maintenance Request System",
        layout="wide"
    )
    st.title("Submit Maintenance Request")
    
    app = MaintenanceApp()
    
    with st.form("maintenance_request", clear_on_submit=True):
        properties = app.db.get_properties()
        property_options = {
            f"{p['name']} - {p['address']}": p['id'] 
            for p in properties
        }
        
        selected_property = st.selectbox(
            "Select Property",
            options=list(property_options.keys()),
            index=None,
            placeholder="Choose a property..."
        )
        
        description = st.text_area(
            "Issue Description",
            placeholder="Please describe the maintenance issue...",
            max_chars=1000
        )
        
        col1, col2 = st.columns(2)
        with col1:
            email = st.text_input("Email", placeholder="your.email@example.com")
        with col2:
            phone = st.text_input("Phone", placeholder="+1234567890")
            
        photo = st.file_uploader("Upload Photo (optional)", type=["jpg", "jpeg", "png"])
        
        if st.form_submit_button("Submit Request"):
            request_data = {
                'property_id': property_options.get(selected_property),
                'description': description,
                'email': email,
                'phone': phone,
                'photo': photo
            }
            
            asyncio.run(app.submit_request(request_data))

if __name__ == "__main__":
    main()