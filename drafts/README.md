# Supplementary evidence preview

Open `evidence.html` in a browser. The main `index.html` contains the design essay, research section, steelman arguments, and links to this preview and Star History. The age-aligned charts remain a separate methodological preview, not a replacement for the main guide's fixed calendar-window snapshot.

## Contents

- `evidence.html` — static, responsive preview with four cumulative age-aligned charts, an equal-age report-share chart, a separately labelled current-star chart, accessible tables, and methodology.
- `evidence-data.json` — timestamped public repository metadata, retained release records, cumulative counts, exact search queries, and an alternative starting-point comparison.
- `evidence.csv` — every point in the four cumulative charts, with project age and corresponding UTC date.

The repository-age charts use the first **285 UTC calendar days** for the equal-age comparison and show Pi's older tail separately. A **277-day sensitivity check** starts at each repository's earliest retained non-prerelease GitHub release instead. Neither date is asserted to be the first public product launch.

The exclusive activity cutoff is **2026-09-05 UTC**. Counts are retrospective, using issue labels and titles at capture, not archived monthly label states. Only current stars were collected; no historical stars or installation counts are inferred. TelePi and Pi Livecraft are not included in Pi's core-repository counts. These are activity measures, not failure rates.

For historical audience growth, the preview links to the [Pi / OpenClaw comparison on Star History](https://www.star-history.com/?repos=earendil-works%2Fpi%2Copenclaw%2Fopenclaw&type=date&legend=top-left). This is a live, third-party calendar-date view, not an age-aligned chart or the source of the fixed snapshot. It is linked rather than automatically embedded.

## Reproduce

From the repository root, render the existing snapshot without network access:

```sh
python3 scripts/evidence.py render drafts/evidence-data.json --output drafts/evidence.html
python3 -B -m unittest discover -s tests -v
```

To collect a new public snapshot, authenticate GitHub CLI yourself, then use a **new cache directory** and your chosen exclusive cutoff. Collection makes read-only API calls and throttles Search requests. The cache can resume an interrupted collection; do not reuse it for a new snapshot.

```sh
python3 scripts/evidence.py collect \
  --cutoff YYYY-MM-DD \
  --output drafts/evidence-data.json \
  --cache /tmp/smallagentstack-evidence-NEW-CAPTURE
```

Then render again. Inspect both the data and the editorial conclusions before proposing any replacement of the published statistics section. New observations can differ as issues are relabelled or records are removed.

The chart generator needs only Python's standard library; the collection step also needs `gh`. No runtime charting libraries or browser network calls are required by the preview itself.
