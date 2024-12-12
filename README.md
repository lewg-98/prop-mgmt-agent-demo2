# Domi AI - Property Maintenance MVP

A streamlined AI-powered system for managing property maintenance requests, built with Crew.ai and Streamlit. This MVP demonstrates automated request processing, smart issue classification, and contractor matching.

## Features

### Core Functionality
- Smart maintenance request processing
- AI-powered issue classification
- Automated contractor matching
- Email notifications
- Cost estimation
- Photo uploads for maintenance issues

### Technical Components
- Streamlit dashboard with tabbed interface
- Single AI agent for request handling
- Supabase (PostgreSQL) for data storage
- S3 photo storage
- Email notifications via SMTP

## Quick Start

1. Clone the repository
```bash
git clone https://github.com/yourusername/domi-ai
cd domi-ai
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Configure environment variables in `.env`:
```env
# App Settings
APP_NAME="Domi AI"
ENV=development
LOG_LEVEL=INFO

# OpenAI
OPENAI_API_KEY=your_key_here
MODEL_NAME=gpt-4-1106-preview

# Database (Supabase)
SUPABASE_URL=your_url
SUPABASE_KEY=your_key
SUPABASE_PROJECT_ID=your_project_id

# AWS S3
AWS_ACCESS_KEY=your_key
AWS_SECRET_KEY=your_secret
AWS_REGION=us-east-1
S3_BUCKET=your_bucket

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email
SMTP_PASSWORD=your_password
```

4. Run the application
```bash
streamlit run app/streamlit_app.py
```

## Architecture

### Frontend (Streamlit)
- Dashboard view for request tracking
- Maintenance request submission form
- Contractor portal
- Resolution summary view

### AI Agent System
Single AI agent handling:
- Issue classification
- Priority assessment
- Cost estimation
- Contractor matching
- Communication coordination

### Database Schema
Simple structure optimized for MVP:
- properties
- contractors
- maintenance_requests

### File Storage
S3 integration for:
- Maintenance request photos
- Basic file management
- Secure access control

## Development

### Local Setup
1. Create and activate virtual environment
```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
```

2. Install dev dependencies
```bash
pip install -r requirements.txt
```

3. Run tests
```bash
pytest
```

### Testing
Quick system check:
```bash
python tests/quick_test.py
```

## Limitations & Future Improvements

Current MVP limitations:
- Single AI agent (vs. multi-agent system)
- Basic cost estimation
- Simple contractor matching
- Limited analytics

Planned improvements:
- Multi-agent orchestration
- ML-based cost prediction
- Advanced contractor matching
- Enhanced analytics dashboard
- Mobile app integration

## License

MIT

## Support

For issues and support:
- Create an issue in the repository
- Contact: support@example.com