#!/usr/bin/env python3
"""Collect public GitHub activity and render a supplementary, dependency-free preview.

Requires an authenticated `gh` CLI for collection; rendering uses only Python's
standard library. No credentials or issue contents are stored in the snapshot.
"""

import argparse
import csv
import hashlib
import html
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import subprocess
import time
from urllib.parse import urlencode

PROJECTS = (("OpenClaw", "openclaw/openclaw"), ("Pi", "earendil-works/pi"))
ECOSYSTEM = (("TelePi", "benedict2310/TelePi"), ("Pi Livecraft", "sebastienservouze/pi-livecraft"))
METRICS = {
    "issues": ("All issue reports opened", ""),
    "bugs": ("Reports currently labelled bug", "label:bug"),
    "upgrade_bugs": ("Update / upgrade bug reports", "label:bug (update OR upgrade) in:title"),
}
COLORS = ("#a74830", "#226a4b")
STAR_HISTORY_URL = "https://www.star-history.com/?repos=earendil-works%2Fpi%2Copenclaw%2Fopenclaw&type=date&legend=top-left"


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sample_ages(age, common_age):
    return sorted(set([0, age, common_age, *range(30, age + 1, 30)]))


def issue_query(repo, start, age, qualifier=""):
    if age <= 0:
        raise ValueError("Day zero has no observation interval")
    last = start + timedelta(days=age - 1)
    return f"repo:{repo} is:issue {qualifier} created:{start.isoformat()}..{last.isoformat()}".replace("  ", " ")


def search_count(payload):
    if payload.get("incomplete_results") is not False:
        raise ValueError("GitHub returned incomplete search results; refusing to plot them")
    count = payload["total_count"]
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ValueError("Invalid GitHub search count")
    return count


def release_count(releases, start, age):
    end = start + timedelta(days=age)
    return sum(start <= date.fromisoformat(r["published_at"][:10]) < end for r in releases)


def bug_share(point):
    return 100 * point["upgrade_bugs"] / point["bugs"] if point["bugs"] else None


class GitHub:
    def __init__(self, cache):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.last_search = 0.0

    def get(self, endpoint, query=None, paginate=False):
        key = hashlib.sha256(json.dumps([endpoint, query, paginate]).encode()).hexdigest()
        target = self.cache / f"{key}.json"
        if target.exists():
            return json.loads(target.read_text())
        if query:
            # Authenticated GitHub Search permits 30 requests/minute.
            time.sleep(max(0, 2.2 - (time.monotonic() - self.last_search)))
        command = ["gh", "api", endpoint]
        if paginate:
            command += ["--paginate", "--slurp"]
        if query:
            command += ["-X", "GET", "-f", f"q={query}", "-f", "per_page=1"]
            self.last_search = time.monotonic()
        result = subprocess.run(command, capture_output=True, text=True, timeout=90, check=True)
        payload = json.loads(result.stdout)
        if query:
            # Cache counts only, never issue titles, bodies, or authors.
            search_count(payload)
            payload = {k: payload[k] for k in ("total_count", "incomplete_results")}
        elif not paginate:
            payload = {k: payload[k] for k in ("full_name", "html_url", "created_at", "stargazers_count")}
        else:
            payload = [
                {k: r[k] for k in ("tag_name", "published_at", "html_url", "draft", "prerelease")}
                for page in payload for r in page
            ]
        record = {"observed_at": utc_now(), "payload": payload}
        target.write_text(json.dumps(record, indent=2) + "\n")
        return record


