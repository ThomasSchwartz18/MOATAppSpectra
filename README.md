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
- `WKHTMLTOPDF_CMD` (optional) – Path to the wkhtmltopdf binary used by the PDF
  fallback backend when WeasyPrint cannot run.

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
1. Install dependencies in your environment. `pywebview` powers the desktop UI
   wrapper and `pyinstaller` can be used to build frozen executables for the
   desktop launcher:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the Flask application (after configuring the environment variables):
   ```bash
   python run.py
   ```
   The script loads variables from `.env`, builds the app factory, and launches a
   development server on `http://127.0.0.1:5000/`.
3. Launch the desktop wrapper when you prefer to host the web UI inside a
   native window via PyWebview. This is also the quickest way to smoke test the
   desktop experience because it exercises the embedded server and window stack
   end-to-end:
   ```bash
   python desktop_main.py
   ```
   A PyWebview window titled "MOAT App Spectra" will appear once the embedded
   Flask server finishes booting. Use the same credentials configured via
   `USER_PASSWORD`, `ADMIN_PASSWORD`, or the Supabase user table to sign in.
4. Launch the AOI operator grading API when needed:
   ```bash
   uvicorn api_aoi_grading:app --reload --port 8080
   ```
   This FastAPI service powers external integrations that require operator grade
   calculations.

### WeasyPrint native dependencies
PDF exports rely on [WeasyPrint](https://weasyprint.org/), which in turn needs
platform-specific libraries for font handling and rendering. **PDF generation is
supported only on Linux or Windows hosts. macOS is not supported.** Install the
native dependencies before attempting to generate Integrated, Operator, or AOI
Daily report PDFs:

- **Debian/Ubuntu:** `sudo apt-get install libcairo2 libgdk-pixbuf2.0-0 libpango-1.0-0 gir1.2-pango-1.0`
- **Windows:** Use the WeasyPrint Windows installer or follow the
  [official installation guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows).

Once the packages are present, `pip install -r requirements.txt` will install
WeasyPrint and the Flask endpoints will be able to stream PDF responses.

If your Linux distribution installs WeasyPrint libraries in non-standard
locations, set the `WEASYPRINT_NATIVE_LIB_PATHS` environment variable to include
paths that contain the required `.so` files.

### wkhtmltopdf fallback setup (Windows & Linux)
If WeasyPrint or its native libraries are unavailable, the application can fall
back to [wkhtmltopdf](https://wkhtmltopdf.org/) via `pdfkit`. Install the tool
and point the app to the binary so developers on supported platforms can still
export reports:

- **Windows:** Download and install the official wkhtmltopdf build. Set the
  `WKHTMLTOPDF_CMD` environment variable to the installed executable, for
  example:

  ```powershell
  setx WKHTMLTOPDF_CMD "C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe"
  ```

- **Linux:** Install wkhtmltopdf from your distribution's repositories and
  ensure it is on the `PATH`, or export the command path before starting Flask.

The fallback runner also honours `app.config["WKHTMLTOPDF_CMD"]` if you prefer
to configure the command within the Flask application. With the binary
configured, PDF generation will transparently switch to wkhtmltopdf whenever
WeasyPrint fails to load.

### Desktop smoke test
Follow this checklist to confirm the desktop experience works after changes to
the launcher or its dependencies:

1. Ensure environment variables are set (for example via `.env`) so the Flask
   app can start and at least one set of credentials is available.
2. Install Python dependencies and optional native requirements as described in
   the [Run](#run) section.
3. Start the desktop wrapper:
   ```bash
   python desktop_main.py
   ```
   A PyWebview window titled "MOAT App Spectra" should appear once the embedded
   Flask server finishes booting.
4. Sign in with a known account and navigate a couple of dashboard pages to
   verify routing, Supabase connectivity, and static asset loading work as
   expected.
5. Close the window and confirm the terminal process exits cleanly (the launcher
   shuts down the embedded Flask server on window close).

### Creating a desktop shortcut / application bundle
Running `python desktop_main.py` is sufficient for day-to-day validation, but
you can also package the launcher as a double-clickable application using
PyInstaller once you are ready to hand it to non-technical teammates:

1. Ensure dependencies are installed and run PyInstaller in windowed mode so the
   terminal does not appear alongside the desktop window:
   ```bash
   pyinstaller desktop_main.py --name "MOATAppSpectra" --windowed --add-data "static:static" --add-data "templates:templates"
   ```
   Adjust `--add-data` paths as needed so the bundled executable can locate
   Flask assets.
2. On Windows, copy the generated `.exe` from `dist/MOATAppSpectra/` to a
   convenient location and use **Send to → Desktop (create shortcut)** from the
   context menu.
3. On macOS and Linux, the build produces an executable inside `dist/`. Copy it
   to `~/Applications` (macOS) or `~/bin` (Linux) and create a shortcut/desktop
   entry that points to the binary (for example, create a `.desktop` file on
   GNOME or drag the binary onto the dock on macOS).

Re-run PyInstaller after code or asset changes so the packaged application stays
in sync with the web app.
