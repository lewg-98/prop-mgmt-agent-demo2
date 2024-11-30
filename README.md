# Property Maintenance AI Agent

An AI-powered system for managing property maintenance requests using Crew.ai and Streamlit.

## Features
- Automated maintenance request processing
- Smart issue classification
- Contractor matching
- Automated communications
- Invoice generation

## Setup
1. Clone repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure `.env` and `.streamlit/secrets.toml`
4. Run: `streamlit run app/streamlit_app.py`

## Configuration
Update `.env` and `secrets.toml` with your credentials:
- Database
- AWS S3
- SMTP
- OpenAI

## Usage
1. Access web interface
2. Submit maintenance request
3. System processes automatically
4. Track status updates

## Architecture
- Streamlit frontend
- Crew.ai agents
- PostgreSQL database
- S3 storage
- SMTP email

## License
MIT