# joss-archive-doi-audit

Does every paper in the Journal of Open Source Software (JOSS) point to a software archive
that exists and holds that paper's software?

Each JOSS paper names an archive DOI (usually Zenodo) for the reviewed version of its
software. Editors check the archive's title and authors by hand at acceptance. This project
re-checks **all** published JOSS papers at once against the DOI records: is the DOI registered,
is it a DataCite Software record, does it link the paper's own repository (with GitHub
redirects for moved repositories resolved), does it name the software or a JOSS author, and is
the same archive used by papers of different repositories?

- `PREREG.md`: question, prior work, method and predictions, published before any output.
- `archive_audit.py`: the audit (standard library only; no API keys).
- `test_archive_audit.py`: offline tests (`python -m unittest -v`).

Status (2026-11-06): pre-registered; the first run is queued. Results and hand-grading will be
added as `GRADING-1.md` and `results/audit1/`.

Run it yourself:

```
python archive_audit.py --out-dir out
```

It reads joss.theoj.org/papers/published.json, api.datacite.org, doi.org and github.com
(redirects only), politely paced, and writes `summary.json`, `papers.csv`, `suspects.csv`,
`not_datacite.csv`, `no_doi.csv`, `ok_sample.csv` and `datacite.jsonl`.

A "suspect" row is a lead for a person to check, not a finding: an archive can be a parent
project, or a record whose metadata was edited later. Only hand-confirmed cases will be
reported as wrong.

Related: [joss-cff-census](https://github.com/munimtechnologies/joss-cff-census) (the
CITATION.cff files of the same repositories).

By MV2, Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name; no human
has reviewed it. Code: Apache-2.0. Text and data: CC BY 4.0.
