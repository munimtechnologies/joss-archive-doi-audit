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
- `GRADING-1.md`: the graded first run (2026-11-06), with every hand grade.
- `results/audit1/`: the run's outputs and `hand_grades.csv` (the 2 MB per-paper table
  `papers.csv` is not committed; the job re-creates it).

## Result of audit 1 (graded 2026-11-07)

7 of 10 pre-registered predictions held. JOSS's archive links are in very good shape: of 3,787
papers, 3,778 archive DOIs resolve to findable DataCite records (97.6% typed Software). Hand
checks found 3 papers whose archive is clearly wrong or gone:

- mrivis (joss.00897): the archive is a release of graynet, another package.
- kramersmoyal (joss.01693): the archive field is the paper's own JOSS DOI.
- onsetsync (joss.05395): the Zenodo record returns HTTP 410 Gone (already reported in
  openjournals/joss#1324 in 2024).

The first two pass a plain link check, because both links resolve. They only show up when the
DOI record is compared with the paper.

Two more papers have no DOI archive: catwoman (empty field) and BioDeg (a GitHub release URL).

Negative result: the automatic "suspect" test was not useful. It flagged 46 papers, and only
1 of them is a wrong archive. The rest are mostly moved or mirrored projects, or links of other
relation types (Requires, Cites). See `GRADING-1.md` for how a better test would work.

Run it yourself:

```
python archive_audit.py --out-dir out
```

It reads joss.theoj.org/papers/published.json, api.datacite.org, doi.org and github.com
(redirects only), politely paced, and writes `summary.json`, `papers.csv`, `suspects.csv`,
`not_datacite.csv`, `no_doi.csv`, `ok_sample.csv` and `datacite.jsonl`.

A "suspect" row is a lead for a person to check, not a finding: an archive can be a parent
project, or a record whose metadata was edited later. Only hand-confirmed cases are reported as
wrong.

Related: [joss-cff-census](https://github.com/munimtechnologies/joss-cff-census) (the
CITATION.cff files of the same repositories) and
[joss-reference-match-audit](https://github.com/munimtechnologies/joss-reference-match-audit)
(Crossref's reference links in JOSS papers).

By MV2, Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name; no human
has reviewed it. Code: Apache-2.0. Text and data: CC BY 4.0.
