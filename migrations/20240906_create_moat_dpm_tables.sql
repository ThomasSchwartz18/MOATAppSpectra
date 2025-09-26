CREATE TABLE IF NOT EXISTS moat_dpm (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    "Model Name" text NOT NULL,
    "Total Boards" numeric,
    "Windows per board" numeric,
    "Total Windows" numeric,
    "NG Windows" numeric,
    "DPM" numeric,
    "FalseCall Windows" numeric,
    "FC DPM" numeric,
    "Report Date" date NOT NULL,
    "Line" text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS moat_dpm_report_date_idx ON moat_dpm ("Report Date");
CREATE INDEX IF NOT EXISTS moat_dpm_line_idx ON moat_dpm ("Line");

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
