"""Render the last year of contributions as an isometric terminal card.

usage: GITHUB_TOKEN=... python contrib3d.py <user> <out.svg>
"""
import json
import math
import sys
import urllib.request
from datetime import date

QUERY = """query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{
  totalContributions weeks{contributionDays{date contributionCount}}}}}}"""

# week axis runs right and slightly down, weekday axis runs down-left
U = (13.2, 4.0)
V = (-7.4, 5.0)
MAX_H = 72
INSET = 0.07  # gap between cells, as a fraction of the cell
TOPS = ["#18201c", "#1f5a45", "#2f9e73", "#3ddc97", "#ffb454"]


def fetch(user, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"u": user}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        sys.exit(f"graphql: {body['errors']}")
    return body["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def shade(hex_, k):
    r, g, b = (int(hex_[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % (int(r * k), int(g * k), int(b * k))


def level(count, peak):
    if count == 0:
        return 0
    return min(4, 1 + int(3.999 * math.sqrt(count / peak)))


def stats(days):
    counts = [d["contributionCount"] for d in days]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    busiest = max(days, key=lambda d: d["contributionCount"])
    return sum(1 for c in counts if c), longest, busiest


def pt(x, y):
    return f"{x:.1f},{y:.1f}"


def render(cal):
    weeks = cal["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    peak = max(d["contributionCount"] for d in days) or 1
    active, longest, busiest = stats(days)

    ox, oy = 80 + 7 * -V[0], 172
    cells = []
    for wi, w in enumerate(weeks):
        for d in w["contributionDays"]:
            di = date.fromisoformat(d["date"]).isoweekday() % 7
            cells.append((wi, di, d["contributionCount"]))
    cells.sort(key=lambda c: c[0] * U[1] + c[1] * V[1])

    boxes = []
    for wi, di, n in cells:
        lv = level(n, peak)
        h = 2 if n == 0 else 4 + (MAX_H - 4) * math.sqrt(n / peak)
        x0 = ox + wi * U[0] + di * V[0]
        y0 = oy + wi * U[1] + di * V[1]
        k = 1 - 2 * INSET
        a = (x0 + INSET * (U[0] + V[0]), y0 + INSET * (U[1] + V[1]))
        b = (a[0] + k * U[0], a[1] + k * U[1])
        dd = (a[0] + k * V[0], a[1] + k * V[1])
        c = (b[0] + k * V[0], b[1] + k * V[1])
        up = lambda p: (p[0], p[1] - h)
        top = TOPS[lv]
        faces = (
            f'<polygon points="{pt(*up(a))} {pt(*up(b))} {pt(*up(c))} {pt(*up(dd))}" fill="{top}"/>'
            f'<polygon points="{pt(*up(dd))} {pt(*up(c))} {pt(*c)} {pt(*dd)}" fill="{shade(top, .62)}"/>'
            f'<polygon points="{pt(*up(b))} {pt(*up(c))} {pt(*c)} {pt(*b)}" fill="{shade(top, .45)}"/>'
        )
        delay = wi * 0.028 + di * 0.01
        boxes.append(f'<g class="b" style="animation-delay:{delay:.2f}s">{faces}</g>')

    total = cal["totalContributions"]
    bday = date.fromisoformat(busiest["date"]).strftime("%b %d")
    legend = "".join(
        f'<rect x="{760 + i * 16}" y="73" width="11" height="11" rx="2" fill="{c}"/>' for i, c in enumerate(TOPS)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 440" width="900" height="440" role="img" aria-labelledby="t">
  <title id="t">{total} contributions in the last year</title>
  <defs>
    <clipPath id="card"><rect x="1" y="1" width="898" height="438" rx="14"/></clipPath>
    <pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#fff" opacity=".035"/></pattern>
    <radialGradient id="glow" cx="75%" cy="70%" r="70%"><stop offset="0" stop-color="#3ddc97" stop-opacity=".08"/><stop offset=".7" stop-color="#3ddc97" stop-opacity="0"/></radialGradient>
  </defs>
  <style>
    text {{ font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, "Cascadia Mono", Consolas, "Liberation Mono", monospace; font-size: 14px; fill: #c8d0c9; white-space: pre; }}
    .dim {{ fill: #5f6f66; }} .amb {{ fill: #ffb454; }} .ok {{ fill: #3ddc97; }} .s {{ font-size: 12px; }}
    .b {{ transform-box: fill-box; transform-origin: 50% 100%; transform: scaleY(0); animation: grow .5s cubic-bezier(.2,.9,.3,1.2) forwards; }}
    @keyframes grow {{ to {{ transform: scaleY(1); }} }}
    @media (prefers-reduced-motion: reduce) {{ .b {{ transform: none; animation: none; }} }}
  </style>
  <rect x="1" y="1" width="898" height="438" rx="14" fill="#0b0f0d" stroke="#243029"/>
  <g clip-path="url(#card)">
    <rect width="900" height="40" fill="#111713"/>
    <line x1="0" y1="40.5" x2="900" y2="40.5" stroke="#1f2a24"/>
    <text x="24" y="25"><tspan class="amb">jonathan@nansen</tspan><tspan class="dim">:~$ </tspan>uptime --graph --3d --last 365d</text>
    <text x="876" y="25" class="dim s" text-anchor="end">regenerated daily</text>
    <text x="32" y="82"><tspan class="amb" font-size="30" font-weight="700">{total}</tspan><tspan class="dim"> contributions</tspan></text>
    <text x="32" y="110" class="s"><tspan class="ok">{active}</tspan><tspan class="dim"> active days · longest streak </tspan><tspan class="ok">{longest}d</tspan><tspan class="dim"> · peak </tspan><tspan class="ok">{peak}</tspan><tspan class="dim"> on {bday}</tspan></text>
    {''.join(boxes)}
    <text x="752" y="83" class="dim s" text-anchor="end">less</text>{legend}<text x="844" y="83" class="dim s">more</text>
    <rect width="900" height="440" fill="url(#glow)"/>
    <rect width="900" height="440" fill="url(#scan)"/>
  </g>
</svg>
"""


if __name__ == "__main__":
    import os

    user, out = sys.argv[1], sys.argv[2]
    cal = fetch(user, os.environ["GITHUB_TOKEN"])
    svg = render(cal)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        f.write(svg)
    print(cal["totalContributions"])
