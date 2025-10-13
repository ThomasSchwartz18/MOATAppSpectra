CREATE TABLE IF NOT EXISTS dpm_moat (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name text NOT NULL,
    total_boards numeric,
    windows_per_board numeric,
    total_windows numeric,
    ng_windows numeric,
    dpm numeric,
    falsecall_windows numeric,
    fc_dpm numeric,
    report_date date NOT NULL,
    line text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS dpm_moat_report_date_idx ON dpm_moat (report_date);
CREATE INDEX IF NOT EXISTS dpm_moat_line_idx ON dpm_moat (line);

CREATE TABLE IF NOT EXISTS dpm_saved_queries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text UNIQUE NOT NULL,
    type text NOT NULL,
    description text,
    start_date date,
    end_date date,
    value_source text,
    x_column text,
    y_agg text,
    chart_type text,
    line_color text,
    params jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS dpm_saved_queries_created_at_idx
    ON dpm_saved_queries (created_at DESC);
