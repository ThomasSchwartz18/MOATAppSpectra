CREATE TABLE IF NOT EXISTS app_feature_states (
    slug text PRIMARY KEY,
    status text NOT NULL DEFAULT 'available',
    message text,
    bug_report_id uuid REFERENCES bug_reports(id) ON DELETE SET NULL,
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_app_feature_states_bug_report
    ON app_feature_states(bug_report_id);
