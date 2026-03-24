-- ============================================================
-- Candidate Tracking — Additional Schema
-- Run this in the Supabase SQL Editor after the main schema
-- ============================================================

-- Candidates table — people you're placing
CREATE TABLE IF NOT EXISTS candidates (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    email           TEXT,
    phone           TEXT,
    linkedin_url    TEXT,
    current_title   TEXT,
    current_company TEXT,
    skills          TEXT[],             -- array of skill tags
    experience_years INT,
    salary_min      INT,               -- in AUD
    salary_max      INT,
    location        TEXT,
    availability    TEXT,               -- "immediate", "2 weeks", "4 weeks", etc.
    notes           TEXT,
    status          TEXT DEFAULT 'active'
                    CHECK (status IN ('active', 'placed', 'unavailable', 'archived')),
    source          TEXT,               -- "referral", "linkedin", "seek", etc.
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Placements — match candidates to companies + track fees
CREATE TABLE IF NOT EXISTS placements (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    candidate_id    UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    contact_id      UUID REFERENCES contacts(id),   -- hiring manager
    role_title      TEXT NOT NULL,
    salary          INT,                             -- agreed salary in AUD
    fee_percent     NUMERIC(5,2) DEFAULT 15.0,       -- recruitment fee %
    fee_amount      NUMERIC(12,2),                    -- calculated fee
    stage           TEXT DEFAULT 'submitted'
                    CHECK (stage IN (
                        'submitted', 'phone_screen', 'interview',
                        'final_round', 'offer', 'accepted', 'started',
                        'withdrawn', 'rejected'
                    )),
    start_date      DATE,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_candidates_owner ON candidates(owner_id);
CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status);
CREATE INDEX IF NOT EXISTS idx_placements_owner ON placements(owner_id);
CREATE INDEX IF NOT EXISTS idx_placements_stage ON placements(stage);
CREATE INDEX IF NOT EXISTS idx_placements_candidate ON placements(candidate_id);
CREATE INDEX IF NOT EXISTS idx_placements_company ON placements(company_id);

-- RLS policies
ALTER TABLE candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE placements ENABLE ROW LEVEL SECURITY;

CREATE POLICY candidates_owner ON candidates
    FOR ALL USING (owner_id = auth.uid());

CREATE POLICY placements_owner ON placements
    FOR ALL USING (owner_id = auth.uid());
