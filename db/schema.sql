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