# Database Schema and Relationships

## Core Tables and Relationships

### Properties

```sql
CREATE TABLE properties (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    address TEXT NOT NULL,
    units INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_properties_status ON properties(status);
```

### Maintenance Requests

```sql
CREATE TABLE maintenance_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID NOT NULL REFERENCES properties(id),
    description TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'new',
    priority VARCHAR(50) NOT NULL,
    contact_email VARCHAR(255),
    contact_phone VARCHAR(20),
    photo_urls TEXT[],
    estimated_cost DECIMAL(10,2),
    scheduled_time TIMESTAMPTZ,
    assigned_contractor UUID REFERENCES contractors(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT fk_property
        FOREIGN KEY(property_id) 
        REFERENCES properties(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_contractor
        FOREIGN KEY(assigned_contractor)
        REFERENCES contractors(id)
        ON DELETE SET NULL
);

-- Indexes
CREATE INDEX idx_maintenance_property ON maintenance_requests(property_id);
CREATE INDEX idx_maintenance_status ON maintenance_requests(status);
CREATE INDEX idx_maintenance_contractor ON maintenance_requests(assigned_contractor);
```

### Contractors

```sql
CREATE TABLE contractors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20) NOT NULL,
    specialties TEXT[],
    rating DECIMAL(3,2),
    availability_status VARCHAR(50) DEFAULT 'available',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_contractors_specialties ON contractors USING gin(specialties);
CREATE INDEX idx_contractors_availability ON contractors(availability_status);
```

### Request History

```sql
CREATE TABLE request_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID NOT NULL,
    status VARCHAR(50) NOT NULL,
    notes TEXT,
    created_by UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT fk_request
        FOREIGN KEY(request_id)
        REFERENCES maintenance_requests(id)
        ON DELETE CASCADE
);

-- Indexes
CREATE INDEX idx_history_request ON request_history(request_id);
```

### Notifications

```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID NOT NULL,
    recipient_type VARCHAR(50) NOT NULL,
    recipient_id UUID NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT fk_request
        FOREIGN KEY(request_id)
        REFERENCES maintenance_requests(id)
        ON DELETE CASCADE
);

-- Indexes
CREATE INDEX idx_notifications_request ON notifications(request_id);
CREATE INDEX idx_notifications_recipient ON notifications(recipient_id, recipient_type);
```

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