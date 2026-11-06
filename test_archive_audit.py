# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Offline tests for archive_audit.py (standard library only, no network)."""
import unittest

import archive_audit as A

OPENREPGRID_RELATED = [
    {"relationType": "IsSupplementTo", "relatedIdentifierType": "URL",
     "relatedIdentifier": "https://github.com/markheckmann/OpenRepGrid/tree/v0.1.16"},
    {"relationType": "IsVersionOf", "relatedIdentifierType": "DOI",
     "relatedIdentifier": "10.5281/zenodo.592673"},
]
PAPER = {"software_repository": "https://github.com/markheckmann/OpenRepGrid",
         "title": "OpenRepGrid: An R Package for the Analysis of Repertory Grid Data",
         "authors": [{"given_name": "Mark", "last_name": "Heckmann"}]}


class TestParseDoi(unittest.TestCase):
    def test_url(self):
        self.assertEqual(A.parse_doi("https://doi.org/10.5281/zenodo.14262588"),
                         "10.5281/zenodo.14262588")

    def test_prefix_and_trailing_dot(self):
        self.assertEqual(A.parse_doi("doi:10.5281/ZENODO.123."), "10.5281/zenodo.123")

    def test_percent_encoded(self):
        self.assertEqual(A.parse_doi("https://dx.doi.org/10.6084/m9.figshare.123%2Fv1"),
                         "10.6084/m9.figshare.123/v1")

    def test_not_a_doi(self):
        self.assertIsNone(A.parse_doi("https://zenodo.org/records/123"))
        self.assertIsNone(A.parse_doi(""))
        self.assertIsNone(A.parse_doi(None))


class TestRepoId(unittest.TestCase):
    def test_github_tree(self):
        self.assertEqual(A.repo_id("https://github.com/MarkHeckmann/OpenRepGrid/tree/v0.1.16"),
                         "github.com/markheckmann/openrepgrid")

    def test_git_ssh(self):
        self.assertEqual(A.repo_id("git@github.com:owner/Repo.git"), "github.com/owner/repo")

    def test_gitlab_subgroup(self):
        self.assertEqual(A.repo_id("https://gitlab.com/group/sub/proj/-/tree/main"),
                         "gitlab.com/group/sub/proj")

    def test_bitbucket_src(self):
        self.assertEqual(A.repo_id("https://bitbucket.org/a/b/src/master/"), "bitbucket.org/a/b")

    def test_www_and_bare(self):
        self.assertEqual(A.repo_id("www.github.com/a/b/"), "github.com/a/b")

    def test_too_short(self):
        self.assertIsNone(A.repo_id("https://github.com/owner"))
        self.assertIsNone(A.repo_id(None))

    def test_ids_match(self):
        self.assertTrue(A.ids_match("gitlab.com/g/p", "gitlab.com/g/p/sub"))
        self.assertTrue(A.ids_match("github.com/a/b", "github.com/a/b"))
        self.assertFalse(A.ids_match("github.com/a/b", "github.com/a/bc"))
        self.assertFalse(A.ids_match("", "github.com/a/b"))


class TestText(unittest.TestCase):
    def test_squash(self):
        self.assertEqual(A.squash("Müller-Lüdenscheidt"), "mullerludenscheidt")

    def test_software_name(self):
        self.assertEqual(A.software_name("OpenRepGrid: An R Package"), "OpenRepGrid")
        self.assertEqual(A.software_name("No colon here"), "")

    def test_tokens(self):
        self.assertEqual(A.tokens(PAPER["title"]), {"openrepgrid", "repertory", "grid"})

    def test_author_hit(self):
        self.assertTrue(A.author_hit([{"last_name": "Heckmann"}],
                                     [{"name": "Heckmann, Mark", "familyName": "Heckmann"}]))
        self.assertFalse(A.author_hit([{"last_name": "Li"}], [{"name": "Lindqvist, Anna"}]))
        self.assertTrue(A.author_hit([{"last_name": "Smith"}], [{"name": "Jane Smith"}]))
        self.assertFalse(A.author_hit([], [{"name": "Jane Smith"}]))


