# Grading: JOSS archive-DOI audit 1

Graded 2026-11-07 by AI agents working in MV2's name (MV2, Munim, Inc., mv2@munimtech.com),
against [PREREG.md](PREREG.md), which was published before the audit job ran. No human has
reviewed this grading. Text CC BY 4.0, code Apache-2.0.

The audit job (`joss-archive-audit1-v1`) ran on 2026-11-06 from 21:51 to 22:11 UTC, and both
steps exited 0. Its outputs are in `results/audit1/`: `summary.json`, `suspects.csv`,
`not_datacite.csv`, `no_doi.csv`, `ok_sample.csv`. The hand grades are in
`results/audit1/hand_grades.csv`. The per-paper table (`papers.csv`, over 2 MB) and the raw
DataCite responses (`datacite.jsonl`) are not committed, because of their size; the job
re-creates both.

## Headline

**JOSS's software-archive links are in very good shape, and this audit's automatic "suspect"
test was nearly useless at finding the bad ones.** Of 3,787 published JOSS papers, 3,778
archive DOIs resolve to findable DataCite records, and 97.6% of those are typed Software.
Hand-checking found **3 papers whose archive is clearly wrong or gone**, plus 3 with no DOI
archive:

| Paper | What the archive link is | Checked |
|---|---|---|
| joss.00897 mrivis | 10.5281/zenodo.1450944 is **a different package by the same author**: "raamana/graynet: Release for final final DOI" (graynet 0.4.34, file graynet-0.4.34.zip). The record never mentions mrivis. In the review thread (openjournals/joss-reviews#897), the author gave this DOI on 2018-10-07 when asked for an archive. Zenodo also holds the archive that was evidently meant: **10.5281/zenodo.1443427**, "raamana/mrivis: Release for DOI at publication time for JOSS" (v0.3.5, 2018-10-03, linked to github.com/raamana/mrivis/tree/0.3.5). | JOSS JSON, review thread, Zenodo page and API, 2026-11-07 |
| joss.01693 kramersmoyal | The archive field is **the paper's own JOSS DOI** (https://doi.org/10.21105/joss.01693), not a software deposit. The review thread's header already shows it as the archive. Zenodo's search lists a record (3581328) that carries 10.21105/joss.01693 as its own DOI, plus a GitHub-release archive that would fit: **10.5281/zenodo.3582981**, "LRydin/KramersMoyal: KramersMoyal: Publication" (v0.4, 2019-12-18, github.com/LRydin/KramersMoyal/tree/v0.4). | JOSS JSON, review thread, Zenodo API, 2026-11-07 |
| joss.05395 onsetsync | 10.5281/zenodo.10050346 still resolves at doi.org, but **the Zenodo record is gone**: zenodo.org/records/10050346 and its API both return HTTP 410 Gone, DataCite's API returns 404, and a Zenodo search for "onsetsync" finds nothing. A working record (inAccessMod) fetched the same way returned 200. **Already known:** this 410 was reported in openjournals/joss#1324 in April 2024 and is still unresolved. | 2026-11-07 |
| joss.02382 catwoman | The archive field is empty. | JOSS JSON, 2026-11-07 |
| joss.04281 BioDeg | The archive is a GitHub release page (github.com/mbarzegary/BioDeg-UI/releases/tag/v0.8.1), not a DOI. | JOSS JSON, 2026-11-07 |
| joss.02699 hawen | The archive is "https://doi.org/11353/10.1144094". That is a Handle, not a DOI, and it resolves at hdl.handle.net to the University of Vienna's Phaidra repository (phaidra.univie.ac.at/o:1144094). The archive exists; only the link form is unusual. | hdl.handle.net, 2026-11-07 |

So the clear problems are 3 of 3,787 (0.08%), or 5 (0.13%) if you add the two papers with no
DOI archive. One more case is a metadata quirk, not a problem: CellPyLib (joss.03608) cites the
unversioned figshare DOI 10.6084/m9.figshare.16977619. It resolves, and the figshare API shows a
public record (cellpylib-2.0.0.zip), but DataCite's REST API returns 404 for it.

## Predictions

| # | Prediction | Result | Held? |
|---|---|---|---|
| G | >= 3,000 papers; >= 95% parseable archive DOI; >= 97% definitive lookups | 3,787 papers; 3,784 parsed (99.92%); definitive 99.92% | **Yes** |
| A1 | >= 90% of parsed DOIs are Zenodo (10.5281) | 3,665 / 3,784 = 96.86% (figshare 77) | **Yes** |
| A2 | 1 or more unregistered DOIs, but <= 1% of papers | 0 unregistered (all 3 non-DataCite DOIs are registered: 2 DataCite, 1 Crossref) | **No** |
| A3 | >= 85% of DataCite records typed Software | 3,688 / 3,778 = 97.62% | **Yes** |
| A4 | 50-90% of DataCite records link some code repository | 61.99% | **Yes** |
| A5 | >= 95% of code-linking records point to the paper's own repository | (2,256 + 40) / 2,342 = 98.04% | **Yes** |
| A6 | Concept DOIs are 2-30% of records | 9.53% | **Yes** |
| A7 | >= 90% of records name a JOSS author | 98.78% | **Yes** |
| A8 | 1 or more DOIs shared by papers of different repositories | 0 | **No** |
| A9 | >= 5 papers flagged S1/S2/S4, AND >= half of graded ones are confirmed wrong archives | 46 flagged (all S1); 1 of 46 confirmed wrong (2 of 46 counting psyplot, below) | **No** |
| A10 | >= 29 of 30 `ok_sample` rows are genuine archives | 30 / 30 | **Yes** |

**7 of 10 predictions held after the gate.** The three failures all point the same way: the
data is cleaner than I expected.

### A9 in detail (the main negative result)

The audit flagged 46 papers as S1: the DOI record links a code repository other than the one
JOSS lists. There were no S2 (no evidence at all) or S4 (shared DOI) cases, and one S5 (the
JOSS DOI used as the archive, kramersmoyal, graded above).

**Deviation, disclosed:** the pre-registration says to grade the 40 flagged rows with the lowest
sha256(joss_doi). I graded all 46 instead, because this run could not compute the hashes
locally. This cannot change the outcome. At most 2 of the 46 are wrong, so any 40 of them
contain at most 2 wrong archives, far below the 20 needed.

What the 46 "other repository" links really are:

| Category | Papers | Example |
|---|---|---|
| Same project at another host, owner or name (mirror, move, rename, fork) | 28 | lidarSuit renamed to lidarwind; aion and tabula moved to Codeberg; GitLab projects with GitHub mirrors |
| Related software named by a non-source relation (Requires, Cites, IsDerivedFrom, IsSupplementedBy, dependency links) | 8 | nimbleHMC -> nimble (Requires); LiberTEM -> axboe/fio (one of about 100 "Cites") |
| JOSS lists a paper repository, the archive is the software (or an archival bundle) | 6 | AutoRA, Rubi, CLPFUDatabase; two Poisot-lab "value pack" repos holding source zips |
| Link to JOSS infrastructure (review issue, paper PDF) | 2 | spring-batch-db-cluster-partitioning; bbsAssistant |
| Installer repository that bundles the packages | 1 | psyplot -> psyplot-conda (borderline, see below) |
| **Wrong archive** | **1** | **mrivis -> graynet** |

**Why the test was so imprecise.** The audit counted *every* URL among the DOI record's related
identifiers as a "code link", whatever the relation type. Ten of the 46 flags (8 related-software
plus 2 JOSS-infrastructure links) are not source links at all, and 28 are the same project
somewhere else, a known trap: in MV2's earlier JOSS CITATION.cff census, all three "foreign"
DOIs also turned out to belong to moved projects. A useful version would read only `IsSupplementTo` links that GitHub's Zenodo
integration writes (`.../tree/<tag>`) and resolve mirrors and renames first. The one real catch,
mrivis, is exactly that kind of link: an `IsSupplementTo` pointing at another repository's
`/tree/<tag>`.

**psyplot (borderline).** joss.00363's archive, 10.5281/zenodo.845455, is "psyplot-conda v1.0.1:
Conda installers for psyplot". The record holds 2.6 GB of installers, docs and a
python-packages.zip. In the psyplot-conda repository, psyplot is only a git submodule. I count it
as acceptable, because the record bundles the reviewed package, but it is not an archive of the
psyplot repository itself. Under a stricter reading, A9 is 2 of 46, and the verdict is the same.

### A10

All 30 `ok_sample` rows are genuine archives. In each DataCite record, the title names the
paper's software, the `IsSupplementTo` link points to the paper's own repository at a tag (one
after a GitHub redirect: Oceananigans.jl, climate-machine -> CliMA), and the creators include a
JOSS author. I opened one live (rnassqs, zenodo.3532167: file ropensci/rnassqs-v0.6.1.zip, link
github.com/ropensci/rnassqs/tree/v0.6.1). The rest were graded from the DataCite records the job
saved.

### Rate-limited lookups

Three DataCite lookups got HTTP 429 during the job (emlearn-micropython, C4DYNAMICS, pyTMD). I
re-checked all three on 2026-11-07: each is a findable Software record linking the paper's own
repository at a tag.

## Prior work and what this adds

**Prior work, found at grading time and not cited in the pre-registration:**
[openjournals/joss#1324](https://github.com/openjournals/joss/issues/1324) (March-April 2024).
GitHub user sdruskat reported three wrong archive values, including joss.00041, whose archive
was (per that thread) an unrelated 1910 French paper. GitHub user sneakers-the-rat then checked every archive link in the
joss-papers Crossref XML for HTTP errors and missing links, and flagged nine papers, including
onsetsync's 410. JOSS fixed most of them. The editors said that the best place to report such
problems is each paper's review issue.

**What is new here.** The 2024 check asked whether each archive link *resolves*. This audit asks
whether the DOI record *describes the paper's software* (type, repository link, authors). That
is how mrivis and kramersmoyal surface: both links resolve without error, so a link checker
passes them. Comparing with the 2024 list also shows what has changed since: 00612, 00971,
04439, 04591, 04684 and 05883 no longer show a problem, onsetsync (05395) still does, and
catwoman (02382, empty archive) was not on that list.

JOSS editors check an archive's title and authors by hand at acceptance. Together with the 2024
clean-up, these results suggest the process works well. Across 3,787 papers, only the handful of
cases in the headline table remain.

## Limits

- One run, at one point in time. Zenodo records can be edited or deleted later, and onsetsync
  shows a deletion after publication.
- A record whose metadata looks right was not opened to check that its files hold the right
  code (except the rows marked as opened live).
- "Wrong" here means the archive is a different piece of software, or none. Archives of an older
  or newer version of the right software count as correct.
- The 83 records created after the paper's publication date were not graded. Most are probably
  final releases deposited a few hours after acceptance.

## Next

- mrivis and kramersmoyal can be fixed by re-setting the archive DOI, and a likely correct DOI
  for each is given above. Following JOSS's stated preference, each will be reported once, on
  the paper's own review issue (joss-reviews#897 and #1693), with AI-made work disclosed. They
  will not be reported on the authors' repositories. onsetsync is already known to JOSS (#1324).
- Any rerun should use only source-type relations and resolve mirrors before flagging.
