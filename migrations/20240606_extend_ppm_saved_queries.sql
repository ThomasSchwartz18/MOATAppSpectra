ALTER TABLE ppm_saved_queries
  ADD COLUMN start_date date,
  ADD COLUMN end_date date,
  ADD COLUMN value_source text,
  ADD COLUMN x_column text,
  ADD COLUMN y_agg text,
  ADD COLUMN chart_type text,
  ADD COLUMN line_color text;

UPDATE ppm_saved_queries SET
  start_date = NULLIF(params->>'start_date','')::date,
  end_date = NULLIF(params->>'end_date','')::date,
  value_source = params->>'value_source',
  x_column = params->>'x_column',
  y_agg = params->>'y_agg',
  chart_type = params->'options'->>'type',
  line_color = params->'options'->>'color';