def collect(cutoff, output, cache):
    if cutoff > datetime.now(timezone.utc).date():
        raise ValueError("Cutoff cannot include future dates")
    api = GitHub(cache)
    data = {
        "schema_version": 1,
        "capture_started_at": utc_now(),
        "cutoff_exclusive": cutoff.isoformat(),
        "alignment": "UTC calendar days since each repository's created_at date; a proxy, not a product launch date",
        "projects": [],
        "ecosystem": [],
    }
    for name, repo in PROJECTS:
        record = api.get(f"repos/{repo}")
        meta = record["payload"]
        start = date.fromisoformat(meta["created_at"][:10])
        age = (cutoff - start).days
        if age <= 0:
            raise ValueError(f"Cutoff must follow repository creation: {repo}")
        releases_record = api.get(f"repos/{repo}/releases?per_page=100", paginate=True)
        releases = sorted(
            (r for r in releases_record["payload"] if not r["draft"] and not r["prerelease"] and r["published_at"]),
            key=lambda r: r["published_at"],
        )
        data["projects"].append({
            "name": name, "repository": repo, "metadata": meta,
            "metadata_observed_at": record["observed_at"],
            "age_days": age, "releases": releases,
            "releases_observed_at": releases_record["observed_at"], "points": [],
        })
    common = min(p["age_days"] for p in data["projects"])
    data["common_age_days"] = common
    for project in data["projects"]:
        start = date.fromisoformat(project["metadata"]["created_at"][:10])
        for age in sample_ages(project["age_days"], common):
            point = {
                "age_days": age,
                "end_exclusive": (start + timedelta(days=age)).isoformat(),
                "releases": release_count(project["releases"], start, age),
                "sources": {},
            }
            for key, (_, qualifier) in METRICS.items():
                if not age:
                    point[key] = 0  # Empty interval, not a fetched historical snapshot.
                    continue
                query = issue_query(project["repository"], start, age, qualifier)
                record = api.get("search/issues", query=query)
                point[key] = search_count(record["payload"])
                point["sources"][key] = {
                    "query": query, "observed_at": record["observed_at"],
                    "incomplete_results": False,
                    "api_url": "https://api.github.com/search/issues?" + urlencode({"q": query, "per_page": 1}),
                    "web_url": "https://github.com/search?" + urlencode({"q": query, "type": "issues"}),
                }
            if not 0 <= point["upgrade_bugs"] <= point["bugs"] <= point["issues"]:
                raise ValueError("Inconsistent counts; use a fresh cache and repeat collection")
            project["points"].append(point)
            print(project["name"], age, {k: point[k] for k in (*METRICS, "releases")}, flush=True)
    if all(p["releases"] for p in data["projects"]):
        starts = [date.fromisoformat(p["releases"][0]["published_at"][:10]) for p in data["projects"]]
        release_age = min((cutoff - start).days for start in starts)
        if release_age > 0:
            check = {"anchor": "Earliest retained non-prerelease GitHub release, not a verified first public launch", "common_age_days": release_age, "projects": []}
            for project, start in zip(data["projects"], starts):
                point = {"name": project["name"], "start": start.isoformat(), "end_exclusive": (start + timedelta(days=release_age)).isoformat(), "releases": release_count(project["releases"], start, release_age), "sources": {}}
                for key, (_, qualifier) in METRICS.items():
                    query = issue_query(project["repository"], start, release_age, qualifier)
                    record = api.get("search/issues", query=query)
                    point[key] = search_count(record["payload"])
                    point["sources"][key] = {"query": query, "observed_at": record["observed_at"], "incomplete_results": False, "api_url": "https://api.github.com/search/issues?" + urlencode({"q": query, "per_page": 1})}
                check["projects"].append(point)
                print("Release-start check", point["name"], release_age, {k: point[k] for k in METRICS}, flush=True)
            data["release_aligned_check"] = check
    for name, repo in ECOSYSTEM:
        record = api.get(f"repos/{repo}")
        data["ecosystem"].append({"name": name, **record})
    data["capture_finished_at"] = utc_now()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2) + "\n")


def nice_top(value):
    if value <= 0:
        return 4
    step = 10 ** math.floor(math.log10(value / 4))
    tick = next(m * step for m in (1, 2, 2.5, 5, 10) if m * step >= value / 4)
    return tick * 4


def fmt(value):
    return f"{value:,.0f}"


