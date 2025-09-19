# MOATAppSpectra

## Overview
MOATAppSpectra is a Flask web application for analysing manufacturing quality
data across Automated Optical Inspection (AOI), Final Inspection (FI), and MOAT
(Production Process Monitoring) reports. The application factory in
[`app/__init__.py`](app/__init__.py) configures Flask, loads environment
variables (including the secret key), and establishes the Supabase client used
throughout the site. Authentication and the main analytical workflows are
registered as blueprints to keep the web UI modular.

## Features
- **Authentication** – [`app/auth/routes.py`](app/auth/routes.py) provides
  username/password login, session management, and logout views to secure the
  dashboards.
- **Report ingestion & saved queries** – The routes in
  [`app/main/routes.py`](app/main/routes.py) accept AOI, FI, and MOAT (PPM)
  uploads, normalise data for preview, and store the records in Supabase. The
  same module also exposes CRUD endpoints for saved AOI, FI, and PPM queries so
  that frequently used filters can be reused across sessions.
- **Analysis dashboards** – `/analysis/ppm`, `/analysis/aoi`, and `/analysis/fi`
  render interactive dashboards, while the AOI/FI daily views combine data into
  operational summaries for recent production activity.
- **Tools & reporting** – Assembly forecasting tools consolidate MOAT and AOI
  data to predict demand, and the generated report endpoints supply Integrated,
  Operator, and AOI Daily report exports for downstream consumers.
- **AOI operator grading API** – [`api_aoi_grading.py`](api_aoi_grading.py)
  exposes a standalone FastAPI service that grades operator reliability and
  provides detailed breakdowns for external systems.

## Configuration
### Environment variables
Set the following variables (a `.env` file is supported via `python-dotenv`):

- `SECRET_KEY` – Flask session secret.
- `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` – Supabase project credentials used
  by the web app to query and persist report data.
- `USER_PASSWORD` and `ADMIN_PASSWORD` – Passwords hashed at startup for the two
  built-in user accounts defined in `app/auth/routes.py`.
- `NON_AOI_PHRASES_FILE` (optional) – Path to a JSON file containing FI rejection
  phrases to ignore when calculating AOI grades. Defaults to
  `config/non_aoi_phrases.json`.

### Non-AOI phrases
The ignore list in [`config/non_aoi_phrases.json`](config/non_aoi_phrases.json)
contains a JSON array of phrases to exclude from AOI grade calculations. Update
this file (or point `NON_AOI_PHRASES_FILE` to an alternative path) and restart
the Flask process to pick up changes.

### MOAT report date offset
Historical MOAT records store `Report Date` one day late. Until those upstream
records are corrected, [`app/db.py`](app/db.py) subtracts one day from each
retrieved MOAT row so that charts and exports display the original run date.
Remove the helper once the source data is fixed.

## Run
1. Install dependencies in your environment:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the Flask application (after configuring the environment variables):
   ```bash
   python run.py
   ```
   The script loads variables from `.env`, builds the app factory, and launches a
   development server on `http://127.0.0.1:5000/`.
3. Launch the AOI operator grading API when needed:
   ```bash
   uvicorn api_aoi_grading:app --reload --port 8080
   ```
   This FastAPI service powers external integrations that require operator grade
   calculations.

### WeasyPrint native dependencies
PDF exports rely on [WeasyPrint](https://weasyprint.org/), which in turn needs
platform-specific libraries for font handling and rendering. Install the native
dependencies before attempting to generate Integrated, Operator, or AOI Daily
report PDFs:

- **macOS (Homebrew):** `brew install cairo gobject-introspection pango`
- **Debian/Ubuntu:** `sudo apt-get install libcairo2 libgdk-pixbuf2.0-0 libpango-1.0-0 gir1.2-pango-1.0`

Once the packages are present, `pip install -r requirements.txt` will install
WeasyPrint and the Flask endpoints will be able to stream PDF responses.
