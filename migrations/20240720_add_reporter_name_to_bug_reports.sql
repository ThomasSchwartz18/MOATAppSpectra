ALTER TABLE bug_reports
    ADD COLUMN IF NOT EXISTS reporter_name text;