def chart(data, metric, title):
    common = data["common_age_days"]
    xmax = math.ceil(max(p["age_days"] for p in data["projects"]) / 30) * 30
    ymax = nice_top(max(pt[metric] for p in data["projects"] for pt in p["points"]))
    x = lambda age: 70 + age / xmax * 510
    y = lambda count: 258 - count / ymax * 194
    parts = [
        f'<svg viewBox="0 0 620 320" role="img" aria-labelledby="{metric}-title {metric}-desc">',
        f'<title id="{metric}-title">{html.escape(title)}</title>',
        f'<desc id="{metric}-desc">Cumulative counts since repository creation, on a shared linear scale starting at zero. '
        f'Both projects have observations through day {common}. The shaded region has only the older repository’s observations. '
        'Exact values and dates are in the data table below.</desc>',
        f'<rect x="{x(common):.2f}" y="55" width="{580-x(common):.2f}" height="203" fill="#dce1da"/>',
        f'<text x="{(x(common)+580)/2:.2f}" y="45" text-anchor="middle" font-size="12">Older repo only</text>',
    ]
    for n in range(5):
        value = ymax * n / 4
        parts += [
            f'<line x1="70" y1="{y(value):.2f}" x2="580" y2="{y(value):.2f}" stroke="#cbd0c8"/>',
            f'<text x="60" y="{y(value)+4:.2f}" text-anchor="end">{fmt(value)}</text>',
        ]
    for age in range(0, xmax + 1, 60):
        parts.append(f'<text x="{x(age):.2f}" y="282" text-anchor="middle">{age}</text>')
    parts += [
        f'<line x1="{x(common):.2f}" y1="55" x2="{x(common):.2f}" y2="258" stroke="#626a66" stroke-dasharray="3 4"/>',
        '<text x="325" y="310" text-anchor="middle">Days since repository creation</text>',
    ]
    for i, project in enumerate(data["projects"]):
        coords = " ".join(f'{x(pt["age_days"]):.2f},{y(pt[metric]):.2f}' for pt in project["points"])
        dash = ' stroke-dasharray="7 4"' if i else ""
        parts.append(f'<polyline points="{coords}" fill="none" stroke="{COLORS[i]}" stroke-width="3"{dash}/>')
        for pt in project["points"]:
            label = f'{project["name"]}, day {pt["age_days"]}: {fmt(pt[metric])}; through {pt["end_exclusive"]} exclusive'
            parts.append(f'<circle cx="{x(pt["age_days"]):.2f}" cy="{y(pt[metric]):.2f}" r="3.4" fill="{COLORS[i]}"><title>{html.escape(label)}</title></circle>')
    parts.append('</svg>')
    return "\n".join(parts)


def bars(values, title, ident, suffix="", percent=False):
    maximum = 100 if percent else max([v for _, v in values if v is not None] + [1])
    parts = [f'<svg viewBox="0 0 620 190" role="img" aria-labelledby="{ident}-title">', f'<title id="{ident}-title">{html.escape(title)}</title>']
    for i, (name, value) in enumerate(values):
        ypos = 34 + i * 75
        label = "Not available (no bug-labelled reports)" if value is None else (f"{value:.2f}" if percent else fmt(value)) + suffix
        parts.append(f'<text x="24" y="{ypos}">{html.escape(name)} · {html.escape(label)}</text>')
        parts.append(f'<rect x="24" y="{ypos+12}" width="550" height="19" rx="3" fill="#dce1da"/>')
        if value is not None:
            parts.append(f'<rect x="24" y="{ypos+12}" width="{550*value/maximum:.2f}" height="19" rx="3" fill="{COLORS[i]}"/>')
    parts.append('</svg>')
    return "\n".join(parts)


