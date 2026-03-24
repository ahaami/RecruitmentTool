-- ============================================================
-- Recruiter Intelligence Tool — Full Database Schema
-- Run this once in the Supabase SQL Editor
-- ============================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- 1. USERS  (links to Supabase Auth)
-- ============================================================
CREATE TABLE users (
    id              UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email           TEXT NOT NULL,
    display_name    TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- 2. VERTICALS  (recruitment sectors)
-- ============================================================
CREATE TABLE verticals (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,       -- e.g. "IT", "Mining"
    description     TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Seed the IT vertical
INSERT INTO verticals (name, description)
VALUES ('IT', 'Information Technology — software, infrastructure, security, data, AI/ML');

-- ============================================================
-- 3. COMPANIES
-- ============================================================
CREATE TABLE companies (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vertical_id     UUID NOT NULL REFERENCES verticals(id),
    name            TEXT NOT NULL,
    domain          TEXT,                       -- e.g. "canva.com"
    abn             TEXT,                       -- Australian Business Number
    industry        TEXT,                       -- e.g. "SaaS", "Fintech", "Cybersecurity"
    headcount_est   INTEGER,                   -- estimated employee count
    city            TEXT,                       -- e.g. "Sydney", "Melbourne"
    state           TEXT,                       -- e.g. "NSW", "VIC"
    linkedin_url    TEXT,
    website         TEXT,
    source          TEXT NOT NULL,              -- "seek_scraper", "google_news", etc.
    growth_score    INTEGER DEFAULT 0,         -- 0-100, computed by scoring module
    status          TEXT DEFAULT 'new'
        CHECK (status IN ('new','researching','qualified','active','paused','dead')),
    notes           TEXT,
    discovered_at   TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (owner_id, domain)
);

-- ============================================================
-- 4. GROWTH SIGNALS
-- ============================================================
CREATE TABLE growth_signals (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    signal_type     TEXT NOT NULL,
        -- 'job_posting', 'funding', 'news_mention', 'headcount_jump',
        -- 'new_office', 'leadership_hire'
    headline        TEXT NOT NULL,              -- short description
    detail          TEXT,                       -- full text / URL
    source          TEXT NOT NULL,              -- where we found it
    signal_date     DATE,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- 5. CONTACTS
-- ============================================================
CREATE TABLE contacts (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    title           TEXT,                       -- e.g. "Head of Engineering"
    email           TEXT,
    phone           TEXT,
    linkedin_url    TEXT,
    source          TEXT,                       -- "apollo", "hunter", "manual"
    confidence      INTEGER DEFAULT 50,        -- 0-100 data accuracy
    is_decision_maker BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- 6. OUTREACH LOG
-- ============================================================
CREATE TABLE outreach_log (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    contact_id      UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel         TEXT NOT NULL
        CHECK (channel IN ('linkedin_connect','linkedin_message','cold_call','email','other')),
    direction       TEXT DEFAULT 'outbound'
        CHECK (direction IN ('outbound','inbound')),
    outcome         TEXT
        CHECK (outcome IN ('no_answer','voicemail','spoke_gatekeeper',
                           'spoke_dm','meeting_booked','not_interested',
                           'callback_requested','connected','pending')),
    notes           TEXT,
    call_opener_used TEXT,                     -- AI-generated opener
    retry_count     INTEGER DEFAULT 0,        -- how many times retried
    next_retry_at   TIMESTAMPTZ,              -- when to retry (null = no retry)
    contacted_at    TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- 7. WARMUP QUEUE
-- ============================================================
CREATE TABLE warmup_queue (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    contact_id      UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    linkedin_message TEXT,                     -- AI-generated, review before sending
    status          TEXT DEFAULT 'pending'
        CHECK (status IN ('pending','sent','skipped')),
    queued_at       TIMESTAMPTZ DEFAULT now(),
    sent_at         TIMESTAMPTZ
);

-- ============================================================
-- 8. DAILY CALLSHEETS
-- ============================================================
CREATE TABLE daily_callsheets (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    generated_at    TIMESTAMPTZ DEFAULT now(),
    total_leads     INTEGER,
    email_sent      BOOLEAN DEFAULT false,
    callsheet_json  JSONB                      -- snapshot of leads for that day
);

-- ============================================================
-- 9. EXCLUDED COMPANIES  (blocklist)
-- ============================================================
CREATE TABLE excluded_companies (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company_name    TEXT NOT NULL,              -- name pattern to block
    domain          TEXT,                       -- domain to block
    reason          TEXT,                       -- why excluded
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (owner_id, company_name)
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX idx_companies_owner ON companies(owner_id);
CREATE INDEX idx_companies_status ON companies(status);
CREATE INDEX idx_companies_growth_score ON companies(growth_score DESC);
CREATE INDEX idx_companies_vertical ON companies(vertical_id);
CREATE INDEX idx_growth_signals_company ON growth_signals(company_id);
CREATE INDEX idx_contacts_company ON contacts(company_id);
CREATE INDEX idx_contacts_owner ON contacts(owner_id);
CREATE INDEX idx_outreach_log_contacted_at ON outreach_log(contacted_at);
CREATE INDEX idx_outreach_log_contact ON outreach_log(contact_id);
CREATE INDEX idx_outreach_log_owner ON outreach_log(owner_id);
CREATE INDEX idx_outreach_log_next_retry ON outreach_log(next_retry_at)
    WHERE next_retry_at IS NOT NULL;
CREATE INDEX idx_warmup_queue_status ON warmup_queue(status);
CREATE INDEX idx_warmup_queue_owner ON warmup_queue(owner_id);
CREATE INDEX idx_excluded_owner ON excluded_companies(owner_id);

-- ============================================================
-- VIEWS
-- ============================================================

-- Companies contacted in the last N days (cooldown period)
CREATE VIEW v_cooldown_active AS
    SELECT DISTINCT company_id, owner_id
    FROM outreach_log
    WHERE contacted_at > now() - INTERVAL '14 days';

-- Contacts ready to call (qualified + decision-maker + not in cooldown + not excluded)
CREATE VIEW v_call_ready_contacts AS
    SELECT
        c.*,
        co.name         AS company_name,
        co.growth_score,
        co.industry,
        co.city         AS company_city,
        co.state        AS company_state,
        co.domain       AS company_domain
    FROM contacts c
    JOIN companies co ON c.company_id = co.id
    WHERE co.status = 'qualified'
      AND c.is_decision_maker = true
      AND co.id NOT IN (
          SELECT company_id FROM v_cooldown_active
          WHERE owner_id = co.owner_id
      )
      AND co.id NOT IN (
          SELECT comp.id FROM companies comp
          JOIN excluded_companies ex
            ON ex.owner_id = comp.owner_id
           AND (comp.name ILIKE ex.company_name OR comp.domain = ex.domain)
      )
    ORDER BY co.growth_score DESC;

-- Contacts due for retry
CREATE VIEW v_retry_due AS
    SELECT ol.*, c.first_name, c.last_name, c.phone, c.email,
           co.name AS company_name
    FROM outreach_log ol
    JOIN contacts c ON ol.contact_id = c.id
    JOIN companies co ON ol.company_id = co.id
    WHERE ol.next_retry_at IS NOT NULL
      AND ol.next_retry_at <= now()
      AND ol.retry_count < 3;

-- ============================================================
-- ROW-LEVEL SECURITY
-- ============================================================
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE outreach_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE warmup_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_callsheets ENABLE ROW LEVEL SECURITY;
ALTER TABLE excluded_companies ENABLE ROW LEVEL SECURITY;

-- Each user can only see/modify their own data
CREATE POLICY "Users see own companies"
    ON companies FOR ALL USING (owner_id = auth.uid());

CREATE POLICY "Users see own contacts"
    ON contacts FOR ALL USING (owner_id = auth.uid());

CREATE POLICY "Users see own outreach"
    ON outreach_log FOR ALL USING (owner_id = auth.uid());

CREATE POLICY "Users see own warmup queue"
    ON warmup_queue FOR ALL USING (owner_id = auth.uid());

CREATE POLICY "Users see own callsheets"
    ON daily_callsheets FOR ALL USING (owner_id = auth.uid());

CREATE POLICY "Users see own exclusions"
    ON excluded_companies FOR ALL USING (owner_id = auth.uid());

-- Growth signals visible if you own the company
CREATE POLICY "Users see own company signals"
    ON growth_signals FOR ALL
    USING (company_id IN (SELECT id FROM companies WHERE owner_id = auth.uid()));

ALTER TABLE growth_signals ENABLE ROW LEVEL SECURITY;

-- Verticals are shared (everyone can read)
ALTER TABLE verticals ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Everyone can read verticals"
    ON verticals FOR SELECT USING (true);
