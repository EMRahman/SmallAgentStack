from html.parser import HTMLParser
from pathlib import Path
import re
import unittest
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.ids = []
        self.references = []
        self.links = []
        self.resources = []
        self.cases = []
        self.current_case = None
        self.sections = {}
        self.section_stack = []
        self.navigation = []
        self.current_nav = None
        self.feed(source)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "section":
            section = {"attributes": attrs, "text": [], "links": [], "details": []}
            self.section_stack.append(section)
            if "id" in attrs:
                self.sections[attrs["id"]] = section
        if tag == "nav":
            self.current_nav = {"attributes": attrs, "links": []}
            self.navigation.append(self.current_nav)
        if tag == "details":
            for section in self.section_stack:
                section["details"].append(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        for name in ("aria-labelledby", "aria-controls", "data-copy-target"):
            self.references.extend(attrs.get(name, "").split())
        if tag == "a":
            self.links.append(attrs)
            for section in self.section_stack:
                section["links"].append(attrs)
            if self.current_nav is not None:
                self.current_nav["links"].append(attrs)
        if tag in ("iframe", "img", "script") and "src" in attrs:
            self.resources.append(attrs["src"])
        if tag == "details" and "steelman-card" in attrs.get("class", "").split():
            self.current_case = {"summary": 0, "items": 0}
            self.cases.append(self.current_case)
        if self.current_case is not None:
            if tag == "summary":
                self.current_case["summary"] += 1
            if tag == "li":
                self.current_case["items"] += 1

    def handle_endtag(self, tag):
        if tag == "details":
            self.current_case = None
        if tag == "section":
            self.section_stack.pop()
        if tag == "nav":
            self.current_nav = None

    def handle_data(self, data):
        for section in self.section_stack:
            section["text"].append(data)


class SiteTests(unittest.TestCase):
    def test_ids_references_and_local_links(self):
        for relative in ("index.html", "evidence/evidence.html"):
            path = ROOT / relative
            page = Page(path.read_text())
            with self.subTest(page=relative):
                self.assertEqual(len(page.ids), len(set(page.ids)), "Duplicate element IDs")
                for ref in page.references:
                    self.assertIn(ref, page.ids)
                for attrs in page.links:
                    url = urlsplit(attrs.get("href", ""))
                    if not url.scheme and not url.netloc:
                        if url.path:
                            self.assertTrue((path.parent / unquote(url.path)).exists(), attrs["href"])
                        elif url.fragment:
                            self.assertIn(unquote(url.fragment), page.ids)
                    if attrs.get("target") == "_blank":
                        self.assertIn("noreferrer", attrs.get("rel", "").split())

    def test_both_steelman_cases_are_native_expandable_sections(self):
        page = Page((ROOT / "index.html").read_text())
        self.assertEqual(page.cases, [{"summary": 1, "items": 5}, {"summary": 1, "items": 5}])
        self.assertIn("steelman", page.ids)
        self.assertIn("steelman-heading", page.references)

    def test_star_history_is_a_calendar_date_reference_not_an_embed(self):
        for relative in ("index.html", "evidence/evidence.html"):
            page = Page((ROOT / relative).read_text())
            matches = [a for a in page.links if urlsplit(a.get("href", "")).netloc == "www.star-history.com"]
            self.assertEqual(len(matches), 1)
            query = parse_qs(urlsplit(matches[0]["href"]).query)
            self.assertEqual(query["repos"], ["earendil-works/pi,openclaw/openclaw"])
            self.assertEqual(query["type"], ["date"])
            self.assertEqual(query["legend"], ["top-left"])
            self.assertFalse(any("star-history.com" in url for url in page.resources))

    def test_central_passage_and_architectural_qualification(self):
        source = (ROOT / "index.html").read_text()
        self.assertIn("Pi won for me when building my own agency became easier", source)
        self.assertIn("less compulsory coordination per personal change", source)
        self.assertIn("The same coding-cost advantage is available to both.", source)
        self.assertIn("https://github.com/openclaw/openclaw/blob/main/VISION.md", source)
        self.assertIn("https://docs.openclaw.ai/start/why-openclaw", source)

    def test_research_is_navigable_and_progressively_disclosed(self):
        source = (ROOT / "index.html").read_text()
        page = Page(source)
        research = page.sections["research"]
        self.assertEqual(research["attributes"]["aria-labelledby"], "research-heading")
        self.assertLess(source.index('id="evidence"'), source.index('id="research"'))
        self.assertLess(source.index('id="research"'), source.index('id="stack"'))
        self.assertEqual(len(page.navigation), 2)
        for nav in page.navigation:
            self.assertEqual(sum(a.get("href") == "#research" for a in nav["links"]), 1)
        self.assertEqual(
            [detail["id"] for detail in research["details"]],
            ["research-governance", "research-precedents", "research-test"],
        )
        self.assertTrue(all("open" not in detail for detail in research["details"]))

    def test_research_distinguishes_personal_reliability_and_security(self):
        page = Page((ROOT / "index.html").read_text())
        text = " ".join(" ".join(page.sections["research"]["text"]).split())
        for qualification in (
            "In my use, Pi updates have kept my workflows working.",
            "The base Pi setup has no periodic AI heartbeat.",
            "I want to know what starts a run.",
            "My extensions do not need to be products for everyone.",
            "Pi can still make mistakes",
            "A prompt is not an enforced permission boundary",
            "scoped credentials",
            "not a controlled reliability or security comparison",
        ):
            with self.subTest(qualification=qualification):
                self.assertIn(qualification, text)

    def test_history_cites_the_shared_roots_without_freezing_the_architecture(self):
        page = Page((ROOT / "index.html").read_text())
        research = page.sections["research"]
        links = {a["href"] for a in research["links"]}
        self.assertIn("research-history", page.ids)
        self.assertIn("research-history-heading", page.references)
        self.assertTrue({
            "https://lucumr.pocoo.org/2026/1/31/pi/",
            "https://mariozechner.at/posts/2026-04-08-ive-sold-out/",
            "https://www.raspberrypi.org/about/",
        }.issubset(links))
        self.assertTrue(any(re.fullmatch(
            r"https://github\.com/openclaw/openclaw/blob/[0-9a-f]{40}/docs/concepts/agent\.md",
            link,
        ) for link in links))
        text = " ".join(" ".join(research["text"]).split())
        for qualification in (
            "The relationship was publicly documented",
            "A history, not a permanent dependency map.",
            "not an accusation of deliberate concealment",
            "my analogy, not a quotation from its founders",
            "open-source components and bespoke setups",
            "MIT-licensed core and plans for commercial additions",
        ):
            self.assertIn(qualification, text)

    def test_recovery_uses_primary_sources_and_an_unmeasured_comparison(self):
        page = Page((ROOT / "index.html").read_text())
        research = page.sections["research"]
        links = {a["href"] for a in research["links"]}
        self.assertTrue({
            "https://openclaw.ai/blog/openclaw-rough-week",
            "https://openclaw.ai/blog/openclaw-2-accidentally",
            "https://openclaw.ai/blog/introducing-openclaw-foundation/",
            "https://openclaw.ai/blog/extended-stable-releases-and-maturity-scorecards",
            "https://docs.openclaw.ai/gateway/heartbeat",
        }.issubset(links))
        text = " ".join(" ".join(research["text"]).split())
        self.assertIn("event-driven wakes remain a separate consideration", text)
        self.assertIn("A proposed comparison, not a result already measured", text)
        self.assertIn("Dependable delegation is agency too.", text)

    def test_numbered_sections_remain_in_order(self):
        source = (ROOT / "index.html").read_text()
        numbers = re.findall(r'<div class="section-index(?: light-index)?">(\d+) /', source)
        self.assertEqual(numbers, [f"{number:02}" for number in range(10)])


if __name__ == "__main__":
    unittest.main()
