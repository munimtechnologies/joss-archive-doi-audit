# Pre-registration: JOSS archive-DOI audit 1

MV2, Munim, Inc. (mv2@munimtech.com). Written 2026-11-06, before any audit output existed.
Made with AI agents working in MV2's name; no human has checked it. Code Apache-2.0; text and
data CC BY 4.0.

## Question

Every paper in the Journal of Open Source Software (JOSS) has a `software_archive`: a DOI,
usually on Zenodo, for the reviewed version of the software. The author makes the archive;
the editor sets it with `@editorialbot set <doi> as archive`. JOSS's editing guide
(openjournals/docs, editing.md, "After acceptance") asks the editor to "Check the Zenodo deposit
has the correct metadata (title and author list)": the check is done by hand, one paper at a
time.

Across **every** published JOSS paper:

1. Does the archive DOI exist at all (registered with any DOI agency)?
2. Is it a DataCite *Software* record, and is it a version DOI or a concept DOI?
3. Does the record link the paper's own code repository (GitHub redirects for renamed or moved
   repositories resolved), and does it name the software or any JOSS author?
4. Is the same archive DOI used by papers of different repositories?

## Nearest prior work and the delta

- Pellizzari di San Girolamo & Tosoni, *From Code Archival to Knowledge Graph*,
  arXiv:2609.21667 (2026): harvests 3,596 JOSS records, but only the paper-to-repository link,
  and archives the repositories in Software Heritage. It does not use or check
  `software_archive`.
- Shan, arXiv:2608.17159 (2026): cross-surface consistency of citation metadata for 117
  projects (15 from JOSS), including `.zenodo.json` and DOI records, but per project, not
  JOSS's own archive field, and not at JOSS scale.
- JOSS's editing guide (openjournals/docs): the archive's title and author list are checked by
  hand at acceptance. No journal-wide re-check of published archives was found.
- Single project issues and PRs (for example a JOSS editor asking that a Zenodo deposit's
  title match the paper) fix one archive at a time. None gives a rate.

No JOSS-wide check of archive DOIs against their DOI records was found (searches 2026-11-06:
"JOSS software archive DOI Zenodo mismatch audit", "Journal of Open Source Software archive
DOI broken OR wrong OR mismatch study", "editorialbot set archive wrong DOI").

## Method (fixed by `archive_audit.py` in this commit)

- Paper list: `https://joss.theoj.org/papers/published.json?page=N` until an empty page.
- Archive DOI: the first DOI-shaped string in `software_archive` (URL-decoded, lower case,
  trailing `.,;)]/` removed). Papers without one are listed in `no_doi.csv`.
- Record: `https://api.datacite.org/dois/<doi>`. If DataCite answers 404, `https://doi.org/ra/<doi>`
  (which agency holds it) and `https://doi.org/api/handles/<doi>`. **Unregistered** means the
  handle API answers 404 *and* doi.org/ra says the DOI does not exist (or is invalid).
- Code links: URLs in the record's `relatedIdentifiers` on github.com, bitbucket.org,
  codeberg.org, sr.ht, any host containing "gitlab", or the paper repository's own host,
  reduced to a repository id (GitHub: owner/repo; GitLab: the path before `/-/`).
  `match`: a link equals the paper's repository (or one contains the other). If not, both
  sides' GitHub URLs are fetched once and their final redirect targets compared
  (`match_after_redirect`); otherwise `other_repo`. No links: `no_code_link`.
- Name/author evidence: repository name or the software name (the part of the JOSS title
  before the first colon) inside the record titles; a shared distinctive title word (four or
  more letters, outside a fixed stop list); any JOSS author's last name among the creators.
- Concept DOI: the record has `HasVersion` and no `IsVersionOf` relations.
- Suspect codes: S1 `other_repo`; S2 no matching code link **and** no name, title-word or
  author evidence; S3 unregistered; S4 the archive DOI is also the archive of a paper whose
  repository is different; S5 the archive DOI is a JOSS DOI.
- Pacing: DataCite at most 6 requests/s, doi.org 3/s, github.com 1/s (at most 800 GitHub
  redirect checks; any excess is counted).

## Predictions (blind: two JOSS records, one DataCite record and the doi.org answer for one
made-up DOI were read beforehand; nothing from the audit)

- **G (gate):** at least 3,000 papers; at least 95% have a parseable archive DOI; at least 97%
  of distinct DOI lookups are definitive (DataCite 200, or DataCite 404 with a handle answer
  of 200 or 404). If the gate fails, nothing below is graded.
- **A1:** at least 90% of parsed archive DOIs are Zenodo's (prefix 10.5281).
- **A2:** at least 1 paper has an unregistered archive DOI, and at most 1% of papers do.
- **A3:** at least 85% of DataCite archive records have resourceTypeGeneral `Software`.
- **A4:** between 50% and 90% of DataCite archive records link a code repository.
- **A5:** of records that link a code repository, at least 95% link the paper's own
  (`match` + `match_after_redirect`).
- **A6:** concept DOIs are between 2% and 30% of DataCite archive records.
- **A7:** at least 90% of DataCite archive records name at least one JOSS author.
- **A8:** at least 1 archive DOI is shared by papers of different repositories.
- **A9:** at least 5 papers carry S1, S2 or S4, and on hand-grading at least half of the
  graded ones are **confirmed wrong archives** (the record holds different software, or another
  paper's archive). If there are more than 40, the 40 with the lowest sha256(joss_doi) are
  graded, plus every S4.
- **A10 (instrument):** of the 30 `ok_sample.csv` rows (matched, no suspect code; lowest
  sha256(joss_doi)), at least 29 are confirmed by hand to be an archive of the paper's software.

Not a wrong archive (graded as "deliberate or acceptable"): an archive of a parent project or
monorepo that contains the software; a record whose metadata was later edited but still holds
the software; an archive on another host that holds the reviewed code.

Descriptive only (no prediction): DOI prefixes, which agencies hold the non-DataCite DOIs,
DataCite states, records created after the paper was published, archive DOIs shared by
papers of the same repository, and S5.

## Grading plan

By hand, from `summary.json`, `papers.csv`, `suspects.csv`, `not_datacite.csv`, `ok_sample.csv`
and `datacite.jsonl`: every S3 DOI is re-checked at doi.org; every graded S1/S2/S4 row is read
on DataCite or Zenodo against the JOSS paper page. Results are reported with and without the
largest single prefix or owner if one holds more than 5% of a suspect count.

## What will not be done

Nothing is reported to JOSS or to any author before grading. After grading, confirmed wrong
or unregistered archives may be sent to JOSS's editors as one list through JOSS's own channel,
disclosed as made with AI agents; no messages to individual authors.
