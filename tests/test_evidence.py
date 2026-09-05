import html
import importlib.util
import json
from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest
from xml.etree import ElementTree

SPEC = importlib.util.spec_from_file_location("evidence", Path(__file__).resolve().parents[1] / "scripts" / "evidence.py")
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)


class EvidenceTests(unittest.TestCase):
    def test_equal_age_endpoint_and_older_tail(self):
        younger = evidence.sample_ages(285, 285)
        older = evidence.sample_ages(392, 285)
        self.assertEqual(younger, [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 285])
        self.assertIn(285, older)
        self.assertEqual(older[-2:], [390, 392])
        self.assertNotIn(300, younger)  # Never invent missing observations.

    def test_issue_windows_are_half_open(self):
        query = evidence.issue_query("owner/repo", date(2025, 11, 24), 30, "label:bug")
        self.assertEqual(query, "repo:owner/repo is:issue label:bug created:2025-11-24..2025-12-23")
        query = evidence.issue_query("owner/repo", date(2025, 11, 24), 285)
        self.assertIn("created:2025-11-24..2026-09-04", query)
        with self.assertRaises(ValueError):
            evidence.issue_query("owner/repo", date(2025, 11, 24), 0)

    def test_incomplete_or_invalid_search_is_rejected(self):
        self.assertEqual(evidence.search_count({"incomplete_results": False, "total_count": 1234}), 1234)
        for payload in ({"incomplete_results": True, "total_count": 12}, {"total_count": 12}, {"incomplete_results": False, "total_count": -1}, {"incomplete_results": False, "total_count": True}):
            with self.assertRaises(ValueError):
                evidence.search_count(payload)

    def test_release_publication_boundaries(self):
        rows = [{"published_at": d} for d in ("2025-11-23T23:59:59Z", "2025-11-24T00:00:00Z", "2025-12-23T23:59:59Z", "2025-12-24T00:00:00Z")]
        self.assertEqual(evidence.release_count(rows, date(2025, 11, 24), 30), 2)
        self.assertEqual(evidence.release_count(rows, date(2025, 11, 24), 0), 0)

    def test_no_bug_reports_is_not_a_zero_percent_rate(self):
        self.assertIsNone(evidence.bug_share({"bugs": 0, "upgrade_bugs": 0}))
        self.assertEqual(evidence.bug_share({"bugs": 20, "upgrade_bugs": 2}), 10)

    def test_linear_scale_covers_counts_and_handles_zero(self):
        for value in (0, 1, 15, 113, 259, 51140):
            self.assertGreaterEqual(evidence.nice_top(value), value)
            self.assertGreater(evidence.nice_top(value), 0)

    def test_chart_does_not_extend_the_younger_series(self):
        data = {"common_age_days": 30, "projects": [
            {"name": "First", "age_days": 30, "points": [{"age_days": 0, "issues": 0, "end_exclusive": "2026-01-01"}, {"age_days": 30, "issues": 20, "end_exclusive": "2026-01-31"}]},
            {"name": "Second", "age_days": 60, "points": [{"age_days": 0, "issues": 0, "end_exclusive": "2025-12-01"}, {"age_days": 30, "issues": 10, "end_exclusive": "2025-12-31"}, {"age_days": 60, "issues": 30, "end_exclusive": "2026-01-30"}]},
        ]}
        chart = ElementTree.fromstring(evidence.chart(data, "issues", "Issues & reports"))
        self.assertEqual(chart.attrib["role"], "img")
        lines = chart.findall("polyline")
        self.assertEqual(len(lines[0].attrib["points"].split()), 2)
        self.assertEqual(len(lines[1].attrib["points"].split()), 3)
        self.assertIn("stroke-dasharray", lines[1].attrib)
        self.assertIsNotNone(chart.find("desc"))

    def test_retained_release_tags_are_snapshot_derived_and_escaped(self):
        snapshot = Path(__file__).resolve().parents[1] / "evidence" / "evidence-data.json"
        data = json.loads(snapshot.read_text())
        pi = next(p for p in data["projects"] if p["repository"] == "earendil-works/pi")
        releases = pi["releases"]
        first = releases[0]
        earlier_date = date.fromisoformat(first["published_at"][:10]) - timedelta(days=1)
        variants = (
            ("earlier release added", [dict(first, tag_name="v0.11.0", published_at=f"{earlier_date}T00:00:00Z"), *releases]),
            ("first release removed", releases[1:]),
            ("tag needs escaping", [dict(first, tag_name='v<preview>&"test"'), *releases[1:]]),
        )
        with tempfile.TemporaryDirectory() as temp:
            modified = Path(temp) / "snapshot.json"
            target = Path(temp) / "evidence.html"
            for label, updated_releases in variants:
                with self.subTest(change=label):
                    pi["releases"] = updated_releases
                    modified.write_text(json.dumps(data))
                    evidence.render(modified, target)
                    methodology = target.read_text().split(
                        "<h2>Check the choice of starting point</h2>", 1,
                    )[1].split("</p>", 1)[0]
                    for project in data["projects"]:
                        expected = f'{html.escape(project["name"])}: <code>{html.escape(project["releases"][0]["tag_name"])}</code>'
                        self.assertIn(expected, methodology)
                    self.assertNotIn("first retained release is already v0.12.0", methodology)

    def test_snapshot_and_render_when_available(self):
        snapshot = Path(__file__).resolve().parents[1] / "evidence" / "evidence-data.json"
        if not snapshot.exists():
            self.skipTest("Public snapshot has not finished collecting")
        data = json.loads(snapshot.read_text())
        self.assertEqual(data["common_age_days"], min(p["age_days"] for p in data["projects"]))
        for project in data["projects"]:
            self.assertEqual(project["points"][-1]["end_exclusive"], data["cutoff_exclusive"])
            self.assertIn(data["common_age_days"], [p["age_days"] for p in project["points"]])
            for point in project["points"]:
                self.assertLessEqual(point["upgrade_bugs"], point["bugs"])
                self.assertLessEqual(point["bugs"], point["issues"])
                self.assertEqual(point["releases"], evidence.release_count(project["releases"], date.fromisoformat(project["metadata"]["created_at"][:10]), point["age_days"]))
                for source in point["sources"].values():
                    self.assertFalse(source["incomplete_results"])
        check = data["release_aligned_check"]
        cutoff = date.fromisoformat(data["cutoff_exclusive"])
        self.assertEqual(check["common_age_days"], min((cutoff - date.fromisoformat(p["start"])).days for p in check["projects"]))
        for point in check["projects"]:
            self.assertEqual((date.fromisoformat(point["end_exclusive"]) - date.fromisoformat(point["start"])).days, check["common_age_days"])
            self.assertLessEqual(point["upgrade_bugs"], point["bugs"])
            self.assertLessEqual(point["bugs"], point["issues"])
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "evidence.html"
            evidence.render(snapshot, target)
            rendered = target.read_text()
            self.assertEqual(rendered.count('<svg '), 6)
            self.assertEqual(rendered.count('<figure>'), 6)
            self.assertIn('name="robots" content="noindex"', rendered)
            self.assertIn('Not', evidence.bars([("A", None), ("B", 0)], "No data", "none", "%", True))
            self.assertTrue(target.with_name("evidence.csv").exists())
            self.assertNotIn("NaN", rendered)
            self.assertEqual(rendered, snapshot.with_name("evidence.html").read_text())
            self.assertEqual(
                target.with_name("evidence.csv").read_bytes(),
                snapshot.with_name("evidence.csv").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
