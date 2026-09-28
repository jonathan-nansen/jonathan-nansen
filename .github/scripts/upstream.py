"""Render open upstream PRs as a `git log --graph` terminal card.

usage: GITHUB_TOKEN=... python upstream.py <user> <exclude-org> <out.svg>
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from html import escape

MAX_ROWS = 8
ROW = 34
TOP = 76


def search(q, per_page=50):
    url = "https://api.github.com/search/issues?" + urllib.parse.urlencode(
        {"q": q, "sort": "created", "order": "desc", "per_page": per_page}
    )
    req = urllib.request.Request(url, headers={
        "Authorization": f"bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def tidy(title):
    # drop "fix(scope): " / "core, eth: " style prefixes
    t = re.sub(r"^[a-z0-9_\-/(). ,]+?:\s+", "", title)
    return t[:1].lower() + t[1:]


def clip(s, n):
    return s if len(s) <= n else s[: n - 1] + "…"


def group_by_repo(prs):
    order = {}
    for p in prs:
        order.setdefault(p["repo"], len(order))
    return sorted(prs, key=lambda p: order[p["repo"]])


def render(prs, merged, exclude):
    rows = group_by_repo(prs)[:MAX_ROWS] or [{"repo": "—", "number": "0", "title": "nothing in review right now"}]
    n = len(rows)
    last_y = TOP + (n - 1) * ROW
    rule_y = last_y + 32
    h = rule_y + 54

    rail, nodes, body = [], [], []
    for i, p in enumerate(rows):
        y = TOP + i * ROW
        branched = i > 0 and rows[i - 1]["repo"] == p["repo"]
        cx = 60 if branched else 44
        if branched and not (i > 1 and rows[i - 2]["repo"] == p["repo"]):
            # fork off the main rail at the previous row
            j = i
            while j + 1 < n and rows[j + 1]["repo"] == p["repo"]:
                j += 1
            yb = TOP + j * ROW
            end = yb + ROW if j + 1 < n else yb + 18
            rail.append(
                f'<path d="M44 {y - ROW} C 44 {y - ROW + 12}, 60 {y - ROW + 12}, 60 {y - ROW + 22} '
                f'L 60 {yb + 12} C 60 {yb + 22}, 44 {yb + 22}, 44 {end}" fill="none" stroke="#7aa2ff" '
                f'stroke-width="2" opacity=".55" class="rail"/>'
            )
        ping = f'<circle cx="{cx}" cy="{y}" r="3" fill="#7aa2ff" class="ping"/>' if i == 0 else ""
        body.append(
            f'<g class="row" style="animation-delay:{.3 + i * .3:.1f}s">'
            f'<circle cx="{cx}" cy="{y}" r="5" fill="#0b0f0d" stroke="#7aa2ff" stroke-width="2"/>{ping}'
            f'<text x="72" y="{y + 5}" class="amb">#{p["number"]}</text>'
            f'<text x="146" y="{y + 5}" class="peer">{escape(clip(p["repo"], 17))}</text>'
            f'<text x="300" y="{y + 5}" class="t">{escape(clip(p["title"], 70))}</text></g>'
        )

    clients = len({p["repo"] for p in prs})
    foot_delay = .3 + n * .3
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 {h}" width="900" height="{h}" role="img" aria-labelledby="title">
  <title id="title">{len(prs)} upstream pull requests in review</title>
  <defs>
    <clipPath id="card"><rect x="1" y="1" width="898" height="{h - 2}" rx="14"/></clipPath>
    <pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#fff" opacity=".035"/></pattern>
    <radialGradient id="vignette" cx="80%" cy="10%" r="90%"><stop offset="0" stop-color="#7aa2ff" stop-opacity=".07"/><stop offset=".6" stop-color="#7aa2ff" stop-opacity="0"/></radialGradient>
  </defs>
  <style>
    text {{ font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, "Cascadia Mono", Consolas, "Liberation Mono", monospace; font-size: 14px; fill: #c8d0c9; white-space: pre; }}
    .dim {{ fill: #5f6f66; }} .amb {{ fill: #ffb454; }} .ok {{ fill: #3ddc97; }} .peer {{ fill: #7aa2ff; }} .t {{ font-size: 13px; }}
    .row {{ opacity: 0; transform: translateX(-8px); animation: in .35s cubic-bezier(.2,.8,.2,1) forwards; }}
    @keyframes in {{ to {{ opacity: 1; transform: none; }} }}
    .rail {{ stroke-dasharray: 1000; stroke-dashoffset: 1000; animation: draw {foot_delay:.1f}s linear .3s forwards; }}
    @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
    .ping {{ transform-box: fill-box; transform-origin: center; animation: ping 2.4s ease-out {foot_delay:.1f}s infinite; }}
    @keyframes ping {{ 0% {{ transform: scale(1); opacity: .8; }} 70%, 100% {{ transform: scale(3.2); opacity: 0; }} }}
    @media (prefers-reduced-motion: reduce) {{ .row {{ opacity: 1; transform: none; animation: none; }} .rail {{ stroke-dashoffset: 0; animation: none; }} .ping {{ animation: none; opacity: 0; }} }}
  </style>
  <rect x="1" y="1" width="898" height="{h - 2}" rx="14" fill="#0b0f0d" stroke="#243029"/>
  <g clip-path="url(#card)">
    <rect width="900" height="40" fill="#111713"/>
    <line x1="0" y1="40.5" x2="900" y2="40.5" stroke="#1f2a24"/>
    <text x="24" y="25"><tspan class="amb">jonathan@nansen</tspan><tspan class="dim">:~$ </tspan>git log --upstream --graph --state=open</text>
    <text x="876" y="25" class="dim t" text-anchor="end">bugs hit in prod · fixed at the source</text>
    <line x1="44" y1="{TOP}" x2="44" y2="{last_y}" stroke="#2c3a33" stroke-width="2"/>
    <line x1="44" y1="{TOP}" x2="44" y2="{last_y}" stroke="#7aa2ff" stroke-width="2" class="rail"/>
    {''.join(rail)}
    {''.join(body)}
    <line x1="24" y1="{rule_y + .5}" x2="876" y2="{rule_y + .5}" stroke="#1f2a24" class="row" style="animation-delay:{foot_delay:.1f}s"/>
    <text x="24" y="{rule_y + 29}" class="row" style="animation-delay:{foot_delay + .1:.1f}s"><tspan class="peer">{len(prs)}</tspan><tspan class="dim"> in review · </tspan><tspan class="peer">{clients}</tspan><tspan class="dim"> clients · </tspan><tspan class="ok">[ MERGED ]</tspan> {merged} pull requests outside {exclude}</text>
    <rect width="900" height="{h}" fill="url(#vignette)" pointer-events="none"/>
    <rect width="900" height="{h}" fill="url(#scan)" pointer-events="none"/>
  </g>
</svg>
"""


if __name__ == "__main__":
    user, exclude, out = sys.argv[1:4]
    scope = f"is:pr author:{user} -user:{user} -org:{exclude}"
    items = search(f"{scope} is:open")["items"]
    prs = [{
        "repo": i["repository_url"].rsplit("/", 1)[1],
        "number": i["number"],
        "title": tidy(i["title"]),
    } for i in items]
    merged = search(f"{scope} is:merged", per_page=1)["total_count"]
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        f.write(render(prs, merged, exclude))