def render(snapshot, output):
    data = json.loads(snapshot.read_text())
    common = data["common_age_days"]
    summary = [(p, next(pt for pt in p["points"] if pt["age_days"] == common)) for p in data["projects"]]
    cards = []
    descriptions = {
        "releases": "Currently retained, published GitHub releases excluding drafts and prereleases. More releases do not mean more reliability.",
        "issues": "Open and closed issues; pull requests excluded. Reporting volume is not the number of broken installations.",
        "bugs": "Issues created in each window that carry the bug label now. Historical label states are not reconstructed.",
        "upgrade_bugs": "Currently bug-labelled issues with update or upgrade in the title. This misses failures described only in the body.",
    }
    for metric, title in [("releases", "Non-prerelease releases published"), *[(k, v[0]) for k, v in METRICS.items()]]:
        cards.append(f'<figure><h3>{title}</h3>{chart(data, metric, title)}<figcaption>{descriptions[metric]}</figcaption></figure>')
    shares = [(p["name"], bug_share(pt)) for p, pt in summary]
    cards.append('<figure><h3>Update / upgrade share of bug reports</h3>' + bars(shares, f'Share of bug-labelled reports in each repository’s first {common} days', 'share', '%', True) + f'<figcaption>First {common} days for both. Percentage of reports, not users or upgrades. Full 0–100% scale; differing labels and reporting practices still matter.</figcaption></figure>')
    stars = [(p["name"], p["metadata"]["stargazers_count"]) for p in data["projects"]]
    cards.append('<figure><h3>Audience now — not age-aligned</h3>' + bars(stars, 'Current GitHub stars, not historical audience or active users', 'stars', ' stars') + '<figcaption>Current metadata snapshot at unequal repository ages. Historical star counts were not collected, so stars are not used to normalise the age-aligned reports. ' + f'<a href="{html.escape(STAR_HISTORY_URL, quote=True)}" target="_blank" rel="noreferrer">Compare star growth on Star History ↗</a>. That live, third-party chart uses calendar dates, not aligned project ages, and is not part of this fixed snapshot.</figcaption></figure>')
    summary_rows = []
    for key, label in [("releases", "Non-prerelease releases"), *[(k, v[0]) for k, v in METRICS.items()]]:
        cells = []
        for p, pt in summary:
            url = pt["sources"][key]["web_url"] if key in METRICS else p["metadata"]["html_url"] + "/releases"
            cells.append(f'<td><a href="{html.escape(url, quote=True)}">{fmt(pt[key])}</a></td>')
        summary_rows.append(f'<tr><th scope="row">{label}</th>{"".join(cells)}</tr>')
    date_cards = []
    for p, pt in summary:
        earliest = p["releases"][0]["published_at"][:10] if p["releases"] else "none retained"
        end = (date.fromisoformat(pt["end_exclusive"]) - timedelta(days=1)).isoformat()
        date_cards.append(f'<div><h3>{p["name"]}</h3><p>Repository created <strong>{p["metadata"]["created_at"][:10]}</strong><br>Earliest retained non-prerelease GitHub release: {earliest}<br>Equal-age window ends {end} (inclusive)<br>Full observed span: {p["age_days"]} calendar days</p></div>')
    rows = []
    csv_rows = []
    for p in data["projects"]:
        for pt in p["points"]:
            values = [p["name"], pt["age_days"], pt["end_exclusive"], pt["releases"], pt["issues"], pt["bugs"], pt["upgrade_bugs"]]
            csv_rows.append(values)
            rows.append('<tr>' + ''.join(f'<td>{html.escape(str(v))}</td>' for v in values) + '</tr>')
    release_check_html = ""
    if check := data.get("release_aligned_check"):
        check_rows = []
        for key, label in [("start", "Starting date"), ("end_exclusive", "End date (exclusive)"), ("releases", "Non-prerelease releases"), *[(k, v[0]) for k, v in METRICS.items()]]:
            cells = ''.join(f'<td>{html.escape(str(p[key])) if isinstance(p[key], str) else fmt(p[key])}</td>' for p in check["projects"])
            check_rows.append(f'<tr><th scope="row">{label}</th>{cells}</tr>')
        share_cells = ''.join(f'<td>{bug_share(p):.2f}%</td>' if bug_share(p) is not None else '<td>Not available</td>' for p in check["projects"])
        check_rows.append(f'<tr><th scope="row">Update / upgrade share of bug reports</th>{share_cells}</tr>')
        earliest_tags = ", ".join(
            f'{html.escape(p["name"])}: <code>{html.escape(p["releases"][0]["tag_name"])}</code>'
            for p in data["projects"] if p["releases"]
        )
        release_check_html = f'<h2>Check the choice of starting point</h2><p>Counting from each repository’s <strong>earliest retained non-prerelease GitHub release</strong> instead gives a shared {check["common_age_days"]}-day window. This excludes history before each first retained release, but still does not establish a public launch date. Earliest retained tags in this snapshot: {earliest_tags}. Neither starting point controls for audience or scope.</p><div class="table-scroll" tabindex="0" role="region" aria-label="Alternative starting point"><table><caption>Starting-point sensitivity check, not the series plotted above. Source queries are included in the JSON snapshot.</caption><thead><tr><th scope="col">Measure</th><th scope="col">OpenClaw</th><th scope="col">Pi</th></tr></thead><tbody>{"".join(check_rows)}</tbody></table></div>'
    ecosystem = []
    for item in data["ecosystem"]:
        meta = item["payload"]
        ecosystem.append(f'<li><a href="{meta["html_url"]}">{item["name"]}</a>: repository created {meta["created_at"][:10]}.</li>')
    stylesheet = """
:root { color-scheme: light; --paper:#f3f0e8; --ink:#17201f; --muted:#535f58; }
* { box-sizing:border-box; } body { margin:0; background:var(--paper); color:var(--ink); font:16px/1.65 system-ui,sans-serif; }
main { max-width:1280px; margin:auto; padding:40px 24px 80px; } a { color:inherit; text-underline-offset:3px; }
.kicker { font:12px/1.5 ui-monospace,monospace; text-transform:uppercase; letter-spacing:.1em; }
h1 { font:clamp(36px,6vw,70px)/1.06 Georgia,serif; letter-spacing:-.035em; max-width:1000px; margin:24px 0; }
h2 { font:32px/1.2 Georgia,serif; margin:36px 0 20px; } h3 { font-size:18px; line-height:1.35; margin:0 0 10px; }
.intro { max-width:850px; font-size:19px; } .note { padding:20px 24px; border:1px solid #9aa499; background:#e4ebdf; }
.legend { display:flex; flex-wrap:wrap; gap:16px 28px; padding:22px 0; } .legend span { display:flex; align-items:center; gap:10px; }
.swatch { display:inline-block; width:32px; border-top:3px solid #a74830; } .swatch.pi { border-color:#226a4b; border-top-style:dashed; }
.grid,.dates { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:20px; }
.dates { margin:30px 0; padding:24px 0; border-top:1px solid #b7bdb4; border-bottom:1px solid #b7bdb4; }
.dates p,figcaption { color:var(--muted); font-size:14px; margin:0; }
figure { margin:0; min-width:0; padding:22px; border:1px solid #b7bdb4; background:#faf8f2; }
svg { display:block; width:100%; height:auto; overflow:visible; } svg text { font:18px system-ui,sans-serif; fill:#46514a; }
figcaption { margin-top:12px; } .table-scroll { max-width:100%; overflow-x:auto; }
table { width:100%; border-collapse:collapse; text-align:left; font-size:14px; }
caption { text-align:left; margin:12px 0; color:var(--muted); } th,td { padding:12px; border-bottom:1px solid #bbc1b8; white-space:nowrap; }
tbody th { white-space:normal; } thead { background:#e4ebdf; } summary { cursor:pointer; font-weight:650; padding:18px 0; }
li { margin:10px 0; } .links { display:flex; flex-wrap:wrap; gap:12px 24px; margin:24px 0; }
footer { margin-top:40px; padding-top:20px; border-top:1px solid #b7bdb4; color:var(--muted); font-size:13px; }
:focus-visible { outline:3px solid #226a4b; outline-offset:4px; }
@media(max-width:760px) { .grid,.dates { grid-template-columns:1fr; } main { padding:24px 14px 60px; } figure { padding:16px 10px; } }
@media print { details > * { display:block; } figure { break-inside:avoid; } }
"""
    content = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>Evidence preview — The Small Agent Stack</title><style>{stylesheet}</style></head>
