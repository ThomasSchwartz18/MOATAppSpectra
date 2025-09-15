# MOATAppSpectra

## Configuring Non-AOI Phrases

The application excludes certain FI rejection phrases from AOI grade
calculations. These phrases are loaded from a JSON file during application
startup.

1. Edit `config/non_aoi_phrases.json` and update the list of phrases to
   ignore.
2. Restart the application process. A full redeploy is not required because
   the list is read from disk on each startup.
3. (Optional) Set the `NON_AOI_PHRASES_FILE` environment variable to point to
   a different JSON file if you want to maintain the list outside the
   repository.

The file contains a simple JSON array of strings, e.g.:

```json
[
  "Missing Coating"
]
```

Administrators can modify this file at any time to adjust the ignore list
without rebuilding the application.

## MOAT Report Date Offset

Historically, MOAT records store the `Report Date` one day after the actual run
date.  Until those historical values are corrected, the application subtracts
one day from `Report Date` whenever MOAT data is retrieved.  This temporary
offset allows PPM analysis and reports to display the original run date.  Once
the source data is fixed, remove the offset logic in `app/db.py`.