class TestRecord(unittest.TestCase):
    def test_code_links(self):
        self.assertEqual(A.code_links(OPENREPGRID_RELATED), ["github.com/markheckmann/openrepgrid"])

    def test_code_links_skip_doi_url_and_use_extra_host(self):
        rel = [{"relatedIdentifier": "https://doi.org/10.21105/joss.01234"},
               {"relatedIdentifier": "https://git.example.org/a/b"}]
        self.assertEqual(A.code_links(rel), [])
        self.assertEqual(A.code_links(rel, extra_host="git.example.org"),
                         ["git.example.org/a/b"])

    def test_is_concept(self):
        self.assertTrue(A.is_concept([{"relationType": "HasVersion"}]))
        self.assertFalse(A.is_concept([{"relationType": "HasVersion"},
                                       {"relationType": "IsVersionOf"}]))
        self.assertFalse(A.is_concept(OPENREPGRID_RELATED))
        self.assertFalse(A.is_concept([]))

    def test_link_status(self):
        self.assertEqual(A.link_status("github.com/a/b", []), "no_code_link")
        self.assertEqual(A.link_status("github.com/a/b", ["github.com/a/b"]), "match")
        moved = {"github.com/old/b": "github.com/a/b"}
        self.assertEqual(A.link_status("github.com/a/b", ["github.com/old/b"],
                                       resolver=lambda r: moved.get(r)),
                         "match_after_redirect")
        self.assertEqual(A.link_status("github.com/a/b", ["github.com/c/d"],
                                       resolver=lambda r: None), "other_repo")

    def test_parse_ra(self):
        self.assertEqual(A.parse_ra(b'[{"DOI":"x","status":"DOI does not exist"}]'),
                         ("", "does_not_exist"))
        self.assertEqual(A.parse_ra(b'[{"DOI":"x","RA":"DataCite"}]'), ("DataCite", "registered"))
        self.assertEqual(A.parse_ra(b"nope"), ("", "unparsed"))

    def test_summarize_datacite(self):
        js = {"data": {"id": "10.5281/zenodo.14262588", "attributes": {
            "titles": [{"title": "OpenRepGrid: An R Package for the Analysis of Repertory Grid Data"},
                       {"title": "markheckmann/OpenRepGrid: OpenRepGrid 0.1.16",
                        "titleType": "AlternativeTitle"}],
            "creators": [{"name": "Heckmann, Mark", "familyName": "Heckmann", "givenName": "Mark"}],
            "version": "v0.1.16", "types": {"resourceTypeGeneral": "Software"},
            "url": "https://zenodo.org/doi/10.5281/zenodo.14262588", "state": "findable",
            "created": "2024-12-03T14:57:51.000Z", "relatedIdentifiers": OPENREPGRID_RELATED}}}
        s = A.summarize_datacite(js)
        self.assertEqual(len(s["titles"]), 2)
        self.assertEqual(s["rtg"], "Software")
        self.assertEqual(s["version"], "v0.1.16")
        self.assertEqual(len(s["related"]), 2)
        self.assertEqual(s["creators"][0]["familyName"], "Heckmann")
        self.assertEqual(A.summarize_datacite({})["titles"], [])

    def test_iso_after(self):
        self.assertTrue(A.iso_after("2024-12-20T00:00:00Z", "2024-12-19T11:36:55.972Z"))
        self.assertFalse(A.iso_after("2024-12-03T14:57:51.000Z", "2024-12-19T11:36:55.972Z"))
        self.assertIsNone(A.iso_after(None, "2024-12-19T11:36:55.972Z"))

    def test_record_checks_positive(self):
        rec = {"titles": ["markheckmann/OpenRepGrid: OpenRepGrid 0.1.16"],
               "creators": [{"name": "Heckmann, Mark", "familyName": "Heckmann"}]}
        self.assertEqual(A.record_checks(PAPER, rec),
                         {"name_hit": True, "sw_name_hit": True, "token_hit": True,
                          "author_hit": True})

    def test_record_checks_negative(self):
        rec = {"titles": ["Totally different thing"], "creators": [{"name": "Doe, Jane"}]}
        self.assertEqual(A.record_checks(PAPER, rec),
                         {"name_hit": False, "sw_name_hit": False, "token_hit": False,
                          "author_hit": False})


if __name__ == "__main__":
    unittest.main()
