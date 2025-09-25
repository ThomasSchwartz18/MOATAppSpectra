CREATE TABLE IF NOT EXISTS app_versions (
    platform text PRIMARY KEY,
    version text NOT NULL,
    download_url text,
    checksum text,
    release_notes text,
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_app_versions_updated_at
    ON app_versions(updated_at DESC);