<body><main>
<header><p class="kicker">Supplementary evidence preview · Small Agent Stack</p><a href="../index.html#evidence">Back to the main guide</a>
<h1>Equal project age.<br>Different responsibilities.</h1>
<p class="intro">Compare public activity from each repository’s beginning, rather than giving both the same calendar window. The first <strong>{common} days</strong> are observed for both. The older repository’s additional history stays visible, but is not an equal-age comparison.</p></header>
<p class="note"><strong>Activity, not a reliability ranking.</strong> Equal ages remove one distortion, not all of them. We do not know active installations, attempted upgrades, failure rates or operator hours. These charts cannot establish that one product is more dependable.</p>
<div class="dates">{''.join(date_cards)}</div>
<div class="legend" aria-label="Chart legend"><span><i class="swatch" aria-hidden="true"></i>OpenClaw · solid rust</span><span><i class="swatch pi" aria-hidden="true"></i>Pi · dashed green</span><span>Grey region: beyond the shared {common}-day window</span></div>
<div class="grid">{''.join(cards)}</div>
<h2>The same first {common} days</h2>
<div class="table-scroll" tabindex="0" role="region" aria-label="Equal-age totals"><table><caption>Counts available at capture, grouped by creation or publication date. Links reproduce the issue queries; release links show the upstream release lists.</caption><thead><tr><th scope="col">Measure</th><th scope="col">OpenClaw</th><th scope="col">Pi</th></tr></thead><tbody>{''.join(summary_rows)}</tbody></table></div>
{release_check_html}
<h2>What changed in the surrounding ecosystem?</h2>
<p>The components matter as well as the core. These dates help locate the emerging alternatives, but repository creation is not proof that a particular feature was usable then.</p><ul>{''.join(ecosystem)}</ul>
<p>Pi Livecraft and TelePi have their own issues, dependencies and maintenance work. They are <strong>not included</strong> in Pi’s core-repository counts. A fair comparison of complete setups must also measure those components and the work of assembling them.</p>
<h2>How to read this fairly</h2>
<ul>
<li><strong>“Inception” is an explicit proxy.</strong> Day zero is the UTC calendar date from GitHub’s <code>created_at</code>, not a verified first public launch or the coding agent’s birth. Pi’s repository covers a broader toolkit; repository creation and a tool’s public availability can differ. Renames, imported history and deleted records can affect both histories.</li>
<li><strong>Windows are half-open.</strong> A point at day 30 includes the creation date through day 29. Activity on or after <code>{data['cutoff_exclusive']}</code> UTC is excluded. Samples are every 30 days plus the shared and latest endpoints; lines only connect those samples.</li>
<li><strong>This is a retrospective count, not archived monthly snapshots.</strong> Open and closed issues are counted by creation date using labels and titles at capture. Releases are the retained, non-draft, non-prerelease GitHub records, dated by publication. Missing or deleted history is not reconstructed.</li>
<li><strong>Age alignment trades away calendar alignment.</strong> Each first {common}-day period took place in different months, with different models, audiences and ecosystem maturity. The guide’s same-calendar comparison answers a different, complementary question.</li>
<li><strong>Reporting policies and scope differ.</strong> Pi documents auto-closing issues and PRs from new contributors by default; OpenClaw has a broader integrated surface. Labels, triage and user reporting habits can move these counts independently of reliability.</li>
<li><strong>Stars are not exposure.</strong> Only current star counts were collected. They neither reconstruct historical popularity nor measure active users, so no reports-per-star reliability claim is made.</li>
<li><strong>Do not substitute this for an operational benchmark.</strong> To test the personal experience, compare matched tasks, upgrade success, repair time, repair tokens, unwanted calls, permission scope and recovery across the whole installed stack.</li>
</ul>
<details><summary>All plotted counts and dates</summary><div class="table-scroll" tabindex="0" role="region" aria-label="All chart observations"><table><caption>Cumulative counts; end dates are exclusive. Day zero denotes an empty interval.</caption><thead><tr>{''.join(f'<th scope="col">{v}</th>' for v in ['Project','Age (days)','End exclusive','Releases','Issues','Bug-labelled','Update/upgrade bugs'])}</tr></thead><tbody>{''.join(rows)}</tbody></table></div></details>
<div class="links"><a href="{html.escape(snapshot.name)}" download>Download source snapshot (JSON)</a><a href="evidence.csv" download>Download plotted counts (CSV)</a><a href="https://api.github.com/repos/openclaw/openclaw">OpenClaw metadata</a><a href="https://api.github.com/repos/earendil-works/pi">Pi metadata</a><a href="https://github.com/earendil-works/pi#readme">Pi reporting policy</a></div>
<footer>Collection run: {data['capture_started_at']} to {data['capture_finished_at']}. Each API observation has its own timestamp in the source snapshot; cached observations may predate the run. Search results marked incomplete are rejected. Supplementary activity preview; not a reliability ranking.</footer>
</main></body></html>
'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content)
    with output.with_name("evidence.csv").open("w", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["project", "age_days", "end_exclusive", "releases", "issues", "bug_label_now", "update_upgrade_bug_title_now"])
        writer.writerows(csv_rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    get = subs.add_parser("collect")
    get.add_argument("--cutoff", type=date.fromisoformat, required=True, help="Exclusive UTC date; today excludes the partial current day")
    get.add_argument("--output", type=Path, required=True)
    get.add_argument("--cache", type=Path, required=True, help="Use a fresh directory for each new snapshot; reuse only to resume a collection")
    draw = subs.add_parser("render")
    draw.add_argument("snapshot", type=Path)
    draw.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "collect":
        collect(args.cutoff, args.output, args.cache)
    else:
        render(args.snapshot, args.output)


if __name__ == "__main__":
    main()
