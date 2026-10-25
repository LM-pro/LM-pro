#!/usr/bin/env python3
"""Render self-contained, animated terminal-style SVG cards from public GitHub data."""
from __future__ import annotations

import html
import json
import os
import re
import urllib.request
from html.parser import HTMLParser
from urllib.parse import quote
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOGIN = os.environ.get("GITHUB_USERNAME", "thorsenbuilds")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = Path(os.environ.get("PROFILE_CARDS_DIR", "assets/profile-cards"))
GREEN = "#42f58d"
LIME = "#b5ff70"
BG = "#07110d"
PANEL = "#0b1711"
LINE = "#1c4a30"
MUTED = "#8aa995"
TEXT = "#d9f8e5"


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def github_data() -> dict:
    query = """
    query($login:String!) {
      user(login:$login) {
        name login bio location websiteUrl followers { totalCount }
        repositories(first:100, ownerAffiliations:OWNER, privacy:PUBLIC,
          orderBy:{field:PUSHED_AT,direction:DESC}) {
          totalCount nodes { name url description stargazerCount forkCount pushedAt
            isFork isPrivate primaryLanguage { name color } }
        }
      }
    }
    """
    body = json.dumps({"query": query, "variables": {"login": LOGIN}}).encode()
    request = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"Authorization": f"Bearer {TOKEN}",
                 "Content-Type": "application/json",
                 "User-Agent": "thorsen-profile-card-renderer"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError("GitHub GraphQL returned errors: " + json.dumps(payload["errors"]))
    user = payload.get("data", {}).get("user")
    if not user:
        raise RuntimeError(f"GitHub user {LOGIN!r} was not found")
    # Privacy is enforced twice: request privacy:PUBLIC and reject any private node.
    repos = [r for r in user["repositories"]["nodes"] if r and not r.get("isPrivate", False)]
    user["repositories"]["nodes"] = repos
    return user


class ContributionCalendarParser(HTMLParser):
    """Read only GitHub's publicly rendered aggregate contribution calendar."""

    def __init__(self) -> None:
        super().__init__()
        self.days: list[dict] = []
        self.heading: list[str] = []
        self.in_heading = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "h2" and values.get("id") == "js-contribution-activity-description":
            self.in_heading = True
        if tag == "td" and values.get("data-date"):
            self.days.append({
                "date": values["data-date"],
                "level": int(values.get("data-level") or 0),
            })

    def handle_data(self, data: str) -> None:
        if self.in_heading:
            self.heading.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2" and self.in_heading:
            self.in_heading = False


