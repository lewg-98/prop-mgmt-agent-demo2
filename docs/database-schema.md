# Database Schema and Relationships

## Core Tables and Relationships

### Properties

-- Core tables for data storage only
CREATE TABLE properties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE contractors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    skills TEXT[], -- Simple array of skills
    available BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE maintenance_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id UUID REFERENCES properties(id),
    description TEXT NOT NULL,
    priority TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL,
    contact_email TEXT NOT NULL,
    contact_phone TEXT,
    assigned_contractor_id UUID REFERENCES contractors(id),
    estimated_cost DECIMAL(10,2),
    scheduled_time TIMESTAMPTZ,
    photo_url TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Basic indices for performance
CREATE INDEX idx_maintenance_status ON maintenance_requests(status);
CREATE INDEX idx_maintenance_property ON maintenance_requests(property_id);
CREATE INDEX idx_contractor_skills ON contractors USING GIN(skills);
## Relationships Overview

### One-to-Many Relationships
- Property → Maintenance Requests
- Contractor → Maintenance Requests
- Maintenance Request → Request History
- Maintenance Request → Notifications

### Key Constraints
- Deleting a property cascades to its maintenance requests
- Deleting a maintenance request cascades to history and notifications
- Deleting a contractor nullifies the assigned_contractor in maintenance requests

### Data Integrity Rules
1. All maintenance requests must be associated with a valid property
2. Contractor assignment is optional but must reference valid contractor
3. Status changes must be tracked in request_history
4. Notifications must be associated with valid maintenance requests

## Performance Considerations
1. Indexed foreign keys for efficient joins
2. Array fields for specialties and photo_urls
3. Timestamp fields for temporal queries
4. Status-based indexes for filtering
```

These documents provide:
1. Clear API endpoint specifications with request/response formats
2. Comprehensive database schema with relationships
3. Data integrity rules and constraints
4. Performance considerations and indexing strategies

Would you like me to expand on any particular section or add more examples? 