def public_calendar(login: str) -> dict:
    """Use only the aggregate heatmap GitHub already shows on the public profile."""
    today = datetime.now(timezone.utc).date()
    url = (f"https://github.com/users/{quote(login, safe='')}/contributions"
           f"?to={today.isoformat()}")
    request = urllib.request.Request(url, headers={
        "User-Agent": "thorsen-profile-card-renderer",
        "Accept": "text/html",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        page = response.read().decode("utf-8", errors="replace")
    parser = ContributionCalendarParser()
    parser.feed(page)
    match = re.search(r"([\d,]+)\s+contributions\s+in\s+(\d{4})",
                      " ".join(parser.heading), re.IGNORECASE)
    if not match or not parser.days:
        raise RuntimeError("Could not read the public GitHub contribution calendar")
    total, year = int(match.group(1).replace(",", "")), int(match.group(2))
    grouped: dict[str, list[dict]] = {}
    for item in parser.days:
        day = datetime.strptime(item["date"], "%Y-%m-%d").date()
        week_start = day - timedelta(days=day.weekday())
        weekday = day.weekday()
        grouped.setdefault(week_start.isoformat(), []).append({
            "date": item["date"], "weekday": weekday,
            # GitHub exposes intensity levels, not exact counts, on this public HTML.
            "contributionCount": item["level"], "level": item["level"],
        })
    weeks = [{"contributionDays": sorted(days, key=lambda d: d["weekday"])}
             for _, days in sorted(grouped.items())]
    return {"totalContributions": total, "year": year, "weeks": weeks}

def card(title: str, body: str, height: int, subtitle: str = "THORSEN // PUBLIC PROFILE") -> str:
    # Each image is self-contained: styles, fonts and animation are embedded; no scripts or remote assets.
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="{height}" viewBox="0 0 900 {height}" role="img" aria-label="{esc(title)}">
<defs>
  <linearGradient id="edge" x1="0" x2="1"><stop stop-color="{GREEN}" stop-opacity=".2"/><stop offset=".5" stop-color="{LIME}" stop-opacity=".9"/><stop offset="1" stop-color="{GREEN}" stop-opacity=".2"/></linearGradient>
  <pattern id="grid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M28 0H0V28" fill="none" stroke="{GREEN}" stroke-opacity=".045" stroke-width="1"/></pattern>
  <filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <style>
    text{{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace}}
    .title{{fill:{TEXT};font-size:19px;font-weight:700;letter-spacing:1.5px}}
    .label{{fill:{MUTED};font-size:12px;letter-spacing:1px}}
    .value{{fill:{TEXT};font-size:16px;font-weight:600}}
    .accent{{fill:{GREEN}}}
    .enter{{opacity:0;animation:enter .75s cubic-bezier(.2,.8,.2,1) forwards}}
    .pulse{{animation:pulse 2.4s ease-in-out infinite}}
    .scan{{animation:scan 5s linear infinite}}
    @keyframes enter{{from{{opacity:0;transform:translateY(9px)}}to{{opacity:1;transform:translateY(0)}}}}
    @keyframes pulse{{0%,100%{{opacity:.45}}50%{{opacity:1}}}}
    @keyframes scan{{from{{transform:translateY(0)}}to{{transform:translateY({height}px)}}}}
    @media(prefers-reduced-motion:reduce){{.enter,.pulse,.scan{{animation:none;opacity:1}}}}
  </style>
</defs>
<rect x="1" y="1" width="898" height="{height-2}" rx="15" fill="{BG}" stroke="{LINE}" stroke-width="2"/>
<rect x="2" y="2" width="896" height="{height-4}" rx="14" fill="url(#grid)"/>
<rect x="2" y="2" width="896" height="3" rx="2" fill="url(#edge)"/>
<circle cx="28" cy="27" r="5" fill="#ff6b6b"/><circle cx="47" cy="27" r="5" fill="#ffd166"/><circle cx="66" cy="27" r="5" fill="{GREEN}"/>
<text x="88" y="32" class="label">{esc(subtitle)}</text><text x="870" y="32" text-anchor="end" class="label pulse">● ONLINE</text>
<text x="30" y="68" class="title">{esc(title)}</text>
<rect class="scan" x="4" y="{height-13}" width="892" height="1" fill="{GREEN}" opacity=".13"/>
{body}
</svg>'''


def render_scan(u: dict, repos: list[dict], total: int) -> str:
    name = u.get("name") or u["login"]
    bio = u.get("bio") or "Building in public · applied AI · music discovery"
    lines = [
        ("IDENTITY", name),
        ("ROLE", "Python builder"),
        ("FOCUS", "applied AI  /  music discovery"),
        ("STATUS", "building  ·  learning  ·  shipping"),
    ]
    body = f'<text x="42" y="99" class="label">{esc(bio[:86])}</text>'
    for i, (label, value) in enumerate(lines):
        y = 132 + i * 30
        body += f'<g class="enter" style="animation-delay:{i*110}ms"><text x="48" y="{y}" class="label">{label}</text><text x="192" y="{y}" class="value">{esc(value)}</text><path d="M48 {y+9}H850" stroke="{LINE}"/></g>'
    body += f'<text x="48" y="260" class="label">PUBLIC REPOSITORIES</text><text x="850" y="260" text-anchor="end" class="value accent">{len(repos):02d}  /  {total:02d}</text>'
    return card("SYSTEM.SCAN // OPERATOR PROFILE", body, 290)


def render_toolbox(repos: list[dict]) -> str:
    counts: dict[str, int] = {}
    colors: dict[str, str] = {}
    for repo in repos:
        lang = (repo.get("primaryLanguage") or {}).get("name")
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
            colors[lang] = (repo.get("primaryLanguage") or {}).get("color") or GREEN
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:7]
    total = max(sum(counts.values()), 1)
    body = '<text x="48" y="101" class="label">LANGUAGE FOOTPRINT // BY PUBLIC REPOSITORY</text>'
    for i, (name, count) in enumerate(ranked):
        y = 132 + i * 27
        pct = round(count * 100 / total)
        width = max(5, 580 * count / total)
        body += f'<g class="enter" style="animation-delay:{i*90}ms"><text x="48" y="{y}" class="value">{esc(name)}</text><rect x="250" y="{y-13}" width="580" height="10" rx="5" fill="{LINE}"/><rect x="250" y="{y-13}" width="{width:.1f}" height="10" rx="5" fill="{esc(colors[name])}" filter="url(#glow)"/><text x="850" y="{y}" text-anchor="end" class="label">{pct}% · {count} repo</text></g>'
    if not ranked:
        body += '<text x="48" y="145" class="value">No public language data yet</text>'
    return card("TOOLBOX.SH // STACK SIGNAL", body, max(180, 145 + len(ranked) * 27))


def render_projects(repos: list[dict]) -> str:
    items = sorted(repos, key=lambda r: (r.get("stargazerCount", 0), r.get("pushedAt") or ""), reverse=True)[:3]
    body = '<text x="48" y="101" class="label">PUBLIC PROJECTS // MOST STARRED, THEN MOST RECENT</text>'
    for i, repo in enumerate(items):
        y = 128 + i * 67
        lang = (repo.get("primaryLanguage") or {}).get("name") or "Open source"
        desc = (repo.get("description") or "No description yet")[:94]
        body += f'<g class="enter" style="animation-delay:{i*120}ms"><rect x="42" y="{y-16}" width="816" height="57" rx="9" fill="{PANEL}" stroke="{LINE}"/><circle cx="61" cy="{y+2}" r="4" fill="{GREEN}" class="pulse"/><text x="76" y="{y+5}" class="value accent">{esc(repo["name"])}</text><text x="834" y="{y+5}" text-anchor="end" class="label">{esc(lang)}  ·  ★ {repo.get("stargazerCount",0)}</text><text x="76" y="{y+25}" class="label">{esc(desc)}</text></g>'
    if not items:
        body += '<text x="48" y="145" class="value">No public repositories found</text>'
    return card("PROJECTS.SH // PUBLIC REPOSITORIES", body, 155 + max(1, len(items)) * 67)


def render_stats(u: dict, repos: list[dict], total: int, year: int) -> str:
    stars = sum(r.get("stargazerCount", 0) for r in repos)
    forks = sum(r.get("forkCount", 0) for r in repos)
    metrics = [(f"CONTRIBUTIONS · {year}", total), ("PUBLIC REPOSITORIES", len(repos)), ("STARS EARNED", stars), ("FORKS", forks)]
    body = '<text x="48" y="101" class="label">OPEN-SOURCE SIGNAL // UPDATED FROM GITHUB DATA</text>'
    for i, (label, value) in enumerate(metrics):
        x = 45 + (i % 2) * 420
        y = 139 + (i // 2) * 58
        body += f'<g class="enter" style="animation-delay:{i*100}ms"><rect x="{x}" y="{y-23}" width="390" height="46" rx="9" fill="{PANEL}" stroke="{LINE}"/><text x="{x+18}" y="{y+5}" class="label">{label}</text><text x="{x+365}" y="{y+5}" text-anchor="end" class="title accent">{value:,}</text></g>'
    return card("CONTRIBUTION.ACTIVITY // SIGNAL", body, 255)


def render_heatmap(calendar: dict) -> str:
    weeks = calendar.get("weeks", [])[-53:]
    body = f'<text x="48" y="101" class="label">{calendar.get("totalContributions",0):,} CONTRIBUTIONS · {calendar.get("year")} · PUBLIC PROFILE TOTAL</text>'
    colors = ["#102017", "#124b2d", "#168a46", "#22c55e", GREEN]
    for wi, week in enumerate(weeks):
        for day in week["contributionDays"]:
            weekday = int(day.get("weekday", 0))
            level = max(0, min(4, int(day.get("level", 0))))
            x, y = 48 + wi * 15, 118 + weekday * 17
            delay = min(1800, wi * 20 + weekday * 15)
            body += f'<rect class="enter" style="animation-delay:{delay}ms" x="{x}" y="{y}" width="10" height="11" rx="2" fill="{colors[level]}" opacity=".92"><title>{esc(day.get("date"))}: GitHub activity level {level}</title></rect>'
    body += f'<text x="48" y="258" class="label">LESS</text><rect x="91" y="247" width="11" height="11" rx="2" fill="#102017"/><rect x="108" y="247" width="11" height="11" rx="2" fill="#164b2d"/><rect x="125" y="247" width="11" height="11" rx="2" fill="#1e8a48"/><rect x="142" y="247" width="11" height="11" rx="2" fill="#22c55e"/><rect x="159" y="247" width="11" height="11" rx="2" fill="{GREEN}"/><text x="182" y="258" class="label">MORE</text>'
    return card("VISUAL.MAP // CONTRIBUTION.SIGNAL", body, 285)


def render_social() -> str:
    body = f'<text x="48" y="111" class="value">If the work is useful, open an issue, improve the docs, or start a conversation.</text><a href="https://github.com/thorsenbuilds"><rect x="48" y="137" width="214" height="43" rx="8" fill="#10281a" stroke="{GREEN}"/><text x="68" y="164" class="value accent">github.com/thorsenbuilds</text></a><text x="48" y="205" class="label">BUILDING IN PUBLIC · PYTHON · APPLIED AI · MUSIC DISCOVERY</text>'
    return card("CONNECT.SH // OPEN CHANNEL", body, 235)


def main() -> None:
    user = github_data()
    repos = user["repositories"]["nodes"]
    calendar = public_calendar(user["login"])
    OUT.mkdir(parents=True, exist_ok=True)
    generated = {
        "system-scan.svg": render_scan(user, repos, user["repositories"]["totalCount"]),
        "toolbox.svg": render_toolbox(repos),
        "projects.svg": render_projects(repos),
        "stats.svg": render_stats(user, repos, calendar["totalContributions"], calendar["year"]),
        "heatmap.svg": render_heatmap(calendar),
        "social.svg": render_social(),
    }
    for filename, svg in generated.items():
        (OUT / filename).write_text(svg, encoding="utf-8")
        print(f"generated {OUT / filename}")
    print(f"Rendered {len(generated)} self-contained SVGs from {len(repos)} public repositories.")


if __name__ == "__main__":
    main()
